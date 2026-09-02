## 1. Configuration

- [ ] 1.1 Add sampling parameters and the request timeout to the `[local]` block of `config/models.toml`, documenting why temperature is non-zero.
- [ ] 1.2 Read them in `config.py` beside the endpoint and served-model name it already resolves, as one settings value.
- [ ] 1.3 Test: the committed configuration parses and carries an endpoint, a model, and sampling.

## 2. The provider

Depends on group 1.

- [ ] 2.1 Implement `_do_complete` against the OpenAI-compatible chat completions endpoint using the standard library, with no provider SDK.
- [ ] 2.2 Read token counts from the server's usage report, subtracting reasoning tokens from the completion count so the three are disjoint.
- [ ] 2.3 Read a separated reasoning field where the server provides one; return the text unmodified where it does not.
- [ ] 2.4 Carry the server's `finish_reason` on the raw completion.
- [ ] 2.5 Raise a typed error naming the endpoint when it is unreachable, times out, returns an error status, or answers with something that is not a completion — carrying the server's own message where it gave one.
- [ ] 2.6 Test against a stub HTTP server: a completion returns the server's answer and its token counts.
- [ ] 2.7 Test: nested reasoning tokens are not double counted.
- [ ] 2.8 Test: an inline chain-of-thought answer is returned whole.
- [ ] 2.9 Test: unreachable, timeout, error status and malformed response each raise, and each classifies to the intended failure type.

## 3. Telemetry for the failure path

Independent of group 2; may run in parallel.

- [ ] 3.1 Record a classified failure when a backend raises, in every provider interface, and re-raise.
- [ ] 3.2 Record a warning event when a completion did not stop cleanly, naming the reason.
- [ ] 3.3 Test: a raising backend records a classified failure and the exception still reaches the caller.
- [ ] 3.4 Test: a failed completion writes no model call row.
- [ ] 3.5 Test: a truncated completion records a warning; a clean stop records none.

## 4. Binding

Depends on groups 1-3.

- [ ] 4.1 Bind the vLLM reasoner on local profiles in the registry, reading the configured endpoint and model; leave `cloud` on the placeholder.
- [ ] 4.2 Refuse a local binding when no served-model name is configured, rather than falling back to an echo.
- [ ] 4.3 Update the two tests that bind `spark` to run against the stub server, so the day-1 gate proves the wiring through a real request.
- [ ] 4.4 Test: the source scan still finds no model identifier or provider SDK outside the providers package.

## 5. Supervising the server

Independent of groups 1-4.

- [ ] 5.1 Add a systemd unit that runs the verified Spike B container in the foreground under systemd supervision, publishing the container port on the port configuration allocates to the local reasoner.
- [ ] 5.2 Add the user-service variant, matching the pattern the API unit already establishes.
- [ ] 5.3 Allow a start long enough for the model to load from a warm cache, and restart on exit.
- [ ] 5.4 Test: the units parse, name the allocated port, and carry no environment detail.

## 6. Documentation and gates

- [ ] 6.1 Record in `docs/MODELS.md` that the served port is the allocated one rather than the spike's, and note the reasoning-parser option as unverified.
- [ ] 6.2 Mark `local-inference` shipped in the roadmap, with what remains unverified.
- [ ] 6.3 Gate: full Python suite passes.
- [ ] 6.4 Gate: web tests and typecheck pass, unchanged.
- [ ] 6.5 Gate: `openspec validate --strict` for this change and every canonical spec.
- [ ] 6.6 Gate: both check scripts pass.
- [ ] 6.7 Gate: the new tests fail with the implementation reverted.
