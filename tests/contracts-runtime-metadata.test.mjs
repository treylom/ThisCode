import { test } from 'node:test';
import assert from 'node:assert/strict';
import { readdirSync, readFileSync } from 'node:fs';
import yaml from 'js-yaml';

const read = (relativePath) =>
  readFileSync(new URL(`../${relativePath}`, import.meta.url), 'utf8').replace(/\r\n?/g, '\n');
const contract = read('contracts/search-fallback-4tier.md');
const hermes = yaml.load(read('hermes-plugin/plugin.yaml'));
const schema = JSON.parse(read('schemas/agent-spec.json'));
const mcpSource = read('vendor/vault-search-mcp/src/index.ts');
const contractFiles = readdirSync(new URL('../contracts/', import.meta.url))
  .filter((name) => name.endsWith('.md'));

test('search fallback contract matches the bundled vault-search MCP tools', () => {
  assert.match(mcpSource, /name:\s*['"]search['"]/);
  assert.match(mcpSource, /name:\s*['"]vault_search['"]/);
  assert.match(
    mcpSource,
    /name:\s*['"]vault_search['"][\s\S]*?properties:[\s\S]*?query:[\s\S]*?topK:/,
    'vault_search must accept query and topK',
  );
  assert.match(
    mcpSource,
    /case\s+['"]vault_search['"][\s\S]*?args\.query[\s\S]*?args\.topK[\s\S]*?formatJsonResult/,
    'vault_search must encode its result in an MCP text content block',
  );
  assert.match(
    mcpSource,
    /text:\s*JSON\.stringify\(\{\s*results:\s*chatgptResults\s*\}\)/,
    'search must encode its {results} response as MCP text',
  );

  const tier3Row = contract.split('\n').find((line) => /^\| 3 \|/.test(line));
  assert.ok(tier3Row, 'contract must define a Tier 3 row');
  assert.match(tier3Row, /vault-search MCP/);
  assert.match(tier3Row, /vault_search/);
  assert.match(tier3Row, /query/);
  assert.match(tier3Row, /topK/);
  assert.match(tier3Row, /content\[0\]\.text/);
  assert.doesNotMatch(
    contract,
    /mcp__vault-search__list_notes|mcp__vault-search__search\(\{[^}]*"q"|mcp__vault-search__search\(\{[^}]*"top_k"/,
  );
  assert.match(contract, /mcp__vault-search__vault_search\(\{\s*"query":\s*"\$QUERY",\s*"topK":\s*N\s*\}\)/);
  assert.match(contract, /content\[0\]\.text[\s\S]{0,240}JSON/i);
  assert.match(contract, /results[\s\S]{0,180}title[\s\S]{0,180}slug[\s\S]{0,180}snippet[\s\S]{0,180}score[\s\S]{0,180}source/i);
  assert.match(contract, /mcp__vault-search__search\(\{\s*"query":\s*"\$QUERY"\s*\}\)/);
  assert.match(
    contract,
    /encoded JSON payload[\s\S]{0,200}"results"[\s\S]{0,100}"id"[\s\S]{0,100}"title"[\s\S]{0,100}"url"/i,
  );
});

test('Hermes metadata and the agent schema carry the current external contracts', () => {
  for (const file of contractFiles) {
    const source = read(`contracts/${file}`);
    assert.match(source, /^---\n(?:[^\n]*\n)*contract:\s*[A-Za-z0-9_-]+\n(?:[^\n]*\n)*version:\s*[0-9]+\.[0-9]+\.[0-9]+\n/m, `${file} must have valid contract frontmatter`);
  }

  const contractVersion = contract.match(/^version:\s*([0-9]+\.[0-9]+\.[0-9]+)\s*$/m)?.[1];
  assert.equal(hermes.metadata.contract_version, '0.2.0');
  assert.equal(contractVersion, hermes.metadata.contract_version);
  const tierOrder = hermes.metadata.tier_order.map((entry) => {
    const [tier, engine] = Object.entries(entry)[0];
    return `${tier}:${engine}`;
  });
  assert.deepEqual(tierOrder, [
    '1:GraphRAG',
    '2:Obsidian CLI',
    '3:vault-search MCP',
    '4:ripgrep',
  ]);

  const phaseDescription = schema.properties.phases.description;
  assert.match(phaseDescription, /historical.*external km plugin/i);
  assert.doesNotMatch(phaseDescription, /v2\.1 km-at|\/km:/i);
});
