#!/usr/bin/env bash
# Verify that Hermes runtime registrations are a subset of plugin.yaml and
# that every manifest-only tool/command is explicitly documented as deferred.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/../.." && pwd)"
SELF_TEST=0
if [ "${1:-}" = "--self-test" ]; then
  SELF_TEST=1
fi

python3 - "$ROOT" "$SELF_TEST" <<'PY'
import re
import sys
from pathlib import Path

root = Path(sys.argv[1])
self_test = sys.argv[2] == "1"
entry = (root / "hermes-plugin" / "__init__.py").read_text()
manifest = (root / "hermes-plugin" / "plugin.yaml").read_text()
status = (root / "docs" / "HERMES-STATUS.md").read_text()

def yaml_list(key):
    match = re.search(rf"(?ms)^{re.escape(key)}:\s*\n((?:\s+-\s+[^\n]+\n?)+)", manifest)
    if not match:
        raise SystemExit(f"FAIL hermes runtime manifest: missing YAML list {key}")
    return {line.strip()[2:].strip().strip('"\'') for line in match.group(1).splitlines() if line.strip().startswith("-")}

manifest_tools = yaml_list("provides_tools")
manifest_hooks = yaml_list("provides_hooks")
manifest_commands = yaml_list("provides_commands")
runtime_tools = set(re.findall(r"register_tool\s*\(\s*name\s*=\s*['\"]([^'\"]+)", entry))
runtime_hooks = set(re.findall(r"register_hook\s*\(\s*['\"]([^'\"]+)", entry))
runtime_commands = set(re.findall(r"register_command\s*\(\s*['\"]([^'\"]+)", entry))

if self_test:
    runtime_tools.add("__thiscode_manifest_self_test_fake__")

errors = []
for label, runtime, advertised in (
    ("tool", runtime_tools, manifest_tools),
    ("hook", runtime_hooks, manifest_hooks),
    ("command", runtime_commands, manifest_commands),
):
    for name in sorted(runtime - advertised):
        errors.append(f"runtime {label} is not in manifest: {name}")

if "## What is deferred" not in status:
    raise SystemExit("FAIL hermes runtime manifest: missing HERMES-STATUS deferred section")
deferred_section = status.split("## What is deferred", 1)[1].split("## ", 1)[0]
for label, runtime, advertised in (
    ("tool", runtime_tools, manifest_tools),
    ("command", runtime_commands, manifest_commands),
):
    for name in sorted(advertised - runtime):
        if name not in deferred_section:
            errors.append(f"manifest-only {label} missing from HERMES-STATUS deferred table: {name}")

if errors:
    print("FAIL hermes runtime manifest")
    for error in errors:
        print(f"  {error}")
    sys.exit(1)

print(
    "PASS hermes runtime manifest "
    f"(runtime tools={len(runtime_tools)}, commands={len(runtime_commands)}, hooks={len(runtime_hooks)}; "
    f"manifest tools={len(manifest_tools)}, commands={len(manifest_commands)}, hooks={len(manifest_hooks)})"
)
PY
