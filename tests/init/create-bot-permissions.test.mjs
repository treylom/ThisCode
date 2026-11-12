// The invite link's permission value and the list of names beside it must say the same thing,
// and the three wider permissions are added only when the user said yes.
//
// skills/create-bot/SKILL.md shows the bot permissions twice (default flow, manual flow):
//   "- Bot Permissions (기본 11종): <names>"            → `permissions=395137117248`
//   "- 더할 권한 3종(‘예’ 일 때만): <names>"             → with the 11: `permissions=2252195487804480`
// This test turns the names into bits and compares the sums with the numbers, so dropping a
// name, adding one, moving one between the lists, or changing a number alone fails here.
import assert from 'node:assert/strict';
import { readFileSync } from 'node:fs';
import test from 'node:test';

// Discord permission bit positions (developer docs · same as discord-api-types PermissionFlagsBits).
const BASE_BITS = {
  'Add Reactions': 6,
  'View Channels': 10,
  'Send Messages': 11,
  'Manage Messages': 13,
  'Embed Links': 14,
  'Attach Files': 15,
  'Read Message History': 16,
  'Manage Threads': 34,
  'Create Public Threads': 35,
  'Create Private Threads': 36,
  'Send Messages in Threads': 38,
};
const EXTRA_BITS = {
  'Mention Everyone': 17,
  'Manage Webhooks': 29,
  'Pin Messages': 51,
};
const BITS = { ...BASE_BITS, ...EXTRA_BITS };
const BASE_VALUE = 395137117248n;
const FULL_VALUE = 2252195487804480n;

function valueOf(names) {
  return names.reduce((sum, name) => {
    assert.ok(name in BITS, `unknown permission name: ${name}`);
    return sum | (1n << BigInt(BITS[name]));
  }, 0n);
}

const text = readFileSync('skills/create-bot/SKILL.md', 'utf8');
const table = readFileSync('skills/create-bot/automation.yaml', 'utf8');
const split = line => line.split(' / ').map(name => name.replace(/\*\*/g, '').trim());
const baseLists = [...text.matchAll(/^\s*- Bot Permissions \(기본 11종\): (.+)$/gm)].map(match => split(match[1]));
const extraLists = [...text.matchAll(/^\s*- 더할 권한 3종\(‘예’ 일 때만\): (.+)$/gm)].map(match => split(match[1]));
const baseValues = [...text.matchAll(/참고 값: 위 (\d+)종 = `permissions=(\d+)`/g)].map(match => ({ count: Number(match[1]), value: BigInt(match[2]) }));
const fullValues = [...text.matchAll(/‘예’ 일 때 값: (\d+)종 = `permissions=(\d+)`/g)].map(match => ({ count: Number(match[1]), value: BigInt(match[2]) }));

test('both flows show 11 default permissions and, apart from them, the 3 that need a yes', () => {
  assert.equal(baseLists.length, 2, 'default flow and manual flow');
  assert.equal(extraLists.length, 2);
  assert.doesNotMatch(text, /^\s*- Bot Permissions: /m, 'no list without the default/extra split');
  for (const names of baseLists) {
    assert.equal(new Set(names).size, 11);
    assert.deepEqual([...names].sort(), Object.keys(BASE_BITS).sort());
  }
  for (const names of extraLists) assert.deepEqual([...names].sort(), Object.keys(EXTRA_BITS).sort());
});

test('default = 11 names = 395137117248 · after a yes = 14 names = 2252195487804480', () => {
  assert.equal(baseValues.length, 2);
  assert.equal(fullValues.length, 2);
  baseLists.forEach((names, index) => {
    assert.equal(baseValues[index].count, names.length);
    assert.equal(baseValues[index].value, valueOf(names), 'the default number is the default names');
    assert.equal(baseValues[index].value, BASE_VALUE);
    const all = [...names, ...extraLists[index]];
    assert.equal(fullValues[index].count, all.length);
    assert.equal(fullValues[index].value, valueOf(all), 'the wider number is default + extra names');
    assert.equal(fullValues[index].value, FULL_VALUE);
  });
  assert.equal(FULL_VALUE & ~BASE_VALUE, valueOf(Object.keys(EXTRA_BITS)), 'the two numbers differ by exactly the three extra bits');
  // every permissions= number in the skill is one of the two (the retired 15-bit number is quoted without "permissions=")
  for (const match of text.matchAll(/permissions=(\d+)/g)) assert.ok([BASE_VALUE, FULL_VALUE].includes(BigInt(match[1])), match[0]);
});

