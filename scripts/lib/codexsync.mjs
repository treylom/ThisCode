// scripts/lib/codexsync.mjs
// Node port of scripts/sync-skills-to-codex.sh (baseline bc37eec). One-way:
// ThisCode/skills/<km> → <codexSkillsDir>/<km>/. ThisCode is SoT; copies not edited.
import { cpSync, existsSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

export const KM_SKILLS = [
  'knowledge-manager', 'knowledge-manager-lite', 'knowledge-manager-plain',
  'knowledge-manager-at', 'knowledge-manager-bootstrap',
];

// compat parity with bash compat(): plain/lite=supported, full/bootstrap=degraded, at=unsupported
export function compat(skill) {
  if (skill === 'knowledge-manager-plain' || skill === 'knowledge-manager-lite') return 'supported';
  if (skill === 'knowledge-manager-at') return 'unsupported';
  return 'degraded';
}

export function planCodexSync(srcSkillsDir, destDir) {
  const plan = [];
  for (const skill of KM_SKILLS) {
    const from = join(srcSkillsDir, skill);
    if (existsSync(from)) plan.push({ skill, from, to: join(destDir, skill), compat: compat(skill) });
  }
  return plan;
}

export function applyCodexSync(srcSkillsDir, destDir) {
  const plan = planCodexSync(srcSkillsDir, destDir);
  if (plan.length === 0) return [];        // DA-review fix: no empty ~/.agents/skills dir on zero-plan
  mkdirSync(destDir, { recursive: true });
  const done = [];
  for (const { skill, from, to } of plan) {
    cpSync(from, to, { recursive: true });
    done.push(skill);
  }
  return done;
}
