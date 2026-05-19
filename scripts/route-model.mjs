// scripts/route-model.mjs — LLM model routing heuristic (claude/codex)
// Usage: node scripts/route-model.mjs --query "<text>" [--model haiku|sonnet|opus]

const args = process.argv.slice(2);
let query = "";
let override = null;

for (let i = 0; i < args.length; i++) {
  if (args[i] === "--query") query = args[i + 1] || "";
  if (args[i] === "--model") override = args[i + 1] || null;
}

const PROVIDER = process.env.CLAUDE_DISCODE_LLM_PROVIDER || "claude";

const MAP = {
  claude: { simple: "haiku", medium: "sonnet", complex: "opus" },
  codex: { simple: "gpt-5.5", medium: "gpt-5.5-codex", complex: "gpt-5.5-codex-spark" },
};

function classify(q) {
  if (!q) return "medium";
  const len = q.length;
  const lower = q.toLowerCase();

  const complexKw = ["왜", "어떻게", "비교", "추론", "예측", "분석", "상관관계", "why", "how", "compare", "infer", "predict"];
  const mediumKw = ["요약", "정리", "분류", "list", "summary", "categorize"];

  if (len > 100 || complexKw.some(k => lower.includes(k.toLowerCase()))) return "complex";
  if (len > 30 || mediumKw.some(k => lower.includes(k.toLowerCase()))) return "medium";
  return "simple";
}

if (override) {
  // override 자체가 claude 모델명 → provider 변환
  if (PROVIDER === "codex") {
    const reverse = { haiku: "gpt-5.5", sonnet: "gpt-5.5-codex", opus: "gpt-5.5-codex-spark" };
    console.log(reverse[override] || override);
  } else {
    console.log(override);
  }
} else {
  const tier = classify(query);
  console.log(MAP[PROVIDER][tier]);
}
