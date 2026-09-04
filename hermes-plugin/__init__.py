"""thiscode — Hermes plugin entry point.

Registers the search / ingest tool surface with Hermes Agent. The programmatic
dispatchers those handlers would shell out to are not bundled in this repo, so
both handlers return a structured "deferred" payload (docs/HERMES-STATUS.md).
"""

from . import schemas, tools


def register(ctx):
    ctx.register_tool(
        name="claude_discode_search",
        toolset="research",
        schema=schemas.SEARCH_SCHEMA,
        handler=tools.handle_search,
    )
    ctx.register_tool(
        name="claude_discode_ingest",
        toolset="knowledge",
        schema=schemas.INGEST_SCHEMA,
        handler=tools.handle_ingest,
    )
    ctx.register_hook("on_session_start", tools.session_start_drift_check)
    ctx.register_command("/search", tools.cmd_search)
    ctx.register_command("/thiscode-km", tools.cmd_km)
