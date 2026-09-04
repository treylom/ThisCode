// scripts/lib/codexsync.mjs
// Node port of scripts/sync-skills-to-codex.sh (baseline bc37eec). One-way:
// ThisCode/skills/<skill> → <codexSkillsDir>/<skill>/. ThisCode is SoT; copies not edited.
import { cpSync, existsSync, mkdirSync } from 'node:fs';
import { join } from 'node:path';

// 1.4.0: the knowledge/search skill family moved out of this repo, so nothing
// is on the Codex sync list any more. Add skill directory names here to resume
// syncing; keep this array and scripts/sync-skills-to-codex.sh in step.
export const KM_SKILLS = [];

// compat parity with bash compat(): anything not explicitly classified
export function compat(_skill) {
  return 'unknown';
}

export function planCodexSync(srcSkillsDir, destDir, skills = KM_SKILLS) {
  const plan = [];
  for (const skill of skills) {
    const from = join(srcSkillsDir, skill);
    if (existsSync(from)) plan.push({ skill, from, to: join(destDir, skill), compat: compat(skill) });
  }
  return plan;
}

export function applyCodexSync(srcSkillsDir, destDir, skills = KM_SKILLS) {
  const plan = planCodexSync(srcSkillsDir, destDir, skills);
  if (plan.length === 0) return [];        // DA-review fix: no empty ~/.agents/skills dir on zero-plan
  mkdirSync(destDir, { recursive: true });
  const done = [];
  for (const { skill, from, to } of plan) {
    cpSync(from, to, { recursive: true });
    done.push(skill);
  }
  return done;
}
