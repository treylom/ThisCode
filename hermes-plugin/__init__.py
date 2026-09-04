"""thiscode — Hermes plugin entry point.

The 1.4.0 runtime surface is deliberately limited to the session-start drift
check. The manifest continues to describe the broader Claude Code plugin
surface; Hermes-only registrations not implemented here are documented as
deferred in docs/HERMES-STATUS.md.
"""

from . import tools


def register(ctx):
    ctx.register_hook("on_session_start", tools.session_start_drift_check)
