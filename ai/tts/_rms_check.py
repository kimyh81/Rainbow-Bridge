import soundfile as sf
import numpy as np


def scan(p):
    x, sr = sf.read(p)
    x = x.mean(1) if x.ndim > 1 else x
    o = float(np.sqrt(np.mean(x ** 2)))
    s = {
        t: float(np.sqrt(np.mean(x[int(t * sr):int(t * sr) + int(sr * 0.5)] ** 2)))
        for t in range(30, 54)
    }
    return round(len(x) / sr, 1), round(o, 4), s


for tag, p in [
    ("RAW", "ai/tts/_output/scenario/letter_3rd.wav"),
    ("DYN", "ai/tts/_output/scenario/letter_3rd_dyn.wav"),
]:
    d, o, s = scan(p)
    print(f"{tag} dur={d}s overall_rms={o}")
    for t, v in s.items():
        bar = "#" * int(v * 200)
        print(f"   {t}s {v:.4f} {bar}")
