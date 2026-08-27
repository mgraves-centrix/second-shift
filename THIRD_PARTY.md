# Third-Party Components

Second Shift's own source is Apache 2.0 (see [LICENSE](LICENSE)). The models and
services it invokes carry their own terms, which the Apache license does not
supersede.

Model weights are never vendored into this repository. They are downloaded at
setup time and governed by the license attached to each model card. Verify the
card at install time — terms change.

## Models

| Component | Source | License | Commercial use |
|---|---|---|---|
| Nemotron 3.5 Lightning 30B A3B (NVFP4 / BF16 / DSpark) | NVIDIA | OpenMDW-1.1 | yes |
| Nemotron 3 Super 120B A12B | NVIDIA, via Nebius Token Factory | verify at model card | verify |
| Nemotron 3 Ultra 550B A55B | NVIDIA, via Nebius Token Factory | verify at model card | verify |
| `nemotron-speech-streaming-en-0.6b` | NVIDIA | verify at model card | verify |
| Parakeet Realtime EOU | NVIDIA | verify at model card | verify |
| `llama-nemotron-embed-vl-1b-v2` | NVIDIA | NVIDIA Open Model License | yes |
| `llama-nemotron-rerank-1b-v2` | NVIDIA | NVIDIA Open Model License + Llama 3.2 Community License | yes |
| MagpieTTS | NVIDIA NeMo Speech | verify at model card | verify |

**Not used:** NV-Embed-v2 — CC-BY-NC-4.0 (non-commercial). Replaced by
`llama-nemotron-embed-vl-1b-v2`, which does the same job from the same vendor at
roughly a fifth the parameter count under a commercial-use license.

## Services

| Service | Role |
|---|---|
| Nebius Token Factory | Hosted Nemotron inference |
| Nebius Serverless Jobs | Parallel build-variant execution |
| Tavily | Web search, extract, crawl, research |
| Tailscale | Private network transport and TLS termination |

## Frameworks

Standard open-source dependencies — vLLM, NeMo, FastAPI, Next.js, SQLite,
PyTorch — under their respective licenses. See the lockfiles for the resolved
set.

## Note on the honest boundary

Model licenses govern the model, not this repository's code. Apache 2.0 here is
accurate. But a downstream user who deploys Second Shift inherits every model
license in the table above, so the table is maintained rather than assumed —
that is what makes the Apache header truthful in practice instead of only on
paper.
