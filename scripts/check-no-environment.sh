#!/usr/bin/env bash
# Refuse to let environment details into a public repository.
#
# The repo is public. Hostnames, tailnet names, private addresses, usernames and
# home paths are not credentials, but they are nobody's business and they
# accumulate silently — five files had collected them within a day of going
# public.
#
# Run before a push, or wire it into a pre-commit hook.
set -uo pipefail
cd "$(git rev-parse --show-toplevel)"

PATTERNS=(
  '192\.168\.[0-9]+\.[0-9]+'          # private IPv4
  '10\.[0-9]+\.[0-9]+\.[0-9]+'
  '172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+'
  '100\.[0-9]+\.[0-9]+\.[0-9]+'       # tailnet CGNAT range
  '[a-z0-9-]+\.tail[a-z0-9]+\.ts\.net' # real tailnet hostnames
  '/home/[a-z][a-z0-9_-]+'            # someone's home directory
  '/Users/[a-z][a-z0-9_-]+'
)

status=0
for pattern in "${PATTERNS[@]}"; do
  # Placeholders are the point of this check, so they are not findings.
  hits=$(git grep -InE "$pattern" -- . ':!package-lock.json' ':!scripts/check-no-environment.sh' 2>/dev/null \
         | grep -vE '<host>|<tailnet>|<spark-host>|REPLACE_USER|\$HOME|\$\{?USER' || true)
  if [ -n "$hits" ]; then
    echo "environment detail found ($pattern):"
    echo "$hits" | sed 's/^/  /'
    status=1
  fi
done

[ $status -eq 0 ] && echo "clean: no environment details in tracked files"
exit $status
