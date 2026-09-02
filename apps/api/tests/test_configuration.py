"""The resolved view, its provenance, and the scan that keeps it honest.

The enumeration test is the load-bearing one. This capability decayed into
existence: `docs/prompts/CONFIGURATION.md` was written on 2 Sep saying "ten
`SECOND_SHIFT_*` variables" and listing ten, while `retrieval` had already added
three the same day. Nothing noticed, because nothing was looking. The test below
looks.

Its mutation was run: adding `os.environ.get("SECOND_SHIFT_THROWAWAY")` to
`secondshift/brain/repo.py` turns `test_every_variable_read_anywhere_is_registered`
red, naming `SECOND_SHIFT_THROWAWAY`. Removing it turns the suite green again.
The registry cannot silently fall behind the tree.
"""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

import pytest

from secondshift import config
from secondshift.api import location
from secondshift.config import (
    SETTINGS,
    Origin,
    UnrecognizedFlagValue,
    resolve_all,
    synthetic_flag,
)
from secondshift.config_cli import show
from secondshift.telemetry.pricing import MissingRate, PricingTable

REPO_ROOT = Path(config.__file__).resolve().parents[3]
PACKAGE = Path(config.__file__).resolve().parent

#: Where a `SECOND_SHIFT_*` read can legitimately live. `deploy/` and `scripts/`
#: are included because a view that only covers Python is a view with a hole in
#: it — `SECOND_SHIFT_RUBRIC_OVERWRITE` is read by shell and nothing else.
SCANNED = (PACKAGE, REPO_ROOT / "deploy", REPO_ROOT / "scripts")

_VARIABLE = re.compile(r"SECOND_SHIFT_[A-Z_]+")


def _variables_in_tree() -> set[str]:
    found: set[str] = set()
    for root in SCANNED:
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".sh"} or "__pycache__" in path.parts:
                continue
            found.update(_VARIABLE.findall(path.read_text()))
    return found


class TestTheRegistryCannotFallBehind:
    def test_every_variable_read_anywhere_is_registered(self):
        """Add a variable without registering it and this goes red.

        Scanned rather than listed, because a list in a test is a second copy of
        the thing under test and drifts with it.
        """
        registered = {s.name for s in SETTINGS}
        unregistered = _variables_in_tree() - registered

        assert not unregistered, (
            f"read in the tree but absent from config.SETTINGS: "
            f"{sorted(unregistered)}"
        )

    def test_the_registry_names_nothing_the_tree_does_not_read(self):
        """The other direction. A setting nobody reads is a setting that lies."""
        registered = {s.name for s in SETTINGS}

        assert not registered - _variables_in_tree()

    def test_the_scan_actually_finds_something(self):
        """A vacuous scan would pass forever, which is how this decayed before."""
        assert len(_variables_in_tree()) >= 13

    def test_the_shell_only_variable_is_present_and_marked(self):
        """A Python-only view has a hole exactly the shape of this variable."""
        overwrite = config.by_name("SECOND_SHIFT_RUBRIC_OVERWRITE")

        assert overwrite.shell_only
        assert "deploy" in overwrite.read_by


class TestProvenance:
    def test_environment_beats_file_beats_default(self, monkeypatch, tmp_path):
        """All three layers asserted, and the reported origin with each.

        Asserting only the value would pass against a view that reports every
        origin as `default`, which is the failure this whole capability exists
        to prevent.
        """
        monkeypatch.setenv(config.ENV_LOCAL_PORT, "9999")
        from_env = _row(config.ENV_LOCAL_PORT)
        assert from_env.value == "9999"
        assert from_env.origin is Origin.ENVIRONMENT

        monkeypatch.delenv(config.ENV_LOCAL_PORT)
        from_file = _row(config.ENV_LOCAL_PORT)
        assert from_file.value == "8200"
        assert from_file.origin is Origin.FILE
        assert from_file.source_path == config._MODELS_CONFIG

        empty = tmp_path / "models.toml"
        empty.write_text("")
        monkeypatch.setattr(config, "_MODELS_CONFIG", empty)
        from_default = _row(config.ENV_LOCAL_PORT)
        assert from_default.value == "8000"
        assert from_default.origin is Origin.DEFAULT

    def test_a_file_sourced_value_names_the_file(self):
        """A reader on the always-on machine fixes it without opening a `.py`."""
        row = _row(config.ENV_EMBEDDER_MODEL)

        assert row.origin is Origin.FILE
        assert row.where.endswith("config/models.toml")

    def test_the_default_database_path_matches_the_one_the_app_uses(self):
        """`config.py` cannot import `api.main` — that would drag FastAPI into
        the one command that must run when nothing else does. So the value is
        duplicated, and this is what stops the two copies drifting."""
        from secondshift.api.main import DEFAULT_DB

        assert str(config._default_db_path()) == DEFAULT_DB


