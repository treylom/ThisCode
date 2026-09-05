import test from 'node:test';
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { resolve } from 'node:path';
import { spawnSync } from 'node:child_process';

const root = fileURLToPath(new URL('../../', import.meta.url));
const read = (path) => readFileSync(resolve(root, path), 'utf8');
const publications = ['MANUAL', 'MANUAL.en', 'SETUP-BEGINNER', 'SETUP-BEGINNER.en'];
const absent = (text, pattern, label) => assert.equal(pattern.test(text), false, label);

// Both the editable input and the distributed PDF must pass the same semantic checks.
function assertSearchContract(text, label) {
  assert.ok(/GraphRAG/.test(text), `${label}: extraction positive control`);
  assert.ok(/Obsidian\s+MCP/.test(text), `${label}: actual km Tier 3 is named`);
  absent(text, /Tier\s*3\s*(?:[—:(-]\s*)?vault-search/i, `${label}: local MCP is not km Tier 3`);
  absent(text, /vault-search\s+MCP\s*\(Tier\s*3\)/i, `${label}: diagnostic must not call local MCP a km tier`);
  absent(text, /\[3\],\s*\[vault-search/i, `${label}: local MCP must not occupy km table row 3`);
  absent(text, /^\s*3\s+vault-search\s+MCP/mi, `${label}: extracted PDF table must not put local MCP in row 3`);
  absent(text, /ghcr\.io\/treylom\/ThisCode-graphrag:v1\.0/i, `${label}: unpublished Docker recipe`);
  absent(text, /thiscode\s+healthcheck\s+v1\.0/i, `${label}: obsolete healthcheck sample`);
  absent(text, /(?:구독 안에|inside your Claude Code subscription)/i, `${label}: unsupported MCP cost attribution`);
}

test('all four editable publication sources describe the actual km search boundary', () => {
  for (const name of publications) assertSearchContract(read(`docs/${name}.typ`), name);
});

test('publication checker rejects each known broken sibling class', () => {
  const good = 'ThisCode local tools; km: GraphRAG → Obsidian CLI → Obsidian MCP → text search';
  assert.doesNotThrow(() => assertSearchContract(good, 'negative control'));
  for (const broken of ['Tier 3 — vault-search MCP', '[3], [vault-search MCP]',
    '3 vault-search MCP', 'vault-search MCP (Tier 3)',
    'ghcr.io/treylom/ThisCode-graphrag:v1.0', 'thiscode healthcheck v1.0',
    '무료 (Claude Code 구독 안에)', 'free (inside your Claude Code subscription)']) {
    assert.throws(() => assertSearchContract(`${good}\n${broken}`, 'positive control'), assert.AssertionError);
  }
});

const pdfTool = spawnSync('pdftotext', ['-v'], { encoding: 'utf8' });
test('all four distributed PDFs pass extraction and semantic checks', {
  skip: pdfTool.error ? 'Poppler pdftotext not installed; release validation must run this check with Poppler' : false,
}, () => {
  for (const name of publications) {
    const extracted = spawnSync('pdftotext', ['-layout', resolve(root, `docs/${name}.pdf`), '-'], { encoding: 'utf8' });
    assert.equal(extracted.status, 0, `${name}: ${extracted.stderr}`);
    assertSearchContract(extracted.stdout, `${name}.pdf`);
  }
});

test('both README search-setup fragment links resolve to actual SETUP headings', () => {
  const setup = read('docs/SETUP.md');
  const anchors = new Set([...setup.matchAll(/^#{1,6}\s+(.+)$/gm)].map((match) => match[1]
    .toLowerCase().replace(/[^\p{L}\p{N}_\-\s]/gu, '').replace(/\s/g, '-')));
  for (const match of setup.matchAll(/<a\s+(?:id|name)=["']([^"']+)["']/g)) anchors.add(match[1]);
  for (const file of ['README.md', 'README.ko.md']) {
    const links = [...read(file).matchAll(/\]\(docs\/SETUP\.md#([^\s)]+)\)/g)];
    assert.ok(links.length > 0, `${file}: positive link control`);
    for (const match of links) assert.ok(anchors.has(decodeURIComponent(match[1])), `${file}: missing #${match[1]}`);
  }
});

test('the Korean hook inventory names all seven registered hook commands', () => {
  const doc = read('README.ko.md');
  const commands = Object.values(JSON.parse(read('hooks/hooks.json')).hooks)
    .flatMap((groups) => groups.flatMap((group) => group.hooks.map((hook) => hook.command)));
  assert.equal(commands.length, 7);
  assert.doesNotMatch(doc, /훅\s*3종/);
  const section = doc.split('### 훅 7종')[1]?.split('\n### ')[0];
  assert.ok(section, 'seven-hook section must exist');
  for (const command of commands) {
    const name = command.match(/\/hooks\/([^/" ]+)"$/)?.[1];
    assert.ok(name, `cannot extract registered hook: ${command}`);
    assert.ok(section.includes(name), `missing hook description: ${name}`);
  }
});

test('all published healthcheck examples name the tools actually probed by the script', () => {
  const labels = [...read('scripts/healthcheck.sh').matchAll(/^phase_check "(Phase \d+)" "([^"]+)"/gm)]
    .map((match) => `${match[1]} ${match[2]}`);
  assert.equal(labels.length, 6, 'six-phase extraction positive control');
  for (const file of ['docs/SETUP.md', 'docs/SETUP-BEGINNER.md',
    'docs/SETUP-BEGINNER.typ', 'docs/SETUP-BEGINNER.en.typ']) {
    const doc = read(file);
    for (const label of labels) assert.ok(doc.includes(label), `${file}: missing actual label ${label}`);
    absent(doc, /Phase 3 obsidian-mcp/i, `${file}: local healthcheck does not probe Obsidian MCP`);
  }
});

test('public bot setup skill siblings contain no reviewed private names or DM identifier', () => {
  for (const file of ['skills/slack-configure/SKILL.md', 'skills/slack-bridge/SKILL.md']) {
    // Escaped private-name fixtures keep public test source free of literal names.
    absent(read(file), /\uC7AC\uACBD\uB2D8|Andre\s*Karpathy|1534838364/, file);
  }
  for (const file of ['skills/create-discord-bot/SKILL.md', 'skills/create-slack-bot/SKILL.md']) {
    absent(read(file), /\uC815\uBCF8/, file);
  }
});

test('installer, support, and generated-persona examples delegate search to km', () => {
  const install = read('install.sh');
  absent(install, /vault (?:access )?3-Tier fallback|3-Tier fallback will use/,
    'installer must not advertise the obsolete search dispatcher');
  assert.ok(install.includes('/km:search'), 'installer points to the external search entry');
  const guide = read('rules/FILL-IN-GUIDE.md');
  assert.ok(guide.includes('KB: /km:search'), 'filled-in rule must delegate search');
  for (const name of ['general-assistant', 'research-bot', 'schedule-bot']) {
    const source = read(`templates/soul-${name}.md`);
    assert.ok(source.includes('/km:search'), `${name}: external search pointer`);
    absent(source, /vault-search \(Obsidian CLI \/ MCP/, `${name}: obsolete local fallback`);
  }
  const form = read('.github/ISSUE_TEMPLATE/setup-failure.yml');
  assert.ok(form.includes('Phase 3 vault-search MCP (local embedding)'), 'form requests the actual printed tool');
  absent(form, /Tier 4 OK \/ Tier 3 OK/, 'form must not request obsolete tier diagnostics');
  const version = read('contracts/search-fallback-4tier.md').match(/^version: (\S+)$/m)?.[1];
  assert.ok(read('docs/08-chapter-mapping.md').includes('`contracts/search-fallback-4tier.md` v' + version),
    'chapter references the current contract revision');
});
