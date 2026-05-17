// scripts/lib/i18n.mjs
// Spec: plain = 쉬운 한국어(전문어 첫 등장 시 풀이) / dev = 압축. 기본 plain.
export const MESSAGES = {
  tone_ask: {
    plain: '설명을 어떻게 받으실래요?  [1] 쉬운 설명(권장)  [2] 개발자용 설명',
    dev: 'Output register?  [1] plain  [2] dev',
  },
  wsl_recommend_reason: {
    plain: 'Windows 에서는 WSL(윈도우 안의 리눅스) 설치를 먼저 권장해요 — 봇을 계속 켜두는 실행기가 WSL 에서 더 안정적이라서요. 그냥 진행해도 스킬 설치 자체는 됩니다.',
    dev: 'Windows native: WSL 권장(persistent runner 안정성). skill 설치는 native 도 가능.',
  },
  placement_explain: {
    plain: '설치 성공이란 = 도구가 스킬을 찾는 폴더에 파일이 들어가는 것이에요. (npm 설치 위치 자체가 아님)',
    dev: '설치 성공 판정 = harness skill-scan path 노출(npm 위치 ❌).',
  },
  topology_benefit: {
    plain: '봇을 여러 개 두면 역할을 나눠 동시에 일하고 서로 회의도 할 수 있어요. 한 개만 둬도 그 봇이 필요할 때 내부적으로 작업을 나눠 처리합니다.',
    dev: '멀티봇 = 도메인 분담·meeting 협업·정체성 분리. 단일도 내부 subagent 가능. 직교.',
  },
  check_only_notice: {
    plain: '지금은 점검만 했어요 (아무 것도 바꾸지 않음). 실제로 적용하려면 --apply 를 붙여 다시 실행하세요.',
    dev: '--check: 무변경 진단 완료. 적용 = --apply.',
  },
  apply_backup_notice: {
    plain: '바꾸기 전에 원본을 백업해 둘게요.',
    dev: 'pre-write backup 수행.',
  },
  apply_needs_consent: {
    plain: '비대화형 환경에서는 --apply 에 동의가 필요해요. 먼저 미리보기:  node bin/thiscode.mjs --check\n적용:  node bin/thiscode.mjs --apply --yes',
    dev: 'non-TTY --apply requires explicit consent. Preview: --check. Apply: --apply --yes',
  },
};

export function msg(key, register = 'plain') {
  const entry = MESSAGES[key];
  if (!entry) throw new Error(`i18n: unknown message key "${key}"`);
  return entry[register] ?? entry.plain;
}
