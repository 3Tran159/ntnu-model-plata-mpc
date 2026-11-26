"""wiener_vs_fizyka.py - zlecenie koordynatora 13.11 20:50: czy najlepszy filtr PRZYCZYNOWY dopasowany do danych (Wiener, FIR) daje przy sondzie fali
wyraznie mniejszy blad niz filtr z fizyki agenta D (k3.probe_kernel).  Wszystko na sygnalach fali (plat nieruchomy, z = 0), bez modelu plata.
Wielkosc szacowana: pionowa predkosc wody na placie (srednia po punktach kontrolnych cieciwy, glebokosc 1,09 m) - jak w k3_diag_sonda.py.
Blad [%] = 100 * sqrt(sredni kwadrat (oszacowanie - prawda) / sredni kwadrat prawdy).
Fale testowe: te same realizacje co widmo_s1s4.py / k3_diag_sonda.py: seed 100 * nr stanu + s (s = 0, 1, 2), pasmo 0,5-3 wp, 80 skladowych, 1200 s, 100 Hz.
Filtry:
  fizyka D      - probe_kernel(d + srednie xc): idealna odpowiedz H(we) = i w0 e^{-k h} e^{-i we tau} obcieta do czesci przyczynowej (3 s). Nie zna widma ani szumu.
  Wiener stanowy- FIR (L wspolczynnikow po 10 ms) z najmniejszych kwadratow na syntetycznych zapisach TEGO stanu morza, INNE ziarna (9000 + 10 * nr + j, j = 0..4, po 300 s),
                  z czlonem szumu sigma^2 * suma h^2 (filtr Wienera przyczynowy o skonczonej pamieci).
  Wiener ogolny - jeden FIR dla wszystkich stanow: zapisy S1..S4 (inne ziarna), kazdy unormowany do tej samej wariancji predkosci wody.
Warunki: (a) bez szumu i opoznienia (jak diagnostyka D), (b) szum sondy 1 cm (domyslny w k3.py), (c) szum 2 cm + opoznienie 20 ms.
Wynik: WIENER_VS_FIZYKA.json, WIENER_VS_FIZYKA.png"""
import json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "ZAWIESZENIE"))
import widmo_sensor as S
from k3 import probe_kernel
DT = 0.01; SEAS = S.SEAS; DS = (1.5, 3.0, 6.0); COND = {"a_bez_szumu": (0.0, 0.0), "b_szum_1cm": (0.01, 0.0), "c_szum_2cm_opoznienie_20ms": (0.02, 0.02)}
L = 150


def records(sea, seeds, d, T):
    out = []
    for sd in seeds:
        P = S.comps(sea, sd); _, eta, w = S.signals(P, d, T); out.append((eta, w))
    return out, float(np.mean(P.F.xc))


def wiener(train, sigma, nl, L=L):
    R = np.zeros((L, L)); r = np.zeros(L)
    for eta, w, sc in train:
        m = np.roll(eta, nl) * sc; y = w * sc; n0 = L + nl; X = np.lib.stride_tricks.sliding_window_view(m, L)[n0 - L + 1: len(m) - L + 1][:, ::-1] if False else np.stack([m[n0 - j: len(m) - j] for j in range(L)], axis=1)
        R += X.T @ X / len(X); r += X.T @ y[n0:] / len(X); R += np.eye(L) * (sigma * sc) ** 2
    return np.linalg.solve(R / len(train), r / len(train))


def err(est, w, skip=1000):
    return float(100 * np.sqrt(np.mean((est[skip:] - w[skip:]) ** 2) / np.mean(w[skip:] ** 2)))


if __name__ == "__main__":
    out = {}
    for d in DS:
        tr = {sea: records(sea, [9000 + 10 * int(sea[1]) + j for j in range(5)], d, 300.0)[0] for sea in SEAS}
        te = {sea: records(sea, [100 * int(sea[1]) + s for s in range(3)], d, 1200.0) for sea in SEAS}
        for cname, (sigma, lat) in COND.items():
            nl = int(round(lat / DT))
            h_gen = wiener([(e, w, 1.0 / w.std()) for sea in SEAS for e, w in tr[sea]], sigma, nl)
            for sea in SEAS:
                recs, xm = te[sea]; kern, lost = probe_kernel(d + xm, dt=DT); h_sea = wiener([(e, w, 1.0) for e, w in tr[sea]], sigma, nl)
                E = {"fizyka_D": [], "Wiener_stanowy": [], "Wiener_ogolny": []}
                for i, (eta, w) in enumerate(recs):
                    m = np.roll(eta, nl) + sigma * np.random.default_rng(777 + i).standard_normal(len(eta))
                    E["fizyka_D"].append(err(np.convolve(m, kern)[:len(m)], w)); E["Wiener_stanowy"].append(err(np.convolve(m, h_sea)[:len(m)], w)); E["Wiener_ogolny"].append(err(np.convolve(m, h_gen)[:len(m)], w))
                out[f"{cname}|d{d:g}|{sea}"] = {k: dict(mean=float(np.mean(v)), min=float(min(v)), max=float(max(v))) for k, v in E.items()}
                print(f"{cname:28s} d {d:3g} m {sea}: fizyka D {np.mean(E['fizyka_D']):5.1f} % | Wiener stanowy {np.mean(E['Wiener_stanowy']):5.1f} % | Wiener ogolny {np.mean(E['Wiener_ogolny']):5.1f} %   (rozrzut 3 realizacji: D {min(E['fizyka_D']):.1f}-{max(E['fizyka_D']):.1f}, stanowy {min(E['Wiener_stanowy']):.1f}-{max(E['Wiener_stanowy']):.1f})", flush=True)
    (HERE / "WIENER_VS_FIZYKA.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
    import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
    fig, ax = plt.subplots(1, 3, figsize=(13, 4), sharey=True)
    for a, (cname, lab) in zip(ax, (("a_bez_szumu", "bez szumu i opoznienia"), ("b_szum_1cm", "szum sondy 1 cm"), ("c_szum_2cm_opoznienie_20ms", "szum 2 cm, opoznienie 20 ms"))):
        x = np.arange(len(SEAS) * len(DS)); labs = [f"{s}\n{d:g} m" for d in DS for s in SEAS]
        for j, (k, col, nm) in enumerate((("fizyka_D", "C1", "filtr z fizyki (D)"), ("Wiener_ogolny", "C2", "Wiener ogolny"), ("Wiener_stanowy", "C0", "Wiener stanowy"))):
            a.bar(x + (j - 1) * 0.27, [out[f"{cname}|d{d:g}|{s}"][k]["mean"] for d in DS for s in SEAS], 0.27, color=col, label=nm)
        a.set_xticks(x); a.set_xticklabels(labs, fontsize=7); a.set_title(lab, fontsize=10); a.grid(alpha=.3, axis="y")
    ax[0].set_ylabel("blad oszacowania predkosci wody na placie RMS [%]"); ax[0].legend(fontsize=8); fig.tight_layout(); fig.savefig(HERE / "WIENER_VS_FIZYKA.png", dpi=130)
