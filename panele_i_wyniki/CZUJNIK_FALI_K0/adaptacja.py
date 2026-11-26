"""adaptacja.py - zlecenie C-Z4 (skrzynka 13.11 23:20): adaptacja filtru Wienera = bank filtrow + rozpoznanie stanu morza z ostatnich minut zapisu sondy.
Wszystko "w modelu", same sygnaly fali (plat nieruchomy, glebokosc 1,09 m), sonda 3 m przed krawedzia natarcia, 100 Hz, szum 1 cm, bez opoznienia.
Bank A: 4 filtry dopasowane do S1-S4.  Bank B: 7 filtrow dla okresow szczytu 3,0 / 3,6 / 4,3 / 5,2 / 6,2 / 7,5 / 9,0 s (co 20 %, zadnego ze stanow S1-S4 dokladnie), Hs 1,5 m.
Filtry: wiener_vs_fizyka.wiener, 150 wspolczynnikow, 5 zapisow uczacych po 300 s o innych ziarnach niz test.
Rozpoznanie: z okna T_w ostatnich sekund pomiaru sondy liczona jest gestosc widmowa (Welch, odcinki 20 s) i "czestosc szczytu" f_p = calka f S^4 df / calka S^4 df
(czestosc spotkaniowa); wybierany jest filtr banku, ktorego wlasna f_p (z zapisow uczacych) jest najblizsza w skali logarytmicznej.
Testy: (1) trafnosc wyboru i blad oszacowania predkosci wody w funkcji dlugosci okna (realizacje testowe seed 100 nr + 0..2, 1200 s, okna co 30 s);
       (2) zmiana stanu morza S2 -> S3 (i S3 -> S2): 600 s + 600 s sklejone z przejsciem 10 s; filtr wybierany co 10 s z ostatnich T_w; blad w oknach po zmianie.
Wynik: ADAPTACJA.json"""
import json, sys
from pathlib import Path
import numpy as np
from scipy.signal import welch
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parent / "ZAWIESZENIE"))
import widmo_sensor as S, wiener_vs_fizyka as V
DT, D, SIG, FS = 0.01, 3.0, 0.01, 100.0; SEAS = S.SEAS
GRID = (3.0, 3.6, 4.3, 5.2, 6.2, 7.5, 9.0)


def sig(Hs, Tp, seed, T):
    P = S.comps("S1", 0); wp = 2 * np.pi / Tp; P.set_irregular(Hs=Hs, Tp=Tp, gamma=3.3, seed=seed, N=80, wmin=0.5 * wp, wmax=3.0 * wp); _, e, w = S.signals(P, D, T); return e, w


