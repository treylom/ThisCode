import { test } from 'node:test';
import assert from 'node:assert/strict';
import { runManifest, evalWhen } from '../../scripts/lib/manifest-runner.mjs';

test('evalWhen DSL is the locked cross-repo superset (always/dotted/quoted/boolean)', () => {
  const ctx = { os: 'win', mode: 'apply', answers: { alias_consent: 'yes' }, tools: { tmux: false } };
  assert.equal(evalWhen('always', ctx), true);
  assert.equal(evalWhen("os == 'win'", ctx), true);
  assert.equal(evalWhen("mode == 'doctor'", ctx), false);
  assert.equal(evalWhen("answers.alias_consent == 'yes'", ctx), true);
  assert.equal(evalWhen('tools.tmux == false', ctx), true);
  assert.equal(evalWhen('os==win', ctx), true);            // bareword still parses (back-compat)
});

test('runs steps in ascending order, emits reason, stops on failed verify', () => {
  const log = [];
  const steps = [
    { id:'a', order:20, when:'always', action:'guide', reason:'RA', safety:'none', verify:{type:'true'} },
    { id:'b', order:10, when:'always', action:'guide', reason:'RB', safety:'none', verify:{type:'true'} },
    { id:'c', order:30, when:'always', action:'guide', reason:'RC', safety:'none', verify:{type:'false'}, on_fail:{ next_command:'thiscode --check' } },
    { id:'d', order:40, when:'always', action:'guide', reason:'RD', safety:'none', verify:{type:'true'} },
  ];
  const res = runManifest(steps, { actions:{ guide:(s)=>log.push(s.id) }, verifiers:{ true:()=>true, false:()=>false }, emit:(m)=>log.push('R:'+m) });
  assert.deepEqual(log.filter(x=>!x.startsWith('R:')), ['b','a','c']); // d not reached
  assert.equal(res.ok, false);
  assert.equal(res.failed, 'c');
  assert.equal(res.next_command, 'thiscode --check');
});

test('skips step when when-condition false; never hangs', () => {
  const log = [];
  const steps = [
    { id:'win', order:10, when:'os==win', action:'guide', reason:'W', safety:'none', verify:{type:'true'} },
    { id:'all', order:20, when:'always', action:'guide', reason:'A', safety:'none', verify:{type:'true'} },
  ];
  const res = runManifest(steps, { ctx:{ os:'linux' }, actions:{ guide:(s)=>log.push(s.id) }, verifiers:{ true:()=>true }, emit:()=>{} });
  assert.deepEqual(log, ['all']);
  assert.equal(res.ok, true);
});
