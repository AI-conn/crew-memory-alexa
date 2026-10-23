# Friction log + product feedback

Kept from day one of the build (the hackathon awards up to a 10% bonus for
this; it is also kept because it is useful). Format per entry: task, steps,
expected vs. actual, severity, workaround, actionable suggestion.
Product: the **MCP Python SDK (`mcp`)** and the Alexa+ track's MCP path,
unless an entry says otherwise.

## FL-1 — SDK client function renamed; examples lag

- **Task:** Connect a client to our Streamable HTTP server using the SDK.
- **Steps:** Follow the SDK's client examples using
  `mcp.client.streamable_http.streamablehttp_client` (SDK 1.28.1).
- **Expected:** Clean run.
- **Actual:** Works, but every call emits
  `DeprecationWarning: Use streamable_http_client instead`. Following the
  warning is not a rename-only change: the new function has a different
  signature — it takes a constructed `http_client` where the old one took
  `httpx_client_factory` (plus headers/timeout/auth kwargs). Code that
  "just renames" fails with TypeError.
- **Severity:** Low–Medium (the warning understates the migration).
- **Workaround:** Adopt the new function and construct the httpx client
  yourself (done in `mcp_client.py`, with a fallback to the old API).
- **Suggestion:** When a deprecation changes call shape, say so in the
  warning text ("signature changed — see migration note"), and sweep the
  official examples repo in the same release.

## FL-2 — Ambient proxy environment breaks localhost MCP clients

- **Task:** Run the SDK client against `http://127.0.0.1:<port>/mcp` inside
  a sandboxed dev environment that sets `HTTP_PROXY`/`NO_PROXY`.
- **Steps:** `streamablehttp_client(url)` with default httpx factory.
- **Expected:** Direct connection to localhost.
- **Actual:** `httpx.InvalidURL: Invalid port: ':1]'` — httpx's env parsing
  choked on a bracketed IPv6 entry (`[::1]`) in `NO_PROXY`, and localhost
  MCP traffic inherited proxy behavior. Nothing in the error points at the
  environment.
- **Severity:** Medium — this is exactly the setup a self-hosted-MCP
  hackathon entrant (or a judge reproducing the demo behind a corporate
  proxy) will have.
- **Workaround:** Pass `httpx_client_factory` that builds
  `httpx.AsyncClient(..., trust_env=False)` (implemented in
  `mcp_client.py`).
- **Suggestion:** The SDK's default client factory could set
  `trust_env=False` for loopback URLs, or the docs could carry one line:
  "behind a proxy, pass a client factory with trust_env=False for local
  servers."

## FL-3 — FastMCP host/port must be set before `run()`

- **Task:** Make the listen host/port configurable via CLI flags.
- **Steps:** Construct `FastMCP(...)`, parse args, call
  `mcp.run(transport="streamable-http")`.
- **Expected:** `run()` accepts host/port, or settings can be passed at
  construction only.
- **Actual:** `run()` takes transport only; host/port live in
  `mcp.settings`, mutable before `run()` — discoverable, but only by
  reading the settings model.
- **Severity:** Low.
- **Workaround:** Assign `mcp.settings.host/port` before `run()` (done in
  `mcp_server.py`), or pass them to the constructor.
- **Suggestion:** Accept `host`/`port` kwargs on `run()` as overrides.

## Product feedback summary (for the Devpost form)

- **MCP Python SDK (FastMCP):** Used for the entire server surface.
  What worked: tool registration from type hints + docstrings is fast and
  the generated schemas were correct on first contact; the Streamable HTTP
  transport negotiated 2025-11-25 with the SDK client with zero hand-rolled
  protocol code on the server side. Onboarding: under an hour from install
  to a live tools/call. Would build with it again: yes — it is the reason
  the "creative tier" (stateful, multi-tool, evidence-carrying) was
  reachable inside a hackathon window.
- **Devpost / event docs:** The rules' own "obvious vs. creative" guidance
  for the Alexa+ track is unusually actionable and shaped the design.
  One gap: the $150 AWS credit exhaustion (Oct 7 update) is easy to miss
  — it changed our mini-challenge strategy; surfacing it on the overview
  page, not only in rules/resources updates, would save entrants a
  wrong turn.
