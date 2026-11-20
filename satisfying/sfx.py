"""Erzeugt die Tonspur zum Berliner-Video, passend zu den Zeitpunkten der Animation.

Alle Geräusche werden synthetisch erzeugt (keine fremden Samples, keine Rechte Dritter):
Rutschen auf der Bahn, Quetschen durch den Ring, Platschen in die Schüssel,
Klonk am Ring, Aufprall auf dem Boden und ein kurzer Gong auf der Abschlusskarte.

Aufruf (in derselben Umgebung wie berliner.py, braucht numpy und scipy):
    python sfx.py <ausgabe.wav>
"""

import sys
import wave

import numpy as np
from scipy.signal import butter, fftconvolve, sosfilt

import berliner as B

SR = 44100
SEG_S = B.SEG / B.FPS
VIDEO_ORDER = ["pudding", "weich", "hart"]  # muss zu ORDER in compose.sh passen
END_S = 2.5
TOTAL = SEG_S * 3 + END_S
rng = np.random.default_rng(7)


def t_arr(dur):
    return np.arange(int(dur * SR)) / SR


def band(x, lo, hi, order=2):
    nyq = SR / 2
    if lo <= 0:
        sos = butter(order, hi / nyq, "low", output="sos")
    elif hi >= nyq:
        sos = butter(order, lo / nyq, "high", output="sos")
    else:
        sos = butter(order, [lo / nyq, hi / nyq], "band", output="sos")
    return sosfilt(sos, x)


def noise(dur):
    return rng.standard_normal(int(dur * SR))


def add(buf, start, sig, gain=1.0):
    i = int(start * SR)
    j = min(len(buf), i + len(sig))
    if j > i:
        buf[i:j] += gain * sig[: j - i]


def fade(sig, a=0.01, r=0.03):
    n = len(sig)
    env = np.ones(n)
    na, nr = int(a * SR), int(r * SR)
    if na:
        env[:na] = np.linspace(0, 1, na)
    if nr:
        env[-nr:] *= np.linspace(1, 0, nr)
    return sig * env


# ---------- Einzelgeräusche ----------

def slide(dur):
    t = t_arr(dur)
    ramp = (t / dur) ** 1.5
    rumble = band(noise(dur), 90, 700) * 0.9
    hiss = band(noise(dur), 2500, 6000) * 0.12
    return fade((rumble + hiss) * ramp * 0.22, 0.05, 0.04)


def thump(freq, decay, dur=0.4):
    t = t_arr(dur)
    pitch = freq * (1 + 0.6 * np.exp(-t / 0.015))
    return np.sin(2 * np.pi * np.cumsum(pitch) / SR) * np.exp(-t / decay)


def ceramic(partials, dur=1.2):
    t = t_arr(dur)
    out = np.zeros_like(t)
    for f, amp, dec in partials:
        out += amp * np.sin(2 * np.pi * f * t) * np.exp(-t / dec)
    click = band(noise(0.01), 2000, 9000) * 0.3
    out[: len(click)] += click
    return out


def squelch(dur, wet=1.0):
    """Nasses Quetschen: viele kleine Blasen plus gedämpftes Rauschen."""
    n = int(dur * SR)
    out = band(noise(dur), 150, 1400) * 0.35 * wet
    for _ in range(int(28 * dur * wet) + 3):
        start = rng.uniform(0, dur * 0.9)
        f0 = rng.uniform(220, 620)
        blen = rng.uniform(0.025, 0.06)
        t = t_arr(blen)
        blip = np.sin(2 * np.pi * np.cumsum(f0 * (1 + 1.4 * t / blen)) / SR) * np.exp(-t / (blen / 3))
        i = int(start * SR)
        j = min(n, i + len(blip))
        out[i:j] += blip[: j - i] * rng.uniform(0.3, 0.7)
    t = t_arr(dur)
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 0.6
    return fade(out * env * 0.5, 0.01, 0.04)


def squeak(dur):
    """Gummiartiges Quietschen für den weichen Berliner."""
    t = t_arr(dur)
    x = t / dur
    f = 720 + 520 * np.sin(np.pi * x) ** 1.3 - 120 * x
    f *= 1 + 0.03 * np.sin(2 * np.pi * 26 * t)
    ph = 2 * np.pi * np.cumsum(f) / SR
    tone = np.sin(ph) + 0.35 * np.sin(2 * ph) + 0.15 * np.sin(3 * ph)
    rub = band(noise(dur), 1800, 4200) * 0.25
    env = np.sin(np.pi * np.clip(x, 0, 1)) ** 0.5
    return fade((tone * 0.3 + rub) * env * 0.45, 0.015, 0.05)


def splat(jelly):
    dur = 1.6
    t = t_arr(dur)
    burst = band(noise(dur), 80, 2200) * np.exp(-t / 0.07) * 0.9
    low = thump(65, 0.14, dur) * 0.8
    out = burst + low
    if jelly:
        jig = np.exp(-t / 0.5) * np.abs(np.sin(2 * np.pi * 1.3 * t)) ** 2
        out += band(noise(dur), 100, 600) * jig * 0.35
        sq = squelch(0.45, 0.6)
        out[: len(sq)] += sq * 0.5
    return out * 0.6


