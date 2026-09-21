"""Whether the machine is well, reported once rather than one failure at a time.

Not a service. `OPERATIONS.md` excludes a monitoring daemon by name — the
telemetry database is the monitoring — so this is a command somebody runs after
a deploy, and its whole output is a status and a table.

Every check here exists because the thing it checks has already gone wrong, or
is recorded in the roadmap as able to.
"""

from __future__ import annotations

import os
import socket
import sqlite3
from dataclasses import dataclass
from pathlib import Path

from .. import config
from ..db.migrate import discover

#: A backup older than this is reported. Long enough that a machine which
#: missed one night is not noisy, short enough that a schedule which stopped is
#: caught in the same week.
STALE_BACKUP_MS = 3 * 24 * 60 * 60 * 1000


@dataclass(frozen=True)
class Check:
    name: str
    ok: bool
    detail: str


def run_checks(
    *,
    env: dict[str, str] | None = None,
    backups: Path | None = None,
    now_ms: int | None = None,
) -> list[Check]:
    """Every check, always all of them.

    Stopping at the first failure makes an operator fix one thing and re-run,
    three times, for information the first run already had.
    """
    environment = dict(os.environ if env is None else env)
    resolved = config.resolve_all(environment)
    by_name = {row.setting.name: row for row in resolved}

    checks = [_configuration(resolved)]
    db_path = Path(by_name[config.ENV_DB].value)
    checks.append(_database(db_path))
    checks.append(_schema(db_path))
    checks.append(_ownership(by_name[config.ENV_DB]))
    checks.append(_reasoner(by_name, environment))
    checks.append(_backups(backups, now_ms))
    return checks


def _configuration(resolved) -> Check:
    """`python -m secondshift.config show` has never been run on the machine.

    It exits non-zero on a malformed file or an unresolved required setting, so
    the first thing worth knowing after a deploy is whether it would.
    """
    broken = [r for r in resolved if r.error]
    if broken:
        return Check(
            "configuration",
            False,
            "; ".join(f"{r.setting.name}: {r.error}" for r in broken),
        )
    missing = [r.setting.name for r in resolved if r.setting.required and not r.value]
    if missing:
        return Check("configuration", False, f"unresolved: {', '.join(missing)}")
    return Check("configuration", True, f"{len(resolved)} settings resolved")


def _database(db_path: Path) -> Check:
    if not db_path.exists():
        return Check("database", False, f"no database at {db_path}")
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.DatabaseError as exc:
        return Check("database", False, f"{db_path}: {exc}")
    try:
        mode = conn.execute("PRAGMA journal_mode").fetchone()[0]
    except sqlite3.DatabaseError as exc:
        return Check("database", False, f"{db_path}: {exc}")
    finally:
        conn.close()
    if mode.lower() != "wal":
        # Not cosmetic: the night writes while the API reads, and any other
        # mode puts a reader in the way of that.
        return Check("database", False, f"journal mode is {mode}, expected wal")
    return Check("database", True, f"{db_path}, wal")


def _schema(db_path: Path) -> Check:
    """A deploy that skipped a migration leaves a night failing at 2am."""
    if not db_path.exists():
        return Check("schema", False, "no database to check")
    expected = max((m.version for m in discover()), default=0)
    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
        try:
            row = conn.execute("SELECT MAX(version) AS v FROM schema_version").fetchone()
        finally:
            conn.close()
    except sqlite3.DatabaseError as exc:
        return Check("schema", False, str(exc))
    applied = row[0] or 0
    if applied != expected:
        return Check("schema", False, f"at {applied}, migrations on disk go to {expected}")
    return Check("schema", True, f"at {applied}")


def _ownership(setting) -> Check:
    """A `/root/...` data path means the unit is running as the wrong user.

    `OPERATIONS.md` records that this has corrupted the write-ahead log before:
    two accounts writing one database leave a `-wal` that one of them cannot
    read.

    Only checked when the path came from the default, because the default is
    `~`-derived and therefore follows whoever is running — which is exactly how
    a unit started as root ends up writing a different database from the one an
    operator inspects. A path the operator named explicitly is a path they
    chose, and second-guessing it would make this check cry wolf every time
    somebody points the tooling at a scratch copy.
    """
    db_path = Path(setting.value)
    if setting.origin is not config.Origin.DEFAULT:
        return Check("data ownership", True, f"{db_path}, named explicitly")
    home = Path.home()
    if home == Path("/root") or os.geteuid() == 0:
        return Check(
            "data ownership",
            False,
            f"running as root, so the default resolved to {db_path}; "
            "a service writing here is not writing where the operator looks",
        )
    return Check("data ownership", True, f"default under {home}")


def _reasoner(by_name, environment: dict[str, str]) -> Check:
    """The port has been wrong once, and the probe believes `config/models.toml`.

    A machine pinned to the cloud profile is not supposed to have one — the
    judge container is exactly that — so its absence is reported as expected
    rather than as a failure. That is a branch on resolved capability, which
    every profile-aware path in this system already takes, and not on which
    deployment is running.
    """
    if environment.get(config.ENV_PROFILE) == str(config.Profile.CLOUD):
        return Check("local reasoner", True, "not expected on the cloud profile")
    host = by_name[config.ENV_LOCAL_HOST].value
    port = int(by_name[config.ENV_LOCAL_PORT].value)
    expected = by_name[config.ENV_LOCAL_MODEL].value
    try:
        with socket.create_connection((host, port), timeout=2):
            pass
    except OSError as exc:
        # Reported, not raised. The judge container is exactly a machine with
        # no reasoner, and `doctor` has to be able to run there.
        return Check("local reasoner", False, f"{host}:{port} unreachable ({exc})")
    served = config.served_models(host, port, 2.0)
    if served is None:
        return Check("local reasoner", False, f"{host}:{port} answered nothing usable")
    if expected not in served:
        return Check(
            "local reasoner",
            False,
            f"{host}:{port} serves {', '.join(served) or 'nothing'}, expected {expected}",
        )
    return Check("local reasoner", True, f"{host}:{port} serving {expected}")


def _backups(backups: Path | None, now_ms: int | None) -> Check:
    """A schedule that silently stopped looks exactly like one never set up."""
    from ..db.connection import now_ms as clock

    from .backup import MANIFEST, Manifest

    if backups is None:
        return Check("backups", False, "no backup directory given to check")
    if not backups.is_dir():
        return Check("backups", False, f"{backups} does not exist")
    manifests = sorted(backups.glob(f"*/{MANIFEST}"))
    if not manifests:
        return Check("backups", False, f"no backup under {backups}")
    newest = max(
        Manifest.from_json(m.read_text()).taken_at_ms for m in manifests
    )
    age_ms = (clock() if now_ms is None else now_ms) - newest
    days = age_ms / 86_400_000
    if age_ms > STALE_BACKUP_MS:
        return Check("backups", False, f"newest is {days:.1f} days old")
    plural = "" if len(manifests) == 1 else "s"
    return Check(
        "backups", True, f"{len(manifests)} backup{plural}, newest {days:.1f} days old"
    )
