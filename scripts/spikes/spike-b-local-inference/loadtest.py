"""Spike B pass gate: does the local endpoint hold up at real concurrency?

Answers three things the pass gate names — that N concurrent requests all
succeed, what tokens/sec that yields, and whether the served identity is what we
expect. The last one matters because a reachable endpoint proved insufficient
evidence once already, on this exact port.

Standard library only: it runs inside the vLLM container, which has no
guarantee of anything else.

  python3 loadtest.py --concurrency 3 --expect nemotron-3.5-lightning
"""

from __future__ import annotations

import argparse
import json
import statistics
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

PROMPT = (
    "A user captured this half-formed idea: 'a tool that tells me which of my "
    "recurring meetings could be an email'. Ask the three sharpest questions "
    "you would need answered before building anything."
)


def served_models(base: str, timeout: float = 10.0) -> list[str]:
    with urllib.request.urlopen(f"{base}/v1/models", timeout=timeout) as r:
        return [m["id"] for m in json.load(r).get("data", [])]


def one_completion(base: str, model: str, max_tokens: int, timeout: float) -> dict:
    body = json.dumps(
        {
            "model": model,
            "messages": [{"role": "user", "content": PROMPT}],
            "max_tokens": max_tokens,
            "temperature": 0.7,
        }
    ).encode()
    req = urllib.request.Request(
        f"{base}/v1/chat/completions",
        data=body,
        headers={"Content-Type": "application/json"},
    )
    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            payload = json.load(r)
    except Exception as exc:  # a failed request is a result, not a crash
        return {"ok": False, "error": f"{type(exc).__name__}: {exc}",
                "elapsed": time.perf_counter() - started}
    elapsed = time.perf_counter() - started
    usage = payload.get("usage", {})
    completion_tokens = usage.get("completion_tokens", 0)
    return {
        "ok": True,
        "elapsed": elapsed,
        "prompt_tokens": usage.get("prompt_tokens", 0),
        "completion_tokens": completion_tokens,
        "tok_per_s": completion_tokens / elapsed if elapsed else 0.0,
        "text": payload["choices"][0]["message"]["content"][:160],
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base", default="http://127.0.0.1:8000")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--rounds", type=int, default=1)
    ap.add_argument("--max-tokens", type=int, default=256)
    ap.add_argument("--timeout", type=float, default=300.0)
    ap.add_argument("--expect", default="")
    args = ap.parse_args()

    models = served_models(args.base)
    print(f"served: {models}")
    if args.expect and args.expect not in models:
        print(f"IDENTITY FAIL: expected {args.expect!r}, endpoint serves {models}")
        return 2
    model = args.expect or models[0]

    results: list[dict] = []
    for round_index in range(args.rounds):
        with ThreadPoolExecutor(max_workers=args.concurrency) as pool:
            futures = [
                pool.submit(one_completion, args.base, model, args.max_tokens, args.timeout)
                for _ in range(args.concurrency)
            ]
            batch = [f.result() for f in futures]
        results.extend(batch)
        ok = sum(1 for r in batch if r["ok"])
        print(f"round {round_index + 1}: {ok}/{len(batch)} ok")

    good = [r for r in results if r["ok"]]
    bad = [r for r in results if not r["ok"]]
    print(f"\nsucceeded {len(good)}/{len(results)}")
    for r in bad:
        print(f"  FAILED after {r['elapsed']:.1f}s: {r['error']}")
    if good:
        rates = [r["tok_per_s"] for r in good]
        lat = [r["elapsed"] for r in good]
        print(f"  tokens/sec  median {statistics.median(rates):.1f}  "
              f"min {min(rates):.1f}  max {max(rates):.1f}")
        print(f"  latency s   median {statistics.median(lat):.1f}  "
              f"min {min(lat):.1f}  max {max(lat):.1f}")
        print(f"  completion tokens total {sum(r['completion_tokens'] for r in good)}")
        print(f"\nsample output:\n  {good[0]['text']}")
    return 0 if not bad else 1


if __name__ == "__main__":
    raise SystemExit(main())
