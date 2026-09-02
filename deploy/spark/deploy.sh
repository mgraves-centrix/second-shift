#!/usr/bin/env bash
# Deploy the capture app to the Spark.
#
# Runs from the repository root on the development machine. COPYFILE_DISABLE is
# not optional: macOS tar emits AppleDouble sidecars that match the *.sql and
# *.py globs, and they break migration discovery and the source scan.
#
# `uv run` is never used on the target — it re-resolves the environment to
# x86_64 and destroys it.
set -euo pipefail

# No defaults: a deployment target is environment, and environment does not
# belong in a public repository. Set these, or the script refuses.
: "${SPARK_HOST:?set SPARK_HOST to the target host or IP}"
: "${SPARK_USER:?set SPARK_USER to the account to deploy as}"
HOST="${SPARK_HOST}"
USER_NAME="${SPARK_USER}"
REMOTE="${SPARK_PATH:-/home/${USER_NAME}/second-shift}"

# The rubric is the one file under config/ whose content hash is recorded in the
# database — `eval_runs.rubric_sha` pins a measurement to it. The transfer below
# does `rm -rf` on the target tree, so a rubric edited only on the target is
# destroyed here with nothing printed, silently changing the rubric under a
# pinned baseline. Compare before anything is built or destroyed.
RUBRIC="config/evals/rubric.md"

sha256_of() {
    # Not `sha256sum` alone: this script runs on macOS, which ships `shasum`.
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | cut -d' ' -f1
    else
        shasum -a 256 "$1" | cut -d' ' -f1
    fi
}

LOCAL_RUBRIC_SHA="$(sha256_of "${RUBRIC}")"
# Reports a hash or the literal `absent`, never nothing: an indeterminate answer
# fails the ssh under `set -e` rather than reading as "no rubric there".
REMOTE_RUBRIC_SHA="$(ssh "${USER_NAME}@${HOST}" "
    set -eu
    if [ ! -f '${REMOTE}/${RUBRIC}' ]; then
        echo absent
    elif command -v sha256sum >/dev/null 2>&1; then
        sha256sum '${REMOTE}/${RUBRIC}' | cut -d' ' -f1
    else
        shasum -a 256 '${REMOTE}/${RUBRIC}' | cut -d' ' -f1
    fi
")"

if [ "${REMOTE_RUBRIC_SHA}" != "absent" ] \
   && [ "${REMOTE_RUBRIC_SHA}" != "${LOCAL_RUBRIC_SHA}" ]; then
    if [ -z "${SECOND_SHIFT_RUBRIC_OVERWRITE:-}" ]; then
        echo "refusing to deploy: the target's rubric is not the one being shipped." >&2
        echo "  on the target  ${REMOTE_RUBRIC_SHA:0:12}" >&2
        echo "  being shipped  ${LOCAL_RUBRIC_SHA:0:12}" >&2
        echo "This deploy would delete the target's copy, and any eval run pinned to" >&2
        echo "it would then be scored against a rubric it never used. Retrieve it:" >&2
        echo "  scp ${USER_NAME}@${HOST}:${REMOTE}/${RUBRIC} ./rubric-from-target.md" >&2
        echo "then reconcile with: python -m secondshift.evals status" >&2
        echo "A rubric is superseded, never edited in place. To replace it anyway:" >&2
        echo "  SECOND_SHIFT_RUBRIC_OVERWRITE=1 $0" >&2
        exit 1
    fi
    echo "override set: replacing the target's rubric ${REMOTE_RUBRIC_SHA:0:12}" \
         "with ${LOCAL_RUBRIC_SHA:0:12}"
fi

echo "building the web export..."
NEXT_PUBLIC_API_BASE="" npm --prefix apps/web run build >/dev/null

echo "shipping to ${USER_NAME}@${HOST}:${REMOTE}..."
COPYFILE_DISABLE=1 tar czf - \
    --exclude='.venv' --exclude='node_modules' --exclude='__pycache__' \
    --exclude='*.pyc' --exclude='.next' \
    apps/api apps/web/out packages config deploy \
  | ssh "${USER_NAME}@${HOST}" "rm -rf ${REMOTE} && mkdir -p ${REMOTE} && tar xzf - -C ${REMOTE}"

echo "installing..."
ssh "${USER_NAME}@${HOST}" "
  set -euo pipefail
  cd ${REMOTE}/apps/api
  python3 -m venv .venv
  ./.venv/bin/pip install -q --upgrade pip
  ./.venv/bin/pip install -q -e . -c constraints.txt
  mkdir -p /home/${USER_NAME}/second-shift-data
"

echo "done. To install the service (needs sudo, so it is not run from here):"
echo "  sudo cp ${REMOTE}/deploy/spark/second-shift-api.service /etc/systemd/system/"
echo "  sudo systemctl daemon-reload && sudo systemctl enable --now second-shift-api"
echo "Then expose it:"
echo "  tailscale serve --bg --https=443 http://127.0.0.1:8080"
