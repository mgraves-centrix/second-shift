"""Profile resolution, the capability report, and quarantine."""

from __future__ import annotations

import pytest

from secondshift.db.connection import now_ms

from secondshift.airlock.capability import build_report
from secondshift.airlock.policy import Policy, PolicySource, resolve_policy
from secondshift.airlock.quarantine import Quarantine
from secondshift.config import (
    CUDA,
    LOCAL_REASONER,
    SPEECH_STACK,
    Capability,
    ProbeResult,
    Profile,
    ProfileSource,
    resolve_profile,
)


def _probe(cuda: bool, endpoint: bool, speech: bool = True) -> ProbeResult:
    return ProbeResult(
        {
            CUDA: Capability(CUDA, cuda, "nvidia-smi present" if cuda else "no CUDA device detected"),
            LOCAL_REASONER: Capability(
                LOCAL_REASONER,
                endpoint,
                "reachable at 127.0.0.1:8000"
                if endpoint
                else "local reasoner endpoint 127.0.0.1:8000 unreachable",
            ),
            SPEECH_STACK: Capability(SPEECH_STACK, speech, "importable" if speech else "not importable"),
        }
    )


FULL = _probe(True, True)
PARTIAL = _probe(True, False)  # CUDA present, endpoint down
NONE = _probe(False, False, False)


class TestProfileResolution:
    def test_environment_overrides_a_working_local_stack(self):
        resolved = resolve_profile(
            env={"SECOND_SHIFT_PROFILE": "cloud"}, probe_result=FULL
        )
        assert resolved.profile is Profile.CLOUD
        assert resolved.source is ProfileSource.ENVIRONMENT

    def test_no_cuda_and_no_endpoint_resolves_to_cloud(self):
        resolved = resolve_profile(env={}, probe_result=NONE)
        assert resolved.profile is Profile.CLOUD

    def test_full_local_stack_resolves_to_spark(self):
        assert resolve_profile(env={}, probe_result=FULL).profile is Profile.SPARK

    def test_local_stack_without_speech_is_workstation(self):
        resolved = resolve_profile(env={}, probe_result=_probe(True, True, speech=False))
        assert resolved.profile is Profile.WORKSTATION

    def test_partial_stack_degrades_and_startup_proceeds(self):
        resolved = resolve_profile(env={}, probe_result=PARTIAL)
        assert resolved.profile is Profile.CLOUD
        assert resolved.degraded is True

    def test_degradation_findings_are_readable_at_runtime(self):
        resolved = resolve_profile(env={}, probe_result=PARTIAL)
        assert "endpoint" in (resolved.degradation_reason or "")
        # The individual findings survive, not just a summary string.
        assert resolved.probe.available(CUDA) is True
        assert resolved.probe.available(LOCAL_REASONER) is False

    def test_unknown_profile_value_is_rejected(self):
        with pytest.raises(ValueError, match="not one of"):
            resolve_profile(env={"SECOND_SHIFT_PROFILE": "gpu-cluster"})


class TestCapabilityReport:
    def test_unavailable_policy_is_marked_not_omitted(self):
        report = build_report(resolve_profile(env={}, probe_result=NONE))
        assert {a.policy for a in report.policies} == {
            Policy.LOCAL_ONLY,
            Policy.CLOUD_ASSISTED,
        }
        assert report.is_available(Policy.LOCAL_ONLY) is False

    def test_reason_names_the_specific_finding(self):
        report = build_report(resolve_profile(env={}, probe_result=PARTIAL))
        reason = report.reason_for(Policy.LOCAL_ONLY) or ""
        assert "endpoint" in reason
        assert reason != "unavailable on this profile"

    def test_pinned_profile_reason_says_so(self):
        report = build_report(
            resolve_profile(env={"SECOND_SHIFT_PROFILE": "cloud"}, probe_result=FULL)
        )
        assert "pinned" in (report.reason_for(Policy.LOCAL_ONLY) or "")

    def test_local_stack_makes_local_only_available(self):
        report = build_report(resolve_profile(env={}, probe_result=FULL))
        assert report.is_available(Policy.LOCAL_ONLY)
        assert report.reason_for(Policy.LOCAL_ONLY) is None

    def test_cloud_assisted_is_always_available(self):
        for result in (FULL, PARTIAL, NONE):
            report = build_report(resolve_profile(env={}, probe_result=result))
            assert report.is_available(Policy.CLOUD_ASSISTED)


