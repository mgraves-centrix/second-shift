"""Spike pass-gate run: synthesize one WAV per voice on GB10, measure RTF."""
import glob, io, json, os, tarfile, time, traceback
import numpy as np, soundfile as sf, torch
from omegaconf import OmegaConf
from nemo.collections.tts.models import MagpieTTSModel

OUT = "$HOME/spikes/tts-magpie/out"; os.makedirs(OUT, exist_ok=True)
SR = 22050  # nemo-nano-codec-22khz

p = glob.glob("$HOME/.cache/huggingface/hub/models--nvidia--magpie_tts_multilingual_357m/**/*.nemo", recursive=True)[0]
t = tarfile.open(p)
speakers, langs = {}, None
for n in t.getnames():
    if n.endswith("speakers.json"):
        speakers = json.load(io.TextIOWrapper(t.extractfile(n)))
    if n.endswith("model_config.yaml") and langs is None:
        c = OmegaConf.load(io.TextIOWrapper(t.extractfile(n)))
        m = OmegaConf.to_container(c, resolve=False).get("language_to_tokenizer_mapping")
        if m: langs = m
print("VOICES", json.dumps(speakers))
print("LANGUAGES", json.dumps(sorted(langs.keys())) if langs else "n/a")

model = MagpieTTSModel.from_pretrained("nvidia/magpie_tts_multilingual_357m").eval().cuda()
TEXT = ("Good morning. Overnight I drafted three artifacts and got stuck on two of them. "
        "Do you have five minutes to unblock me?")

res = {}
for name, idx in sorted(speakers.items(), key=lambda kv: kv[1]):
    try:
        torch.cuda.synchronize(); t0 = time.time()
        with torch.inference_mode():
            out = model.do_tts(TEXT, language="en", apply_TN=False, speaker_index=idx)
        torch.cuda.synchronize(); dt = time.time() - t0
        a = (out[0] if isinstance(out, (tuple, list)) else out).detach().float().cpu().reshape(-1).numpy()
        dur = len(a) / SR
        path = f"{OUT}/{name.lower()}.wav"
        sf.write(path, a, SR)
        peak = float(np.abs(a).max())
        print(f"SYNTH_OK {name} idx={idx} gen={dt:.2f}s audio={dur:.2f}s rtf={dt/dur:.3f} peak={peak:.3f} bytes={os.path.getsize(path)}")
        res[name] = {"ok": True, "gen_s": round(dt,2), "audio_s": round(dur,2), "rtf": round(dt/dur,3), "peak": round(peak,3)}
    except Exception as e:
        print(f"SYNTH_FAIL {name} {type(e).__name__}: {str(e)[:300]}"); traceback.print_exc()
        res[name] = {"ok": False, "err": f"{type(e).__name__}: {str(e)[:200]}"}
print("GPU_MEM_ALLOC_GB", round(torch.cuda.memory_allocated()/1e9, 2))
json.dump({"voices": speakers, "languages": sorted(langs.keys()) if langs else None, "results": res},
          open(f"{OUT}/results.json","w"), indent=2)
print("RESULTS", json.dumps(res))
