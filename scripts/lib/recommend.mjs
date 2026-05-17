// scripts/lib/recommend.mjs
export function recommendPhases({ note_count = 0, python = false, obsidian_cli = false }) {
  const current = ['phase-0-obsidian', 'phase-1-ripgrep'];
  const recommended = [];
  const later = [];

  if (obsidian_cli) current.push('phase-2-cli');
  else recommended.push('phase-2-cli-install');

  if (note_count >= 100) recommended.push('phase-3-mcp');
  else later.push('phase-3-mcp');

  if (!python) later.push('phase-4-graphrag-no-python');
  else if (note_count >= 1000) recommended.push('phase-4-graphrag-strong');
  else if (note_count >= 500) recommended.push('phase-4-graphrag');
  else later.push('phase-4-graphrag-optional');

  if (note_count >= 2000) recommended.push('phase-5-mode-r-preflight');
  if (note_count >= 3000) later.push('phase-6-dashboard');
  later.push('phase-7-hybrid-search');

  return { current, recommended, later };
}
