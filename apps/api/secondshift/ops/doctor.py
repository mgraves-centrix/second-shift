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

#: A backup older than this is reported. Backups are taken nightly, ordered
#: after the night pipeline, so this is three missed nights — long enough that
#: one skipped night is not noisy, short enough that a schedule which stopped is
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
    checks.append(_backups_elsewhere(backups, db_path))
    checks.append(_night_in_flight(db_path))
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


def night_in_flight(db_path: Path) -> bool:
    """Whether a night is running against this database right now.

    From the lock the night holds, not from an open `runs` row. An open run is
    also what a night killed last week left behind — the case
    `recover_interrupted` exists for — so a restart gated on that evidence would
    refuse forever.

    The lock is an advisory `flock` that the kernel releases when the process
    exits however it exits, which is exactly the property that makes it a
    statement about *now*. Taking it and dropping it is the only way to ask:
    there is no way to read a lock without attempting it.
    """
    import fcntl

    lock = Path(f"{db_path}.night.lock")
    if not lock.exists():
        # A machine that has never run a night is idle, not broken. The judge
        # container is exactly that.
        return False
    with lock.open("a") as handle:
        try:
            fcntl.flock(handle, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            return True
        fcntl.flock(handle, fcntl.LOCK_UN)
    return False


def _night_in_flight(db_path: Path) -> Check:
    """Reported, never failed. A night running is the machine working.

    It is here because it bears on a deploy, a restart and a reboot alike:
    `docker rm -f` on the reasoner during a night costs that night its morning.
    """
    if night_in_flight(db_path):
        return Check("night", True, "a night is in flight — do not restart anything")
    return Check("night", True, "none in flight")


def _backups_elsewhere(backups: Path | None, db_path: Path) -> Check:
    """Whether the backups are on a disk other than the one they protect.

    The nightly schedule writes to a network share. An unmounted share is an
    ordinary empty directory on the local disk, so every backup succeeds, the
    staleness check above reports them fresh, and all of them are on the one
    device whose failure this capability exists for. `ops backup` refuses to
    create that state; this reports a machine that is already in it.
    """
    from .backup import same_device

    if backups is None or not backups.is_dir():
        return Check("backup location", False, "no backup directory to check")
    if not db_path.exists():
        return Check("backup location", False, "no database to compare against")
    if same_device(db_path, backups):
        return Check(
            "backup location",
            False,
            f"{backups} is on the same device as the database; if it is a "
            "network share, it is not mounted",
        )
    return Check("backup location", True, f"{backups} is on another device")


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
