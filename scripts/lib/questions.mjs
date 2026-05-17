// scripts/lib/questions.mjs
// Canonical = spec §6.A. Each: {id, ask, choices, default (non-interactive), scope}
const hasCodex = a => a.harness === 'codex' || a.harness === 'both';

export const SCRIPT = [
  { id:'tone', ask:'설명 말투', choices:['plain','dev'], default:'plain', scope:()=>true },
  { id:'os_confirm', ask:'감지된 OS 맞나', choices:['confirm','manual'], default:'confirm', scope:()=>true },
  { id:'wsl_recommend', ask:'(Windows) WSL 먼저?', choices:['wsl_guide','native'], default:'native', scope:c=>c.os==='win' },
  { id:'harness', ask:'어떤 도구용', choices:['claude','codex','both'], default:'auto', scope:()=>true },
  { id:'codex_auth', ask:'Codex 로그인 되어 있나요?', choices:['detected','guide','later'], default:'detected', scope:c=>hasCodex(c.answers) },
  { id:'codex_skill_layer', ask:'ThisCodex skill 설치 위치', choices:['user','repo'], default:'user', scope:c=>hasCodex(c.answers) },
  { id:'codex_marketplace', ask:'.codex-plugin marketplace 안내?', choices:['yes','no'], default:'no', scope:c=>hasCodex(c.answers) },
  { id:'codex_config', ask:'~/.codex/config.toml 점검/패치?', choices:['check','patch','skip'], default:'check', scope:c=>hasCodex(c.answers) },
  { id:'vault', ask:'vault 경로', choices:['auto','manual'], default:'auto', scope:()=>true },
  { id:'bot_topology', ask:'봇 몇 개', choices:['single','multi_now','multi_planned'], default:'single', scope:()=>true },
  { id:'bot_detail', ask:'봇별 이름/WD/토큰', choices:['repeat'], default:null, scope:c=>c.answers.bot_topology==='multi_now' },
  { id:'daemon_guide', ask:'봇 자동실행 안내 볼래', choices:['yes','no'], default:'no', scope:()=>true },
  { id:'codex_runner', ask:'Codex runner 파일 만들까', choices:['launchd','systemd','tmux','guide'], default:'guide', scope:c=>hasCodex(c.answers)&&c.answers.daemon_guide==='yes' },
  { id:'codex_launch_compat', ask:'기존 launch.sh 처리', choices:['legacy','thiscodex_shell','node_runner'], default:'node_runner', scope:c=>hasCodex(c.answers)&&c.answers.daemon_guide==='yes' },
  { id:'codex_yolo', ask:'Codex bridge 권한 모드', choices:['safe','yolo_hint','sentinel_hint'], default:'safe', scope:c=>hasCodex(c.answers)&&c.answers.daemon_guide==='yes' },
  { id:'apply_confirm', ask:'지금 적용할까', choices:['apply','check_only'], default:'check_only', scope:()=>true },
];
export function isInScope(q, ctx) {
  return q.scope({ os: ctx.os, answers: ctx.answers || {} });
}
export function nextQuestion(ctx, completed) {
  for (const q of SCRIPT) {
    if (completed.includes(q.id)) continue;
    if (!isInScope(q, ctx)) continue;
    return q;
  }
  return null;
}
