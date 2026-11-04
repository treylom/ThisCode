#!/usr/bin/env node
// Print which browser ThisCode should drive: ego lite → Aside → fallback (one JSON line).
// Usage: node scripts/browser-detect.mjs [--prefer ego|aside|auto] [--no-probe] [--get provider|bin|reason]
// Exit 0 = a decision was printed · 2 = bad arguments.
import { detectBrowser } from './lib/browser-detect.mjs';

const argv = process.argv.slice(2);
let prefer = process.env.THISCODE_BROWSER || 'auto';
let doProbe = true;
let get = null;
for (let i = 0; i < argv.length; i++) {
  const a = argv[i];
  if (a === '--prefer') prefer = argv[++i] ?? '';
  else if (a === '--no-probe') doProbe = false;
  else if (a === '--get') get = argv[++i] ?? '';
  else { console.error(`unknown argument: ${a}`); process.exit(2); }
}
if (get !== null && !['provider', 'bin', 'reason'].includes(get)) { console.error('--get must be provider|bin|reason'); process.exit(2); }

const res = detectBrowser({ prefer, doProbe });
console.log(get ? (res[get] ?? '') : JSON.stringify(res));
