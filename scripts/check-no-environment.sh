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
# Resolved from this file, not the caller's directory, and passed to git with
# -C rather than entered: the check runs identically from anywhere.
ROOT="$(git -C "$(dirname "${BASH_SOURCE[0]}")" rev-parse --show-toplevel)"

PATTERNS=(
  '192\.168\.[0-9]+\.[0-9]+'          # private IPv4
  '10\.[0-9]+\.[0-9]+\.[0-9]+'
  '172\.(1[6-9]|2[0-9]|3[01])\.[0-9]+\.[0-9]+'
  '100\.[0-9]+\.[0-9]+\.[0-9]+'       # tailnet CGNAT range
  '[a-z0-9-]+\.tail[a-z0-9]+\.ts\.net' # real tailnet hostnames
  '/home/[a-z][a-z0-9_-]+'            # someone's home directory
  '/Users/[a-z][a-z0-9_-]+'
  '[A-Za-z]:\\{1,2}Users\\{1,2}[a-z][a-z0-9_-]+'  # a Windows profile path, escaped or not
  # A machine named in an ssh invocation. The patterns above catch a tailnet
  # name only in its full `*.tail____.ts.net` form, and MagicDNS means the short
  # name is what anyone actually types. That gap is worse than it looks here:
  # the always-on machine's short name is also this project's compute-profile
  # name, so the leaked token is indistinguishable from a domain term that
  # appears legitimately in hundreds of places. Nothing can catch it by its
  # spelling; this catches it by its position.
  #
  # Anchored to the start of a command so prose about ssh is not a finding. The
  # backtick is in that set because reports are markdown and a command inside
  # one is written inline — `ssh <spark> 'uptime'` — which the first version of
  # this pattern walked straight past. Prose like "the `ssh` under set -e" still
  # does not fire, because a name has to follow whitespace.
  #
  # Deliberately narrow: it does not catch a host that follows flags
  # (`ssh -o ... host`). Use `<spark>` and this never fires.
  '(^|[;&|(`'"'"'"]|\$\()[[:space:]]*ssh[[:space:]]+[a-z0-9]'
)

status=0
for pattern in "${PATTERNS[@]}"; do
  # Placeholders are the point of this check, so they are not findings.
  # --untracked so a file that has not been committed yet is still checked.
  # git grep defaults to tracked files only, which meant a brand-new file passed
  # the check right up until the moment it was added — the one moment it matters.
  hits=$(git -C "$ROOT" grep -InE --untracked "$pattern" -- . ':!package-lock.json' ':!scripts/check-no-environment.sh' 2>/dev/null \
         | grep -vE '<host>|<tailnet>|<spark>|<spark-host>|REPLACE_USER|\$HOME|\$\{?USER' || true)
  if [ -n "$hits" ]; then
    echo "environment detail found ($pattern):"
    echo "$hits" | sed 's/^/  /'
    status=1
  fi
done

[ $status -eq 0 ] && echo "clean: no environment details in tracked or new files"
exit $status
