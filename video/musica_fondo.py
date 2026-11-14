"""Música de fondo original (sin derechos de terceros): pad ambiental suave Am-F-C-G con arpegio.
Uso: python musica_fondo.py <segundos> <salida.wav>"""
import sys, wave, numpy as np
SR = 32000; DUR = float(sys.argv[1]); OUT = sys.argv[2]
BPM = 76; beat = 60 / BPM; bar = 4 * beat
n = lambda m: 440 * 2 ** ((m - 69) / 12)
ACORDES = [[57, 60, 64], [53, 57, 60], [48, 52, 55], [55, 59, 62]]   # Am F C G
t = (np.arange(int(SR * DUR)) / SR).astype(np.float32)
y = np.zeros_like(t, dtype=np.float32)
def env(tt, a, r, L):
    e = np.clip(tt / a, 0, 1) * np.clip((L - tt) / r, 0, 1); return e
nbars = int(DUR / bar) + 1
for b in range(nbars):
    ch = ACORDES[b % 4]; t0 = b * bar
    i0, i1 = int(t0 * SR), min(len(t), int((t0 + bar + 1.0) * SR))
    if i0 >= len(t): break
    tt = t[i0:i1] - t0; e = env(tt, 1.2, 1.2, bar + 1.0)
    for m in ch + [ch[0] - 12]:
        f = n(m); y[i0:i1] += 0.05 * e * (np.sin(2 * np.pi * f * tt) + 0.3 * np.sin(2 * np.pi * 2 * f * tt + 0.5) + 0.15 * np.sin(2*np.pi*f*1.003*tt))
    for k in range(8):                                    # arpegio en corcheas
        ts = t0 + k * beat / 2; j0 = int(ts * SR); j1 = min(len(t), j0 + int(1.6 * SR))
        if j0 >= len(t): break
        m = (ch + [ch[0] + 12])[[0, 1, 2, 3, 2, 1, 0, 2][k]] + 12
        tk = t[j0:j1] - ts
        y[j0:j1] += 0.035 * np.exp(-tk * 3.2) * np.sin(2 * np.pi * n(m) * tk) * np.clip(tk / 0.01, 0, 1)
# eco simple y fundidos
d = int(0.33 * SR); y[d:] += 0.35 * y[:-d]
fade = int(3 * SR); y[:fade] *= np.linspace(0, 1, fade); y[-fade:] *= np.linspace(1, 0, fade)
y = y / np.max(np.abs(y)) * 0.6
st = np.empty((len(y), 2), np.int16); st[:, 0] = (y * 32767).astype(np.int16); st[:, 1] = np.roll(st[:, 0], int(0.012 * SR))
with wave.open(OUT, "wb") as w:
    w.setnchannels(2); w.setsampwidth(2); w.setframerate(SR); w.writeframes(st.tobytes())
print("musica", OUT, DUR)
