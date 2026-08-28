# Spike B — serving Nemotron 3.5 Lightning on the Spark

**Question:** does vLLM serve Nemotron 3.5 Lightning NVFP4 on the DGX Spark at
usable concurrency?

Findings recorded as hit, 2026-08-27/28.

## Environment

| | |
|---|---|
| Image | `vllm/vllm-openai:v0.27.1` — **has a linux/arm64 build**, confirmed |
| Checkpoint | `nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4` — public, not gated, 52 shards, ~21 GB |
| Host | Ubuntu 24.04, aarch64, 121 GiB unified, 3.1 TB free |
| GPU access | `--gpus all` works; the existing Qwen container used a CDI device request, but the standard flag is sufficient |

The NVIDIA vLLM image already on the box (`nvcr.io/nvidia/vllm:26.07-py3`) ships
**vLLM 0.24.0**, below the 0.27.1 the recipe requires. No newer `nvcr.io` tag
was published at the time of the spike. The Docker Hub `vllm/vllm-openai:v0.27.1`
image is the working route, and it does build for arm64.

## The published quick-start command does not run on the version it names

The model card gives this for DGX Spark:

```
vllm serve --model $MODEL_CKPT --moe-backend marlin --kv-cache-dtype fp8 \
  --enable-prefix-caching --gpu-memory-utilization 0.85 \
  --speculative_config.num_speculative_tokens 3
```

It failed twice, for two unrelated reasons.

### 1. Speculative config is incomplete

```
ValidationError: 1 validation error for SpeculativeConfig
  Value error, num_speculative_tokens was provided but without speculative model.
```

`num_speculative_tokens` alone is rejected — 0.27.1 requires a method. Supplying
`--speculative-config '{"method":"mtp","num_speculative_tokens":3}'` gets past
it. MTP is built into the checkpoint, so no separate draft model is needed.

### 2. `--moe-backend marlin` is rejected for this checkpoint

```
ValueError: moe_backend='marlin' is not supported for unquantized MoE.
  Expected one of ['triton', 'batched_triton', 'flashinfer_trtllm', 'flashinfer_...']
```

"Unquantized" is misleading. vLLM detects the quantization correctly — the log
shows **four** schemes in one checkpoint:

```
Detected ModelOpt fp8 checkpoint (quant_algo=FP8)
Detected ModelOpt NVFP4 checkpoint (quant_algo=NVFP4)
Detected ModelOpt NVFP4 checkpoint (quant_algo=W4A16_NVFP4)
Detected ModelOpt MXFP8 checkpoint
```

`model_type` is `nemotron_h`, the hybrid Mamba-MoE. `config.json` shows the
Mamba mixer projections quantized to FP8 while the MoE experts carry NVFP4. The
marlin kernel wants a scheme the MoE weights do not present, so it refuses.

Dropping `--moe-backend` and letting vLLM select is the next rung.

## Why this matters beyond the spike

Both failures are in a first-party quick-start for this exact hardware, on the
exact image version it names. The day-4 plan assumed the recipe's existence made
this low-risk, which was right about *feasibility* and wrong about
*friction* — the risk was never that it could not work, it was that the
published path is stale. Budget configuration time for any first-party recipe,
not just for unproven ones.

## The command that works

```bash
docker run -d --name nemotron-lightning \
  --gpus all --ipc=host --shm-size=8g \
  -v $HOME/.cache/huggingface:/root/.cache/huggingface \
  -p 8000:8000 \
  vllm/vllm-openai:v0.27.1 \
  nvidia/NVIDIA-Nemotron-3.5-Lightning-30B-A3B-NVFP4 \
  --served-model-name nemotron-3.5-lightning \
  --host 0.0.0.0 --port 8000 \
  --kv-cache-dtype fp8 --enable-prefix-caching \
  --gpu-memory-utilization 0.30 \
  --max-model-len 65536 --max-num-seqs 8 \
  --speculative-config '{"method":"mtp","num_speculative_tokens":3}'
```

Differences from the published recipe: no `--moe-backend marlin`, a full
speculative config with `method`, and a much lower memory ceiling.

## Results

| | 3 concurrent | 6 concurrent |
|---|---|---|
| Succeeded | 9/9 | 6/6 |
| tokens/sec, median | 48.6 | 39.8 |
| Latency, median | 5.3s | 6.4s |

Load time from a warm HuggingFace cache is roughly three minutes.

## `--gpu-memory-utilization` is the finding that matters

On unified memory that flag takes a fraction of **the whole machine**, and vLLM
fills the remainder with KV cache. The published `0.85`:

- 112 of 121 GiB consumed, 9 GiB left
- KV cache sized at **4,608,737 tokens**

That is a KV cache for a workload nobody has. At `0.30` with a 65,536-token
context limit:

- 43 of 121 GiB consumed, **77 GiB left**
- KV cache 631,852 tokens, 9.64x maximum concurrency
- Measurably *faster* at 3 concurrent — 48.6 tok/s against 43.8

Co-residency with ASR and the embedder was the whole argument for NVFP4, and at
`0.85` there is no room for either. The weights are about 21 GB; everything else
was cache nobody asked for.

## Probe verified end to end against the real server

```
cuda: available
local_reasoner: available
speech_stack: speech stack 'nemo' not importable
profile: workstation | degraded: False
local-only available: True
```

`workstation` rather than `spark` is correct: the local stack is complete except
the speech stack, which is day 6. It becomes `spark` when NeMo lands. Profile
resolution was written before any of this hardware ran, and reality agrees with
it.

## Two things for later

**The model emits visible chain-of-thought.** Every reply begins "Here's a
thinking process:". Agent prompts must account for it, and the distinction
between reasoning and answer tokens matters for both cost and for what gets
shown in a brief.

**Port 8000 is contested.** The stopped Qwen container claims it too. Whichever
starts first wins, and the probe now refuses the wrong one by name rather than
serving it — but the collision should be designed away, not relied on the probe
to catch.
