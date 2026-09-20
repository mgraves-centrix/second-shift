"""What the judge image is allowed to carry.

The image bakes a database in, so it is the one deployment path where the
subject's real data could ship to a public endpoint. `deploy/spark/deploy.sh`
is not that path: it ships code only.

These assert the Dockerfile's shape rather than a built image, and say so.
Building it needs a docker daemon, which this suite does not have — the build
itself is `2026-09-19-add-judge-mode` task 6.4 and is deliberately still open.
What is checked here is everything that can go wrong in the file: a COPY that
names something absent, a COPY widened until it takes the tree, a missing
environment variable, or the package check being dropped.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[3]
DOCKERFILE = ROOT / "deploy" / "judge" / "Dockerfile"
DOCKERIGNORE = ROOT / ".dockerignore"


@pytest.fixture(scope="module")
def dockerfile() -> str:
    return DOCKERFILE.read_text()


def _copies(text: str) -> list[str]:
    """Every source a COPY takes from the build context."""
    sources: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line.startswith("COPY ") or "--from=" in line:
            continue
        parts = line.split()[1:]
        sources.extend(parts[:-1])
    return sources


class TestItTakesOnlyWhatItNames:
    def test_every_copied_path_exists(self, dockerfile):
        """A COPY naming something absent fails the build. Cheap to catch here
        and expensive to find on a runner."""
        for source in _copies(dockerfile):
            assert (ROOT / source).exists(), f"COPY {source} names nothing"

    def test_it_never_copies_the_whole_tree(self, dockerfile):
        """An allowlist stays correct when somebody adds a directory; a
        denylist silently stops being one. `COPY . .` is how the brain arrives
        in an image six months from now."""
        for source in _copies(dockerfile):
            assert source not in {".", "./", "/"}, (
                "the image takes the whole build context, so what it carries is "
                "decided by .dockerignore rather than by this file"
            )

    def test_it_copies_nothing_that_could_hold_real_data(self, dockerfile):
        """The brain is the subject's memory and `data/` holds the payload files
        `model_call_payloads` points at."""
        for source in _copies(dockerfile):
            head = source.strip("./").split("/")[0]
            assert head not in {"data", "brain"}, f"the image copies {source}"
            assert not source.endswith(".db"), f"the image copies a database: {source}"


class TestItIsTheJudgeDeployment:
    def test_it_marks_everything_it_writes_synthetic(self, dockerfile):
        """Without this the seeded persona's rows are indistinguishable from
        real ones, and anything captured against the demo is written as real."""
        assert re.search(r"SECOND_SHIFT_SYNTHETIC=1", dockerfile)

    def test_it_runs_on_the_cloud_profile(self, dockerfile):
        assert re.search(r"SECOND_SHIFT_PROFILE=cloud", dockerfile)

    def test_it_builds_its_night_rather_than_copying_one(self, dockerfile):
        """A seeded database written at build time has no path by which a real
        one reaches the image."""
        assert "secondshift_seed" in dockerfile

    def test_the_package_check_runs_after_the_seed(self, dockerfile):
        """It passes trivially today, because the line above it wrote the
        database from a seed. It is there to catch the day somebody changes
        that line."""
        seed = dockerfile.index("secondshift_seed")
        check = dockerfile.index("check-judge-package.py", seed)

        assert check > seed

    def test_it_does_not_run_as_root(self, dockerfile):
        assert re.search(r"^USER\s+(?!root)", dockerfile, re.M)


class TestTheBuildContextRefusesRealData:
    def test_dockerignore_excludes_databases_and_the_brain(self):
        ignored = {
            line.strip()
            for line in DOCKERIGNORE.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }

        for pattern in ("data", "brain", "**/*.db"):
            assert pattern in ignored, f".dockerignore does not exclude {pattern}"

    def test_dockerignore_does_not_exclude_what_the_image_needs(self, dockerfile):
        ignored = {
            line.strip()
            for line in DOCKERIGNORE.read_text().splitlines()
            if line.strip() and not line.startswith("#")
        }

        for source in _copies(dockerfile):
            assert source not in ignored, (
                f"{source} is both copied and excluded, so the build fails"
            )
