"""Perplexity Agent API ask_perplexity tool.

Exposes Hermes' ``ask_perplexity`` tool, backed by Perplexity's Agent API
(``POST /v1/responses``). One call runs Perplexity's agentic loop — web
search, URL fetch, people search, finance search — and returns the final
synthesized answer with citations. Use it for one-shot questions that need
multi-hop research ("what's the consensus on X", "research this person/org")
rather than as a raw search backend.

Non-streaming (``stream: false``) for reliable single-shot parsing.

Auth env var::

    PERPLEXITY_API_KEY=...
"""

from __future__ import annotations

import json
import logging
import os
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

_PERPLEXITY_RESPONSES_ENDPOINT = "https://api.perplexity.ai/v1/responses"

# Built-in Perplexity Agent API tools, enabled by type. Kept as defaults so
# one call can search, read pages, and pull people/finance data. These are
# built-in tool *types* — not custom function names — so Perplexity's
# reserved-name rejection does not apply.
_DEFAULT_BUILTIN_TOOLS = [
    {"type": "web_search"},
    {"type": "fetch_url"},
    {"type": "people_search"},
    {"type": "finance_search"},
]

# Verified against the live API: only these two preset values are accepted.
# Anything else returns HTTP 400 "Invalid model '<preset>'".
_PRESETS = {"pro-search", "deep-research"}

ASK_PERPLEXITY_SCHEMA = {
    "name": "ask_perplexity",
    "description": (
        "Run a multi-step deep research query via the Perplexity Agent API. "
        "Perplexity's agent performs web searches, fetches and reads pages, "
        "and can query people/finance data, then returns a synthesized answer "
        "with citations. Use for one-shot research questions that need "
        "several hops of evidence gathering; prefer web_search when you want "
        "raw ranked results to reason over yourself."
    ),
    "parameters": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The research question. Be specific — the agent works autonomously from this prompt.",
            },
            "preset": {
                "type": "string",
                "enum": sorted(_PRESETS),
                "description": "Perplexity preset controlling effort/quality. Default: pro-search.",
            },
            "max_steps": {
                "type": "integer",
                "description": "Maximum agent tool-loop steps (1-20). Default: provider default.",
                "minimum": 1,
                "maximum": 20,
            },
            "model": {
                "type": "string",
                "description": "Optional Agent API model override (e.g. perplexity/deepseek-v4-pro-0813).",
            },
        },
        "required": ["query"],
    },
}


def check_perplexity_key() -> bool:
    """Availability check for the tool registry (no network calls)."""
    return bool(os.environ.get("PERPLEXITY_API_KEY"))


def _extract_answer_text(data: Dict[str, Any]) -> str:
    """Pull the assistant answer text out of a Responses API payload."""
    for item in data.get("output", []):
        if item.get("type") == "message" and item.get("role") == "assistant":
            parts = []
            for content in item.get("content", []):
                if content.get("type") in ("output_text", "text"):
                    parts.append(content.get("text", ""))
            if parts:
                return "\n".join(parts)
    # Fallbacks for alternate response shapes.
    if data.get("output_text"):
        return str(data["output_text"])
    if data.get("answer"):
        return str(data["answer"])
    return ""


def _extract_citations(data: Dict[str, Any]) -> list:
    """Collect citation URLs from the response, deduplicated, order kept."""
    citations: list = []
    seen = set()
    for raw in (
        data.get("citations")
        or [c.get("url") for c in data.get("search_results", []) if c.get("url")]
        or []
    ):
        url = str(raw)
        if url and url not in seen:
            seen.add(url)
            citations.append(url)
    return citations


def ask_perplexity_tool(
    query: str,
    preset: str = "pro-search",
    max_steps: Optional[int] = None,
    model: Optional[str] = None,
) -> str:
    """Run a Perplexity Agent API research query and return the answer.

    Returns a JSON string:
        {"success": true, "data": {"answer": str, "citations": [url, ...],
                                   "preset": str, "model": str}}
    or {"success": false, "error": str} on failure.
    """
    import httpx

    if not query.strip():
        return json.dumps({"success": False, "error": "query is required"})

    api_key = os.environ.get("PERPLEXITY_API_KEY")
    if not api_key:
        return json.dumps({"success": False, "error": "PERPLEXITY_API_KEY is not set"})

    payload: Dict[str, Any] = {
        "input": query,
        "stream": False,
        "tools": _DEFAULT_BUILTIN_TOOLS,
    }
    # Only send a preset the API verifiably accepts; unknown values fall back
    # to pro-search (a preset/model is REQUIRED — omitting it 400s).
    payload["preset"] = preset if preset in _PRESETS else "pro-search"
    if model:
        payload["model"] = model
    if max_steps:
        payload["max_steps"] = max(1, min(int(max_steps), 20))

    try:
        resp = httpx.post(
            _PERPLEXITY_RESPONSES_ENDPOINT,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=300,
        )
        resp.raise_for_status()
    except httpx.HTTPStatusError as exc:
        logger.warning("Perplexity deep research HTTP error: %s", exc)
        return json.dumps({
            "success": False,
            "error": f"Perplexity Agent API returned HTTP {exc.response.status_code}: "
            f"{exc.response.text[:500]}",
        })
    except httpx.RequestError as exc:
        logger.warning("Perplexity deep research request error: %s", exc)
        return json.dumps({
            "success": False,
            "error": f"Could not reach Perplexity Agent API: {exc}",
        })

    try:
        data = resp.json()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Perplexity deep research parse error: %s", exc)
        return json.dumps({
            "success": False,
            "error": "Could not parse Perplexity Agent API response as JSON",
        })

    answer = _extract_answer_text(data)
    if not answer:
        # Incomplete/failed run — surface whatever the API said.
        status = data.get("status") or data.get("error") or "empty answer"
        return json.dumps({
            "success": False,
            "error": f"Agent API returned no answer text (status: {status})",
        })

    citations = _extract_citations(data)
    used_model = data.get("model") or payload.get("model") or "agent-api-default"

    logger.info(
        "Perplexity deep research: %d chars, %d citations (preset=%s)",
        len(answer), len(citations), payload["preset"],
    )

    return json.dumps({
        "success": True,
        "data": {
            "answer": answer,
            "citations": citations,
            "preset": payload["preset"],
            "model": used_model,
        },
    })
