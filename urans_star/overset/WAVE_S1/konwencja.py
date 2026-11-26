"""21.11 08:40: (1) ktora konwencja fazy STAR zgadza sie z modelem - porownanie eta przy LE z URANS (OVS_CEL_005g_S1_90, t 0-2,19 s) z suma skladowych;
(2) dobor przesuniecia czasu t0 realizacji, tak zeby pierwsze 15 s nie mialo dolin glebszych niz 0,6 m (start MPC) - przebieg 21.11 07:50 stanal na HOLD_LIMIT
(dolina -0,94 m przy t 2,19 s, zanurzenie 0,15 m < c/2). Wynik: KONWENCJA.json"""
import json, csv, numpy as np
H = r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR"
S = json.load(open(H + r"\overset\WAVE_S1\S1_SKLADOWE.json")); C = S["skladowe"]
a = np.array([c["a"] for c in C]); w0 = np.array([c["w0"] for c in C]); k = np.array([c["k"] for c in C]); eps = np.array([c["eps"] for c in C])
U = 12.3466667; XLE = 0.0
r = list(csv.reader(open(H + r"\overset_runs\OVS_CEL_005g_S1_90\history.csv"))); h = r[0]; it, ie = h.index("time_s"), h.index("GODO_eta_at_LE")
d = {}
for x in r[1:]:
    if len(x) >= len(h):
        try: d[float(x[it])] = float(x[ie])
        except ValueError: pass
t = np.array(sorted(d)); e = np.array([d[q] for q in t]); m = t > 0.3; t, e = t[m], e[m]
# fala z dziobu: w ukladzie plata (prad +U w +x, fala biegnie w +x wzgledem wody) czestosc spotkania we = w0 + k U
we = w0 + k * U
best = []
for nm, f in (("cos(k x - we t + eps)", lambda tt, x: np.cos(k * x - we * tt + eps)), ("cos(k x - we t - eps)", lambda tt, x: np.cos(k * x - we * tt - eps)),
              ("cos(-k x + we t + eps)", lambda tt, x: np.cos(-k * x + we * tt + eps)), ("sin(k x - we t + eps)", lambda tt, x: np.sin(k * x - we * tt + eps)),
              ("cos(k x - w0 t + eps)", lambda tt, x: np.cos(k * x - w0 * tt + eps))):
    for x0 in np.arange(-10, 10.01, 0.25):
        E = np.array([(a * f(tt, x0)).sum() for tt in t]); err = float(np.sqrt(np.mean((E - e) ** 2))); best.append((err, nm, x0))
best.sort(); out = dict(eta_rms_urans=float(e.std()), najlepsze=[dict(blad=b[0], konw=b[1], x0=b[2]) for b in best[:5]])
print(json.dumps(out, indent=1))
# (2) dolina przy LE w funkcji przesuniecia t0 (konwencja najlepsza): szukamy t0 z min(eta) > -0.6 w [t0, t0+15] i min(eta) > -1.0 w [t0, t0+60]
err, nm, x0 = best[0]
f = dict((b[1], None) for b in best)
fn = {"cos(k x - we t + eps)": lambda tt: np.cos(k * x0 - we * tt + eps), "cos(k x - we t - eps)": lambda tt: np.cos(k * x0 - we * tt - eps),
      "cos(-k x + we t + eps)": lambda tt: np.cos(-k * x0 + we * tt + eps), "sin(k x - we t + eps)": lambda tt: np.sin(k * x0 - we * tt + eps),
      "cos(k x - w0 t + eps)": lambda tt: np.cos(k * x0 - w0 * tt + eps)}[nm]
TT = np.arange(0, 400, 0.02); EE = np.array([(a * fn(q)).sum() for q in TT]); cand = []
for t0 in np.arange(0, 330, 0.5):
    m15 = (TT >= t0) & (TT < t0 + 15); m60 = (TT >= t0) & (TT < t0 + 60)
    cand.append((float(EE[m15].min()), float(EE[m60].min()), float(EE[m60].std() * 4), float(t0)))
ok = [c for c in cand if c[0] > -0.6 and c[1] > -1.05]; ok.sort(key=lambda c: (-c[1], -c[0]))
out.update(eta_min_pelne=float(EE.min()), kandydaci=[dict(min15=c[0], min60=c[1], Hs60=c[2], t0=c[3]) for c in ok[:8]], bez_przesuniecia=dict(min15=cand[0][0], min60=cand[0][1]))
json.dump(out, open(H + r"\overset\WAVE_S1\KONWENCJA.json", "w"), indent=1); print(json.dumps({k_: v for k_, v in out.items() if k_ != "najlepsze"}, indent=1))
