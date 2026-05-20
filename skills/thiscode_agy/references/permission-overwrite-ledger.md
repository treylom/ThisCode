# references/permission-overwrite-ledger.md

When a Discord bridge bot is granted channel-level permission overwrites (e.g. by an orchestrator bot with guild admin authority, or by the user via Discord UI), record the change in an append-only ledger.

Why: Discord audit logs are not queryable by bots and only kept ~90 days. Without a local ledger, no one can answer "why does this bot have access to channel X, who granted it, how do we roll back."

This is HARD acceptance gate for any "B-option" — exposing the bot as a server, MCP, plugin, or otherwise increasing its surface beyond receive-respond.

## Schema (one JSON object per line, append-only)

File path: `<bot-root>/state/permission-ledger.jsonl` (mode 600)

| field | type | required | description |
|---|---|---|---|
| `ts_kst` | ISO8601 with `+09:00` | yes | KST timestamp |
| `operator` | string | yes | who executed it (bot short name or "user") |
| `operator_bot_id` | string (Discord user_id) | when bot | |
| `operator_authority` | string | yes | why the operator has authority |
| `rest` | string | yes | `PUT` or `DELETE` |
| `path` | string | yes | full Discord REST path |
| `channel_id` | string | yes | target channel |
| `channel_name` | string | yes | human-readable channel name |
| `target_bot_id` | string | yes | bot/user whose perms changed |
| `target_bot_name` | string | yes | human-readable |
| `type` | integer | yes | 0=role, 1=member |
| `allow` | string (bits) | yes | string to avoid 64-bit truncation |
| `allow_decoded` | array<string> | yes | decoded permission names |
| `deny` | string (bits) | yes | |
| `reason` | string | yes | why |
| `http_status` | integer | yes | response status |
| `ttl` | ISO8601 or null | no | expiration; null = indefinite |
| `rollback` | string | yes | exact REST to reverse |
| `rollback_safe` | bool | yes | true if rollback does not break legitimate access |
| `related_meeting` | string | no | meeting folder that triggered |
| `related_review` | string | no | security review citation |

## Operator authority verification

Before any PUT/DELETE, the operator MUST:
1. `GET /users/@me/guilds` and inspect own `permissions` integer.
2. Confirm `ADMINISTRATOR (1 << 3)` or `MANAGE_ROLES (1 << 28)` + `MANAGE_CHANNELS (1 << 4)` are set.
3. Record this in `operator_authority` field.

If the user performs the edit via Discord UI, record `"operator": "user", "operator_authority": "Discord UI by guild owner"`.

## Lifecycle

**PUT (grant)**: confirm authority → compute decoded perms → REST PUT → on success, append ledger entry. If REST fails, log to `state/logs/<date>/permission-errors.log` and DO NOT append.

**DELETE (revoke)**: append entry with `rest:"DELETE"`, `allow:"0"`, `reason` citing prior PUT ts → REST DELETE → verify with `GET /channels/{id}` that access state is what you expected.

**TTL review (quarterly)**: scan for `ttl:null` and `ts_kst > 90 days ago`. For each, decide if still needed; if not, DELETE.

## Anti-patterns (BLOCK)

- Granting overwrites without a ledger entry → loses traceability, fails audit.
- Editing past ledger entries → corrections go as new entries referencing the prior one.
- Storing secrets in `reason` → ledger may be reviewed cross-bot.
- Granting `ADMINISTRATOR (1<<3)` or `MANAGE_*` to a bridge bot → capability creep.

## Example entry (one line in the JSONL file)

```json
{"ts_kst":"2026-05-21T00:34:00+09:00","operator":"orchestrator-bot","operator_bot_id":"<id>","operator_authority":"guild admin (perms <int>)","rest":"PUT","path":"/channels/<channel_id>/permissions/<bot_user_id>","channel_id":"<channel_id>","channel_name":"main-team-channel","target_bot_id":"<bot_user_id>","target_bot_name":"<your-bot>","type":1,"allow":"117824","allow_decoded":["VIEW_CHANNEL","SEND_MESSAGES","EMBED_LINKS","ATTACH_FILES","READ_MESSAGE_HISTORY","ADD_REACTIONS"],"deny":"0","reason":"first-launch channel access; channel-level overwrite was masking guild-level perms","http_status":204,"ttl":null,"rollback":"DELETE same path","rollback_safe":true,"related_meeting":"<vault-meeting-folder>","related_review":"<security-review-citation>"}
```

## See also

- `references/troubleshooting.md` §1 case (b) — channel permission overwrite as a root cause for `Missing Access 50001` despite gateway READY.
- `references/architecture.md` — bridge architecture; ledger sits in `state/` next to per-channel locks.
