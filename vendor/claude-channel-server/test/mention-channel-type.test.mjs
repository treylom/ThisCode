import test from 'node:test';
import assert from 'node:assert/strict';
import { mentionChannelType } from '../dist/config.js';

// Mirrors the wildcard branch of isListenedChannel (server.ts): an unlisted
// channel passes only when its type is 'channel' or 'group'.
const wildcardAccepts = (channelType) => channelType === 'channel' || channelType === 'group';

test('an app_mention without channel_type is treated as a channel', () => {
  assert.equal(mentionChannelType(undefined), 'channel');
  assert.equal(wildcardAccepts(mentionChannelType(undefined)), true);
  // Without the tag the wildcard gate would drop it — the regression this guards.
  assert.equal(wildcardAccepts(undefined), false);
});

test('a channel_type Slack did send is kept as is', () => {
  assert.equal(mentionChannelType('group'), 'group');
  assert.equal(mentionChannelType('channel'), 'channel');
  assert.equal(mentionChannelType('im'), 'im');
});
