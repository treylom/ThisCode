#!/usr/bin/env node
// Thin MCP stdio proxy — this is what Claude Code actually spawns per
// session (see README "Registering the channel"). It holds no Slack
// credentials and no Socket Mode connection of its own; it only speaks:
//   - stdio JSON-RPC to Claude Code (the MCP side)
//   - a Unix socket to the one resident server.ts (the IPC side)
// and translates between the two. Multiple sessions can each run their own
// mcp.ts against the same server.ts — the server broadcasts inbound Slack
// messages to every connected proxy.

import { randomUUID } from 'node:crypto';
import net from 'node:net';
import { Server } from '@modelcontextprotocol/sdk/server/index.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { CallToolRequestSchema, ListToolsRequestSchema } from '@modelcontextprotocol/sdk/types.js';
import { z } from 'zod';
import { SOCKET_PATH, log } from './config.js';
import { AckMessage, ServerToClient, encodeLine, type ServerToClientMsg } from './ipc-protocol.js';
import { LineReader } from './line-reader.js';

const SESSION_ID = randomUUID();

const INSTRUCTIONS = [
  'Messages arrive as <channel source="slack" channel="..." user="..." ts="..." thread_ts="...">.',
  'Reply with the `reply` tool: pass `chat_id` echoed from the tag\'s channel attribute to reply in the',
  'same conversation (a DM or a channel), `thread_ts` from the tag to keep it threaded (omit for a new',
  'top-level message), and `text` with what to say.',
  'React with the `react` tool to add an emoji reaction to a message: pass `chat_id` and `message_ts`',
  'echoed from the inbound tag, and `emoji` (e.g. "thumbsup", colons optional).',
  'Every message reaching you here has already passed the Slack-side channel and sender allowlist —',
  'you do not need to re-check who sent it.',
].join(' ');

const mcp = new Server(
  { name: 'slack-channel', version: '0.1.0' },
  {
    capabilities: {
      experimental: {
        'claude/channel': {},
        // Declared alongside the sender gate this bridge already enforces
        // on every inbound path (see server.ts handleSlackEvent) — per the
        // channels-reference contract, anyone who can reply through the
        // channel can approve/deny tool use, so this must not be declared
        // without that gate in place.
        'claude/channel/permission': {},
      },
      tools: {},
    },
    instructions: INSTRUCTIONS,
  },
);

// ---- reply tool -------------------------------------------------------

mcp.setRequestHandler(ListToolsRequestSchema, async () => ({
  tools: [
    {
      name: 'reply',
      description: 'Send a message back to the Slack channel this session is bridged to.',
      inputSchema: {
        type: 'object',
        properties: {
          thread_ts: {
            type: 'string',
            description:
              'Thread timestamp to reply in, echoed from the inbound <channel> tag\'s thread_ts attribute. Omit to post a new top-level message.',
          },
          chat_id: {
            type: 'string',
            description:
              "The conversation to reply in — always echo the inbound <channel> tag's channel attribute (D… for a DM, C… for a channel) so the reply lands where the message came from. If omitted, the bridge falls back to the most recent conversation.",
          },
          text: { type: 'string', description: 'The message text to send.' },
        },
        required: ['text'],
      },
    },
    {
      name: 'react',
      description: 'Add an emoji reaction to a Slack message this session has seen.',
      inputSchema: {
        type: 'object',
        properties: {
          chat_id: {
            type: 'string',
            description: "The conversation the message lives in — echo the inbound <channel> tag's channel attribute.",
          },
          message_ts: {
            type: 'string',
            description: "Timestamp of the message to react to — echo the inbound <channel> tag's ts attribute.",
          },
          emoji: {
            type: 'string',
            description: 'Emoji name, e.g. "thumbsup" or ":tada:" (surrounding colons are stripped).',
          },
        },
        required: ['chat_id', 'message_ts', 'emoji'],
      },
    },
  ],
}));

// ---- IPC client to server.ts -------------------------------------------

let ipcSocket: net.Socket | null = null;
const pending = new Map<string, (result: { ok: boolean; error?: string }) => void>();

function ipcRequest(payload: Record<string, unknown>, timeoutMs = 10_000): Promise<{ ok: boolean; error?: string }> {
  return new Promise((resolve) => {
    if (!ipcSocket || ipcSocket.destroyed) {
      resolve({ ok: false, error: 'not connected to claude-channel-server (is it running?)' });
      return;
    }
    const req_id = randomUUID();
    const timer = setTimeout(() => {
      pending.delete(req_id);
      resolve({ ok: false, error: 'timed out waiting for claude-channel-server to ack' });
    }, timeoutMs);
    pending.set(req_id, (result) => {
      clearTimeout(timer);
      resolve(result);
    });
    ipcSocket.write(encodeLine({ ...payload, req_id }));
  });
}

