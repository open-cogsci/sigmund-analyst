"""This code is based on from https://github.com/jasp-stats/jasp-mcp/ and is
available under an MIT license.

In-process MCP server that exposes JASP (https://jasp-stats.org/) to the
Sigmund MCP relay.

JASP itself only offers a JSON-RPC v2 API over HTTP (enable it under
Preferences -> Advanced -> Remote Control; it then listens on
``http://127.0.0.1:48164/rpc`` and answers with ``content-type: text/plain``,
so it cannot be connected to as an MCP server directly). This module is the
bridge: an in-process MCP server (mcp SDK 2.x, low-level API) that discovers
JASP's RPC methods through ``rpc_discover`` and exposes each of them as an MCP
tool. It is a rebuild of https://github.com/jasp-stats/jasp-mcp on the mcp 2.x
SDK, embedded in the IDE process instead of running as a ``uvx`` subprocess.

The tool list is dynamic: while JASP is unreachable the server exposes only a
``ping`` tool, and once JASP answers ``rpc_discover`` the full method list is
registered and a ``notifications/tools/list_changed`` is sent so that clients
re-fetch the list. The same happens in reverse when JASP disappears.

``make_mcp(url)`` is the server factory passed to
``InProcessServerProvider``: it is called once per relay session (with the
URL from the provider's ``args_provider``) and returns a fresh server
instance, so every session gets its own JASP connection, poller, and status
message.
"""

import asyncio
import json
import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Any

import httpx
import mcp_types as types
from mcp.server.lowlevel import NotificationOptions, Server

logger = logging.getLogger(__name__)

POLL_INTERVAL = 2.0  # seconds between JASP reachability checks

SERVER_INSTRUCTIONS = """\
You are connected to JASP statistical software through this MCP server. Each
tool maps to one JASP JSON-RPC method.

## Workflow for running an analysis

1.  **Load data** -- Use `data_load` with a file path. For small datasets,
    pass `wait=true` (default) for a blocking call that returns column
    metadata. For large files, pass `wait=false` to start an async load and
    poll with `data_load_status` until the status is `complete`. Then use
    `data_info` to inspect columns and their types.
2.  **Discover analyses** -- Use `modules_list` to see available modules and
    analyses.
3.  **Get analysis context** -- Use `analysis_context` for the target
    analysis. It returns help text describing every available option, its
    type, valid values, and allowed column types. Always do this before
    configuring an unfamiliar analysis.
4.  **Create the analysis** -- Use `analysis_create` with the module and
    analysis name. Save the returned `analysisId`. The response includes
    default `options` and `optionMeta` describing the kind of each control.
5.  **Configure and run** -- Use `analysis_run` with the `analysisId` and an
    options object. Common option patterns:
    - Checkboxes: `{ "wantsEffectSize": true }`
    - Dropdowns / combos: `{ "hypothesis": "groupOneGreater" }`
    - Variable assignments: `{ "dependent": ["score"], "groupingVariable": ["group"] }`
    - Numbers: `{ "confidenceInterval": 0.95 }`
    `analysis_run` blocks up to `timeoutMs` (default 30000 ms) and returns one
    of: `success` (results included), `running` (poll with `analysis_results`),
    or `error` (check `message`). Some analyses reveal options only after prior
    selections -- inspect `optionMeta` / `optionMetaDelta` in the response and
    iterate with additional `analysis_run` calls if needed.
6.  **Poll if running** -- If step 5 returned `running`, poll with
    `analysis_results` (same `analysisId`) until `success`. Do NOT call it if
    step 5 already returned `success`.
7.  **Compose output** -- Use `analysis_composeResults` to reorder result
    elements or insert Markdown annotations, `analysis_createAnnotation` to
    annotate an existing analysis, and `write_report` for a standalone
    cross-analysis report.

## Important notes

- Variable lists expect an array of column name strings.
- Plot results contain base64-encoded images under `data` keys -- summarise
  these rather than including the raw base64 in your response.
- If an analysis returns `fatalError`, use `get_analyses_state` to review the
  current options and check that required variables are assigned.
- JASP must be running with Remote Control enabled (Preferences -> Advanced)
  for these tools to work; `ping` tells you whether it is reachable.
"""


class JASPClientError(Exception):
    """Raised when JASP returns a JSON-RPC error or the HTTP request fails."""

    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


