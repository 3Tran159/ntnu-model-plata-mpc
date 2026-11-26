r"""krok1_godo_2d.py - Godø 3D sprowadzony do 2D i porownanie z NASZYM 2D (nasze 2D bez zmian).
Wejscie: KROK1_WYNIKI.json (z krok1_zestaw.py). Wyjscie: klucz "godo_w_2D" w tym samym pliku + KROK1_porownanie_2D.png.

Sprowadzenie (wszystko dla calego plata Godø, rozpietosc b = 7,987 m):
  L        = 110,4 kN   sila pionowa odczytana z rys. 5 i 7 (1,098e5 i 1,103e5 N) = 90 % ciezaru 12,5 t (jak w Godø 2024b, s. 3: glowny plat niesie 90 %)
  D_cw_3D  = 3301 N     odczyt z rys. 7 (srednie -Fx agenta komfort 3268 N / 0,99)
  D_i_cw   = L^2 / (0,5 rho U^2 pi b^2)                       opor indukowany w wodzie spokojnej (obrys eliptyczny)
  D_cw_2D  = D_cw_3D - D_i_cw
  dD_3D    = (procent z artykulu) x D_cw_3D
  dD_i     = D_i_cw x (srednia(CL^2) na fali / CL^2 w wodzie spokojnej - 1)   ten stosunek z NASZYCH przebiegow CL(t); dla TD3 z przyspieszenia Godø
  dD_2D    = dD_3D - dD_i ;  procent_2D = dD_2D / D_cw_2D
"""
import json, math
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).parent
d = json.loads((HERE / "KROK1_WYNIKI.json").read_text(encoding="utf-8"))
mw, ur = d["model_wirowy"], d["urans"]
U, B, RHO_G, G = 12.3466667, 25.6 * 0.312, 1025.0, 9.81
L = 110.4e3; D3 = 3301.0
q = 0.5 * RHO_G * U * U
Di = L * L / (q * math.pi * B * B); D2 = D3 - Di
S = 25.6 * 0.312 ** 2
pct3 = dict(PID1=-11.2, PID2=-2.45, PID3=18.0, I=-15.0, TD3_GODO=-63.9)
# stosunek sredniej CL^2 na fali do wody spokojnej - z naszych przebiegow (model wirowy V1 i URANS), srednia z obu gdy sa oba
calm_v = mw["V1_ind"]["calm"]["P_ind_W"]; calm_u = ur["CALM_PID2"]["P_ind_W"]
# recenzja B4 (13.11): stosunek z przyspieszen RMS GODØ (tab. 4 i 5): wahanie nosnej / nosna srednia = przyspieszenie / g
#   (masa w rownaniu nurzania = nosna srednia / g: odczyt z rys. 5 i 8 daje 11,3 i 11,2 t). Nie korzysta z naszego CL(t).
ACC_GODO = dict(PID1=1.8, PID2=2.0, PID3=1.4, I=1.8, TD3_GODO=4.6)
ex = {k: (a / G) ** 2 for k, a in ACC_GODO.items()}
g2 = dict(L_N=L, CL=L / (q * S), D_cw_3D_N=D3, D_ind_cw_N=Di, D_cw_2D_N=D2, CD_2D=D2 / (q * S), rho=RHO_G, przypadki={})
for k, p in pct3.items():
    dD3 = p / 100 * D3; dDi = Di * ex[k]; dD2 = dD3 - dDi
    g2["przypadki"][k] = dict(pct_3D=p, dD_3D_N=dD3, CL2_ratio_minus1=ex[k], dD_ind_N=dDi, dD_2D_N=dD2, pct_2D=100 * dD2 / D2)
d["godo_w_2D"] = g2
(HERE / "KROK1_WYNIKI.json").write_text(json.dumps(d, indent=1, ensure_ascii=False), encoding="utf-8")

print(f"Godø: L {L:.0f} N, CL {g2['CL']:.3f}, D_cw 3D {D3:.0f} N, D_ind {Di:.0f} N, D_cw 2D {D2:.0f} N, CD_2D {g2['CD_2D']:.5f}")
keys = ["PID1", "PID2", "PID3", "I", "TD3_GODO"]
v0 = mw["V0_2D"]
for k in keys:
    c = g2["przypadki"][k]
    u = f"{ur[k]['pct_vs_calm']:+.1f} % / {ur[k]['dD_full_N']:+.0f} N" if k in ur else "brak"
    print(f"{k:9s} Godø 3D {c['pct_3D']:+6.2f} % ({c['dD_3D_N']:+6.0f} N) | dD_ind {c['dD_ind_N']:+5.0f} N | Godø 2D {c['pct_2D']:+6.1f} % ({c['dD_2D_N']:+6.0f} N) | model wirowy {v0[k]['pct_vs_calm']:+6.1f} % / {v0[k]['dD_full_N']:+6.0f} N | URANS {u}")

# wykres: tylko kierunek 2D
lab = ["PID 1\n(wolny)", "PID 2\n(średni)", "PID 3\n(szybki)", "regulator I", "TD3\n(różne sieci)"]
ser = [("Godø 3D (artykuł)", [g2["przypadki"][k]["pct_3D"] for k in keys], "#bdbdbd"),
       ("Godø sprowadzony do 2D", [g2["przypadki"][k]["pct_2D"] for k in keys], "#222222"),
       ("nasz model wirowy 2D", [v0[k]["pct_vs_calm"] for k in keys], "#2171b5"),
       ("nasz URANS 2D", [ur[k]["pct_vs_calm"] if k in ur else np.nan for k in keys], "#d94801")]
fig, ax = plt.subplots(figsize=(11, 5.2)); x = np.arange(len(keys)); w = 0.2
for j, (name, vals, col) in enumerate(ser):
    xs = x + (j - 1.5) * w
    ax.bar(xs, vals, w, label=name, color=col)
    for xi, v in zip(xs, vals):
        if np.isfinite(v):
            ax.text(xi, v + (2 if v >= 0 else -2), f"{v:+.0f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=8)
ax.axhline(0, color="k", lw=0.8); ax.set_xticks(x); ax.set_xticklabels(lab)
ax.set_ylabel("zmiana oporu płata względem wody spokojnej [%]"); ax.grid(axis="y", alpha=0.3); ax.set_ylim(-112, 72)
ax.legend(fontsize=9, loc="upper left")
ax.set_title("Fala czołowa regularna H 1,5 m, T 5 s, 24 węzły. Ujemne = mniejszy opór niż w wodzie spokojnej.\n"
             "Każdy słupek względem własnej wody spokojnej; URANS dla regulatora I nie był liczony", fontsize=10)
fig.tight_layout(); fig.savefig(HERE / "KROK1_porownanie_2D.png", dpi=160)
old = HERE / "KROK1_porownanie.png"
if old.exists():
    old.unlink()          # stary uklad (2D podniesione do 3D) zastapiony
print("wykres OK")
