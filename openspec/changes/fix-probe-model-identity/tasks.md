## 1. Probe identity check

- [x] 1.1 Add the expected local model identifier to configuration, defaulting to the local Nemotron binding, overridable by environment variable.
- [x] 1.2 Extend the endpoint check to query the served model list over the OpenAI-compatible route, with a short timeout that cannot stall startup.
- [x] 1.3 Report available only when a served identifier matches the expected one. Report unavailable with a reason naming what was found otherwise.
- [x] 1.4 Treat a connectable endpoint that does not answer the identity query as unavailable, not as present.
- [x] 1.5 Keep the check independent: an identity failure degrades the profile exactly as an unreachable endpoint does, and never raises.

## 2. Tests

- [x] 2.1 Test: a stub endpoint serving the expected model reports available.
- [x] 2.2 Test: a stub endpoint serving a different model reports unavailable, and the reason names both the found and expected identifiers.
- [x] 2.3 Test: a socket that accepts but never answers reports unavailable within the timeout rather than hanging.
- [x] 2.4 Test: an endpoint returning malformed output reports unavailable rather than raising.
- [x] 2.5 Test: with an unexpected model present, the profile resolves to `cloud` and `local-only` is reported unavailable with that reason.
- [x] 2.6 Regression: an unreachable endpoint behaves exactly as before.

## 3. Verification

- [x] 3.1 Full suite green locally.
- [x] 3.2 Run against the Spark with nothing on the port, confirming unavailable.
- [x] 3.3 Run against the Spark with the Qwen container temporarily started, confirming the probe now refuses it by name. Stop it again afterwards.
- [x] 3.4 `openspec validate --strict` for the change and all canonical specs.
