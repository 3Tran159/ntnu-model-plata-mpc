"""susp_test.py - pomysl Julka: plat na ZAWIESZENIU (mala masa nieresorowana), jeden plat, tylko pion. W modelu wirowym.

Uklad (na 1 m rozpietosci):
  kadlub  M_h = 1525 kg/m   :  M_h dV/dt = F_s - M_h g
  plat    m_f = 40 kg/m + masa dodana wody m_a = rho*pi*c^2/4 = 76 kg/m (ZALOZENIE: model wirowy nie liczy jej osobno)
                             :  (m_f + m_a) dv/dt = L + B - m_f g - F_s
  zawieszenie (poduszka pneumatyczna ~ stala sila + tlumik):  F_s = M_h g + k*x + c*dx/dt,  x = z_plat - z_kadlub (dodatnie = plat podjechal w gore, sciska)
     k = M_h (2 pi f_n)^2 (f_n = czestotliwosc wlasna kadluba na zawieszeniu), c = 2 zeta sqrt(k M_h); odboje przy |x| > 0,9 m (bardzo sztywna sprezyna)
  odzysk: P_odz = 0,7 * c * (dx/dt)^2  (tlumik-pradnica, sprawnosc 70 %)
  wysokosc: wolny PID (Kp, Ki jak PID2 Godø) na wysokosc KADLUBA -> kat plata.
ZALOZENIE: opoznienie sily od nurzania z kalibracji (0,08 s) wylaczone - dla lekkiego plata jest fizycznie natychmiastowe (Wagner jest w modelu wirowym).
Warianty: sztywny (dzisiejszy), pasywne f_n = 0,3 / 0,7 / 1,5 Hz (zeta 0,3), polaktywne z prognoza (czujnik 3 m):
  normalnie twardo (zeta 0,7, odzysk), "upust" (zeta 0,05) gdy przewidziane w ciagu 0,5 s zanurzenie plata < 2,5c.
Fala: te same 5 realizacji krotkogrzbietowych co MPC_IRR2 (JONSWAP Hs 1,5 m, Tp 5 s), szum czujnikow.
Upadek: zanurzenie plata < 1c albo |z kadluba| > 0,75 m.
Wynik: SUSP_RESULT.json + podglad na zywo (runs/SUSP/live_ep.json).
"""
import json, sys, time, pickle
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import vortex_plant as VP
from vortex_plant import Plant, C, DEPTH, U, SPAN, BUOY, RHO
from uvm_step import G
import mpc_irr as M
import mpc_irr2 as M2

M_TOT = VP.MASS; M_F = 40.0; M_H = M_TOT - M_F; M_A = RHO * np.pi * C ** 2 / 4
TH_REF = VP.TH_REF_DEG; KP, KI = 6.63, 1.18; TH_MAX = 7.5
X_STOP, K_STOP = 0.9, 5e6
DT_TICK = 0.01
LIVE = HERE / "runs" / "SUSP"


class SuspPlant(Plant):
    def __init__(self, fn=0.7, zeta=0.3, **kw):
        cal = dict(json.loads((HERE / "CALIB_CL.json").read_text())["G_gain_delay_fit_BASE2+PRBS1"]); cal["d_heave_s"] = 0.0
        super().__init__(calib=cal, **kw)
        self.set_spring(fn, zeta); self.zeta_now = zeta

    def set_spring(self, fn, zeta):
        self.k = M_H * (2 * np.pi * fn) ** 2; self.c_crit = 2 * np.sqrt(self.k * M_H); self.c = zeta * self.c_crit

    def reset(self, *a, **kw):
        super().reset(*a, **kw); self.zh = 0.0; self.vh = 0.0; self.E_odz = 0.0; self.ah = 0.0

    def heave_update(self, dt):
        x = self.z - self.zh; xd = self.v - self.vh
        Fs = M_H * G + self.k * x + self.c * xd
        if abs(x) > X_STOP: Fs += K_STOP * (abs(x) - X_STOP) * np.sign(x)
        self.ah = (Fs - M_H * G) / M_H
        self.vh += dt * self.ah; self.zh += dt * self.vh
        self.v += dt * (self.Fy + BUOY - M_F * G - Fs) / (M_F + M_A)
        self.E_odz += 0.7 * self.c * xd * xd * dt


