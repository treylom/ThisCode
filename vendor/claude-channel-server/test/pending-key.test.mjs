import test from 'node:test';
import assert from 'node:assert/strict';
import { pickInboundDoneKey } from '../dist/pending-key.js';

const newest = new Map([['D1', 'D1:100.2'], ['C1', 'C1:50.1']]);

test('threaded reply closes the thread root, DM or channel', () => {
  assert.equal(pickInboundDoneKey('D1', '100.1', true, newest), 'D1:100.1');
  assert.equal(pickInboundDoneKey('C1', '50.1', false, newest), 'C1:50.1');
});

test('top-level DM reply closes the newest pending inbound of that DM', () => {
  assert.equal(pickInboundDoneKey('D1', undefined, true, newest), 'D1:100.2');
});

test('top-level DM reply with nothing pending closes nothing', () => {
  assert.equal(pickInboundDoneKey('D9', undefined, true, newest), undefined);
});

test('top-level channel reply closes nothing', () => {
  assert.equal(pickInboundDoneKey('C1', undefined, false, newest), undefined);
});
