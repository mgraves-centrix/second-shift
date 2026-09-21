"""The shape of the API layer, as distinct from what its routes answer.

`test_api_characterization.py` asserts the responses. This asserts the structure
that makes adding the next route a one-file change, and the two orderings that
are silent when they break.
"""

from __future__ import annotations

import ast
from pathlib import Path

import pytest
from fastapi import APIRouter, FastAPI
from fastapi.testclient import TestClient

from secondshift.api import app as app_module
from secondshift.api.app import assert_web_mounted_last, create_app
from secondshift.api.routes import ROUTERS

API = Path(app_module.__file__).resolve().parent
ROUTE_MODULES = sorted(p for p in (API / "routes").glob("*.py") if p.name != "__init__.py")


@pytest.fixture
def built_web(tmp_path, monkeypatch):
    """A built web export, so the mount is real rather than skipped.

    The gate runs the API suite before the web build, so `apps/web/out` is
    usually absent while these run — and a test that silently skips the mount is
    a test of the case that cannot go wrong.
    """
    out = tmp_path / "out"
    out.mkdir()
    (out / "index.html").write_text("<!doctype html><title>the PWA</title>")
    monkeypatch.setattr(app_module, "WEB_EXPORT", out)
    return out


class TestTheWebSurfaceIsLast:
    def test_it_is_the_last_route(self, repo, recorder, built_web):
        app = _app(repo, recorder)
        assert app.routes[-1] is next(r for r in app.routes if getattr(r, "name", None) == "web")

    def test_an_api_path_is_not_answered_by_the_page(self, repo, recorder, built_web):
        """The failure this ordering exists to prevent, and it is silent.

        A caller asking for data gets a working page and a 200, which reads as a
        frontend bug for as long as it takes somebody to open the response.
        """
        response = TestClient(_app(repo, recorder)).get("/runs")

        assert response.headers["content-type"].startswith("application/json")
        assert "<!doctype html>" not in response.text.lower()

    def test_a_route_registered_after_it_is_refused(self, repo, recorder, built_web):
        app = _app(repo, recorder)
        later = APIRouter()

        @later.get("/added-after-the-mount")
        def _unreachable() -> dict[str, str]:  # pragma: no cover - never matched
            return {}

        app.include_router(later)

        with pytest.raises(RuntimeError, match="after every route"):
            assert_web_mounted_last(app)

    def test_an_application_with_no_web_surface_passes(self):
        """Nothing to be last. The PWA is a separate build step."""
        assert_web_mounted_last(FastAPI())


class TestARouteLivesInOneModule:
    def test_every_route_is_declared_by_a_router(self, repo, recorder):
        declared = {
            route.path for router in ROUTERS for route in router.routes
        }
        served = set(TestClient(_app(repo, recorder)).app.openapi()["paths"])

        assert served == declared

    def test_no_route_module_imports_another(self):
        """The collision this package exists to remove.

        A shared mapper belongs in `mappers.py`; a route module reaching into
        another one puts two capabilities back in one edit.
        """
        siblings = {p.stem for p in ROUTE_MODULES}
        offenders = []
        for path in ROUTE_MODULES:
            for node in ast.walk(ast.parse(path.read_text())):
                if not isinstance(node, ast.ImportFrom) or node.level != 1:
                    # Level 1 is this package. `from ...morning import assemble`
                    # reaches the capability's own module, which is the point.
                    continue
                named = [node.module] if node.module else [a.name for a in node.names]
                offenders += [f"{path.name} imports {n}" for n in named if n in siblings]

        assert offenders == []

    def test_app_declares_no_route_of_its_own(self):
        """`app.py` assembles. A route declared here is a route in the wrong file."""
        source = (API / "app.py").read_text()

        assert "@app.get" not in source
        assert "@app.post" not in source

    def test_every_route_module_is_registered(self):
        """A module nobody includes is a set of routes nobody can call.

        The defect this repository keeps producing is code that is correct,
        tested and unreachable; a router left out of `ROUTERS` is exactly that,
        and its own tests would pass.
        """
        from secondshift.api import routes as package

        registered = [id(router) for router in ROUTERS]
        for path in ROUTE_MODULES:
            module = getattr(package, path.stem)
            assert id(module.router) in registered, f"{path.name} is not in ROUTERS"


class TestTheMappersAreShared:
    def test_nothing_in_mappers_is_unused(self):
        """The orphan check, for the module the split created.

        A mapper moved out of `app.py` with no caller was moved for nothing.

        By identifier rather than by substring. The first draft searched the
        text, and `model_call` is a substring of `model_calls` and of
        `model_calls_for_invocation` — so removing its only call left the check
        green. Searching source text for a name is how a test ends up asserting
        that a word appears somewhere.
        """
        mappers = ast.parse((API / "mappers.py").read_text())
        public = [
            n.name
            for n in mappers.body
            if isinstance(n, ast.FunctionDef) and not n.name.startswith("_")
        ]
        called: set[str] = set()
        for path in [*ROUTE_MODULES, API / "app.py", API / "context.py"]:
            for node in ast.walk(ast.parse(path.read_text())):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    called.add(node.func.id)

        assert [name for name in public if name not in called] == []


def _app(repo, recorder) -> FastAPI:
    from secondshift.airlock.capability import build_report
    from secondshift.api.app import Context
    from secondshift.config import resolve_profile

    resolved = resolve_profile(env={"SECOND_SHIFT_PROFILE": "cloud"})
    return create_app(
        Context(
            repo=repo,
            recorder=recorder,
            profile=resolved,
            report=build_report(resolved),
            is_synthetic=False,
        )
    )