mcp.setRequestHandler(CallToolRequestSchema, async (req) => {
  if (req.params.name === 'reply') {
    const args = req.params.arguments as { thread_ts?: string; chat_id?: string; text?: string } | undefined;
    if (!args?.text) {
      throw new Error('reply requires a non-empty `text` argument');
    }
    const result = await ipcRequest({ type: 'reply', thread_ts: args.thread_ts, channel: args.chat_id, text: args.text });
    return {
      content: [{ type: 'text', text: result.ok ? 'sent' : `failed: ${result.error ?? 'unknown error'}` }],
      isError: !result.ok,
    };
  }
  if (req.params.name === 'react') {
    const args = req.params.arguments as { chat_id?: string; message_ts?: string; emoji?: string } | undefined;
    if (!args?.chat_id || !args?.message_ts || !args?.emoji) {
      throw new Error('react requires `chat_id`, `message_ts`, and `emoji` arguments');
    }
    const result = await ipcRequest({ type: 'react', channel: args.chat_id, ts: args.message_ts, emoji: args.emoji });
    return {
      content: [{ type: 'text', text: result.ok ? 'reacted' : `failed: ${result.error ?? 'unknown error'}` }],
      isError: !result.ok,
    };
  }
  throw new Error(`unknown tool: ${req.params.name}`);
});

// ---- permission relay (opt-in, declared above) --------------------------

const PermissionRequestNotification = z.object({
  method: z.literal('notifications/claude/channel/permission_request'),
  params: z.object({
    request_id: z.string(),
    tool_name: z.string(),
    description: z.string(),
    input_preview: z.string(),
  }),
});

mcp.setNotificationHandler(PermissionRequestNotification, async ({ params }) => {
  const result = await ipcRequest({
    type: 'permission_ask',
    request_id: params.request_id,
    tool_name: params.tool_name,
    description: params.description,
    input_preview: params.input_preview,
  });
  if (!result.ok) {
    log('mcp', `permission relay for ${params.request_id} failed: ${result.error ?? 'unknown error'}`);
  }
});

// ---- IPC connection lifecycle -------------------------------------------

function connectIpc(): void {
  const socket = net.createConnection(SOCKET_PATH);
  ipcSocket = socket;
  const reader = new LineReader(handleServerLine);

  socket.on('connect', () => {
    socket.write(encodeLine({ type: 'register', session_id: SESSION_ID }));
    log('mcp', `connected to claude-channel-server at ${SOCKET_PATH}`);
  });
  socket.on('data', (chunk) => reader.push(chunk));
  socket.on('error', (err) => log('mcp', `ipc error: ${err.message}`));
  socket.on('close', () => {
    ipcSocket = null;
    log('mcp', 'ipc connection closed, retrying in 3s');
    setTimeout(connectIpc, 3000);
  });
}

function handleServerLine(line: string): void {
  let parsed: unknown;
  try {
    parsed = JSON.parse(line);
  } catch {
    return;
  }

  const ack = AckMessage.safeParse(parsed);
  if (ack.success) {
    pending.get(ack.data.req_id)?.({ ok: ack.data.ok, error: ack.data.error });
    pending.delete(ack.data.req_id);
    return;
  }

  const result = ServerToClient.safeParse(parsed);
  if (!result.success) return;
  void relayToClaude(result.data);
}

async function relayToClaude(msg: ServerToClientMsg): Promise<void> {
  if (msg.type === 'inbound') {
    await mcp.notification({
      method: 'notifications/claude/channel',
      params: { content: msg.content, meta: msg.meta ?? {} },
    });
    return;
  }
  await mcp.notification({
    method: 'notifications/claude/channel/permission',
    params: { request_id: msg.request_id, behavior: msg.behavior },
  });
}

// ---- entry point ----------------------------------------------------------

async function main(): Promise<void> {
  connectIpc();
  await mcp.connect(new StdioServerTransport());
  log('mcp', 'stdio transport connected');
}

main().catch((err) => {
  log('mcp', `fatal: ${err instanceof Error ? (err.stack ?? err.message) : String(err)}`);
  process.exit(1);
});
