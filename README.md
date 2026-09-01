# hermes-agent-perplexity-plugin

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) tool plugin that
exposes an `ask_perplexity` tool backed by the [Perplexity Agent API](https://docs.perplexity.ai/docs/agent-api/quickstart)
(`POST /v1/responses`). One call runs Perplexity's agentic loop — `web_search`,
`fetch_url`, `people_search`, `finance_search` — and returns the synthesized
answer with citations.

> This replaces the earlier Perplexity Search API (`/search`) web-search
> backend that this repo previously published; use the built-in `web_search`
> (or any search backend) alongside this tool.

## When to use it

- **`ask_perplexity`** — one-shot questions needing multi-hop research
  ("research this person/company", "what's the consensus on X"). Perplexity
  fetches and reads the pages; you get the conclusion.
- **`web_search`** (Hermes built-in) — raw ranked results when the agent
  should reason over sources itself.

## Install

```bash
hermes plugins install WilliamGazeley/hermes-agent-perplexity-plugin --enable
echo 'PERPLEXITY_API_KEY=pplx-...' >> ~/.hermes/.env
```

Restart Hermes (new CLI session, or `hermes gateway restart`) and the
`ask_perplexity` tool appears in the `web` toolset.

## Tool parameters

| Param | Type | Notes |
|---|---|---|
| `query` | string, required | The research question |
| `preset` | string | `pro-search` (default, fast) or `deep-research` (slower, deeper). Verified against the live API — other values fall back to `pro-search` |
| `max_steps` | int (1–20) | Agent tool-loop step cap |
| `model` | string | Optional Agent API model override |

The call is non-streaming (`stream: false`) and can take 1–3 minutes for
`deep-research`-grade queries — the tool timeout is set accordingly.

## Layout

```
<repo root>/
├── plugin.yaml    # manifest (provides_tools: ask_perplexity)
├── __init__.py    # register(ctx) hook
└── tool.py        # ask_perplexity_tool implementation
```