def plop_in_bowl():
    out = thump(105, 0.08, 1.2) * 0.7 + band(noise(1.2), 100, 1800) * np.exp(-t_arr(1.2) / 0.03) * 0.4
    out += ceramic([(1850, 0.10, 0.5), (3120, 0.06, 0.35), (4700, 0.03, 0.2)], 1.2)
    return out * 0.7


def ring_bonk():
    out = ceramic([(2350, 0.22, 0.7), (3870, 0.12, 0.5), (5600, 0.06, 0.3), (1180, 0.08, 0.4)], 1.4)
    out[: int(0.4 * SR)] += thump(170, 0.03, 0.4) * 0.5
    return out * 0.8


def floor_hit(strength):
    out = thump(85, 0.09, 0.5) * 0.9 + band(noise(0.5), 60, 1200) * np.exp(-t_arr(0.5) / 0.02) * 0.5
    return out * strength


def chime():
    t = t_arr(1.6)
    a = np.sin(2 * np.pi * 659.3 * t) * np.exp(-t / 0.5)
    b = np.zeros_like(t)
    off = int(0.12 * SR)
    tb = t[: len(t) - off]
    b[off:] = np.sin(2 * np.pi * 987.8 * tb) * np.exp(-tb / 0.7)
    return (a + b) * 0.12


# ---------- Zeitpunkte aus der Animation ----------

def events(level):
    states = B.hard_states() if level == "hart" else B.soft_states(level)
    fps = B.FPS
    hold = 8 / fps
    slide_end = hold + B.slide_time()
    ev = {"slide": (hold, slide_end)}
    ring_pos, ring_tan = B.flight_point(B.T_RING)
    if level == "hart":
        xs = [s[0].x for s in states]
        zs = [s[0].z for s in states]
        bonk = next(f for f in range(1, len(xs)) if f / fps > slide_end and xs[f] < xs[f - 1])
        ev["bonk"] = bonk / fps
        hits = [f for f in range(1, len(zs) - 1)
                if f > bonk and zs[f - 1] > zs[f] <= zs[f + 1] and zs[f] < B.HALF_H + 0.15]
        ev["floor"] = [f / fps for f in hits]
    else:
        L = B.RADIUS + B.RING_MINOR + 0.05
        land_x = B.landing_x()
        land = next(f for f, s in enumerate(states) if abs(s[0].x - land_x) < 1e-6 and f / fps > slide_end)
        inside = [f for f, s in enumerate(states)
                  if slide_end < f / fps and f < land and abs((s[0] - ring_pos).dot(ring_tan)) < L]
        ev["squeeze"] = (inside[0] / fps, (inside[-1] + 1) / fps)
        ev["land"] = land / fps
    return ev


def build():
    buf = np.zeros(int(TOTAL * SR) + SR)
    for k, level in enumerate(VIDEO_ORDER):
        off = k * SEG_S
        ev = events(level)
        s0, s1 = ev["slide"]
        add(buf, off + s0, slide(s1 - s0))
        if level == "hart":
            add(buf, off + ev["bonk"], ring_bonk())
            for i, tf in enumerate(ev["floor"]):
                add(buf, off + tf, floor_hit([0.8, 0.4, 0.2, 0.1][min(i, 3)]))
        else:
            q0, q1 = ev["squeeze"]
            if level == "pudding":
                add(buf, off + q0 - 0.03, squelch(q1 - q0 + 0.12))
                add(buf, off + ev["land"], splat(True))
            else:
                add(buf, off + q0 - 0.02, squeak(q1 - q0 + 0.1))
                add(buf, off + ev["land"], plop_in_bowl())
        print(level, {k2: (round(v[0], 2), round(v[1], 2)) if isinstance(v, tuple) else v for k2, v in ev.items()})
    add(buf, SEG_S * 3 + 0.15, chime())

    # etwas Raumklang
    ir_t = t_arr(0.45)
    ir = rng.standard_normal(len(ir_t)) * np.exp(-ir_t / 0.12)
    ir = band(ir, 200, 6000)
    wet = fftconvolve(buf, ir)[: len(buf)]
    wet *= 0.12 * np.max(np.abs(buf)) / (np.max(np.abs(wet)) + 1e-9)
    mix = buf + wet
    mix = mix[: int(TOTAL * SR)]
    mix = np.tanh(mix / np.max(np.abs(mix)) * 1.2) / np.tanh(1.2) * 0.89
    return mix


def write_wav(path, mono):
    data = (np.clip(mono, -1, 1) * 32767).astype(np.int16)
    stereo = np.repeat(data[:, None], 2, axis=1)
    with wave.open(path, "wb") as w:
        w.setnchannels(2)
        w.setsampwidth(2)
        w.setframerate(SR)
        w.writeframes(stereo.tobytes())


if __name__ == "__main__":
    write_wav(sys.argv[1], build())
    print(sys.argv[1])
