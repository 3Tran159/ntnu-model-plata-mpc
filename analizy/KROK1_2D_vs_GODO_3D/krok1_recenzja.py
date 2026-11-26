r"""krok1_recenzja.py - odpowiedz na recenzje B1-B7 (13.11.2026).
 (B4) krok1_godo_2d.py: dodatkowy opor indukowany na fali liczony z przyspieszen GODØ (tab. 4 i 5), nie z naszego CL(t).
 (B6) PID3 w modelu Faltinsena B: zakres kata +-7,5 deg liczony od trymu (jak u Godø) zamiast od zera; oba obciazenia.
 (B7) uruchamia krok1_godo_2d.py na dysku. Wynik: KROK1_RECENZJA.json
"""
import sys, json, math, subprocess
sys.dont_write_bytecode = True
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent
# --- B4: poprawka skryptu (idempotentna) ---
p = HERE / "krok1_godo_2d.py"; s = p.read_text(encoding="utf-8")
old = '''ex = {}
for k in ("PID1", "PID2", "PID3"):
    ex[k] = float(np.mean([mw["V1_ind"][k]["P_ind_W"] / calm_v - 1, ur[k]["P_ind_W"] / calm_u - 1]))
ex["I"] = mw["V2_ind_kappa"]["I"]["P_ind_W"] / calm_v - 1
ex["TD3_GODO"] = (4.6 / G) ** 2                      # przyspieszenie RMS Godø 4,6 m/s2 -> wahanie nosnej / ciezar
'''
new = '''# recenzja B4 (13.11): stosunek z przyspieszen RMS GODØ (tab. 4 i 5): wahanie nosnej / nosna srednia = przyspieszenie / g
#   (masa w rownaniu nurzania = nosna srednia / g: odczyt z rys. 5 i 8 daje 11,3 i 11,2 t). Nie korzysta z naszego CL(t).
ACC_GODO = dict(PID1=1.8, PID2=2.0, PID3=1.4, I=1.8, TD3_GODO=4.6)
ex = {k: (a / G) ** 2 for k, a in ACC_GODO.items()}
'''
if old in s:
    p.write_text(s.replace(old, new), encoding="utf-8")
else:
    assert "ACC_GODO" in s
out = dict(godo_2d_stdout=subprocess.run([sys.executable, str(p)], capture_output=True, text=True, encoding="utf-8", env={**__import__("os").environ, "PYTHONIOENCODING": "utf-8"}).stdout)
print(out["godo_2d_stdout"])

# --- B6: PID3, zakres kata od trymu ---
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\40_MODEL_WIROWY_I_STEROWANIE\faltinsen_model")
import faltinsen_plant as FP
PH = (0.0, 0.5 * math.pi, math.pi, 1.5 * math.pi); KP, KI = 22.3, 7.25
q = 0.5 * FP.RHO * FP.U ** 2 * FP.C
for load in ("NASZE", "GODO"):
    FP.MASS = (0.9 if load == "GODO" else 1.0) * 12500.0 / (25.6 * 0.312)
    FP.CL_REF = (FP.MASS * FP.G - FP.BUOY) / q if load == "GODO" else 0.642
    for trim in (False, True):
        P, acc, thmin, thmax, sat = [], [], [], [], []
        TR = FP.TH_REF_DEG; lo, hi = (TR - 7.5, TR + 7.5) if trim else (-7.5, 7.5)
        for ph in PH:
            pl = FP.FaltinsenPlant(wave_amp=0.73, wave_phase=ph); pl.reset(theta_deg=TR); pl.cmd = np.radians(TR)
            for _ in range(1000):
                pl.step(free_heave=False)
            n = int(round(8 * pl.Te / 0.01)); integ, rows = 0.0, []
            for k in range(n):
                e = -pl.z; integ += e * 0.01
                pl.cmd = np.radians(np.clip(TR + KP * e + KI * integ, lo, hi)); fx, v0 = 0.0, pl.v
                for _ in range(pl.tick):
                    r = pl.step(free_heave=True, th_max_deg=max(abs(lo), abs(hi))); fx += r["Fx"]
                rows.append((fx / pl.tick * FP.SPAN * FP.U, (pl.v - v0) / 0.01, r["theta_deg"]))
            a = np.array(rows[-int(round(4 * pl.Te / 0.01)):])
            P.append(a[:, 0].mean()); acc.append(np.sqrt(np.mean(a[:, 1] ** 2))); thmin.append(a[:, 2].min()); thmax.append(a[:, 2].max())
            sat.append(np.mean((np.abs(a[:, 2] - lo) < 0.02) | (np.abs(a[:, 2] - hi) < 0.02)))
        calm = json.loads((HERE / "KROK1_FALTINSEN.json").read_text())[f"B_{load}"]["calm_P_W"]
        o = dict(P_W=float(np.mean(P)), dD_full_N=float((np.mean(P) - calm) * 25.6 * 0.312 / 0.02 / FP.U), acc=float(np.mean(acc)), th_min=float(min(thmin)), th_max=float(max(thmax)), sat_frac=float(np.mean(sat)))
        out[f"PID3_B_{load}_{'od_trymu' if trim else 'od_zera'}"] = o
        print(f"PID3 model B, obciazenie {load}, zakres {'od trymu' if trim else 'od zera '}: {o['P_W']:.2f} W, {o['dD_full_N']:+.0f} N, acc {o['acc']:.2f}, kat {o['th_min']:+.2f}..{o['th_max']:+.2f}, nasycenie {100*o['sat_frac']:.0f} % czasu")
(HERE / "KROK1_RECENZJA.json").write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
