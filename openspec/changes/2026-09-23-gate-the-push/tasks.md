# Tasks — gate the push

- [x] 1.1 `.githooks/pre-push`, refusing on any non-zero gate exit and naming
      `--no-verify`.
- [x] 1.2 A deletion is not gated.
- [x] 1.3 Tests: refuses on red, proceeds on green, skips a deletion. Against a
      stubbed gate — the hook's job is propagating an exit code, and re-running
      the real gate would test the gate.
- [x] 1.4 `docs/development/GATES.md`: the enabling line, the cost, and the
      override.
- [x] 1.5 `python3 scripts/gate.py` green, run so its exit status is its own.
- [x] 1.6 Sync, archive.
