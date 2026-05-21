# Rule: external-channel communication

Trigger: any moment you respond/report/notify to an external channel
(Discord etc.).

## 1. Reply gate (critical)
- The user reads the channel, **not** your terminal transcript. Send via the
  channel reply tool. Terminal-only output = the user never sees it.
- In a channel session, do not use terminal-only UI prompts — present choices
  as plain channel text.
- Inbound arrives as a `<channel chat_id=… message_id=…>` block → reply with
  that `chat_id` (use `reply_to=message_id` to thread under an earlier message;
  omit for the latest).

## 2. Addressing another bot
- In a shared channel, a message aimed at another bot **must** carry its
  `<@user_id>` mention or a `reply_to` — otherwise the receiving bot silently
  drops it. Derive user_ids deterministically; never guess/invent bot names.
- **Split-message retag**: if a long message is auto-split into 2+ parts,
  re-include the recipient `<@user_id>` mention at the head of **every**
  continuation part. A continuation without the mention is silently dropped
  (= effectively unsent). Self-check: if the send result reports "N parts",
  verify each part carries the mention; prefer compressing to one part. Ask
  other bots to do the same when their reports are truncated.
- **Conversation-target mention at start AND end of message**: in a meeting
  thread or shared channel, every outbound message must include **only the
  message's direct conversation target(s) — i.e., the recipient bot(s) you
  are actually addressing** — at both the start and the end of the message
  body, each with their `<@user_id>` mention. Do **not** blanket-mention
  every active bot in the channel; mention the actual addressees only.
  Examples: (a) a 1:1 dispatch tags only that single bot; (b) a broadcast
  status report tags every bot it broadcasts to; (c) a plain inbound notify
  or sideline awareness of another 1:1 exchange = no mention. Start-only or
  end-only is not enough; both ends carry the same conversation-target list.
  Why: the start mention drives reliable inbound routing for bots that match
  on opening tokens; the end mention guarantees the next-firing addressee
  reads this message in its inbound batch (long replies can otherwise be
  silently skipped at the tail). The recipient roster comes from your
  SessionStart context, your meeting manifest's `active_participants` list,
  or your operator-maintained roster — never invented. Human users are
  **exempt** (mentioning them renders the `<@id>` as a raw string and
  self-pings — use `reply_to` plain reply for human users instead).
  Self-check before sending: the first line AND the last line both contain
  the message's conversation target(s); if either is missing, abort the
  send and rewrite.

## 3. Meeting / topic threads
- ≥2 bots · ≥10 min · has an agenda (2-of-3) → spin a dedicated thread; the
  main channel gets only a redirect. One-shot relays/acks stay inline.

## 4. Completion gate
- On finishing a directed deliverable, pre-report to your completion/report
  channel **before** saying "done" to the requester. Repeating ops loops are
  exempt.

▶ Fill in: your reply tool name; your bots' user_ids + roster source; your
completion-report channel/thread id; which channels are meeting vs. main.
