"""
DctStub — a tiny Starlette app that pretends to be the DCT API.

Runs on 127.0.0.1:<random-port> inside the pytest process. The MCP server
(spawned as a subprocess by mcp_client) is pointed at the stub via
DCT_BASE_URL. Every request is recorded so tests can assert exactly what
the server sent.

Scope: just enough routes to support the VDB lifecycle workflow and the
delete-VDB confirmation handshake. More routes get added as new workflows
are translated.

Note: deliberately does NOT serve /dct/static/api-external.yaml so the MCP
server's startup OpenAPI generator fails fast (non-fatal — caught in
main.py) and the pre-built tool modules register as the fallback.
"""

import socket
import threading
import time
from typing import Any, Dict, List, Optional, Tuple

import uvicorn
from starlette.applications import Starlette
from starlette.requests import Request
from starlette.responses import JSONResponse, PlainTextResponse
from starlette.routing import Route


# Stable canned data — same fixture every test, so "the first VDB" is always v-1.
_FIXTURE_VDBS = [
    {
        "id": "v-1",
        "name": "fake-vdb-1",
        "status": "RUNNING",
        "engine_id": "e-1",
        "environment_id": "env-1",
    },
    {
        "id": "v-2",
        "name": "fake-vdb-2",
        "status": "STOPPED",
        "engine_id": "e-1",
        "environment_id": "env-1",
    },
]


def _generic_item(resource: str, item_id: Optional[str] = None,
                  parent_id: Optional[str] = None) -> Dict[str, Any]:
    """A deterministic canned object for the catch-all routes.

    Stable per-resource id (e.g. vg-1 for vdb-groups) so `search` ->
    `items[0]["id"]` chains predictably across workflow steps.
    """
    prefixes = {
        "vdb-groups": "vg",
        "vdb-group": "vg",
        "dsources": "ds",
        "dsource": "ds",
        "snapshots": "snap",
        "snapshot": "snap",
        "bookmarks": "bk",
        "bookmark": "bk",
        "jobs": "j",
        "job": "j",
        "timeflows": "tf",
        "timeflow": "tf",
        "tag": "tag",
    }
    prefix = prefixes.get(resource, resource[:3] if resource else "x")
    rid = item_id or f"{prefix}-1"
    obj: Dict[str, Any] = {"id": rid, "name": f"{prefix}-{rid}"}
    if resource in ("jobs", "job"):
        obj["status"] = "RUNNING"
    if parent_id is not None:
        obj["parent_id"] = parent_id
    return obj


