# hermes-perplexity-plugin

A [Hermes Agent](https://github.com/NousResearch/hermes-agent) web-search plugin
backed by the [Perplexity Search API](https://docs.perplexity.ai/docs/search/quickstart)
(`POST https://api.perplexity.ai/search`) — raw, ranked web results with no LLM
answer pass. Search-only; pair with Firecrawl/Tavily/Exa for `web_extract`.

Migrated from [bo17age/hermes-plugin-perplexity](https://github.com/bo17age/hermes-plugin-perplexity),
which used the legacy `/chat/completions` + `sonar-pro` answer flow.

## Install

Copy (or symlink) the plugin directory into your Hermes user plugins tree:

```bash
git clone https://github.com/WilliamGazeley/hermes-agent-perplexity-plugin.git
mkdir -p ~/.hermes/plugins/web
cp -r hermes-agent-perplexity-plugin/plugins/web/perplexity ~/.hermes/plugins/web/
```

Then set the backend and add your key to `~/.hermes/.env`:

```bash
hermes config set web.search_backend perplexity
echo 'PERPLEXITY_API_KEY=pplx-...' >> ~/.hermes/.env
```

Restart Hermes (new session) and `web_search` now routes through Perplexity.

## Optional tuning (env vars)

| Variable | Values | Effect |
|---|---|---|
| `PERPLEXITY_SEARCH_RECENCY` | `hour` `day` `week` `month` `year` | `search_recency_filter` |
| `PERPLEXITY_SEARCH_COUNTRY` | ISO 3166-1 alpha-2 (e.g. `US`, `HK`) | region-relevant results |
| `PERPLEXITY_SEARCH_CONTEXT_SIZE` | `low` `medium` `high` | snippet depth |
| `PERPLEXITY_SEARCH_MAX_TOKENS` | int | total snippet budget |
| `PERPLEXITY_SEARCH_MAX_TOKENS_PER_PAGE` | int | per-page snippet budget |

## Notes

- Hermes' `WebSearchProvider.search()` interface passes a single `query: str`
  per call, so the Search API's batch-query list form is not used — one query
  per request.
- Perplexity's Agent API (`/v1/responses`) rejects function tools named
  `web_search` / `search_files` (reserved names), which breaks Hermes as a
  *model* provider out of the box. This plugin only uses the Search API and is
  unaffected.

## Layout

```
plugins/web/perplexity/
├── plugin.yaml    # manifest (kind: backend, provides: perplexity)
├── __init__.py    # register(ctx) hook
└── provider.py    # PerplexitySearchWebProvider (WebSearchProvider ABC)
```
