/**
 * Which pending inbound a posted reply closes (✅ beside the receipt emoji).
 *
 * - Threaded reply: the thread root is the key — `${channel}:${thread_ts}`.
 * - Top-level reply in a DM (2026-09-23: DM replies are top-level again, a
 *   threaded DM post raises no notification): there is no root, so the reply
 *   closes the newest still-pending inbound of that DM.
 * - Top-level reply in a channel: closes nothing (a channel reply that is
 *   not threaded is a new topic, not an answer).
 */
export function pickInboundDoneKey(
  target: string,
  threadTs: string | undefined,
  isImTarget: boolean,
  newestPendingKeyByChannel: ReadonlyMap<string, string>,
): string | undefined {
  if (threadTs) return `${target}:${threadTs}`;
  if (isImTarget) return newestPendingKeyByChannel.get(target);
  return undefined;
}
