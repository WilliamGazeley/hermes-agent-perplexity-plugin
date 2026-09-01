"""Perplexity Search web provider plugin — user-installed."""

from __future__ import annotations

from .provider import PerplexitySearchWebProvider


def register(ctx) -> None:
    """Register the Perplexity provider with the plugin context."""
    ctx.register_web_search_provider(PerplexitySearchWebProvider())