class TestSecretsAreRedacted:
    def test_a_secret_shaped_name_is_not_printed(self, monkeypatch):
        """Nothing here is a credential today. `nebius-executor` changes that,
        and a diagnostic that prints a key once is one nobody runs twice."""
        secret = config.Setting("SECOND_SHIFT_NEBIUS_KEY", "future", "a credential")
        resolved = config.Resolved(secret, "sk-not-a-real-key", Origin.ENVIRONMENT)

        assert resolved.display == config.REDACTED
        assert "not-a-real-key" not in resolved.display

    def test_presence_and_origin_survive_redaction(self):
        """Redaction must not cost the operator the two facts they need."""
        secret = config.Setting("SECOND_SHIFT_A_TOKEN", "future", "a credential")
        resolved = config.Resolved(secret, "value", Origin.ENVIRONMENT)

        assert resolved.where == "environment"

    def test_an_ordinary_name_is_printed_in_full(self):
        assert not config.by_name(config.ENV_LOCAL_PORT).secret


class TestMalformedIsNotAbsent:
    def test_a_malformed_models_file_names_itself(self, monkeypatch, tmp_path):
        bad = tmp_path / "models.toml"
        bad.write_text("this is not = = valid toml [[[")
        monkeypatch.setattr(config, "_MODELS_CONFIG", bad)

        assert "models.toml" in config.models_config_error()
        assert "malformed" in config.models_config_error()

    def test_an_absent_models_file_is_not_an_error(self, monkeypatch, tmp_path):
        """Absent is a legitimate deployment state. Only malformed is not."""
        monkeypatch.setattr(config, "_MODELS_CONFIG", tmp_path / "nope.toml")

        assert config.models_config_error() is None
        assert config.local_endpoint() == ("127.0.0.1", 8000)

    def test_the_probe_blames_the_file_rather_than_the_network(
        self, monkeypatch, tmp_path
    ):
        """The defect this capability exists to end.

        Before: an operator mistypes `models.toml`, redeploys, and the probe
        says the endpoint is unreachable. They then debug a network that is
        fine. The finding has to name the real cause.
        """
        bad = tmp_path / "models.toml"
        bad.write_text("[local\nreasoner_port =")
        monkeypatch.setattr(config, "_MODELS_CONFIG", bad)

        finding = config._check_endpoint("127.0.0.1", 8200)

        assert not finding.available
        assert "models.toml" in finding.detail
        assert "unreachable" not in finding.detail

    def test_a_malformed_models_file_does_not_stop_the_api_starting(
        self, monkeypatch, tmp_path
    ):
        """Capture never reads this file and must not go down with it.

        A mistyped model name costing captures that cannot be recovered is a
        worse failure than the one being fixed.
        """
        bad = tmp_path / "models.toml"
        bad.write_text("nonsense = = =")
        monkeypatch.setattr(config, "_MODELS_CONFIG", bad)

        resolved = config.resolve_profile(probe_result=config.ProbeResult())

        assert resolved.profile is config.Profile.CLOUD

    def test_a_malformed_location_file_is_distinguishable_from_an_absent_one(
        self, tmp_path
    ):
        bad = tmp_path / "location.toml"
        bad.write_text("[home\nlat = ")

        assert location.location_config_error(bad) is not None
        assert location.location_config_error(tmp_path / "gone.toml") is None
        # Still degrades rather than raising: the celestial layer is optional.
        assert location.home_location(bad) == location.Home(None, None)

    def test_a_malformed_pricing_file_names_the_file(self, tmp_path):
        """This one raises, unlike the others, because a missing rate already
        does: the cost curve is a scored measurement and a silent zero
        understates it in the direction that flatters the project."""
        bad = tmp_path / "pricing.toml"
        bad.write_text("[[rate]\nprovider =")

        with pytest.raises(MissingRate, match="pricing.toml is malformed"):
            PricingTable.load(bad)

    def test_a_missing_pricing_file_still_names_the_path(self, tmp_path):
        with pytest.raises(MissingRate, match="not found at"):
            PricingTable.load(tmp_path / "gone.toml")