class TestPolicyResolution:
    def test_default_is_carried_through(self):
        resolution = resolve_policy("local-only", available=True)
        assert resolution.effective_policy is Policy.LOCAL_ONLY
        assert resolution.policy_source is PolicySource.ENTRY_DEFAULT
        assert resolution.permitted

    def test_not_widened_without_a_decision(self):
        resolution = resolve_policy("local-only", available=True)
        assert resolution.effective_policy is Policy.LOCAL_ONLY

    def test_widened_only_with_an_attributable_decision(self):
        resolution = resolve_policy(
            "local-only", available=False, upgrade_decision_id="01JDECISION"
        )
        assert resolution.effective_policy is Policy.CLOUD_ASSISTED
        assert resolution.policy_source is PolicySource.DECISION_UPGRADE
        assert resolution.permitted

    def test_unavailable_local_only_is_not_permitted(self):
        resolution = resolve_policy(
            "local-only", available=False, unavailable_reason="endpoint unreachable"
        )
        assert resolution.permitted is False
        assert "endpoint" in (resolution.cause or "")


class TestQuarantine:
    @pytest.fixture
    def queued(self, repo):
        def _add(policy: str) -> str:
            return repo.insert_entry(
                created_at_ms=now_ms(),
                captured_tz="America/Los_Angeles",
                tz_offset_min=-420,
                modality="text",
                default_policy=policy,
                status="queued",
                capture_profile="spark",
                raw_text=f"idea under {policy}",
            )

        return _add

    def test_local_only_quarantined_while_cloud_assisted_dispatches(
        self, repo, queued
    ):
        private = queued("local-only")
        shared = queued("cloud-assisted")
        report = build_report(resolve_profile(env={}, probe_result=PARTIAL))
        quarantine = Quarantine(repo, report)

        assert [s.entry_id for s in quarantine.blocked()] == [private]
        assert [s.entry_id for s in quarantine.dispatchable()] == [shared]

    def test_blocked_entry_carries_its_cause(self, repo, queued):
        queued("local-only")
        quarantine = Quarantine(
            repo, build_report(resolve_profile(env={}, probe_result=PARTIAL))
        )
        assert "endpoint" in (quarantine.blocked()[0].cause or "")

    def test_no_run_is_created_for_a_blocked_entry(self, repo, queued, conn):
        queued("local-only")
        quarantine = Quarantine(
            repo, build_report(resolve_profile(env={}, probe_result=PARTIAL))
        )
        assert quarantine.blocked()
        assert conn.execute("SELECT COUNT(*) n FROM runs").fetchone()["n"] == 0

    def test_release_is_automatic_when_capability_returns(self, repo, queued):
        private = queued("local-only")
        degraded = Quarantine(
            repo, build_report(resolve_profile(env={}, probe_result=PARTIAL))
        )
        assert [s.entry_id for s in degraded.blocked()] == [private]

        # The endpoint comes back. No manual re-entry, no reconciliation job.
        restored = Quarantine(
            repo, build_report(resolve_profile(env={}, probe_result=FULL))
        )
        assert restored.blocked() == []
        assert [s.entry_id for s in restored.dispatchable()] == [private]

    def test_nothing_is_quarantined_on_a_capable_profile(self, repo, queued):
        queued("local-only")
        queued("cloud-assisted")
        quarantine = Quarantine(
            repo, build_report(resolve_profile(env={}, probe_result=FULL))
        )
        assert quarantine.blocked() == []
        assert len(quarantine.dispatchable()) == 2

    def test_quarantined_entry_is_never_silently_downgraded(self, repo, queued):
        queued("local-only")
        quarantine = Quarantine(
            repo, build_report(resolve_profile(env={}, probe_result=PARTIAL))
        )
        blocked = quarantine.blocked()[0]
        assert blocked.resolution.effective_policy is Policy.LOCAL_ONLY
