# Spike C — MagpieTTS on the Spark

**Question:** does MagpieTTS run on the Spark's aarch64 + Blackwell stack, and
which voices ship with it?

**Answer: yes, and five.** Findings recorded as hit, 2026-08-28.

## Result

All five voices synthesized on GB10, faster than real time, while the
`nemotron-lightning` vLLM container stayed up.

| Voice | Index | Generate | Audio | RTF |
|---|---|---|---|---|
| Aria | 0 | 4.14s | 7.29s | 0.567 |
| Jason | 1 | 3.23s | 7.38s | 0.437 |
| John | 2 | 3.80s | 8.64s | 0.440 |
| Leo | 3 | 3.33s | 7.52s | 0.442 |
| Sofia | 4 | 3.24s | 7.48s | 0.434 |

Output is 22.05 kHz mono 16-bit PCM. First call carries ~0.9s of warm-up; the
steady-state RTF is ~0.44, so a 60-second briefing costs ~26 seconds of GPU.
Weights occupy **1.85 GB** — trivial against the 77 GiB the `0.30`
`--gpu-memory-utilization` split leaves free.

**Not yet verified: whether it sounds good.** RTF and peak amplitude prove it
emitted real audio, not silence. Intelligibility and prosody need a human ear
before a voice is bound as the briefing default.

## The voices are fixed, and there are exactly five

Read from `speakers.json` inside the `.nemo` archive, not from the model card:

```json
{"Aria": 0, "Jason": 1, "John": 2, "Leo": 3, "Sofia": 4}
```

Selection is `speaker_index`, an int. **No reference audio is required or
accepted** — these are fixed speaker context embeddings, so there is no voice
cloning here and no way to add a sixth voice without finetuning. Anything in
the settings model that implies an open-ended voice list is modeling a
capability the checkpoint does not have.

14 language tags: `ar-AE ar-MSA ar-SA de en es fr hi it ja ko pt-BR vi zh`.

```python
model.do_tts(transcript, language="en", apply_TN=False,
             use_cfg=True, speaker_index=4)
```

## Environment

| | |
|---|---|
| Checkpoint | `nvidia/magpie_tts_multilingual_357m` — public, **not gated**, no HF token |
| Codec | `nvidia/nemo-nano-codec-22khz-1.89kbps-21.5fps`, pulled automatically |
| NeMo | `3.1.0+6281c939a` from `git+https://github.com/NVIDIA/NeMo.git@main` |
| Torch | `2.13.0+cu130`, aarch64 wheel, `cuda True`, `NVIDIA GB10` |
| Python | 3.12 (conda-forge) |

## Four things that broke

### 1. The ASR spike has not run, so this stack had no head start

`docs/WEEK_ONE.md` justified the half-day box on the grounds that MagpieTTS
"shares the ASR dependency stack the ASR spike already installs." The Spark has
no NeMo, no torch and no CUDA toolkit outside the two running containers. This
spike paid the full dependency cost. **The saving is real but it runs the other
way — the ASR spike now inherits a working NeMo 3.1.0 aarch64 env from this one.**

### 2. `pyopenjtalk` has no aarch64 wheel and the host has no Python headers

```
pyopenjtalk/openjtalk.cpp:124:10: fatal error: Python.h: No such file or directory
```

`nemo_toolkit[tts]` pulls `pyopenjtalk` (Japanese G2P) unconditionally, even for
English-only use. There is no aarch64 wheel, so pip builds from source, and the
Spark has `build-essential` but not `python3-dev`. The clean fix is
`sudo apt install python3.12-dev` — **sudo on the Spark requires a password**, so
this spike used a conda-forge Python instead, which ships its own headers and
needs no root. Either route works; the conda route leaves the host untouched.

### 3. Miniforge defaults to Python 3.14, which NeMo's dependencies reject

```
ERROR: Could not find a version that satisfies the requirement
  nv_one_logger_pytorch_lightning_integration>=2.3.1
```

The ceiling is `<3.14`. Pin `python=3.12` explicitly when creating the env —
the default is now past the edge of what NeMo supports.

### 4. `MagpieTTSModel` needs `peft`, which `nemo_toolkit[tts]` does not pull

`ModuleNotFoundError: No module named 'peft'` on import, not at call time.
`pip install peft` fixes it. Missing from the extra's dependency set.

## The model card understates the hardware

It lists Ada, Ampere and Hopper as supported, and does not mention Blackwell,
GB10, or aarch64 at all. It works anyway, on all three counts. Treat the card's
hardware list as untested-elsewhere rather than as a constraint.

## What this changes

- TTS is no longer a week-3 gamble. It is a verified dependency with a known
  cost, so the assistant half of the interview visualization is unblocked.
- The voice setting in `docs/prompts/OVERNIGHT.md` is now data entry against a
  closed set of five, not a placeholder for an unknown.
- **Text-first still holds.** Nothing here argues for putting TTS on a critical
  path; it argues that the fallback will rarely be needed.

## Reproducing

`bootstrap.sh` builds the env, `synth.py` runs the gate. Both assume
`$HOME/spikes/tts-magpie` on the Spark. Add `pip install peft soundfile`
between them — folded into neither script because both were run as-hit.

## Footprint left on the Spark

`~/spikes/tts-magpie` — 12 GB, of which `env312` is 6.3 GB and the conda base is
5.4 GB. Model weights add 1.8 GB in the shared HF cache. The dead rung-1 venv
and the Miniforge installer were removed. Remove the rest with:

```
rm -rf ~/spikes/tts-magpie
```

The conda base is only still there because `env312/compiler_compat/ld` points
into it; nothing at runtime does. Deleting the base leaves `env312` working —
conda hardlinks survive it — but breaks future source builds in that env.
