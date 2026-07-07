#!/usr/bin/env python3
"""discord-embed-send.py — send a rich Discord embed card from a bot session.

Structured reports (morning briefings, completion cards, status summaries) read
far better as embed cards than as flat text walls. The bundled MCP reply tool
only supports text+files, so this REST helper is the canonical embed path.

Usage — the payload MUST be a JSON file (inline -c assembly corrupts backticks and $()):
    python3 scripts/discord-embed-send.py --bot <bot> --channel <id> --payload p.json
    python3 scripts/discord-embed-send.py --bot <bot> --channel <id> --payload p.json --dry-run

payload.json (Discord API embeds schema, content optional):
    {"content": "", "embeds": [{"title": "...", "description": "...",
      "color": 3066993, "fields": [{"name": "...", "value": "...", "inline": false}],
      "footer": {"text": "..."}}]}

Color convention: green 0x2ECC71=done, yellow 0xF1C40F=waiting/attention,
red 0xE74C3C=issue. Notes: the User-Agent header is required (Cloudflare 403
code 1010 without it); a duplicated "Bot " token prefix is stripped.
"""
import argparse
import json
import os
import sys
import urllib.request


def load_token(bot: str) -> str:
    env_path = os.path.expanduser(f"~/.claude/channels/discord-{bot}/.env")
    token = ""
    with open(env_path, encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if line.startswith("DISCORD_BOT_TOKEN="):
                token = line.split("=", 1)[1].strip().strip('"').strip("'")
                break
    if not token:
        raise SystemExit(f"DISCORD_BOT_TOKEN not found in {env_path}")
    return token[4:] if token.startswith("Bot ") else token


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--bot", required=True, help="discord-<bot> channel dir name")
    ap.add_argument("--channel", required=True, help="target channel/thread id")
    ap.add_argument("--payload", required=True, help="embed payload JSON file")
    ap.add_argument("--dry-run", action="store_true", help="validate only, no send")
    args = ap.parse_args()

    payload = json.load(open(args.payload, encoding="utf-8"))
    embeds = payload.get("embeds")
    if not isinstance(embeds, list) or not embeds:
        raise SystemExit("payload.embeds is empty — this helper is for embed sends")
    if len(embeds) > 10:
        raise SystemExit("Discord limit: max 10 embeds per message")
    for e in embeds:
        total = len(json.dumps(e, ensure_ascii=False))
        if total > 5900:
            raise SystemExit(f"embed size {total}B — near the 6000-char Discord limit, split it")

    if args.dry_run:
        print(f"DRY-RUN OK: bot={args.bot} channel={args.channel} embeds={len(embeds)}")
        return

    token = load_token(args.bot)
    req = urllib.request.Request(
        f"https://discord.com/api/v10/channels/{args.channel}/messages",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Authorization": f"Bot {token}",
            "Content-Type": "application/json",
            "User-Agent": f"DiscordBot (thiscode-{args.bot}, 1.0)",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            body = json.loads(resp.read().decode("utf-8"))
            print(f"sent HTTP {resp.status} | message id {body.get('id')} | embeds {len(body.get('embeds', []))}")
    except urllib.error.HTTPError as err:
        sys.stderr.write(f"HTTP {err.code}: {err.read().decode('utf-8', 'replace')[:300]}\n")
        raise SystemExit(1)


if __name__ == "__main__":
    main()
