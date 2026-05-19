const CADENCE_TO_SECONDS = {
  per_task: 0,
  '1m': 60,
  '3m': 180,
  '5m': 300,
  off: 0,
  custom: 0,
};

export function normalizeProgressCadence(value) {
  return Object.hasOwn(CADENCE_TO_SECONDS, value) ? value : 'per_task';
}

export function progressEnv({ cadence = 'per_task', prefix = 'THISCODE' } = {}) {
  const progress_report_cadence = normalizeProgressCadence(cadence);
  const heartbeat_interval_sec = CADENCE_TO_SECONDS[progress_report_cadence];
  return {
    [`${prefix}_PROGRESS_CADENCE`]: progress_report_cadence,
    [`${prefix}_HEARTBEAT_SEC`]: String(heartbeat_interval_sec),
  };
}
