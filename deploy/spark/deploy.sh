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
