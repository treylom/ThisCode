// scripts/lib/manifest.mjs — declarative ordered install manifest loader (zero-dep, JSON).
// Schema/contract is LOCKED identical to ThisCodex scripts/lib/manifest.mjs (spec §1 shared engine).
import { readFileSync } from 'node:fs';
import { fileURLToPath } from 'node:url';
import { join, dirname } from 'node:path';

// D1: on_fail.next_command REQUIRED on every step (matches ThisCodex strict validator; spec §3.2 "failed step MUST NOT hang").
const REQUIRED = ['id', 'order', 'when', 'action', 'reason', 'safety', 'verify', 'on_fail'];
const ACTIONS = new Set(['detect', 'prompt', 'check', 'apply', 'generate', 'guide']);

export function validateStep(s) {
  if (!s || typeof s !== 'object') return false;
  for (const f of REQUIRED) if (!(f in s)) return false;
  if (typeof s.order !== 'number') return false;
  if (!ACTIONS.has(s.action)) return false;
  if (!s.verify || !s.verify.type) return false;
  if (!s.on_fail || !s.on_fail.next_command) return false;
  return true;
}

export function loadManifest(path) {
  const p = path || join(dirname(fileURLToPath(import.meta.url)), '..', '..', 'install', 'thiscode.install.json');
  const doc = JSON.parse(readFileSync(p, 'utf8'));
  const steps = (doc.steps || []).slice().sort((a, b) => a.order - b.order);
  return steps;
}
