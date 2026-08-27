"""Invocation context propagation.

The invocation tree is carried in a `contextvar` rather than threaded through
call signatures. A provider therefore records its own telemetry without being
handed an invocation id, which is what makes instrumentation hard to skip —
the constitution's Telemetry From Line One principle is exactly the kind of
thing that erodes when every new code path has to remember to pass something.

SHARP EDGE: `contextvars` propagate into `asyncio` tasks automatically. They do
NOT propagate into threads started by `ThreadPoolExecutor` or `threading.Thread`
— a worker thread starts from an empty context and its telemetry would be
recorded as a root invocation. Wrap any threaded work with `propagate()` below,
which captures the calling context and re-attaches it inside the worker.
"""

from __future__ import annotations

import contextvars
import functools
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, TypeVar

T = TypeVar("T")


@dataclass(frozen=True, slots=True)
class InvocationContext:
    """The invocation currently executing."""

    invocation_id: str
    run_id: str | None = None
    depth: int = 0


_current: contextvars.ContextVar[InvocationContext | None] = contextvars.ContextVar(
    "secondshift_invocation", default=None
)


def current() -> InvocationContext | None:
    """The active invocation, or None outside any invocation."""
    return _current.get()


def current_id() -> str | None:
    ctx = _current.get()
    return ctx.invocation_id if ctx else None


def bind(ctx: InvocationContext | None) -> contextvars.Token:
    """Make `ctx` current. Returns a token for `release()`."""
    return _current.set(ctx)


def release(token: contextvars.Token) -> None:
    """Restore whatever context was current before the matching `bind()`."""
    _current.reset(token)


def propagate(fn: Callable[..., T]) -> Callable[..., T]:
    """Wrap a callable so it runs under the caller's context in another thread.

    Use for any work handed to a thread pool:

        pool.submit(propagate(do_work), arg)

    Without this the worker starts from an empty context and its telemetry is
    recorded as a root invocation rather than a child.
    """
    captured = contextvars.copy_context()

    @functools.wraps(fn)
    def runner(*args: Any, **kwargs: Any) -> T:
        return captured.run(fn, *args, **kwargs)

    return runner
