// Per-step automation tables (skills/<skill>/automation.yaml) and the
// "three automatic attempts before handing a step to the user" rule.
//
// What this suite locks:
//  - every skill whose SKILL.md has "### Step" headings ships an automation.yaml
//  - the steps in the yaml and the headings in SKILL.md are the same list, in the same order
//  - human-only stops are exactly the names in configs/install.yaml (both directions)
//  - install-gate.sh --handoff says "not yet" until three failed attempts are recorded,
//    and says "go ahead" at once for a human-only stop
//  - the guidance text carries the Korean screen names next to the English ones
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { existsSync, mkdtempSync, readdirSync, readFileSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { spawnSync } from 'node:child_process';

const SKILLS_DIR = 'skills';
const MODES = ['auto', 'auto_then_human', 'human_only'];

// The yaml files use a small fixed subset: top-level `key: "value"`, one map
// section (`policy:`), and list sections (`always_human:`, `steps:`) of flat
// maps. Every value is a one-line double-quoted string with no escapes.
export function parseAutomation(text) {
  const out = { policy: {}, always_human: [], steps: [] };
  let section = null;
  let item = null;
  const value = (raw, where) => {
    const match = /^"([^"\\]*)"$/.exec(raw.trim());
    assert.ok(match, `${where}: a value must be a one-line double-quoted string without escapes — got ${raw}`);
    return match[1];
  };
  text.split(/\r?\n/).forEach((line, index) => {
    const where = `line ${index + 1}`;
    if (!line.trim() || line.trim().startsWith('#')) return;
    let match;
    if ((match = /^([a-z_]+):\s*$/.exec(line))) {
      section = match[1];
      assert.ok(['policy', 'always_human', 'steps'].includes(section), `${where}: unknown section ${section}`);
      item = null;
    } else if ((match = /^([a-z_]+):\s+(.+)$/.exec(line))) {
      out[match[1]] = value(match[2], where);
      section = null;
    } else if ((match = /^ {2}- ([a-z_0-9]+):\s+(.+)$/.exec(line))) {
      assert.ok(section === 'always_human' || section === 'steps', `${where}: a list item outside a list section`);
      item = { [match[1]]: value(match[2], where) };
      out[section].push(item);
    } else if ((match = /^ {4}([a-z_0-9]+):\s+(.+)$/.exec(line))) {
      assert.ok(item, `${where}: a field with no list item above it`);
      assert.ok(!(match[1] in item), `${where}: field ${match[1]} given twice`);
      item[match[1]] = value(match[2], where);
    } else if ((match = /^ {2}([a-z_0-9]+):\s+(.+)$/.exec(line))) {
      assert.equal(section, 'policy', `${where}: a plain field outside policy`);
      out.policy[match[1]] = value(match[2], where);
    } else {
      assert.fail(`${where}: not in the supported yaml subset — ${line}`);
    }
  });
  return out;
}