class TestTheSyntheticFlagRefusesToGuess:
    @pytest.mark.parametrize("raw", ["1", "true", "TRUE", "yes", "on"])
    def test_recognized_true_spellings(self, raw):
        assert synthetic_flag({config.ENV_SYNTHETIC: raw}) is True

    @pytest.mark.parametrize("raw", ["", "0", "false", "no", "off"])
    def test_recognized_false_spellings(self, raw):
        assert synthetic_flag({config.ENV_SYNTHETIC: raw}) is False

    def test_unset_is_false(self):
        assert synthetic_flag({}) is False

    def test_a_typo_raises_rather_than_meaning_real_data(self):
        """`SYNTHETIC=ture` resolving to false writes seed rows that no later
        measurement can tell apart from real ones. Principle 7 is why this is
        the one setting that refuses."""
        with pytest.raises(UnrecognizedFlagValue, match="neither true nor false"):
            synthetic_flag({config.ENV_SYNTHETIC: "ture"})

    def test_the_refusal_names_what_it_accepts(self):
        with pytest.raises(UnrecognizedFlagValue) as caught:
            synthetic_flag({config.ENV_SYNTHETIC: "maybe"})

        assert "true" in str(caught.value) and "false" in str(caught.value)

    def test_the_view_reports_a_bad_value_instead_of_raising(self, monkeypatch):
        """The point of a diagnostic is to answer when something is wrong. A
        traceback here would hide the other twelve settings."""
        monkeypatch.setenv(config.ENV_SYNTHETIC, "ture")

        row = _row(config.ENV_SYNTHETIC)

        assert row.error is not None
        assert row.value == "ture"


class TestItRunsWhenNothingElseDoes:
    def test_no_database_no_brain_no_files_no_network(self, monkeypatch, tmp_path):
        """Diagnosis that needs the thing being diagnosed is a second failure."""
        for setting in SETTINGS:
            monkeypatch.delenv(setting.name, raising=False)
        monkeypatch.setattr(config, "_MODELS_CONFIG", tmp_path / "absent.toml")

        rows = resolve_all()

        assert len(rows) == len(SETTINGS)
        assert all(r.origin is Origin.DEFAULT for r in rows)

    def test_it_opens_no_database(self, monkeypatch, tmp_path):
        """Principle 7 is not implicated and must stay that way: resolving
        configuration is neither an agent invocation nor a model call, so it
        opens no row — and a write in the one command that has to work when the
        database is missing is a write that defeats the command."""
        import sqlite3

        def refuse(*args, **kwargs):
            raise AssertionError("resolve_all opened a database connection")

        monkeypatch.setattr(sqlite3, "connect", refuse)

        resolve_all()

    def test_the_command_runs_in_a_subprocess_with_an_empty_environment(self):
        """The real entry point, not the function behind it."""
        completed = subprocess.run(
            [sys.executable, "-m", "secondshift.config", "show"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT / "apps" / "api",
            env={"PATH": "/usr/bin:/bin", "HOME": "/tmp"},
        )

        assert completed.returncode == 0, completed.stderr
        assert "SECOND_SHIFT_DB" in completed.stdout


class TestTheExitCode:
    def test_zero_when_everything_resolved(self, capsys):
        assert show(["show"]) == 0

    def test_non_zero_on_a_malformed_file(self, monkeypatch, tmp_path, capsys):
        """Non-zero is what lets a deploy gate on this."""
        bad = tmp_path / "models.toml"
        bad.write_text("= = =")
        monkeypatch.setattr(config, "_MODELS_CONFIG", bad)

        assert show(["show"]) == 1
        assert "models.toml" in capsys.readouterr().out

    def test_the_output_names_every_setting(self, capsys):
        show(["show"])
        printed = capsys.readouterr().out

        for setting in SETTINGS:
            assert setting.name in printed


def _row(name: str):
    return next(r for r in resolve_all() if r.setting.name == name)
