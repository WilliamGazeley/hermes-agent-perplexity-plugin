"""Perplexity ask_perplexity tool plugin — user-installed."""

from __future__ import annotations

from .tool import ask_perplexity_tool, ASK_PERPLEXITY_SCHEMA, check_perplexity_key


def register(ctx) -> None:
    """Register the ask_perplexity tool with the plugin context."""
    ctx.register_tool(
        name="ask_perplexity",
        toolset="web",
        schema=ASK_PERPLEXITY_SCHEMA,
        handler=lambda args, **kw: ask_perplexity_tool(
            query=args.get("query", ""),
            preset=args.get("preset", "pro-search"),
            max_steps=args.get("max_steps"),
            model=args.get("model"),
        ),
        check_fn=check_perplexity_key,
        requires_env=["PERPLEXITY_API_KEY"],
        description="Perplexity Agent API multi-step research with web search, URL fetch, people and finance search",
        emoji="🧭",
    )
