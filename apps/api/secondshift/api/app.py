"""The application: the routes it serves, and the web surface under them.

Every route lives in `routes/`, one module per capability. This module builds
the application, hands it the context those routes read, includes them, and
mounts the exported PWA last.

Last matters. The mount answers everything that reaches it, so a route included
after it is a route nobody can call — and the symptom is the page being returned
to a caller that wanted data, which reads as a frontend bug for as long as it
takes to find. `assert_web_mounted_last` refuses to return an application in
that state.
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from starlette.routing import Mount

from .context import Context, build_context
from .routes import ROUTERS

#: Re-exported: `main.py` and the tests import the context from here, and moving
#: it into its own module is not a reason to make them say so.
__all__ = ["Context", "assert_web_mounted_last", "build_context", "create_app"]

#: The exported PWA, when it has been built. Serving it from the API keeps the
#: capture app and its API on one origin — no CORS, no second process to be down
#: at 2am, and `NEXT_PUBLIC_API_BASE` can stay empty.
WEB_EXPORT = Path(__file__).resolve().parents[3] / "web" / "out"


def create_app(context: Context) -> FastAPI:
    app = FastAPI(title="Second Shift — capture", version="0.1.0")
    # Read back by `get_context`. On the application rather than in a closure,
    # so a route declared in another module can reach it.
    app.state.context = context

    for router in ROUTERS:
        app.include_router(router)

    _mount_web(app)
    assert_web_mounted_last(app)
    return app


def _mount_web(app: FastAPI) -> None:
    if not WEB_EXPORT.is_dir():
        # Not built. The API still serves; the PWA is a separate build step and
        # a test run has no reason to have performed it.
        return
    app.mount("/", StaticFiles(directory=WEB_EXPORT, html=True), name="web")


def assert_web_mounted_last(app: FastAPI) -> None:
    """Refuse an application whose web surface is not its last route.

    An invariant rather than a step, so it can be checked again later: called
    from `create_app` it sees everything registered there, and a test can call
    it on an application that has had a route added since.

    An application with no web surface passes. There is nothing to be last, and
    the PWA is a separate build step a test run has no reason to have performed.
    """
    mounts = [i for i, route in enumerate(app.routes) if _is_web_mount(route)]
    if not mounts:
        return
    if mounts[-1] != len(app.routes) - 1:
        after = app.routes[mounts[-1] + 1 :]
        raise RuntimeError(
            "the web surface must be mounted after every route, because it "
            "answers everything that reaches it: "
            f"{[getattr(r, 'path', r) for r in after]} would never match"
        )


def _is_web_mount(route: object) -> bool:
    return isinstance(route, Mount) and getattr(route, "name", None) == "web"
