import { test } from 'node:test';
import assert from 'node:assert/strict';
import { execFileSync, spawnSync } from 'node:child_process';
import { chmodSync, mkdtempSync, mkdirSync, readFileSync, writeFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const REPO = join(dirname(fileURLToPath(import.meta.url)), '..', '..');
const GATE = join(REPO, 'scripts', 'install-browser-gate.sh');
const COMMAND = join(REPO, 'commands', 'install-browser.md');
const CARDS = join(REPO, 'docs', 'install-browser-manual-cards.md');
const BASH = process.platform === 'win32' ? 'bash' : '/bin/bash';

function makeLocaleFailureFixture() {
  const root = mkdtempSync(join(tmpdir(), 'thiscode-browser-locale-'));
  const project = join(root, 'project');
  const config = join(root, 'config');
  const fakeClaude = join(root, 'claude');
  mkdirSync(project);
  mkdirSync(config);
  writeFileSync(join(project, '.mcp.json'), JSON.stringify({
    mcpServers: {
      playwright: { command: 'npx', args: ['@playwright/mcp@0.0.0'] },
    },
  }));
  writeFileSync(fakeClaude, `#!/usr/bin/env bash
if [ "\${1:-}" = --version ]; then echo '2.test'; exit 0; fi
if [ "\${1:-}" = mcp ] && [ "\${2:-}" = add ]; then
  echo 'MCP server playwright already exists in .mcp.json' >&2
  exit 7
fi
exit 0
`);
  chmodSync(fakeClaude, 0o755);
  return { root, project, config, fakeClaude };
}

function makeMcpReplacementFixture() {
  const root = mkdtempSync(join(tmpdir(), 'thiscode-browser-replace-'));
  const project = join(root, 'project');
  const config = join(root, 'config');
  const fakeClaude = join(root, 'claude');
  const callLog = join(root, 'claude-calls.log');
  mkdirSync(project);
  mkdirSync(config);
  writeFileSync(join(project, '.mcp.json'), JSON.stringify({
    mcpServers: {
      playwright: { command: 'npx', args: ['@playwright/mcp@0.0.0'] },
      keep: { command: 'node', args: ['keep.mjs'] },
    },
  }));
  writeFileSync(fakeClaude, `#!/usr/bin/env bash
printf '%s\\n' "$*" >>"$FAKE_CLAUDE_CALL_LOG"
if [ "\${1:-}" = --version ]; then echo '2.test'; exit 0; fi
if [ "\${1:-}" = mcp ] && [ "\${2:-}" = remove ]; then
  node -e 'const fs=require("fs"),p=".mcp.json",d=JSON.parse(fs.readFileSync(p));delete d.mcpServers.playwright;fs.writeFileSync(p,JSON.stringify(d));'
  exit 0
fi
if [ "\${1:-}" = mcp ] && [ "\${2:-}" = add ]; then
  node -e 'const fs=require("fs"),p=".mcp.json",d=JSON.parse(fs.readFileSync(p));if(d.mcpServers.playwright)process.exit(9);d.mcpServers.playwright={type:"stdio",command:"npx",args:["@playwright/mcp@latest"],env:{}};fs.writeFileSync(p,JSON.stringify(d));'
  exit $?
fi
if [ "\${1:-}" = mcp ] && [ "\${2:-}" = list ]; then
  echo 'playwright: npx @playwright/mcp@latest - ✔ Connected'
  exit 0
fi
exit 2
`);
  chmodSync(fakeClaude, 0o755);
  return { root, project, config, fakeClaude, callLog };
}

function makeBrowserProbeFixture(mode, mcpPackage = '@playwright/mcp@latest') {
  const root = mkdtempSync(join(tmpdir(), 'thiscode-browser-probe-'));
  const project = join(root, 'project');
  const config = join(root, 'config');
  const browserDir = join(root, 'browsers', 'chromium-1243');
  const fakeClaude = join(root, 'claude');
  const fakeNpx = join(root, 'npx');
  const npxLog = join(root, 'npx-calls.log');
  mkdirSync(project);
  mkdirSync(config);
  mkdirSync(browserDir, { recursive: true });
  writeFileSync(join(project, '.mcp.json'), JSON.stringify({
    mcpServers: {
      playwright: { command: 'npx', args: ['@playwright/mcp@latest'] },
    },
  }));
  const mcpConfig = JSON.parse(readFileSync(join(project, '.mcp.json'), 'utf8'));
  mcpConfig.mcpServers.playwright.args = [mcpPackage];
  writeFileSync(join(project, '.mcp.json'), JSON.stringify(mcpConfig));
  writeFileSync(join(browserDir, 'chrome'), '#!/usr/bin/env bash\nexit 0\n');
  writeFileSync(join(browserDir, 'chrome.exe'), 'fixture');
  chmodSync(join(browserDir, 'chrome'), 0o755);
  writeFileSync(fakeClaude, `#!/usr/bin/env bash
if [ "\${1:-}" = --version ]; then echo '2.test'; exit 0; fi
if [ "\${1:-}" = mcp ] && [ "\${2:-}" = list ]; then
  case "\${FAKE_MCP_LIST_VARIANT:-connected}" in
    conflict_user_row)
      echo 'playwright: npx -y @playwright/mcp@latest - ✔ Connected'
      echo ''
      echo '[Conflicting scopes]'
      echo '  Server "playwright" is defined in multiple scopes with different endpoints:'
      echo '  user (npx -y @playwright/mcp@latest), project (npx @playwright/mcp@0.0.80).'
      ;;
    *) echo 'playwright: npx ${mcpPackage} - ✔ Connected' ;;
  esac
  exit 0
fi
if [ -n "\${FAKE_CLAUDE_STREAM_JSON:-}" ]; then
  echo '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"nav-1","name":"mcp__playwright__browser_navigate"}]}}'
  echo '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"nav-1","content":"Page URL: https://example.com"}]}}'
  echo '{"type":"assistant","message":{"content":[{"type":"tool_use","id":"snap-1","name":"mcp__playwright__browser_snapshot"}]}}'
  echo '{"type":"user","message":{"content":[{"type":"tool_result","tool_use_id":"snap-1","content":[{"type":"text","text":"Page Title: Example Domain"}]}]}}'
  echo '{"type":"result","result":"TITLE=Example Domain"}'
  exit 0
fi
exit 2
`);
  writeFileSync(fakeNpx, `#!/usr/bin/env bash
if [ -n "\${FAKE_NPX_CALL_LOG:-}" ]; then printf '%s\\n' "$*" >>"$FAKE_NPX_CALL_LOG"; fi
if [ "$FAKE_NPX_MODE" = fail ]; then
  echo 'npm ERR! simulated registry failure' >&2
  exit 7
fi
printf '  Install location:    %s\\n' "$FAKE_BROWSER_DIR"
exit 0
`);
  chmodSync(fakeClaude, 0o755);
  chmodSync(fakeNpx, 0o755);
  return { root, project, config, browserDir, fakeClaude, fakeNpx, npxLog, mode, mcpPackage };
}

test('browser gate replays 0~4 and fails closed for isolated step 4', () => {
  const r = spawnSync('bash', [GATE, '--self-test'], { encoding: 'utf8' });
  assert.equal(r.status, 0, [r.stdout, r.stderr].filter(Boolean).join('\n'));
  assert.match(r.stdout, /\[SELFTEST\] 28\/28 passed/);
});

test('browser gate uses Node for config diff and has no Python runtime dependency', () => {
  const text = readFileSync(GATE, 'utf8');
  assert.doesNotMatch(text, /\bpython3\b/);
  assert.match(text, /node - "\$before_file" "\$after_file"/);
});

test('isolated verification never copies Claude credentials', () => {
  const text = readFileSync(GATE, 'utf8');
  assert.doesNotMatch(text, /cp[^\n]*\.credentials\.json/);
  assert.match(text, /4단계 검증 불가\(인증 미승계\)/);
});

test('student command has one machine gate per step in 0→4 order', () => {
  const text = readFileSync(COMMAND, 'utf8');
  const steps = [...text.matchAll(/install-browser-gate\.sh" ([0-4])/g)].map((m) => Number(m[1]));
  assert.deepEqual(steps, [0, 1, 2, 3, 4]);
  assert.match(text, /n단계 실패 → 수동 카드 X/);
  assert.match(text, /프로젝트 Playwright 연결 승인 상태까지 확인했습니다/);
  assert.match(text, /승인 대기 상태면 자동으로 우회하지 않고/);
});

test('manual fallback keeps the A~E recovery boundary', () => {
  const text = readFileSync(CARDS, 'utf8');
  const cards = [...text.matchAll(/^## 카드 ([A-E]) —/gm)].map((m) => m[1]);
  assert.deepEqual(cards, ['A', 'B', 'C', 'D', 'E']);
  assert.match(text, /-s project/);
  assert.match(text, /4b 승인 상태 확인: 프로젝트 Playwright 연결 승인됨/);
  assert.match(text, /\/thiscode:install-browser`를 다시 실행/);
  assert.match(text, /Playwright 연결을 한 곳만 남긴 뒤/);
});

test('R1: card E exposes exactly one approval and one rerun instruction', () => {
  const cards = readFileSync(CARDS, 'utf8');
  const cardE = cards.slice(cards.indexOf('## 카드 E'));
  assert.match(cardE, /연결을 한 번 승인한 뒤/);
  assert.match(cardE, /한 번만 재실행/);
  assert.equal([...cardE.matchAll(/\/thiscode:install-browser/g)].length, 1);
});

test('R1 mutation: clearing only the approval profile makes the state machine fail', () => {
  const root = mkdtempSync(join(tmpdir(), 'thiscode-browser-r1-mutation-'));
  const mutated = join(root, 'install-browser-gate.sh');
  const original = readFileSync(GATE, 'utf8');
  const needle = 'out="$(cd "$PROJECT_DIR" && run_claude_configured mcp list 2>&1)"; rc=$?';
  const first = original.indexOf(needle);
  const second = original.indexOf(needle, first + needle.length);
  assert.notEqual(first, -1);
  assert.notEqual(second, -1);
  const replacement = 'out="$(cd "$PROJECT_DIR" && env -u CLAUDE_CONFIG_DIR "$CLAUDE_BIN" mcp list 2>&1)"; rc=$?';
  const text = `${original.slice(0, second)}${replacement}${original.slice(second + needle.length)}`;
  writeFileSync(mutated, text);
  chmodSync(mutated, 0o755);
  const r = spawnSync(BASH, [mutated, '--self-test'], {
    encoding: 'utf8',
    env: { ...process.env, LC_ALL: 'C' },
  });
  assert.equal(r.status, 1, [r.stdout, r.stderr].filter(Boolean).join('\n'));
  assert.match(r.stdout, /\[SELFTEST\] 26\/28 passed/);
});

test('automatic completion and card E share the approval-state sentence', () => {
  const command = readFileSync(COMMAND, 'utf8');
  const cards = readFileSync(CARDS, 'utf8');
  const sentence = '브라우저 준비가 끝났습니다. 프로젝트 Playwright 연결 승인 상태까지 확인했습니다. 이 프로젝트에서 웹페이지 열기와 화면 읽기를 사용할 수 있습니다.';
  assert.equal(command.includes(sentence), true);
  assert.equal(cards.includes(sentence), true);
});

test('R6: C and UTF-8 locales preserve the step 2 exit cause under Bash nounset', () => {
  for (const locale of ['C', 'en_US.UTF-8']) {
    const fixture = makeLocaleFailureFixture();
    const r = spawnSync(BASH, [GATE, '2'], {
      cwd: fixture.project,
      encoding: 'utf8',
      env: {
        ...process.env,
        LC_ALL: locale,
        CLAUDE_CONFIG_DIR: fixture.config,
        THISCODE_BROWSER_CLAUDE_CONFIG_DIR: fixture.config,
        THISCODE_BROWSER_PROJECT_DIR: fixture.project,
        THISCODE_BROWSER_CLAUDE: fixture.fakeClaude,
      },
    });
    assert.equal(r.status, 1, locale);
    assert.match(r.stderr, /\[CAUSE\] 프로젝트 MCP 등록 명령이 exit 7로 끝났습니다/, locale);
    assert.doesNotMatch(r.stderr, /unbound variable/, locale);
  }
});

test('R6: shell sources reject a bare variable immediately followed by non-ASCII', () => {
  const unsafe = /\$[A-Za-z_][A-Za-z0-9_]*[^\x00-\x7f]/u;
  assert.equal(unsafe.test('$rc로'), true, 'positive decoy must be detected');
  assert.equal(unsafe.test('${rc}로'), false, 'braced negative control must stay allowed');
  const tracked = execFileSync('git', ['ls-files', '-z'], { cwd: REPO })
    .toString('utf8')
    .split('\0')
    .filter(Boolean);
  const findings = [];
  for (const relative of tracked) {
    let text;
    try {
      text = readFileSync(join(REPO, relative), 'utf8');
    } catch {
      continue;
    }
    const firstLine = text.split(/\r?\n/, 1)[0];
    if (!relative.endsWith('.sh') && !/^#!.*(?:^|[\/ ])bash(?:\s|$)/.test(firstLine)) continue;
    text.split(/\r?\n/).forEach((line, index) => {
      if (unsafe.test(line)) findings.push(`${relative}:${index + 1}`);
    });
  }
  assert.deepEqual(findings, []);
});

test('R7: mismatched project MCP entry is replaced instead of looping on already exists', () => {
  const fixture = makeMcpReplacementFixture();
  const r = spawnSync(BASH, [GATE, '2'], {
    cwd: fixture.project,
    encoding: 'utf8',
    env: {
      ...process.env,
      LC_ALL: 'C',
      CLAUDE_CONFIG_DIR: fixture.config,
      THISCODE_BROWSER_CLAUDE_CONFIG_DIR: fixture.config,
      THISCODE_BROWSER_PROJECT_DIR: fixture.project,
      THISCODE_BROWSER_CLAUDE: fixture.fakeClaude,
      THISCODE_BROWSER_MCP_PACKAGE: '@playwright/mcp@latest',
      FAKE_CLAUDE_CALL_LOG: fixture.callLog,
    },
  });
  assert.equal(r.status, 0, [r.stdout, r.stderr].filter(Boolean).join('\n'));
  const config = JSON.parse(readFileSync(join(fixture.project, '.mcp.json'), 'utf8'));
  assert.deepEqual(config.mcpServers.playwright.args, ['@playwright/mcp@latest']);
  assert.deepEqual(config.mcpServers.keep, { command: 'node', args: ['keep.mjs'] });
  const calls = readFileSync(fixture.callLog, 'utf8');
  assert.match(calls, /^mcp remove -s project playwright$/m);
  assert.match(calls, /^mcp add -s project playwright -- npx @playwright\/mcp@latest$/m);
  assert.doesNotMatch(r.stderr, /already exists/);
});

test('R3: one dry-run location passes when it contains a runnable Chromium executable', () => {
  const fixture = makeBrowserProbeFixture('one');
  const r = spawnSync(BASH, [GATE, '3', '--check-only'], {
    cwd: fixture.project,
    encoding: 'utf8',
    env: {
      ...process.env,
      LC_ALL: 'C',
      CLAUDE_CONFIG_DIR: fixture.config,
      THISCODE_BROWSER_CLAUDE_CONFIG_DIR: fixture.config,
      THISCODE_BROWSER_PROJECT_DIR: fixture.project,
      THISCODE_BROWSER_CLAUDE: fixture.fakeClaude,
      THISCODE_BROWSER_NPX: fixture.fakeNpx,
      THISCODE_BROWSER_MCP_PACKAGE: '@playwright/mcp@latest',
      FAKE_NPX_MODE: fixture.mode,
      FAKE_BROWSER_DIR: fixture.browserDir,
    },
  });
  assert.equal(r.status, 0, [r.stdout, r.stderr].filter(Boolean).join('\n'));
  assert.match(r.stdout, /\[PASS\] 3단계 브라우저 바이너리 확인/);
});

test('R4: dry-run command failure has a distinct cause with its exit code', () => {
  const fixture = makeBrowserProbeFixture('fail');
  const r = spawnSync(BASH, [GATE, '3', '--check-only'], {
    cwd: fixture.project,
    encoding: 'utf8',
    env: {
      ...process.env,
      LC_ALL: 'C',
      CLAUDE_CONFIG_DIR: fixture.config,
      THISCODE_BROWSER_CLAUDE_CONFIG_DIR: fixture.config,
      THISCODE_BROWSER_PROJECT_DIR: fixture.project,
      THISCODE_BROWSER_CLAUDE: fixture.fakeClaude,
      THISCODE_BROWSER_NPX: fixture.fakeNpx,
      THISCODE_BROWSER_MCP_PACKAGE: '@playwright/mcp@latest',
      FAKE_NPX_MODE: fixture.mode,
      FAKE_BROWSER_DIR: fixture.browserDir,
    },
  });
  assert.equal(r.status, 1);
  assert.match(r.stderr, /npm ERR! simulated registry failure/);
  assert.match(r.stderr, /\[CAUSE\] Chromium 설치 위치 판정 명령이 exit 7로 끝났습니다/);
  assert.doesNotMatch(r.stderr, /Chromium 설치 위치 또는 실행 파일을 확인하지 못했습니다/);
});

test('R2: Chromium probe is resolved through the same pinned MCP package used at runtime', () => {
  const fixture = makeBrowserProbeFixture('one', '@playwright/mcp@0.0.80');
  const r = spawnSync(BASH, [GATE, '3', '--check-only'], {
    cwd: fixture.project,
    encoding: 'utf8',
    env: {
      ...process.env,
      LC_ALL: 'C',
      CLAUDE_CONFIG_DIR: fixture.config,
      THISCODE_BROWSER_CLAUDE_CONFIG_DIR: fixture.config,
      THISCODE_BROWSER_PROJECT_DIR: fixture.project,
      THISCODE_BROWSER_CLAUDE: fixture.fakeClaude,
      THISCODE_BROWSER_NPX: fixture.fakeNpx,
      FAKE_NPX_CALL_LOG: fixture.npxLog,
      FAKE_NPX_MODE: fixture.mode,
      FAKE_BROWSER_DIR: fixture.browserDir,
    },
  });
  assert.equal(r.status, 0, [r.stdout, r.stderr].filter(Boolean).join('\n'));
  assert.match(
    readFileSync(fixture.npxLog, 'utf8'),
    /^-y --package=@playwright\/mcp@0\.0\.80 playwright install --dry-run chromium$/m,
  );
});

test('R8a: user-scope conflict sends step 2 to card F instead of looping on card C', () => {
  const fixture = makeBrowserProbeFixture('one', '@playwright/mcp@0.0.80');
  const r = spawnSync(BASH, [GATE, '2'], {
    cwd: fixture.project,
    encoding: 'utf8',
    env: {
      ...process.env,
      LC_ALL: 'C',
      CLAUDE_CONFIG_DIR: fixture.config,
      THISCODE_BROWSER_CLAUDE_CONFIG_DIR: fixture.config,
      THISCODE_BROWSER_PROJECT_DIR: fixture.project,
      THISCODE_BROWSER_CLAUDE: fixture.fakeClaude,
      THISCODE_BROWSER_NPX: fixture.fakeNpx,
      THISCODE_BROWSER_MCP_PACKAGE: fixture.mcpPackage,
      FAKE_MCP_LIST_VARIANT: 'conflict_user_row',
      FAKE_NPX_MODE: fixture.mode,
      FAKE_BROWSER_DIR: fixture.browserDir,
    },
  });
  assert.notEqual(r.status, 0, [r.stdout, r.stderr].filter(Boolean).join('\n'));
  assert.match(r.stderr, /2단계 실패 → 수동 카드 F/);
  assert.match(r.stderr, /사용자 전체\(user\) 범위에도 등록되어 있어/);
  assert.doesNotMatch(r.stderr, /카드 C/);
});

test('R8b: user-scope conflict sends step 4b to card F', () => {
  const fixture = makeBrowserProbeFixture('one', '@playwright/mcp@0.0.80');
  const r = spawnSync(BASH, [GATE, '4'], {
    cwd: fixture.project,
    encoding: 'utf8',
    env: {
      ...process.env,
      LC_ALL: 'C',
      HOME: fixture.root,
      CLAUDE_CONFIG_DIR: fixture.config,
      THISCODE_BROWSER_PROJECT_DIR: fixture.project,
      THISCODE_BROWSER_CLAUDE: fixture.fakeClaude,
      THISCODE_BROWSER_NPX: fixture.fakeNpx,
      THISCODE_BROWSER_MCP_PACKAGE: fixture.mcpPackage,
      THISCODE_BROWSER_LOG: join(fixture.root, 'step4.log'),
      FAKE_MCP_LIST_VARIANT: 'conflict_user_row',
      FAKE_CLAUDE_STREAM_JSON: '1',
      FAKE_NPX_MODE: fixture.mode,
      FAKE_BROWSER_DIR: fixture.browserDir,
    },
  });
  assert.notEqual(r.status, 0, [r.stdout, r.stderr].filter(Boolean).join('\n'));
  assert.match(r.stderr, /4b단계 실패 → 수동 카드 F/);
  assert.match(r.stderr, /사용자 전체\(user\) 범위에도 등록되어 있어/);
});

test('R8c: negative control — the connected variant keeps step 2 passing', () => {
  const fixture = makeBrowserProbeFixture('one', '@playwright/mcp@0.0.80');
  const r = spawnSync(BASH, [GATE, '2'], {
    cwd: fixture.project,
    encoding: 'utf8',
    env: {
      ...process.env,
      LC_ALL: 'C',
      CLAUDE_CONFIG_DIR: fixture.config,
      THISCODE_BROWSER_CLAUDE_CONFIG_DIR: fixture.config,
      THISCODE_BROWSER_PROJECT_DIR: fixture.project,
      THISCODE_BROWSER_CLAUDE: fixture.fakeClaude,
      THISCODE_BROWSER_NPX: fixture.fakeNpx,
      THISCODE_BROWSER_MCP_PACKAGE: fixture.mcpPackage,
      FAKE_NPX_MODE: fixture.mode,
      FAKE_BROWSER_DIR: fixture.browserDir,
    },
  });
  assert.equal(r.status, 0, [r.stdout, r.stderr].filter(Boolean).join('\n'));
  assert.match(r.stdout, /\[PASS\] 2단계 프로젝트 MCP 등록 확인/);
});