class JASPClient:
    """Minimal async JSON-RPC v2 client for JASP's HTTP endpoint."""

    def __init__(self, url: str, http: httpx.AsyncClient):
        self.url = url.rstrip('/')
        self._http = http
        self._id = 0

    async def call(self, method: str, params: dict[str, Any] | None = None) -> Any:
        """Call a JASP RPC method and return the ``result`` field.

        Raises JASPClientError on a JSON-RPC error, httpx.HTTPError on
        transport problems.
        """
        self._id += 1
        payload = {
            'jsonrpc': '2.0',
            'method': method,
            'params': params or {},
            'id': self._id,
        }
        # JASP replies with content-type text/plain, so parse explicitly
        # instead of relying on resp.json()'s content-type check.
        resp = await self._http.post(self.url, json=payload)
        resp.raise_for_status()
        try:
            body = json.loads(resp.text)
        except ValueError as exc:
            raise JASPClientError(
                f'Invalid JSON response from JASP for {method}: {resp.text[:500]}'
            ) from exc
        if 'error' in body:
            err = body['error']
            raise JASPClientError(
                f"JASP RPC error on {method}: {err.get('message', str(err))}",
                code=err.get('code'),
            )
        return body.get('result')


def _tool_from_method(method: dict[str, Any]) -> types.Tool:
    """Build an MCP tool from one OpenRPC method descriptor of rpc_discover."""
    properties: dict[str, Any] = {}
    required: list[str] = []
    for p in method.get('params', []):
        prop = dict(p.get('schema') or {'type': 'object'})
        if p.get('description'):
            prop['description'] = p['description']
        properties[p['name']] = prop
        if p.get('required'):
            required.append(p['name'])
    input_schema: dict[str, Any] = {'type': 'object', 'properties': properties}
    if required:
        input_schema['required'] = required
    return types.Tool(
        name=method['name'],
        description=method.get('summary') or f"JASP RPC method: {method['name']}",
        inputSchema=input_schema,
    )


def _ping_tool() -> types.Tool:
    """A static connectivity-check tool, served even when JASP is down."""
    return types.Tool(
        name='ping',
        description='Connectivity check for JASP. Returns "pong" when JASP is '
                    'running with Remote Control enabled, otherwise an error.',
        inputSchema={'type': 'object', 'properties': {}},
    )


