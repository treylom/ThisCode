#!/bin/bash
# Bot identity dir (~/.claude/channels/discord-<bot>/) + state dir setup.
# All directories created with mode 0700, umask 077 (Codex code-review item 3 + 7 mitigation).
set -euo pipefail

CHANNELS_DIR="${1:-$HOME/.claude/channels/discord-mybot}"
STATE_DIR="${2:-$PWD/state}"

umask 077

mkdir -p "$CHANNELS_DIR/inbox" "$CHANNELS_DIR/outbox"
chmod 700 "$CHANNELS_DIR"

mkdir -p "$STATE_DIR"/{conversations,attachments,assets,logs,channels}
chmod -R 700 "$STATE_DIR"

echo "OK: $CHANNELS_DIR + $STATE_DIR ready (mode 700, umask 077)"
