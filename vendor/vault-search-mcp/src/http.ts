import express, { type Request, type Response, type NextFunction } from 'express'
import { randomUUID } from 'node:crypto'
import { StreamableHTTPServerTransport } from '@modelcontextprotocol/sdk/server/streamableHttp.js'
import { isInitializeRequest } from '@modelcontextprotocol/sdk/types.js'
import { createVaultSearchServer } from './index.js'
import {
  authMiddleware,
  buildAuthorizationServerMetadata,
  buildProtectedResourceMetadata,
  getAuthMode,
  getProvider,
} from './auth.js'

const PORT = Number(process.env.MCP_HTTP_PORT) || 8401
const HOST = process.env.MCP_HTTP_HOST || '127.0.0.1'
const ALLOWED_ORIGINS = (process.env.MCP_ALLOWED_ORIGINS || '')
  .split(',')
  .map(origin => origin.trim())
  .filter(Boolean)

const transports = new Map<string, StreamableHTTPServerTransport>()

function originGuard(req: Request, res: Response, next: NextFunction): void {
  if (ALLOWED_ORIGINS.length === 0) {
    next()
    return
  }

  const origin = req.header('origin') || ''
  if (origin && !ALLOWED_ORIGINS.includes(origin)) {
    res.status(403).json({
      jsonrpc: '2.0',
      error: { code: -32002, message: `origin not allowed: ${origin}` },
      id: null,
    })
    return
  }

  next()
}

async function getOrCreateTransport(req: Request): Promise<StreamableHTTPServerTransport | null> {
  const existingId = req.header('mcp-session-id')
  if (existingId && transports.has(existingId)) {
    return transports.get(existingId) ?? null
  }

  if (!isInitializeRequest(req.body)) {
    return null
  }

  const transport = new StreamableHTTPServerTransport({
    sessionIdGenerator: () => randomUUID(),
    onsessioninitialized: (sessionId: string) => {
      transports.set(sessionId, transport)
    },
  })

  transport.onclose = () => {
    if (transport.sessionId) {
      transports.delete(transport.sessionId)
    }
  }

  const server = createVaultSearchServer()
  await server.connect(transport)
  return transport
}

const app = express()
app.use(express.json({ limit: '4mb' }))

// Access log — every request, before any guard, so we see ChatGPT registration probes
app.use((req, _res, next) => {
  const ua = req.header('user-agent') || ''
  const origin = req.header('origin') || ''
  console.error(`[access] ${req.method} ${req.url} origin="${origin}" ua="${ua.slice(0, 80)}"`)
  next()
})

// CORS — required so browser-side MCP clients (ChatGPT web) can read responses + WWW-Authenticate
app.use((req, res, next) => {
  res.setHeader('Access-Control-Allow-Origin', '*')
  res.setHeader('Access-Control-Allow-Methods', 'GET, POST, DELETE, OPTIONS')
  res.setHeader(
    'Access-Control-Allow-Headers',
    'Authorization, Content-Type, mcp-session-id, mcp-protocol-version',
  )
  res.setHeader('Access-Control-Expose-Headers', 'mcp-session-id, www-authenticate')
  res.setHeader('Access-Control-Max-Age', '86400')
  if (req.method === 'OPTIONS') {
    res.status(204).end()
    return
  }
  next()
})

app.get('/healthz', (_req, res) => {
  res.json({
    ok: true,
    sessions: transports.size,
    authMode: getAuthMode(),
    oauthProvider: getProvider(),
  })
})

// RFC 9728: OAuth 2.0 Protected Resource Metadata
// ChatGPT requests this to discover the auth server. Must be public (no auth).
app.get('/.well-known/oauth-protected-resource/mcp', (_req, res) => {
  const meta = buildProtectedResourceMetadata()
  if (!meta) {
    res.status(404).json({ error: 'OAuth not configured' })
    return
  }
  res.json(meta)
})

// Some clients fetch without the resource path
app.get('/.well-known/oauth-protected-resource', (_req, res) => {
  const meta = buildProtectedResourceMetadata()
  if (!meta) {
    res.status(404).json({ error: 'OAuth not configured' })
    return
  }
  res.json(meta)
})

// RFC 8414: Authorization Server Metadata (mirrors Auth0 /.well-known/openid-configuration)
// Some MCP clients query this on the resource server too.
app.get('/.well-known/oauth-authorization-server', (_req, res) => {
  const meta = buildAuthorizationServerMetadata()
  if (!meta) {
    res.status(404).json({ error: 'OAuth not configured' })
    return
  }
  res.json(meta)
})

// ChatGPT specifically requires /.well-known/oauth-authorization-server/mcp (with /mcp suffix).
// Claude works without suffix; ChatGPT silent-fails if missing.
// Source: https://community.openai.com/t/resolved-trouble-with-chatgpt-connector-oauth-detailed/1359112
app.get('/.well-known/oauth-authorization-server/mcp', (_req, res) => {
  const meta = buildAuthorizationServerMetadata()
  if (!meta) {
    res.status(404).json({ error: 'OAuth not configured' })
    return
  }
  res.json(meta)
})

app.use(originGuard)
app.use(authMiddleware)

app.post('/mcp', async (req: Request, res: Response) => {
  try {
    const transport = await getOrCreateTransport(req)
    if (!transport) {
      res.status(400).json({
        jsonrpc: '2.0',
        error: { code: -32000, message: 'session not initialized; send initialize request first' },
        id: null,
      })
      return
    }

    await transport.handleRequest(req, res, req.body)
  } catch (error) {
    const message = error instanceof Error ? error.message : String(error)
    console.error(`[http] POST /mcp error: ${message}`)
    if (!res.headersSent) {
      res.status(500).json({
        jsonrpc: '2.0',
        error: { code: -32603, message },
        id: null,
      })
    }
  }
})

app.get('/mcp', async (req: Request, res: Response) => {
  const sessionId = req.header('mcp-session-id')
  if (!sessionId || !transports.has(sessionId)) {
    res.status(400).send('mcp-session-id header required')
    return
  }
  await transports.get(sessionId)!.handleRequest(req, res)
})

app.delete('/mcp', async (req: Request, res: Response) => {
  const sessionId = req.header('mcp-session-id')
  if (!sessionId || !transports.has(sessionId)) {
    res.status(400).send('mcp-session-id header required')
    return
  }
  await transports.get(sessionId)!.handleRequest(req, res)
})

app.listen(PORT, HOST, () => {
  const mode = getAuthMode()
  console.error(`vault-search-mcp HTTP listening on http://${HOST}:${PORT}/mcp [auth=${mode}]`)
  if (mode === 'none') {
    console.error('WARNING: no authentication configured. Do NOT expose externally.')
  }
  if (mode === 'oauth') {
    console.error(`OAuth metadata at /.well-known/oauth-protected-resource/mcp`)
  }
})