class DctStub:
    """A fake DCT API. Records every request and serves canned responses."""

    def __init__(self) -> None:
        # Each entry: (method, path, body_dict_or_none)
        self.requests: List[Tuple[str, str, Optional[Dict[str, Any]]]] = []
        self.url: str = ""

    # ---- Recording helper ------------------------------------------------

    async def _record(self, request: Request) -> Optional[Dict[str, Any]]:
        body: Optional[Dict[str, Any]] = None
        if request.method in ("POST", "PUT", "PATCH"):
            try:
                if await request.body():
                    body = await request.json()
            except Exception:
                body = None
        self.requests.append((request.method, request.url.path, body))
        return body

    def received_request(self, method: str, path: str) -> bool:
        """Assertion helper: did the MCP server send <method> <path> to DCT?"""
        return any(m == method and p == path for m, p, _ in self.requests)

    def reset(self) -> None:
        self.requests.clear()

    # ---- Route handlers --------------------------------------------------

    async def vdbs_search(self, request: Request) -> JSONResponse:
        await self._record(request)
        return JSONResponse({"items": _FIXTURE_VDBS})

    async def vdb_get(self, request: Request) -> JSONResponse:
        await self._record(request)
        vdb_id = request.path_params["vdbId"]
        for vdb in _FIXTURE_VDBS:
            if vdb["id"] == vdb_id:
                return JSONResponse(vdb)
        return JSONResponse({"error": "not found"}, status_code=404)

    async def vdb_job_action(self, request: Request) -> JSONResponse:
        """Handles start/stop/enable/disable etc. — returns a fake job_id."""
        await self._record(request)
        return JSONResponse({"job": {"id": "j-1", "status": "STARTED"}})

    async def vdb_delete(self, request: Request) -> JSONResponse:
        await self._record(request)
        return JSONResponse({"job": {"id": "j-2", "status": "STARTED"}})

    async def ack(self, request: Request) -> JSONResponse:
        """
        Generic 2xx acknowledgement for action endpoints (rollback, disable,
        tags/delete, bookmark/timeflow update+delete, etc.). Records the request
        and returns a completed-job body so the tool call succeeds.
        """
        await self._record(request)
        return JSONResponse({"job": {"id": "j-ack", "status": "COMPLETED"}})

    # ---- Catch-all (workflow scope) --------------------------------------
    #
    # Added for Phase L3/3b workflow tests. Serves every OTHER /dct/v3/...
    # endpoint (vdb-groups, dsources, snapshots, bookmarks, jobs, timeflows
    # and their sub-resources) with shape-appropriate canned data, so a
    # search -> get -> action chain works end-to-end. The explicit routes
    # above still win (Starlette matches in declaration order), so the demo's
    # v-1-centric VDB lifecycle is untouched.
    #
    # IMPORTANT: this only matches the /dct/v3 prefix, so /dct/static/...
    # (the OpenAPI bootstrap) still 404s and the server keeps using the
    # pre-built tool modules — exactly as before.

    async def catch_all(self, request: Request) -> JSONResponse:
        await self._record(request)
        path = request.url.path  # e.g. /dct/v3/vdb-groups/vg-1/snapshots
        method = request.method
        # Strip the /dct/v3 prefix, split into segments.
        rel = path[len("/dct/v3"):].lstrip("/")
        segs = [s for s in rel.split("/") if s]

        # POST .../search -> a list with a stable first item.
        if method == "POST" and segs and segs[-1] == "search":
            resource = segs[-2] if len(segs) >= 2 else "item"
            return JSONResponse({"items": [_generic_item(resource), _generic_item(resource, "2")]})

        # GET sub-resource lists / detail blobs.
        if method == "GET" and segs:
            tail = segs[-1]
            if tail in ("snapshots", "bookmarks", "tags", "vdb-groups"):
                # Parent id is segs[-2] when present.
                parent = segs[-2] if len(segs) >= 2 else tail
                return JSONResponse({"items": [_generic_item(tail.rstrip("s"), parent_id=parent)]})
            if tail in ("runtime", "timeflow_range", "timeflowSnapshotDayRange"):
                return JSONResponse({tail: {"start": "2024-01-01T00:00:00.000Z",
                                            "end": "2024-01-02T00:00:00.000Z"}})
            if tail in ("find_by_location", "find_by_timestamp"):
                return JSONResponse({"items": [_generic_item("snapshot")]})
            if tail == "timeflows":
                # GET /timeflows (list) -> items.
                return JSONResponse({"items": [_generic_item("timeflow")]})
            # GET /{resource}/{id} -> single object with the requested id.
            obj_id = segs[-1]
            resource = segs[-2] if len(segs) >= 2 else "item"
            return JSONResponse(_generic_item(resource.rstrip("s"), obj_id))

        # POST /{resource} (no sub-path) -> create -> object with a new id.
        if method == "POST" and len(segs) == 1:
            return JSONResponse({"id": "new-1", "name": f"{segs[0].rstrip('s')}-new-1"})

        # Everything else: actions (start/stop/refresh/rollback/lock/abandon/
        # repair/add_tags/...), PATCH, DELETE -> a completed-job ack.
        return JSONResponse({"job": {"id": "j-x", "status": "COMPLETED"}})


