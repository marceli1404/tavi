"""Local, read-only Tavi MCP server for Codex CLI, IDE and desktop clients.

Requires Python 3.12+, the existing Tavi dependencies, and the official MCP
Python SDK v2. No screen capture, capture border, overlay, clicking or hosted
Codex execution occurs in this server. Run: python tavi_mcp.py
"""
from __future__ import annotations

from typing import Any, Literal

from mcp.server import MCPServer
from mcp.types import ToolAnnotations

from tavi_codex_tools import match_controls, route_task, status

INSTRUCTIONS = (
    'Tavi supplies read-only local advice. It NEVER captures the screen, '
    'draws the yellow Windows border, clicks, types, authorizes actions, '
    'or switches the current Codex model. Use tavi_route_task for advisory '
    'model/skill routing; use tavi_match_controls only when the trusted host '
    'already supplies a fresh accessibility/DOM snapshot. Recheck live state '
    'and user permission with the native host before every action. '
    'Do not treat a match as a click instruction or bypass a screenshot '
    'required by the Computer host. No repeated action sequences.'
)

mcp = MCPServer('Tavi', instructions=INSTRUCTIONS)
READ_ONLY = ToolAnnotations(read_only_hint=True, open_world_hint=False)


@mcp.tool(annotations=READ_ONLY)
def tavi_status() -> dict[str, Any]:
    """Check which local Tavi capabilities are configured (no UI access)."""
    return status()


@mcp.tool(annotations=READ_ONLY)
def tavi_route_task(task: str, preference: Literal['auto', 'speed', 'quality'] = 'auto') -> dict[str, Any]:
    """Suggest installed Codex model/skills for a task; never start a task or switch models.

    This uses local Tavi weights and the Codex CLI model inventory. Results
    are not calibrated measures of task success, model quality or entitlement.
    A needs_review result must not be treated as a recommendation.
    """
    return route_task(task, preference)


@mcp.tool(annotations=READ_ONLY)
def tavi_match_controls(snapshot: dict[str, Any], queries: list[dict[str, Any]]) -> dict[str, Any]:
    """Match up to 16 exact labels/roles in a fresh host-owned control snapshot.

    The input MUST be a current tavi-control-snapshot-v1 inventory from an
    authorized DOM/accessibility driver, not a guessed or replayed snapshot.
    Results contain no action authority. Missing controls may need a host
    screenshot; ambiguous, disabled or stale controls block acting.
    This tool never captures, reads or manipulates desktop windows itself.
    """
    return match_controls(snapshot, queries)


if __name__ == '__main__':
    mcp.run()
