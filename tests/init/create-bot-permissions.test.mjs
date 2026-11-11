// The invite link's permission value and the list of names beside it must say the same thing.
//
// skills/create-bot/SKILL.md shows the bot permissions twice (default flow, manual flow):
// a "Bot Permissions:" line with names, then a "permissions=<number>" line.
// This test turns the names into bits and compares the sum with the number,
// so dropping a name, adding one, or changing the number alone fails here.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

// Discord permission bit positions (developer docs · same as discord-api-types PermissionFlagsBits).
const BITS = {
  'Add Reactions': 6,
  'View Channels': 10,
  'Send Messages': 11,
  'Manage Messages': 13,
  'Embed Links': 14,
  'Attach Files': 15,
  'Read Message History': 16,
  'Mention Everyone': 17,
  'Manage Webhooks': 29,
  'Manage Threads': 34,
  'Create Public Threads': 35,
  'Create Private Threads': 36,
  'Send Messages in Threads': 38,
  'Pin Messages': 51,
};
const EXPECTED = 2252195487804480n;

function valueOf(names) {
  return names.reduce((sum, name) => {
    assert.ok(name in BITS, `unknown permission name: ${name}`);
    return sum | (1n << BigInt(BITS[name]));
  }, 0n);
}

const text = readFileSync('skills/create-bot/SKILL.md', 'utf8');
const lists = [...text.matchAll(/^\s*- Bot Permissions: (.+)$/gm)]
  .map(match => match[1].split(' / ').map(name => name.replace(/\*\*/g, '').trim()));
const values = [...text.matchAll(/참고 값: 위 (\d+)종 = `permissions=(\d+)`/g)]
  .map(match => ({ count: Number(match[1]), value: BigInt(match[2]) }));

test('create-bot shows the bot permissions in both flows, 14 names each, no name twice', () => {
  assert.equal(lists.length, 2, 'default flow and manual flow');
  for (const names of lists) {
    assert.equal(names.length, 14);
    assert.equal(new Set(names).size, 14);
    assert.deepEqual([...names].sort(), Object.keys(BITS).sort());
  }
});

test('the permissions number is exactly the 14 names turned into bits', () => {
  assert.equal(values.length, 2, 'one number under each list');
  lists.forEach((names, index) => {
    assert.equal(values[index].count, names.length, 'the count in the text is the length of the list');
    assert.equal(values[index].value, valueOf(names), 'number and names agree');
    assert.equal(values[index].value, EXPECTED);
  });
});

test('the step table and the change log use the same count and number', () => {
  const table = readFileSync('skills/create-bot/automation.yaml', 'utf8');
  assert.match(table, /권한 14종/);
  assert.doesNotMatch(table, /권한 11종/);
  assert.doesNotMatch(text, /395137117248/, 'the 11-permission number is gone');
});