class _JASPServer(Server):
    """Low-level MCP server exposing JASP's dynamically discovered RPC methods.

    The low-level (rather than MCPServer high-level) API is used because the
    tool set is not known upfront: it is whatever JASP's ``rpc_discover``
    returns, with full JSON schemas.
    """

    def __init__(self, url):
        self._url = url
        self._http: httpx.AsyncClient | None = None
        self._client: JASPClient | None = None
        self._poll_task: asyncio.Task | None = None
        self._tools: list[types.Tool] = [_ping_tool()]
        self._discovered = False
        self._session = None  # captured from the first request's ctx
        self._status = f'Connecting to JASP at {url} ...'
        super().__init__(
            'jasp',
            instructions=SERVER_INSTRUCTIONS,
            lifespan=self._lifespan,
            on_list_tools=self._on_list_tools,
            on_call_tool=self._on_call_tool,
        )

    # ------------------------------------------------------------------
    # Relay/GUI integration
    # ------------------------------------------------------------------
    @property
    def status_message(self) -> str:
        """Shown in small print on the relay GUI toggle button.

        Only reads a plain str attribute (atomic in CPython), so it is safe
        to poll from the GUI thread while the agent thread updates it.
        """
        return self._status

    def create_initialization_options(
        self,
        notification_options: NotificationOptions | None = None,
        experimental_capabilities: dict[str, dict[str, Any]] | None = None,
        extensions: dict[str, dict[str, Any]] | None = None,
    ):
        # The relay calls this with no arguments; advertise listChanged so
        # clients know they may receive notifications/tools/list_changed.
        if notification_options is None:
            notification_options = NotificationOptions(tools_changed=True)
        return super().create_initialization_options(
            notification_options, experimental_capabilities, extensions)

    # ------------------------------------------------------------------
    # Lifespan: own the httpx client and the background poller per session
    # ------------------------------------------------------------------
    @asynccontextmanager
    async def _lifespan(self, server) -> AsyncIterator[dict[str, Any]]:
        # read=None: JASP blocks server-side up to the caller's timeoutMs
        # (e.g. analysis_run), so never time out the read.
        self._http = httpx.AsyncClient(
            timeout=httpx.Timeout(connect=5.0, read=None, write=60.0, pool=5.0),
            headers={'Accept': 'application/json'},
        )
        self._client = JASPClient(self._url, self._http)
        self._poll_task = asyncio.create_task(self._poll())
        logger.info('JASP MCP server session started (endpoint: %r)', self._url)
        try:
            yield {}
        finally:
            if self._poll_task is not None:
                self._poll_task.cancel()
                try:
                    await self._poll_task
                except asyncio.CancelledError:
                    pass
            if self._http is not None:
                await self._http.aclose()
                self._http = None
            logger.info('JASP MCP server session ended')

    # ------------------------------------------------------------------
    # MCP request handlers
    # ------------------------------------------------------------------
    async def _on_list_tools(self, ctx, params) -> types.ListToolsResult:
        self._session = ctx.session
        if not self._discovered:
            await self._try_discover()
        return types.ListToolsResult(tools=list(self._tools))

    async def _on_call_tool(self, ctx, params) -> types.CallToolResult:
        self._session = ctx.session
        if not self._discovered:
            await self._try_discover()
        if self._client is None:
            return _error_result('JASP client is not initialised yet.')
        try:
            result = await self._client.call(params.name, params.arguments or {})
        except JASPClientError as exc:
            detail = str(exc)
            if exc.code is not None:
                detail += f' (code {exc.code})'
            return _error_result(detail)
        except (httpx.HTTPError, OSError) as exc:
            return _error_result(
                f'Cannot reach JASP at {self._url!r}: {exc}. Make sure JASP is '
                'running with Remote Control enabled (Preferences -> Advanced).'
            )
        text = result if isinstance(result, str) else json.dumps(
            result, indent=2, ensure_ascii=False, default=str)
        return types.CallToolResult(
            content=[types.TextContent(type='text', text=text)])

    # ------------------------------------------------------------------
    # Discovery, health checking, list-changed notifications
    # ------------------------------------------------------------------
    async def _try_discover(self) -> bool:
        """Call rpc_discover and rebuild the tool list. Returns True on
        transition to discovered."""
        if self._client is None or self._discovered:
            return False
        try:
            result = await self._client.call('rpc_discover', {})
        except (JASPClientError, httpx.HTTPError, OSError) as exc:
            logger.debug('rpc_discover failed: %s', exc)
            self._status = (f'JASP unreachable at {self._url} -- enable Remote '
                            'Control in JASP (Preferences -> Advanced)')
            return False
        methods = (result or {}).get('methods', [])
        if not methods:
            return False
        self._tools = [_tool_from_method(m) for m in methods]
        self._discovered = True
        self._status = f'Connected to JASP'
        logger.info('Discovered %d JASP RPC method(s) -> MCP tools',
                    len(self._tools))
        await self._notify_list_changed()
        return True

    async def _poll(self) -> None:
        """Background task: discover JASP once reachable; health-check while
        discovered; revert to the static ping tool if JASP disappears."""
        while True:
            await asyncio.sleep(POLL_INTERVAL)
            if self._client is None:
                continue
            try:
                if self._discovered:
                    await self._client.call('ping', {})
                else:
                    await self._try_discover()
            except (JASPClientError, httpx.HTTPError, OSError) as exc:
                if self._discovered:
                    logger.info('JASP disappeared: %s', exc)
                    self._discovered = False
                    self._tools = [_ping_tool()]
                    self._status = (f'JASP unreachable at {self._url} -- enable '
                                    'Remote Control in JASP (Preferences -> Advanced)')
                    await self._notify_list_changed()
                else:
                    self._status = (f'JASP unreachable at {self._url} -- enable '
                                    'Remote Control in JASP (Preferences -> Advanced)')

    async def _notify_list_changed(self) -> None:
        if self._session is not None:
            try:
                await self._session.send_notification(
                    types.ToolListChangedNotification())
            except Exception:
                pass  # session may have disconnected


def _error_result(text: str) -> types.CallToolResult:
    return types.CallToolResult(
        content=[types.TextContent(type='text', text=text)], is_error=True)


def make_mcp(url) -> _JASPServer:
    """Build a fresh JASP MCP server for one relay session.

    Used directly as the ``server_factory`` of an ``InProcessServerProvider``
    (called once per session as ``make_mcp(*args)``), with ``url`` supplied
    through the provider's ``args_provider`` -- e.g. from the
    ``sigmund_mcp_jasp_rpc_url`` setting (default
    ``http://127.0.0.1:48164/rpc``).

    Returns:
        A new ``_JASPServer`` with its own JASP connection, poller, and
        status message.
    """
    return _JASPServer(url)