def run(seed, mode, pred, T=30.0):
    rng = np.random.default_rng(3000 + seed)
    rigid = mode == "sztywny"
    if rigid: p = Plant()
    else:
        fn = {"pasywne_0.3Hz": 0.3, "pasywne_0.7Hz": 0.7, "pasywne_1.5Hz": 1.5}.get(mode, 0.7)
        p = SuspPlant(fn=fn, zeta=0.3 if mode.startswith("pasywne") else 0.7)
    M2.irr(p, seed); p.reset(theta_deg=TH_REF); p.cmd = np.radians(TH_REF)
    for _ in range(1000): p.step(free_heave=False)
    if not rigid: p.zh, p.vh = p.z, 0.0
    he = {s: [M2.noisy(p.eta_ahead(s[0], p.t - DT_TICK * i, s[1]), rng, 0.0) for i in range(5 * M2.NH)][::-1] for s in M2.ALLS}
    integ, rows, k = 0.0, [], 0
    n_ticks = int(T / DT_TICK); fail = None; soft = 0
    for k in range(n_ticks):
        zh = p.z if rigid else p.zh
        e = -zh; integ += e * DT_TICK
        p.cmd = np.radians(np.clip(TH_REF + KP * e + KI * integ, -TH_MAX, TH_MAX))
        if mode == "polaktywne_prognoza":
            efut = M2.regs(he, "d3") @ pred["d3"]["Pe"]          # przewidziana powierzchnia nad platem na 1,94 s
            sub_pred = efut[:50] - (p.z - DEPTH)                  # nastepne 0,5 s przy obecnym polozeniu plata
            if sub_pred.min() < 2.5 * C: p.c = 0.05 * p.c_crit; soft += 1
            else: p.c = 0.7 * p.c_crit
        Dsum = 0.0; ah = []
        v0 = p.v if rigid else p.vh
        for _ in range(p.tick):
            r = p.step(True); Dsum += r["Fx"]
        acc_h = ((p.v if rigid else p.vh) - v0) / DT_TICK
        sub = p.eta_LE() - (p.z - DEPTH)
        rows.append(dict(t=round((k + 1) * DT_TICK, 2), z_f=p.z, z_h=zh if rigid else p.zh, x=0.0 if rigid else p.z - p.zh, th=r["theta_deg"],
                         eta=r["eta_LE"], sub=sub, D=Dsum / p.tick * SPAN, acc=acc_h, E=0.0 if rigid else p.E_odz))
        for s in he: he[s] = he[s][1:] + [M2.noisy(p.eta_ahead(s[0], p.t, s[1]), rng, he[s][-1])]
        if k % 50 == 0: live(seed, mode, rows, False, None)
        if sub < C: fail = "zanurzenie < 1c"; break
        if abs(rows[-1]["z_h"]) > 0.75: fail = "|z kadluba| > 0,75 m"; break
        if not np.isfinite(p.z): fail = "niestabilnosc"; break
    live(seed, mode, rows, True, fail)
    n = len(rows); h = rows[max(0, n - 2000):]; A = lambda q: np.array([x[q] for x in h])
    res = dict(upadek=fail, t_upadek=round(n * DT_TICK, 2) if fail else None, udzial_upustu=round(soft / max(1, n), 3))
    if not fail:
        Dcw = json.loads((HERE / "D_CW.json").read_text())["D_cw_N_strip"]
        res.update(D_rel=float(A("D").mean() / Dcw - 1), acc_rms_kadlub=float(np.sqrt((A("acc") ** 2).mean())), sub_min_c=float(A("sub").min() / C),
                   skok=[float(A("x").min()), float(A("x").max())], z_h=[float(A("z_h").min()), float(A("z_h").max())],
                   odzysk_W_na_pasek=float((h[-1]["E"] - h[0]["E"]) / (h[-1]["t"] - h[0]["t"]) * SPAN))
    return res


def live(seed, mode, rows, done, fail):
    LIVE.mkdir(parents=True, exist_ok=True)
    g = lambda q: [round(float(x[q]), 4) for x in rows]
    M._atomic(LIVE / "live_ep.json", dict(alg="susp", episode=seed, step=len(rows), mode=mode, seed=seed, sigma=0, R=0, done=done, term=bool(fail) if done else None,
                                         loss_c=None, loss_a=None, alpha=None, D_cw=json.loads((HERE / "D_CW.json").read_text())["D_cw_N_strip"], dt=DT_TICK,
                                         z=g("z_f"), z_hull=g("z_h"), th=g("th"), cmd=g("th"), eta=g("eta"), sub=g("sub"), D=g("D"), r=[0] * len(rows),
                                         fail=fail, time=time.strftime("%H:%M:%S")))


if __name__ == "__main__":
    t0 = time.time()
    _, pred = pickle.loads((HERE / "MPC_IRR2_MODEL.pkl").read_bytes())
    rf = HERE / "SUSP_RESULT.json"
    out = dict(opis=__doc__, wyniki={})
    if rf.exists(): out["wyniki"] = json.loads(rf.read_text(encoding="utf-8")).get("wyniki", {})
    SEEDS = (1, 3, 4, 5, 6); MODES = ["sztywny", "pasywne_0.3Hz", "pasywne_0.7Hz", "pasywne_1.5Hz", "polaktywne_prognoza"]
    for seed in SEEDS:
        for mode in MODES:
            key = f"fala{seed}_{mode}"
            if key in out["wyniki"]: continue
            r = run(seed, mode, pred); out["wyniki"][key] = r
            print(f"fala {seed} {mode:20s}: " + (f"UPADEK po {r['t_upadek']} s ({r['upadek']})" if r["upadek"] else
                  f"opor {100*r['D_rel']:+.0f}% | zacc kadluba RMS {r['acc_rms_kadlub']:.2f} | zanurz. min {r['sub_min_c']:.2f}c | skok {r['skok'][0]:+.2f}..{r['skok'][1]:+.2f} m | odzysk {r['odzysk_W_na_pasek']:.2f} W/pasek | upust {100*r['udzial_upustu']:.0f}%"), flush=True)
            rf.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    summ = {}
    for mode in MODES:
        rs = [out["wyniki"][f"fala{s}_{mode}"] for s in SEEDS]; ok = [r for r in rs if not r["upadek"]]
        summ[mode] = dict(przezyl=f"{len(ok)}/{len(rs)}", opor_sr=None if not ok else round(100 * np.mean([r["D_rel"] for r in ok]), 1),
                          acc_sr=None if not ok else round(np.mean([r["acc_rms_kadlub"] for r in ok]), 2))
        print(f"PODSUMOWANIE {mode:20s}: przezyl {summ[mode]['przezyl']}, opor {summ[mode]['opor_sr']} %, zacc kadluba {summ[mode]['acc_sr']} m/s2", flush=True)
    out["podsumowanie"] = summ; rf.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("gotowe", round(time.time() - t0), "s")
