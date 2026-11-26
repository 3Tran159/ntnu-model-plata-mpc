"""k3_wiener.py - zlecenie D-Z3 (koordynator 13.11 21:55): szacunek pionowej predkosci wody na placie filtrem Wienera agenta C
(wspolny dla S1-S4, "Wiener ogolny" z claude/krok3-filtr-wienera-vs-fizyka.md) zamiast filtru z fizyki (k3.probe_kernel).
Wszystko "w modelu" (Faltinsen B, 90 %), nic z URANS.

CELOWO OSOBNY PLIK: k3.py i k3_widmo.py NIE sa zmieniane, bo nocny przebieg K3 (start koordynatora po MPC) importuje je przy starcie.
Ten modul dziala tylko we wlasnym procesie: dopisuje przypadki do slownika k3_widmo.CASES i podmienia klasy K3/K0P na wersje z Wienerem.

Filtr: FIR 150 wspolczynnikow po 10 ms (pamiec 1,5 s), j = 0 najnowsza probka; projekt dokladnie jak u C (wiener_vs_fizyka.wiener):
  zapisy treningowe S1-S4 o INNYCH ziarnach niz test (9000 + 10*nr + j, j = 0..4, po 300 s), kazdy unormowany do jednakowej wariancji w,
  szum sondy sigma w projekcie = noise_m z konfiguracji (domyslnie 1 cm), bez opoznienia.
  Wspolczynniki liczone raz i zapisywane: K3_WIENER\\FIR_ogolny_d<d>_s<sigma mm>.json (ponowne uzycie bez liczenia).
Uzycie:  python k3_wiener.py fir 3 [6]   - tylko zaprojektuj i zapisz filtry (ok. kilka min na 1 rdzeniu)
         python k3_wiener.py test         - krotki test 40 s na S1 (K0P_85 z Wienerem 3 m i 6 m; K3 z Wienerem 6 m) - PO zakonczeniu nocnego K3
         python k3_wiener.py worker K N [rdzen0] / summary - jak k3_widmo.py, wyniki w K3_WIENER\\wyniki (tylko na zlecenie koordynatora)"""
import json, sys, time
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; ROOT = HERE.parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(ROOT / "CZUJNIK_FALI_K0"))
import k3_widmo as KW
from k3 import K3, K0P
OUT = HERE / "K3_WIENER"


def fir_ogolny(d, sigma=0.01, L=150):
    """filtr Wienera ogolny agenta C dla sondy d m przed krawedzia natarcia; z pliku, jesli juz policzony"""
    OUT.mkdir(exist_ok=True); f = OUT / f"FIR_ogolny_d{d:g}_s{int(round(1000 * sigma))}.json"
    if f.exists(): return np.array(json.loads(f.read_text())["h"])
    import wiener_vs_fizyka as C                                       # modul agenta C - tylko import, bez zmian
    seeds = lambda sea: [9000 + 10 * int(sea[1]) + j for j in range(5)]
    train = [(e, w, 1.0 / w.std()) for sea in C.SEAS for e, w in C.records(sea, seeds(sea), d, 300.0)[0]]
    h = C.wiener(train, sigma, 0, L)
    f.write_text(json.dumps(dict(d=d, sigma=sigma, L=L, dt=0.01, zrodlo="wiener_vs_fizyka.wiener (agent C), ogolny S1-S4, ziarna 9000+10*nr+j", h=h.tolist())))
    return h


class _WienerMixin:
    """preview='wiener': przed pierwszym taktem wstawia FIR Wienera w miejsce probe_kernel; reszta (bufor sondy, szum, statystyki) bez zmian z k3._Probe"""
    def _probe_tick(self):
        if self.preview == "wiener" and self.kern is None:
            self.kern = fir_ogolny(self.probe_d, self.noise_m); self.kern_lost = None; self.buf = np.zeros(len(self.kern))
        super()._probe_tick()


class K3W(_WienerMixin, K3):
    last = {}


class K0PW(_WienerMixin, K0P):
    last = {}; CFG = {}

    def __init__(self, *a, **kw):
        K0P.CFG = K0PW.CFG; super().__init__(*a, **kw)


S = KW.S
CASES = {
    "K0P_85_wiener3m":            dict(rigid=dict(k_wave=0.85, probe_d=3.0, preview="wiener")),
    "K0P_85_wiener6m":            dict(rigid=dict(k_wave=0.85, probe_d=6.0, preview="wiener")),
    "K3_sky+K0_85_wiener3m":      dict(susp=dict(S, c_rel=0.0, c_sky=1.0, k_wave=0.85, probe_d=3.0, preview="wiener")),
    "K3_sky+odzysk+K0_50_wiener3m": dict(susp=dict(S, c_rel=0.5, c_sky=1.0, k_wave=0.5, probe_d=3.0, preview="wiener")),
}


def install():
    """tylko w tym procesie: przypadki Wienera do k3_widmo.CASES, klasy K3/K0P w k3_widmo -> wersje z Wienerem, wyniki do K3_WIENER"""
    KW.CASES.clear(); KW.CASES.update(CASES); KW.K3, KW.K0P = K3W, K0PW
    KW.OUT = OUT; KW.RES = OUT / "wyniki"; KW.LOG = OUT / "k3_wiener.log"; OUT.mkdir(exist_ok=True)


if __name__ == "__main__":
    a = sys.argv[1]
    if a == "fir":
        for d in sys.argv[2:]:
            t0 = time.time(); h = fir_ogolny(float(d)); print(f"FIR Wiener ogolny d {d} m: {len(h)} wsp., suma {h.sum():.4f}, {time.time() - t0:.0f} s", flush=True)
    else:
        install()
        if a == "worker": KW.worker(int(sys.argv[2]), int(sys.argv[3]), int(sys.argv[4]) if len(sys.argv) > 4 else None)
        elif a == "summary": KW.summary()
        elif a == "test":
            KW.W.T_SIM, KW.W.T_SKIP = 40.0, 10.0
            for c in ("K0P_85_wiener3m", "K0P_85_wiener6m", "K3_sky+odzysk+K0_50_wiener3m"):
                t0 = time.time(); r = KW.run(c, "S1", 0)
                print(c, {k: (round(float(v), 3) if isinstance(v, (float, np.floating)) else v) for k, v in r.items() if k in
                          ("P_W", "acc_rms", "MSI_2h_pct", "sub_min", "stroke_absmax", "P_gen_el_W_per_m", "rate_rms_deg_s", "w_est_err_rel")},
                      f"{time.time() - t0:.0f} s", flush=True)