test('the three wider permissions are asked for before the link is made, and only a yes adds them', () => {
  const flow = text.slice(text.indexOf('**기본 흐름 (도구 있음, 기본값)'), text.indexOf('완료 후 **한 게 뭔지**'));
  const ask = flow.indexOf('더할 권한 3종은 묻는다 — 초대 주소를 만들기 «전에» 한 번');
  assert.ok(ask > 0, 'the default flow asks');
  assert.ok(ask < flow.indexOf('생성된 URL 로 이동'), 'the question comes before the link is used');
  for (const [name, effect] of [
    ['Mention Everyone', /@everyone · @here 로 서버 전체를 부를 수 있습니다/],
    ['Pin Messages', /메시지를 고정하거나 고정을 풀 수 있습니다/],
    ['Manage Webhooks', /웹후크를 만들고 고치고 지울 수 있습니다/],
  ]) {
    assert.ok(flow.includes(name));
    assert.match(flow, effect, `${name}: what it lets the bot do`);
  }
  assert.match(flow, /세 가지를 더할까요\? \(예 \/ 아니오 — 답이 없으면 더하지 않습니다/);
  assert.match(flow, /\*\*‘예’\*\* → 이번 초대 주소에만 3종을 더한다\. 주소를 만들기 직전에 한 번 보여 준다: "선택된 권한 14개: /, 'yes → 14, shown once before the link');
  assert.match(flow, /\*\*‘아니오’ · 답이 없음 · 다른 말\*\* → 기본 11종 그대로 만든다/, 'no / no answer / anything else → 11');
  assert.match(flow, /지난번 답으로 ‘예’ 를 짐작하지 않는다/, 'a yes is never inferred');
  const shown = flow.match(/"선택된 권한 14개: ([^"]+)"/)[1].split(' · ');
  assert.deepEqual([...shown].sort(), Object.keys(BITS).sort(), 'the list shown before the link is the 14 names');
});

test('the step table says the same: 11 by default, 14 only after a yes', () => {
  const row = table.slice(table.indexOf('gate: "discord_invite_url"'), table.indexOf('- id: "3/6"'));
  assert.match(row, /asks_consent: "[^"]*세 가지를 더할까요\? \(예 \/ 아니오/);
  assert.match(row, /consent_required: "‘예’ 를 받은 이번 초대 주소에만 3종을 더한다\(권한 14종 · permissions=2252195487804480\) — 아니오 · 답 없음 · 다른 말이면 기본 권한 11종\(permissions=395137117248\)/);
  assert.match(row, /show_before_create: "선택된 권한 14개: /);
  assert.match(row, /reason: "범위와 기본 권한 11종 고르기는 자동/);
  assert.doesNotMatch(table, /권한 14종 고르기는 자동/, 'the old "14 automatically" line is gone');
});

test('commands/start.md lists the same 11 default permissions and number as the skill', () => {
  const start = readFileSync('commands/start.md', 'utf8');
  const line = start.match(/^\s*- Bot Permissions \(기본 11종\): (.+) — `permissions=(\d+)`$/m);
  assert.ok(line, 'the manual flow of start.md has the default list with its number');
  assert.deepEqual(split(line[1]).sort(), Object.keys(BASE_BITS).sort());
  assert.equal(BigInt(line[2]), BASE_VALUE);
  assert.match(start, /원하면 3종을 더 고른다\(Mention Everyone \/ Pin Messages \/ Manage Webhooks/);
  assert.doesNotMatch(start, /Read Messages,/, 'the old six-name summary is gone');
  assert.match(start, /포털 로그인\(로그인이 안 돼 있을 때\) · hCaptcha · 비밀번호\/다단계 인증\(MFA\) 창 3곳에서만/, 'three human-only stops, as in the skill');
});

test('the folder-trust prompt is answered by its label, not by a line number', () => {
  for (const path of ['skills/create-bot/SKILL.md', 'skills/create-bot/automation.yaml']) {
    const body = readFileSync(path, 'utf8');
    assert.match(body, /Yes, I trust this folder/, path);
    assert.doesNotMatch(body, /1번 선택 후 Enter|1번을 고르고 Enter/, `${path}: the first line of that window can be "No, exit"`);
  }
});