def fpeak(m):
    f, Pxx = welch(m, FS, nperseg=min(len(m), 2000), noverlap=min(len(m), 2000) // 2); k = (f > 0.1) & (f < 3.0); return float((f[k] * Pxx[k] ** 4).sum() / (Pxx[k] ** 4).sum())


def member(Hs, Tp, seed0):
    tr = [sig(Hs, Tp, seed0 + j, 300.0) for j in range(5)]; rng = np.random.default_rng(seed0)
    return dict(h=V.wiener([(e, w, 1.0) for e, w in tr], SIG, 0), fp=float(np.mean([fpeak(e + SIG * rng.standard_normal(len(e))) for e, _ in tr])), Hs=Hs, Tp=Tp)


def choose(bank, m): 
    fp = fpeak(m); names = list(bank); return names[int(np.argmin([abs(np.log(fp / bank[n]["fp"])) for n in names]))]


def err(est, w): return float(100 * np.sqrt(np.mean((est - w) ** 2) / np.mean(w ** 2)))


if __name__ == "__main__":
    A = {s: member(*SEAS[s], 9000 + 10 * int(s[1])) for s in SEAS}; B = {f"Tp{tp:g}": member(1.5, tp, 9500 + 10 * i) for i, tp in enumerate(GRID)}
    tr = [(e, w, 1.0 / w.std()) for s in SEAS for e, w in [sig(*SEAS[s], 9000 + 10 * int(s[1]) + j, 300.0) for j in range(5)]]; hgen = V.wiener(tr, SIG, 0)
    out = dict(bank_A={k: dict(fp_Hz=v["fp"], Tp=v["Tp"]) for k, v in A.items()}, bank_B={k: dict(fp_Hz=v["fp"], Tp=v["Tp"]) for k, v in B.items()}, test1={}, test2={})
    print("f_p [Hz] bank A:", {k: round(v["fp"], 3) for k, v in A.items()}, " bank B:", {k: round(v["fp"], 3) for k, v in B.items()})
    # --- test 1: stan ustalony
    WINS = (30, 60, 120, 180, 300); best_B = {}
    for s in SEAS:
        recs = []
        for sd in range(3):
            e, w = sig(*SEAS[s], 100 * int(s[1]) + sd, 1200.0); m = e + SIG * np.random.default_rng(777 + sd).standard_normal(len(e)); recs.append((m, w))
        EA = {n: np.mean([err(np.convolve(m, A[n]["h"])[:len(m)][1000:], w[1000:]) for m, w in recs]) for n in A}; EB = {n: np.mean([err(np.convolve(m, B[n]["h"])[:len(m)][1000:], w[1000:]) for m, w in recs]) for n in B}
        Eg = np.mean([err(np.convolve(m, hgen)[:len(m)][1000:], w[1000:]) for m, w in recs]); best_B[s] = min(EB, key=EB.get)
        o = dict(err_bank_A_pct=EA, err_bank_B_pct=EB, err_ogolny_pct=float(Eg), best_B=best_B[s], okna={})
        for Tw in WINS:
            nw = int(Tw * FS); cA, cB = [], []
            for m, w in recs:
                for i0 in range(nw, len(m) + 1, 3000): cA.append(choose(A, m[i0 - nw:i0])); cB.append(choose(B, m[i0 - nw:i0]))
            o["okna"][Tw] = dict(n=len(cA), traf_A_pct=float(100 * np.mean([c == s for c in cA])), blad_A_sr_pct=float(np.mean([EA[c] for c in cA])), blad_A_max_pct=float(max(EA[c] for c in cA)),
                                 traf_B_pct=float(100 * np.mean([c == best_B[s] for c in cB])), blad_B_sr_pct=float(np.mean([EB[c] for c in cB])), blad_B_max_pct=float(max(EB[c] for c in cB)),
                                 wybory_A={c: cA.count(c) for c in set(cA)}, wybory_B={c: cB.count(c) for c in set(cB)})
        out["test1"][s] = o
        print(s, "blad filtrow A:", {k: round(v, 1) for k, v in EA.items()}, "| B:", {k: round(v, 1) for k, v in EB.items()}, "| ogolny", round(Eg, 1))
        for Tw in WINS: q = o["okna"][Tw]; print(f"   okno {Tw:3d} s (n={q['n']}): bank A trafnosc {q['traf_A_pct']:5.1f} %, blad sr. {q['blad_A_sr_pct']:5.1f} % (najgorszy {q['blad_A_max_pct']:.0f} %) | bank B trafnosc {q['traf_B_pct']:5.1f} %, blad sr. {q['blad_B_sr_pct']:5.1f} % (najgorszy {q['blad_B_max_pct']:.0f} %)  {q['wybory_B']}", flush=True)
    # --- test 2: zmiana stanu morza
    def joined(s1, s2, sd):
        e1, w1 = sig(*SEAS[s1], 100 * int(s1[1]) + sd, 610.0); e2, w2 = sig(*SEAS[s2], 100 * int(s2[1]) + sd, 1210.0)   # ta sama os czasu w obu zapisach
        r = np.clip((np.arange(len(e1)) * DT - 600.0) / 10.0, 0, 1); n = len(e1); e = np.concatenate([e1 * (1 - r) + e2[:n] * r, e2[n:]]); w = np.concatenate([w1 * (1 - r) + w2[:n] * r, w2[n:]]); return e, w
    SEG = ((-300, 0), (0, 30), (30, 60), (60, 120), (120, 300), (300, 600))
    for s1, s2 in (("S2", "S3"), ("S3", "S2"), ("S1", "S4"), ("S4", "S1")):
        for Tw in (60, 120, 300):
            R = {k: [] for k in ("A", "B", "ogolny", "wyrocznia")}; tsw = {"A": [], "B": []}
            for sd in range(3):
                e, w = joined(s1, s2, sd); m = e + SIG * np.random.default_rng(900 + sd).standard_normal(len(e)); t = np.arange(len(m)) * DT - 605.0; nw = int(Tw * FS)
                est = {}
                for nm, bank, fin in (("A", A, s2), ("B", B, best_B[s2])):
                    full = {n: np.convolve(m, bank[n]["h"])[:len(m)] for n in bank}; y = np.zeros(len(m)); cur = s1 if nm == "A" else best_B[s1]; tfirst = None; last_wrong = -605.0
                    for i0 in range(0, len(m), 1000):
                        if i0 >= nw: cur = choose(bank, m[i0 - nw:i0])
                        y[i0:i0 + 1000] = full[cur][i0:i0 + 1000]
                        if t[i0] >= 0 and cur != fin: last_wrong = t[i0] + 10.0
                    est[nm] = y; tsw[nm].append(max(0.0, last_wrong))
                est["ogolny"] = np.convolve(m, hgen)[:len(m)]; est["wyrocznia"] = np.where(t < 0, np.convolve(m, A[s1]["h"])[:len(m)], np.convolve(m, A[s2]["h"])[:len(m)])
                for k in R: R[k].append([err(est[k][(t >= a) & (t < b)], w[(t >= a) & (t < b)]) for a, b in SEG])
            o = {k: np.mean(R[k], axis=0).tolist() for k in R}; o["czas_do_ostatniego_zlego_wyboru_s"] = {k: [float(x) for x in v] for k, v in tsw.items()}; out["test2"][f"{s1}->{s2}|Tw{Tw}"] = o
            print(f"{s1}->{s2} okno {Tw:3d} s: " + " | ".join(f"{k} " + "/".join(f"{x:.0f}" for x in o[k]) for k in R) + f" | ostatni zly wybor po [s]: A {tsw['A']}, B {tsw['B']}", flush=True)
    out["segmenty_s_wzgledem_srodka_przejscia"] = SEG
    (HERE / "ADAPTACJA.json").write_text(json.dumps(out, indent=1), encoding="utf-8")
