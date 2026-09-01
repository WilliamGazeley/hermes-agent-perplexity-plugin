"""Perplexity Search API — plugin form.

Subclasses :class:`agent.web_search_provider.WebSearchProvider` (the
plugin-facing ABC). Uses Perplexity's dedicated ``/search`` endpoint, which
returns raw ranked web results (no LLM answer, no chat completions).

Migrated from the bo17age/hermes-plugin-perplexity ``provider.py``, which
called ``/chat/completions`` with the ``sonar-pro`` model — that endpoint
family is superseded by the Search API.

Config keys this provider responds to::

    web:
      search_backend: "perplexity"     # explicit per-capability
      backend: "perplexity"            # shared fallback

Auth env var::

    PERPLEXITY_API_KEY=...     # https://docs.perplexity.ai/docs/getting-started

Search params (env-configurable, sensible defaults):
    PERPLEXITY_SEARCH_CONTEXT_SIZE   low | medium | high   (default: medium)
    PERPLEXITY_SEARCH_COUNTRY        ISO 3166-1 alpha-2    (default: unset)
    PERPLEXITY_SEARCH_MAX_TOKENS     int snippet budget    (default: unset)
    PERPLEXITY_SEARCH_MAX_TOKENS_PER_PAGE  int             (default: unset)

Note: the WebSearchProvider ABC passes a single ``query: str`` per call, so
the Search API's batch-query list form is not used.
"""

from __future__ import annotations

import logging
import os
from typing import Any, Dict, List, Optional

from agent.web_search_provider import WebSearchProvider

logger = logging.getLogger(__name__)

_PERPLEXITY_SEARCH_ENDPOINT = "https://api.perplexity.ai/search"

# ``max_results`` accepts 1-20 per the Search API docs.
_MAX_RESULTS_CAP = 20

_RECENCY_VALUES = {"hour", "day", "week", "month", "year"}


def _env_int(name: str) -> Optional[int]:
    """Parse an optional positive int from an env var, None if unset/invalid."""
    raw = os.environ.get(name)
    if not raw:
        return None
    try:
        value = int(raw)
    except ValueError:
        logger.warning("Ignoring non-integer %s=%r", name, raw)
        return None
    return value if value > 0 else None


class PerplexitySearchWebProvider(WebSearchProvider):
    """Search-only Perplexity provider using the Search API ``/search`` endpoint.

    No content-extraction capability — pair with Firecrawl/Tavily/Exa for
    ``web_extract``.
    """

    @property
    def name(self) -> str:
        return "perplexity"

    @property
    def display_name(self) -> str:
        return "Perplexity Search"

    def is_available(self) -> bool:
        """Return True when ``PERPLEXITY_API_KEY`` is set to a non-empty value."""
        from agent.web_search_provider import get_provider_env

        return bool(get_provider_env("PERPLEXITY_API_KEY"))

    def supports_search(self) -> bool:
        return True

    def supports_extract(self) -> bool:
        return False

    def _build_payload(self, query: str, limit: int) -> Dict[str, Any]:
        """Build the /search request body for one query."""
        payload: Dict[str, Any] = {
            "query": query,
            "max_results": max(1, min(int(limit), _MAX_RESULTS_CAP)),
        }

        context_size = os.environ.get("PERPLEXITY_SEARCH_CONTEXT_SIZE")
        if context_size:
            payload["search_context_size"] = context_size

        country = os.environ.get("PERPLEXITY_SEARCH_COUNTRY")
        if country:
            payload["country"] = country

        recency = os.environ.get("PERPLEXITY_SEARCH_RECENCY")
        if recency and recency.lower() in _RECENCY_VALUES:
            payload["search_recency_filter"] = recency.lower()

        max_tokens = _env_int("PERPLEXITY_SEARCH_MAX_TOKENS")
        if max_tokens:
            payload["max_tokens"] = max_tokens

        max_tokens_per_page = _env_int("PERPLEXITY_SEARCH_MAX_TOKENS_PER_PAGE")
        if max_tokens_per_page:
            payload["max_tokens_per_page"] = max_tokens_per_page

        return payload

    def search(self, query: str, limit: int = 5) -> Dict[str, Any]:
        """Execute a search against the Perplexity Search API.

        Returns ``{"success": True, "data": {"web": [{"title", "url", "description", "position"}]}}``
        on success, or ``{"success": False, "error": str}`` on failure.
        """
        import httpx

        from agent.web_search_provider import get_provider_env

        api_key = get_provider_env("PERPLEXITY_API_KEY")
        if not api_key:
            return {"success": False, "error": "PERPLEXITY_API_KEY is not set"}

        try:
            resp = httpx.post(
                _PERPLEXITY_SEARCH_ENDPOINT,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json=self._build_payload(query, limit),
                timeout=30,
            )
            resp.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.warning("Perplexity Search HTTP error: %s", exc)
            return {
                "success": False,
                "error": f"Perplexity Search returned HTTP {exc.response.status_code}: "
                f"{exc.response.text[:500]}",
            }
        except httpx.RequestError as exc:
            logger.warning("Perplexity Search request error: %s", exc)
            return {
                "success": False,
                "error": f"Could not reach Perplexity Search: {exc}",
            }

        try:
            data = resp.json()
        except Exception as exc:  # noqa: BLE001
            logger.warning("Perplexity Search response parse error: %s", exc)
            return {
                "success": False,
                "error": "Could not parse Perplexity Search response as JSON",
            }

        raw_results: List[Dict[str, Any]] = data.get("results") or []
        truncated = raw_results[:limit]

        web_results = [
            {
                "title": str(r.get("title", "")),
                "url": str(r.get("url", "")),
                "description": str(r.get("snippet", "")),
                "position": i + 1,
                "date": str(r["date"]) if r.get("date") else "",
            }
            for i, r in enumerate(truncated)
        ]

        logger.info(
            "Perplexity Search '%s': %d results (from %d raw, limit %d)",
            query,
            len(web_results),
            len(raw_results),
            limit,
        )

        return {"success": True, "data": {"web": web_results}}

    def get_setup_schema(self) -> Dict[str, Any]:
        return {
            "name": "Perplexity Search",
            "badge": "search-api",
            "tag": "Search API /search endpoint — raw ranked results, search only.",
            "env_vars": [
                {
                    "key": "PERPLEXITY_API_KEY",
                    "prompt": "Perplexity API key",
                    "url": "https://docs.perplexity.ai/docs/getting-started",
                },
            ],
        }