def _free_port() -> int:
    """Bind ephemeral, immediately release — the port is then ours to use."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def build_app(stub: DctStub) -> Starlette:
    """All known routes for the PoC's VDB-lifecycle scope."""
    return Starlette(
        routes=[
            Route("/dct/v3/vdbs/search", stub.vdbs_search, methods=["POST"]),
            Route("/dct/v3/vdbs/{vdbId}", stub.vdb_get, methods=["GET"]),
            Route("/dct/v3/vdbs/{vdbId}/start", stub.vdb_job_action, methods=["POST"]),
            Route("/dct/v3/vdbs/{vdbId}/stop", stub.vdb_job_action, methods=["POST"]),
            # data_tool uses POST /vdbs/{id}/delete (with manual confirmation),
            # not DELETE /vdbs/{id} — match the production endpoint.
            Route("/dct/v3/vdbs/{vdbId}/delete", stub.vdb_delete, methods=["POST"]),
            # --- Confirmation-gated self_service endpoints (3c) ---
            Route("/dct/v3/vdbs/{vdbId}/disable", stub.ack, methods=["POST"]),
            Route("/dct/v3/vdbs/{vdbId}/rollback_by_timestamp", stub.ack, methods=["POST"]),
            Route("/dct/v3/vdbs/{vdbId}/rollback_by_snapshot", stub.ack, methods=["POST"]),
            Route("/dct/v3/vdbs/{vdbId}/rollback_from_bookmark", stub.ack, methods=["POST"]),
            Route("/dct/v3/vdbs/{vdbId}/tags/delete", stub.ack, methods=["POST"]),
            Route("/dct/v3/vdb-groups/{vdbGroupId}/rollback", stub.ack, methods=["POST"]),
            Route("/dct/v3/vdb-groups/{vdbGroupId}/tags/delete", stub.ack, methods=["POST"]),
            Route("/dct/v3/snapshots/{snapshotId}/tags/delete", stub.ack, methods=["POST"]),
            Route("/dct/v3/bookmarks/{bookmarkId}", stub.ack, methods=["PATCH", "DELETE"]),
            Route("/dct/v3/bookmarks/{bookmarkId}/tags/delete", stub.ack, methods=["POST"]),
            Route("/dct/v3/timeflows/{timeflowId}", stub.ack, methods=["DELETE"]),
            Route("/dct/v3/timeflows/{timeflowId}/tags/delete", stub.ack, methods=["POST"]),
            # --- Workflow catch-all (3b) ---
            # Last route: handles every other /dct/v3 endpoint for the workflow
            # chains (vdb-groups, dsources, snapshots, bookmarks, jobs,
            # timeflows + sub-resources). Declared LAST so all explicit routes
            # above win. Does NOT match /dct/static/... so the OpenAPI bootstrap
            # still 404s and the pre-built tools remain the active toolset.
            Route("/dct/v3/{rest:path}", stub.catch_all,
                  methods=["GET", "POST", "PATCH", "DELETE", "PUT"]),
            # Anything outside /dct/v3 (including /dct/static/api-external.yaml)
            # → 404. That is intentional: the OpenAPI bootstrap fails fast, MCP
            # server falls back to pre-built tools, and we get a clean toolset.
        ]
    )


class StubServer:
    """Manages the uvicorn thread lifecycle for a single test."""

    def __init__(self) -> None:
        self.stub = DctStub()
        self.port = _free_port()
        self.stub.url = f"http://127.0.0.1:{self.port}"
        self._server: Optional[uvicorn.Server] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> DctStub:
        config = uvicorn.Config(
            build_app(self.stub),
            host="127.0.0.1",
            port=self.port,
            log_level="error",
            access_log=False,
        )
        self._server = uvicorn.Server(config)
        self._thread = threading.Thread(target=self._server.run, daemon=True)
        self._thread.start()

        # Wait until uvicorn reports itself started (capped at ~5s).
        deadline = time.time() + 5
        while time.time() < deadline:
            if self._server.started:
                return self.stub
            time.sleep(0.05)
        raise RuntimeError("dct_stub uvicorn server did not start in time")

    def stop(self) -> None:
        if self._server is not None:
            self._server.should_exit = True
        if self._thread is not None:
            self._thread.join(timeout=5)
