import test from 'node:test';
import assert from 'node:assert/strict';
import { parseChannelIds, ANY_MEMBER_CHANNEL } from '../dist/config.js';

test('a single id and a plain list parse in order', () => {
  assert.deepEqual(parseChannelIds('C1'), ['C1']);
  assert.deepEqual(parseChannelIds('C1, C2 ,C3,'), ['C1', 'C2', 'C3']);
});

test('the wildcard is kept as an entry, anywhere after the first', () => {
  assert.deepEqual(parseChannelIds('C1,*'), ['C1', ANY_MEMBER_CHANNEL]);
  assert.deepEqual(parseChannelIds('C1, * ,C2'), ['C1', ANY_MEMBER_CHANNEL, 'C2']);
});

test('the first entry must be a real channel id', () => {
  assert.throws(() => parseChannelIds('*'), /first entry must be a channel id/);
  assert.throws(() => parseChannelIds('*,C1'), /first entry must be a channel id/);
  assert.throws(() => parseChannelIds(' , '), /no channel ids/);
});