// "### Step 4.7. access.json 직접 생성" → "4.7"
export function headingIds(skillText) {
  return [...skillText.matchAll(/^### Step (.+?)\. /gm)].map(match => match[1]);
}

// What is wrong between a SKILL.md and its automation.yaml (empty = in step).
export function drift(skillText, table) {
  const problems = [];
  const headings = headingIds(skillText);
  const top = table.steps.filter(step => !step.id.includes('/')).map(step => step.id);
  if (headings.join(' | ') !== top.join(' | ')) {
    problems.push(`step list differs — SKILL.md: [${headings.join(', ')}] · yaml: [${top.join(', ')}]`);
  }
  for (const step of table.steps) {
    if (!step.id.includes('/')) continue;
    const parent = step.id.split('/')[0];
    if (!top.includes(parent)) problems.push(`sub-step ${step.id} has no parent step ${parent}`);
    if (!step.anchor) problems.push(`sub-step ${step.id} has no anchor`);
    else if (!skillText.includes(step.anchor)) problems.push(`sub-step ${step.id}: anchor not found in SKILL.md — ${step.anchor}`);
  }
  return problems;
}

function skillsWithSteps() {
  return readdirSync(SKILLS_DIR, { withFileTypes: true })
    .filter(entry => entry.isDirectory() && existsSync(join(SKILLS_DIR, entry.name, 'SKILL.md')))
    .map(entry => entry.name)
    .filter(name => headingIds(readFileSync(join(SKILLS_DIR, name, 'SKILL.md'), 'utf8')).length > 0)
    .sort();
}

function load(skill) {
  return {
    skillText: readFileSync(join(SKILLS_DIR, skill, 'SKILL.md'), 'utf8'),
    table: parseAutomation(readFileSync(join(SKILLS_DIR, skill, 'automation.yaml'), 'utf8')),
  };
}

function manualNames() {
  const yaml = readFileSync('configs/install.yaml', 'utf8');
  const list = yaml.slice(yaml.indexOf('manual_allowed_without_attempt:'));
  return [...list.matchAll(/^\s*-\s*name:\s*([A-Za-z0-9_]+)/gm)].map(match => match[1]);
}

function names(field) {
  return String(field || '').split(/\s+/).filter(Boolean);
}

test('every skill with "### Step" headings ships an automation.yaml', () => {
  const skills = skillsWithSteps();
  assert.ok(skills.includes('create-bot') && skills.includes('slack-configure'), `skills with steps: ${skills.join(', ')}`);
  for (const skill of skills) {
    assert.ok(existsSync(join(SKILLS_DIR, skill, 'automation.yaml')), `${skill}: SKILL.md has Step headings but there is no skills/${skill}/automation.yaml`);
  }
});

test('the yaml steps and the SKILL.md step headings are the same list in the same order', () => {
  for (const skill of skillsWithSteps()) {
    const { skillText, table } = load(skill);
    assert.equal(table.schema, 'thiscode-automation-v1', `${skill}: schema`);
    assert.equal(table.skill, skill, `${skill}: the skill field names the folder`);
    assert.deepEqual(drift(skillText, table), [], `${skill}: SKILL.md and automation.yaml drifted apart`);
    assert.equal(headingIds(skillText).length, table.steps.filter(step => !step.id.includes('/')).length, `${skill}: step count`);
  }
});

test('drift is caught: a step missing from the yaml, an extra one, a renamed heading, a reordered pair, a lost anchor', () => {
  const { skillText, table } = load('create-bot');
  const clone = () => ({ ...table, steps: table.steps.map(step => ({ ...step })) });

  const missing = clone();
  missing.steps = missing.steps.filter(step => step.id !== '4.7');
  assert.notDeepEqual(drift(skillText, missing), []);

  const extra = clone();
  extra.steps.push({ id: '9', title: 'x', mode: 'auto', reason: 'x' });
  assert.notDeepEqual(drift(skillText, extra), []);

  assert.notDeepEqual(drift(skillText.replace('### Step 2. ', '### Step 2b. '), table), []);
  assert.notDeepEqual(drift(skillText.replace('### Step 2. ', '### 2. '), table), [], 'a heading that stops being a Step is a drift too');

  const swapped = clone();
  const a = swapped.steps.findIndex(step => step.id === '1');
  const b = swapped.steps.findIndex(step => step.id === '2');
  [swapped.steps[a], swapped.steps[b]] = [swapped.steps[b], swapped.steps[a]];
  assert.notDeepEqual(drift(skillText, swapped), []);

  const sub = table.steps.find(step => step.id.includes('/') && step.anchor);
  assert.notDeepEqual(drift(skillText.split(sub.anchor).join('(지워진 문장)'), table), []);
});

test('every step says who does it, why, and what to tell the user when it is handed over', () => {
  for (const skill of skillsWithSteps()) {
    const { table } = load(skill);
    const ids = table.steps.map(step => step.id);
    assert.equal(new Set(ids).size, ids.length, `${skill}: a step id is used twice`);
    for (const step of table.steps) {
      const where = `${skill} step ${step.id}`;
      assert.ok(step.title, `${where}: title`);
      assert.ok(MODES.includes(step.mode), `${where}: mode must be one of ${MODES.join(' / ')} — got ${step.mode}`);
      assert.ok(step.reason, `${where}: reason`);
      if (step.mode === 'human_only') {
        assert.ok(step.handoff, `${where}: a human-only step needs the handoff text`);
        assert.ok(step.kind === 'answer' || names(step.human_stops).length > 0, `${where}: a human-only step is an answer or names its stop`);
      }
      if (step.mode === 'auto_then_human') {
        assert.match(step.gate || '', /^[a-z0-9_]+$/, `${where}: an auto-then-human step needs a gate name`);
        assert.ok(step.handoff, `${where}: an auto-then-human step needs the handoff text`);
      }
      if (names(step.human_stops).length) assert.ok(step.handoff, `${where}: a step with a human-only stop needs the handoff text`);
    }
    for (const stop of table.always_human) {
      assert.match(stop.gate || '', /^[a-z0-9_]+$/, `${skill}: always_human gate`);
      assert.ok(stop.when && stop.reason && stop.handoff, `${skill}: always_human ${stop.gate} needs when / reason / handoff`);
    }
  }
});

test('human-only stops are exactly the names in configs/install.yaml, and no gate that must be attempted first is on that list', () => {
  const manual = manualNames();
  assert.ok(manual.length >= 9, `install.yaml names: ${manual.length}`);
  const used = new Set();
  for (const skill of skillsWithSteps()) {
    const { table } = load(skill);
    for (const step of table.steps) {
      for (const name of names(step.human_stops)) {
        assert.ok(manual.includes(name), `${skill} step ${step.id}: human-only stop ${name} is not in configs/install.yaml`);
        used.add(name);
      }
      if (step.mode !== 'human_only' && step.gate) {
        assert.ok(!manual.includes(step.gate), `${skill} step ${step.id}: gate ${step.gate} is on the no-attempt list, so the three attempts would be skipped`);
      }
    }
    for (const stop of table.always_human) {
      assert.ok(manual.includes(stop.gate), `${skill}: always_human ${stop.gate} is not in configs/install.yaml`);
      used.add(stop.gate);
    }
  }
  assert.deepEqual(manual.filter(name => !used.has(name)), [], 'a name on the install.yaml list that no automation.yaml mentions');
});

test('the number of automatic attempts is 3 in install.yaml and in every table', () => {
  const yaml = readFileSync('configs/install.yaml', 'utf8');
  assert.match(yaml, /^\s*auto_attempts_before_handoff:\s*3\b/m);
  for (const skill of skillsWithSteps()) {
    const { table } = load(skill);
    assert.equal(table.policy.attempts_before_handoff, '3', `${skill}: policy.attempts_before_handoff`);
    assert.equal(table.policy.browser_order, 'ego aside fallback', `${skill}: policy.browser_order`);
  }
});

test('create-bot: the portal flow has one sub-step per numbered item, each tied to a sentence in the text', () => {
  const { skillText, table } = load('create-bot');
  const start = skillText.indexOf('**기본 흐름 (도구 있음, 기본값)');
  const end = skillText.indexOf('완료 후 **한 게 뭔지**');
  assert.ok(start > 0 && end > start, 'default-flow block not found');
  const numbered = [...skillText.slice(start, end).matchAll(/^(\d+)\. /gm)].map(match => match[1]);
  const subs = table.steps.filter(step => /^3\/[1-9]/.test(step.id)).map(step => step.id.split('/')[1]);
  assert.deepEqual(subs, numbered, 'sub-steps 3/1… must match the numbered items of the default flow');
  for (const step of table.steps.filter(item => /^3\/[1-9]/.test(item.id))) {
    const at = skillText.indexOf(step.anchor);
    assert.ok(at > start && at < end, `sub-step ${step.id}: its anchor sits outside the default flow`);
  }
});

// ---- install-gate.sh --handoff ----------------------------------------------

function gateBox() {
  const dir = mkdtempSync(join(tmpdir(), 'handoff-gate-'));
  const env = { ...process.env, HOME: dir, THISCODE_INSTALL_STATE: join(dir, 'state.yaml'), THISCODE_INSTALL_LOG: join(dir, 'log.jsonl') };
  const run = (...args) => spawnSync('bash', ['scripts/install-gate.sh', ...args], { encoding: 'utf8', env });
  run.log = env.THISCODE_INSTALL_LOG;
  return run;
}

test('handoff gate: not before three failed attempts are recorded, then yes', () => {
  const gate = gateBox();
  assert.equal(gate('--handoff', 'discord_intents').status, 1, 'no attempt yet');
  for (const round of [1, 2]) {
    assert.equal(gate('--attempted', 'discord_intents', 'fail', 'click-no-effect').status, 0);
    const verdict = gate('--handoff', 'discord_intents');
    assert.equal(verdict.status, 1, `after ${round} failed attempt(s) it is still not time`);
    assert.match(verdict.stderr, new RegExp(`${round}/3`));
  }
  assert.equal(gate('--attempted', 'discord_intents', 'fail', 'click-no-effect').status, 0);
  const verdict = gate('--handoff', 'discord_intents');
  assert.equal(verdict.status, 0, 'three failed attempts → hand over');
  assert.match(verdict.stdout, /3\/3/);
});

test('handoff gate: the hint walks retry → another way → the next browser', () => {
  const gate = gateBox();
  assert.match(gate('--handoff', 'discord_intents').stderr, /시도 1: .*다시/);
  gate('--attempted', 'discord_intents', 'fail', 'click-no-effect');
  assert.match(gate('--handoff', 'discord_intents').stderr, /시도 2: .*다른 길/);
  gate('--attempted', 'discord_intents', 'fail', 'click-no-effect');
  assert.match(gate('--handoff', 'discord_intents').stderr, /시도 3: .*다음 브라우저/);
});

test('handoff gate: a human-only stop is handed over at once and never counted', () => {
  const gate = gateBox();
  for (const name of ['discord_portal_login', 'discord_hcaptcha', 'discord_reset_token_modal']) {
    const verdict = gate('--handoff', name);
    assert.equal(verdict.status, 0, name);
    assert.match(verdict.stdout, /사람만/);
  }
});

test('handoff gate: a success or an allowed handoff starts the count again, and other gates do not count', () => {
  const gate = gateBox();
  gate('--attempted', 'discord_intents', 'fail', 'click-no-effect');
  gate('--attempted', 'discord_intents', 'fail', 'click-no-effect');
  gate('--attempted', 'discord_intents', 'ok');
  gate('--attempted', 'discord_intents', 'fail', 'click-no-effect');
  gate('--attempted', 'discord_invite_url', 'fail', 'click-no-effect');
  gate('--attempted', 'discord_invite_url', 'fail', 'click-no-effect');
  assert.equal(gate('--handoff', 'discord_intents').status, 1, 'only one failure since the success');
  gate('--attempted', 'discord_intents', 'fail', 'click-no-effect');
  gate('--attempted', 'discord_intents', 'fail', 'click-no-effect');
  assert.equal(gate('--handoff', 'discord_intents').status, 0);
  assert.equal(gate('--handoff', 'discord_intents').status, 1, 'the count starts again after an allowed handoff');
});

test('handoff gate: no name or a strange name is a usage error', () => {
  const gate = gateBox();
  assert.equal(gate('--handoff', 'discord_developer_terms').status, 1, 'the consent box goes through the three attempts like any other step');
  assert.equal(gate('--handoff').status, 2);
  assert.equal(gate('--handoff', 'a b').status, 2);
  assert.equal(gate('--handoff', '.*').status, 2);
});

test('handoff gate: a name is checked as a whole — a second line cannot smuggle a human-only name in', () => {
  const gate = gateBox();
  const twoLines = 'discord_intents\ndiscord_hcaptcha';
  assert.equal(gate('--handoff', 'discord_intents').status, 1, 'control: the plain name still has to be attempted');
  assert.equal(gate('--handoff', twoLines).status, 2, 'a two-line name is a usage error, not a human-only stop');
  assert.equal(gate('--handoff', 'discord_hcaptcha\n').status, 2, 'a trailing line break is refused too');
  assert.equal(gate('--attempted', twoLines, 'fail', 'click-no-effect').status, 2, 'the same check guards --attempted');
  assert.equal(gate('--attempted', 'a b', 'ok').status, 2);
  assert.equal(gate('--attempted', 'discord_intents', 'ok').status, 0, 'control: a plain name is still recorded');
  const ledger = existsSync(gate.log) ? readFileSync(gate.log, 'utf8') : '';
  assert.doesNotMatch(ledger, /handoff-allowed/, 'nothing was allowed along the way');
  assert.doesNotMatch(ledger, /discord_intentsdiscord_hcaptcha/, 'the smuggled name never reached the ledger');
});

// ---- the text the user is shown ----------------------------------------------

test('skill text: the three-attempt rule and the table are part of the flow', () => {
  for (const skill of ['create-bot', 'slack-configure']) {
    const text = readFileSync(join(SKILLS_DIR, skill, 'SKILL.md'), 'utf8');
    assert.match(text, /automation\.yaml/, `${skill}: points at its table`);
    assert.match(text, /install-gate\.sh --handoff/, `${skill}: calls the handoff gate before handing over`);
    assert.match(text, /막혔을 때 — 자동 시도 3회, 그 뒤에만 사람/, `${skill}: states the rule`);
    assert.match(text, /① [^\n]*다시[^\n]*② [^\n]*다른 길[^\n]*③ [^\n]*다음 브라우저/, `${skill}: says what each of the three attempts is`);
    assert.match(text, /곧바로 사용자에게 넘기지 않는다/, `${skill}: a blocked step is not handed over right away`);
    assert.match(text, /시도 횟수에 넣지 않/, `${skill}: human-only stops are not counted`);
  }
});

test('token steps: Reset Token is pressed once, the browser is not switched while the token is on screen, and attempt reasons carry no values', () => {
  const text = readFileSync('skills/create-bot/SKILL.md', 'utf8');
  const flow = text.slice(text.indexOf('**기본 흐름 (도구 있음, 기본값)'), text.indexOf('완료 후 **한 게 뭔지**'));
  assert.match(flow, /Reset Token 은 이 단계에서 한 번만 누른다\*\* — 다시 시도할 때 다시 누르지 않는다/, 'default flow: one press');
  assert.match(flow, /토큰 화면이 떠 있는 동안에는 브라우저를 바꾸지 않는다/, 'default flow: stay in the browser that shows the token');
  assert.match(flow, /저장이 세 번 안 되면 그때만 사람에게 넘기고, 다시 발급이 필요하다고 한 줄로 말한다/);

  const { table } = load('create-bot');
  const reset = table.steps.find(item => item.id === '3/3');
  assert.match(reset.once || '', /한 번만 누른다 — 다시 시도할 때 다시 누르지 않는다/, 'the table says it for step 3/3');
  const save = table.steps.find(item => item.id === '4');
  assert.match(save.keep_browser || '', /브라우저를 바꾸지 않는다/, 'the table says it for step 4');
  assert.match(save.keep_browser || '', /다시 발급이 필요하다고 한 줄로 말한다/);

  const never = /화면에서 본 글 · 오류 원문 · 값(?:\(토큰 · 비밀번호 · 인증 코드 · 주소\))?을 명령에 넣지 않는다/;
  for (const skill of ['create-bot', 'slack-configure']) {
    assert.match(readFileSync(join(SKILLS_DIR, skill, 'SKILL.md'), 'utf8'), never, `${skill}: the text says what never goes into a reason`);
  }
  for (const skill of skillsWithSteps()) {
    assert.match(load(skill).table.policy.record_never || '', never, `${skill}: policy.record_never`);
  }
});

// Portal sub-steps that are automatic but hold a human-only stop need two texts:
// `handoff` for the stop itself, `handoff_after_attempts` for a hand-over after three failed attempts.
const TWO_TEXT_STEPS = ['3/1', '3/2', '3/3'];

test('create-bot: a portal step with a human-only stop inside has its own text for a hand-over after three attempts', () => {
  const { table, skillText } = load('create-bot');
  for (const id of TWO_TEXT_STEPS) {
    const step = table.steps.find(item => item.id === id);
    assert.equal(step.mode, 'auto_then_human', id);
    assert.ok(names(step.human_stops).length > 0, `${id}: has a human-only stop`);
    const text = step.handoff_after_attempts || '';
    assert.match(text, /세 번 시도했는데 <사유>로 안 됐습니다\./, `${id}: says what was tried and why it failed`);
    assert.match(text, /그 다음은 제가 이어갑니다\.$/, `${id}: says the bot carries on`);
    assert.notEqual(text, step.handoff, `${id}: not the text of the human-only stop`);
  }
  const newApp = table.steps.find(item => item.id === '3/2');
  assert.doesNotMatch(newApp.handoff_after_attempts, /로봇 아니고 사람/, 'a failed consent box is not announced as the human check');
  assert.match(newApp.handoff_after_attempts, /동의 칸을 체크한 뒤 «만들기»\(Create\)를 누르면 됩니다/);
  const reset = table.steps.find(item => item.id === '3/3');
  assert.match(reset.handoff_after_attempts, /‘Reset Token’ 을 한 번만 눌러 주세요/, 'the user is asked for one press, as the step itself allows only one');
  assert.match(skillText, /자동 시도 3회가 다 실패해 넘길 때는 `handoff_after_attempts` 가 있으면 그것을, 없으면 `handoff` 를 쓰고/, 'the text says which one to use');
  assert.match(skillText, /사람만 하는 자리\(`human_stops`\)에서 넘길 때는 `handoff` 를 쓴다/);
});

test('create-bot: the consent box of the new-app window is ticked only after the user answers yes — no answer, no click', () => {
  const text = readFileSync('skills/create-bot/SKILL.md', 'utf8');
  const flow = text.slice(text.indexOf('**기본 흐름 (도구 있음, 기본값)'), text.indexOf('완료 후 **한 게 뭔지**'));
  const question = /제가 동의 칸을 체크하고 ‘만들기’ 를 눌러도 될까요\? \(예 \/ 아니오 — 아니오면 직접 체크해 주세요\)/;
  assert.match(flow, /약관 동의 칸은 묻고, ‘예’ 를 받은 뒤에만 체크한다/, 'default flow: ask first');
  assert.match(flow, question, 'the question, with both answers named');
  assert.match(flow, /체크하기 \*\*전에\*\* 묻고 답을 기다린다/, 'it waits for the answer');
  assert.match(flow, /\*\*‘예’\*\* → 동의 칸을 체크하고 «만들기»를 누른다/, 'yes: the bot ticks and creates');
  assert.match(flow, /\*\*‘아니오’\*\* → 동의 칸도 «만들기»도 누르지 않는다/, 'no: zero clicks');
  assert.match(flow, /사용자가 직접 체크하고 만들기 전에는 다음 단계로 가지 않는다/, 'no: the flow stops at the user');
  assert.match(flow, /\*\*답이 없거나 다른 말\*\* → 누르지 않고 기다린다/, 'no answer or anything else: zero clicks');
  assert.match(flow, /지난번 답으로 ‘예’ 를 짐작하지 않는다/, 'a yes is never inferred');
  // the old "tell and tick right away" wording must not come back anywhere
  for (const gone of [/알림이지 묻고 기다리는 관문이 아니다/, /알리고 바로 체크/, /원치 않으면 지금 말해 주세요/, /약관 동의 칸은 봇이 체크한다/, /먼저 한 줄로 알린다/]) {
    assert.doesNotMatch(text, gone, `gone from the skill: ${gone}`);
    assert.doesNotMatch(readFileSync('skills/create-bot/automation.yaml', 'utf8'), gone, `gone from the table: ${gone}`);
  }
  assert.match(flow, /입력 칸\(input\)을 직접 세어 체크 칸\(checkbox\)을 찾아/, 'how to find the box the page text does not show');
  const manual = text.slice(text.indexOf('**수동 안내 (도구 없음'), text.indexOf('### Step 4. '));
  assert.match(manual, /동의 칸/, 'manual flow still tells the user about the box');
  assert.match(text, /신규 앱 만들기/);

  assert.ok(!manualNames().includes('discord_developer_terms'), 'the consent box is not on the hand-over-at-once list');
  const { table } = load('create-bot');
  const step = table.steps.find(item => item.id === '3/2');
  assert.equal(step.mode, 'auto_then_human');
  assert.equal(step.human_stops, 'discord_hcaptcha', 'only the human check is a human-only stop in this step');
  assert.equal(step.notice, undefined, 'a notice is not consent');
  assert.match(step.asks_consent || '', question, 'the table carries the same question');
  assert.match(step.consent_required || '', /‘예’ 를 받은 뒤에만 동의 칸을 체크하고 ‘만들기’ 를 누른다 — 답이 없거나 다른 말이면 누르지 않고 기다린다/);
  assert.match(step.if_declined || '', /동의 칸도 ‘만들기’ 도 누르지 않고 사용자 차례에서 멈춘다/, 'a refusal stops at the user');
  assert.match(step.if_declined || '', /--handoff 를 부르지 않는다/, 'a refusal is the user\'s choice, not a hand-over');
  assert.doesNotMatch(step.handoff, /동의 칸/, 'the hand-over text of the human check does not mention the box');
});

test('human-only means answers, login, the human check, a password or a permission prompt — never a terms box', () => {
  for (const skill of skillsWithSteps()) {
    const { table } = load(skill);
    for (const step of table.steps) {
      assert.doesNotMatch(step.human_stops || '', /terms/, `${skill} step ${step.id}`);
    }
  }
  for (const skill of skillsWithSteps()) {
    const head = readFileSync(join(SKILLS_DIR, skill, 'automation.yaml'), 'utf8').split('\n').find(line => line.includes('human_only       '));
    if (head) assert.doesNotMatch(head, /동의/, `${skill}: the header comment does not list consent under human_only`);
  }
});

test('guidance text: "New Application" is never shown without its Korean screen name', () => {
  const files = ['skills/create-bot/SKILL.md', 'skills/help/SKILL.md', 'skills/slack-bridge/SKILL.md', 'commands/start.md', 'commands/add-bot.md'];
  let seen = 0;
  for (const file of files) {
    readFileSync(file, 'utf8').split('\n').forEach((line, index) => {
      if (!line.includes('New Application')) return;
      seen += 1;
      assert.ok(line.includes('신규 애플리케이션'), `${file}:${index + 1} shows "New Application" without «신규 애플리케이션»`);
    });
  }
  assert.ok(seen >= 6, `lines with "New Application": ${seen}`);
});
