# Apollo 13 Agent Demo 🚀

**English | [简体中文](README.zh-CN.md)**

**One Python file that shows you the entire skeleton of an AI agent.**

April 1970. The engineers in Houston had all the knowledge in the world, but couldn't lay a finger on the spacecraft. The astronauts had hands, but didn't know what to build. Between them: one radio loop.

That is the basic move behind many LLM agents today:

| Apollo 13 | Agent system | Where in the code |
|---|---|---|
| Houston (brain, no hands) | LLM | `houston_llm()` / `houston_offline()` |
| The cabin (the hands) | runtime | `execute()` |
| Radio calls + readback | function calling + validation | `TOOLS` + rejection logic in `execute()` |
| Step-by-step guidance | the loop (heartbeat) | the `for` loop in `main()` |
| Mission log | context window (the workbench) | `messages` |
| Status-board notes | compaction | `compact()` |
| Hard acceptance criteria | anti "fake done" | the refusal logic in `report_done` |

## Quick start

**No API key needed — watch the mechanics first (recommended):**

```bash
python3 houston.py --offline
```

You'll watch a complete rescue: Houston directs the crew step by step to collect materials and assemble the adapter. Two classic failures are deliberately scripted in:

- **Turn 4** — Houston asks for *a sock*. The cabin rejects it because the demo's onboard inventory **intentionally excludes socks** — this is the **tool hallucination** case: the model calls for something that doesn't exist, and the runtime sends it back. (Historical note: in the real mission transcript Kerwin *did* mention "wetwipe / sock / crumpled tape" as candidate bypass-hole plugs, and the crew ended up stuffing a towel. The core mailbox adapter never relied on a sock.)
- **Turn 7** — Houston reports the job done before the adapter is even assembled. Ground refuses sign-off against hard acceptance criteria (**fake done**)

**Let a real LLM play Houston (any OpenAI-compatible API):**

```bash
pip install openai

export API_KEY=your_key
export BASE_URL=https://api.deepseek.com   # or any compatible endpoint
export MODEL=deepseek-chat                 # or qwen-plus / gpt-4o-mini etc.

python3 houston.py
```

A real model takes a different route every run — sometimes it hallucinates a tool, sometimes it declares victory early. Watch the cabin send it back.

## What this demo is trying to say

1. **The model has no hands.** It only ever outputs text. Everything that actually touches the world happens in `execute()`. The model never pressed a single button.
2. **An agent is not a new species — it's a loop.** The main loop is under thirty lines: the model speaks; if it's a call, validate & execute & paste the result back; stop at the acceptance criteria or when you hit a rope (turn cap / red line).
3. **Hands need rules more than brains do.** Validation, rejection, refusal, caps — the "don't trust the model" parts are the real body of agent engineering.

The real Apollo 13 "mailbox" was built from the command module's square LiOH canisters, plastic bags, plastic-coated cue cards, suit hoses, and grey duct tape. CAPCOM Joe Kerwin read the build procedure up to the crew over about an hour. See the [Apollo Journals transcript](https://apollojournals.org/alsj//a13/a13_LIOH_Adapter.html).

This repo is the companion code for a Chinese-language article on how agents work (《大模型没有手》, "The Model Has No Hands").

## License

MIT
