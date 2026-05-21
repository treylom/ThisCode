---
name: prompt
description: Use when writing, generating, refining, reviewing, or being asked for ANY prompt aimed at an LLM (Claude / GPT / Gemini / Codex), or when building GPTs / Gems system instructions, or when a task is fact-check / research / image-generation prompting. Produces structured, framework-grounded prompts instead of ad-hoc ones. Invoke this BEFORE handing any hand-written prompt to a model.
---

# prompt — structured prompt generation

Vendored, unmodified-in-substance copy of the public **`prompt-engineering-skills`**
package (MIT). It turns a rough intent into a structured, framework-grounded
prompt rather than an ad-hoc one, and routes by task type.

## When to use (mandatory-invocation)

Invoke this skill — do not free-hand a prompt — whenever the work is:

- "write / make / improve / review a prompt" for any model
- building **GPTs** or **Gems** system instructions
- fact-check / research prompting (IFCN-grounded base templates required)
- image-generation prompting (5-stage framework)
- any request whose deliverable is itself a prompt

A bot whose config mandates `/prompt` (see the repo's
`docs/SETUP-CONFIG-GUIDE.md` §"force-invoke") MUST route here first.

## How it routes (progressive disclosure)

This `SKILL.md` is the router. Load the heavy reference only for the matched
task — do not read all of it up front:

See `references/` for detailed procedures only when the matched prompt task asks for them.

| Task | Load |
|---|---|
| Generate / refine a prompt (main workflow) | [`references/prompt-generator.md`](references/prompt-generator.md) |
| Framework / technique deep reference | [`references/prompt-engineering-guide.md`](references/prompt-engineering-guide.md) |
| Worked examples (Claude / GPT / image) | [`references/examples/`](references/examples/) |
| Build a GPTs instruction | [`references/instructions/GPTs-Prompt-Generator.md`](references/instructions/GPTs-Prompt-Generator.md) |
| Build a Gems instruction | [`references/instructions/Gems-Prompt-Generator.md`](references/instructions/Gems-Prompt-Generator.md) |

Procedure:

1. Classify the request (generate / fact-check / research / image / GPTs / Gems).
2. Read **only** the matched reference above.
3. For fact-check / research, the engineering guide's IFCN base template is
   mandatory — do not emit a generic XML prompt.
4. Produce the structured prompt; show the user the final prompt explicitly.

## Attribution

- Upstream: `github.com/treylom/prompt-engineering-skills` (public, MIT) —
  see [`LICENSE`](LICENSE). Context-Engineering basis: Muratcan Koylan,
  *Agent-Skills-for-Context-Engineering*.
- Vendored here so the bot ships self-contained. The upstream maintainer's
  personal deploy script (`commands/prompt-sync.md`) is intentionally
  **excluded** (machine-specific, not relevant to distributees).
