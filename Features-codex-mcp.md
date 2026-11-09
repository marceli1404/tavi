# Tavi as a local Codex MCP server (experimental)

This exposes Tavi's existing **advisory routing and exact-control matching** as discoverable tools to Codex CLI, Codex IDE and compatible desktop clients. It is not an overlay, screen recorder, auto-clicker or patch to Codex Computer Use. The persistent Windows yellow capture border is tracked separately in [Codex issue #57101](https://github.com/openai/codex/issues/57101); Tavi does not open a Windows Graphics Capture session.

## Set up on the local machine

1. Check out this feature branch (until merged) from the Tavi repository. From its root, run:

   ```powershell
   py -m venv .venv
   .\.venv\Scripts\python.exe -m pip install -r requirements.txt -r requirements-mcp.txt
   Copy-Item tavi.config.example.json tavi.config.json  # only if not already configured
   .\.venv\Scripts\python.exe -m unittest -q test_tavi_codex_tools
   ```

2. Register Tavi as a **STDIO** MCP server using the absolute path to your virtualenv Python and Tavi checkout. Example where Tavi is in `C:\code\tavi`:

   ```powershell
   codex mcp add tavi -- C:\code\tavi\.venv\Scripts\python.exe C:\code\tavi\tavi_mcp.py
   codex mcp list
   ```

   Alternatively, add the same Python command and server file arguments under Codex Settings → MCP servers. Restart the Codex client if needed. Run `/mcp` to confirm the three tools. This server never modifies `config.toml` itself.

3. Test in an ordinary Codex conversation: "Call `tavi_status` and ask `tavi_route_task` to suggest skills for refactoring this repository." No screenshot is needed. The CLI-visible model catalog is advisory and may require the Codex CLI installed on `PATH`. A routing failure is returned, not treated as a successful recommendation.

## What the three tools can and cannot do

- `tavi_status`: report local configuration/capabilities; no screen access.
- `tavi_route_task(task, preference)`: call Tavi's local `route` without `--plan`, `--execute`, `--record`, hosted work, or model switching. Codex may independently review or disregard its recommendations.
- `tavi_match_controls(snapshot, queries)`: accept a fresh, trusted-host-provided `tavi-control-snapshot-v1` and up to 16 `{id,task,target,role,context}` queries. Return compact planner-only candidates, reasons and hashes. No desktop search, screenshot/OCR request, click, typing, focus, permission grant or replay. Stale, disabled and ambiguous controls must be reviewed or reobserved by the host.

Codex Computer owns the user request, observation, permission checks, actual action and result verification. A Tavi match never authorizes an action. **Codex's built-in Computer driver may not expose its internal snapshot to third-party MCP tools**: in that case `tavi_match_controls` remains unusable until a trusted host supplies a compatible snapshot. This bridge does not bypass that limitation or repair Codex's screenshot-helper lifecycle.

## Verification

`python -m unittest -q test_tavi_codex_tools` verifies the adapter's read-only contract and fail-closed errors. The official MCP SDK's live protocol handshake, real Codex catalog, the user's local environment and Windows capture cleanup require separate desktop tests. No live screenshot-border fix or end-to-end speedup is claimed.
