"""susp3.py - pomysl Julka 12.11: poduszka powietrzna (+ tlumik polaktywny) MIEDZY KADLUBEM A WSPORNIKIEM
oraz dodatkowa SPREZYNA PRZY PLACIE, ktora lapie szybkie oscylacje. W modelu wirowym, jeden plat, tylko pion.

Trzy masy (na 1 m rozpietosci):
  kadlub   M_h = 1525 - m_s kg/m
  nosnik   m_s = 30 kg/m (wspornik + gniazdo sprezyny)
  plat     m_f = 40 kg/m + masa dodana 76 kg/m
  kadlub --[poduszka: stala sila + k1 + tlumik c1 (odzysk 70 %), odboje +-0,9 m]-- nosnik --[sprezyna plata k2 + c2, odboje +-0,15 m]-- plat
  k1 z f1 = 0,7 Hz (kadlub na poduszce), k2 z f2 = czestotliwosc wlasna PLATA na sprezynie (3 / 6 Hz), zeta2 0,1.
  polaktywne: tlumik poduszki twardo (zeta 0,7) normalnie, upust (0,05) gdy zmierzone albo przewidziane w 0,5 s zanurzenie < 2,2c.
Sterowanie: PID (PID2 Godo na wysokosc kadluba) i MPC (model dwoch mas: sprezyna plata traktowana jako sztywna - przyblizenie).
Porownanie z wynikami z nocy (SUSP_MPC_RESULT.json): te same fale (5 realizacji), z_ref -0,4 m.
Wynik: SUSP3_RESULT.json, log susp3.out.
"""
import json, sys, time, pickle
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import vortex_plant as VP
from vortex_plant import Plant, C, DEPTH, SPAN, BUOY
from uvm_step import G
import mpc_irr as M
import mpc_irr2 as M2
import susp_test as S
import susp_mpc as SM
import godo_vortex_env as GE

M_S = 30.0
DT = SM.DT


class SuspPlant3(S.SuspPlant):
    def __init__(self, f1=0.7, zeta1=0.7, f2=3.0, zeta2=0.1, **kw):
        super().__init__(fn=f1, zeta=zeta1, **kw)
        self.MH = S.M_H - M_S
        self.k = self.MH * (2 * np.pi * f1) ** 2; self.c_crit = 2 * np.sqrt(self.k * self.MH); self.c = zeta1 * self.c_crit
        mfa = S.M_F + S.M_A
        self.k2 = mfa * (2 * np.pi * f2) ** 2; self.c2 = zeta2 * 2 * np.sqrt(self.k2 * mfa)

    def reset(self, *a, **kw):
        super().reset(*a, **kw); self.zc = 0.0; self.vc = 0.0

    def heave_update(self, dt):
        x1 = self.zc - self.zh; x1d = self.vc - self.vh
        x2 = self.z - self.zc; x2d = self.v - self.vc
        F1 = self.MH * G + self.k * x1 + self.c * x1d
        if abs(x1) > 0.9: F1 += S.K_STOP * (abs(x1) - 0.9) * np.sign(x1)
        F2 = (self.MH + M_S) * G + self.k2 * x2 + self.c2 * x2d
        if abs(x2) > 0.15: F2 += S.K_STOP * (abs(x2) - 0.15) * np.sign(x2)
        self.ah = (F1 - self.MH * G) / self.MH
        self.vh += dt * self.ah; self.zh += dt * self.vh
        self.vc += dt * (F2 - F1 - M_S * G) / M_S; self.zc += dt * self.vc
        self.v += dt * (self.Fy + BUOY - S.M_F * G - F2) / (S.M_F + S.M_A)
        self.E_odz += 0.7 * self.c * x1d * x1d * dt


# wariant: (f1, zeta1, f2, polaktywny)
VAR = {"polaktywne+sprezyna_3Hz": (0.7, 0.7, 3.0, True), "polaktywne+sprezyna_6Hz": (0.7, 0.7, 6.0, True),
       "pasywne0.7+sprezyna_3Hz": (0.7, 0.3, 3.0, False)}


def run(seed, var, ctrl, zref, mdl, pred, T=30.0):
    rng = np.random.default_rng(4000 + seed)
    f1, z1, f2, semi = VAR[var]
    p = SuspPlant3(f1=f1, zeta1=z1, f2=f2)
    M2.irr(p, seed); p.reset(theta_deg=VP.TH_REF_DEG, z=zref); p.cmd = SM.THR
    for _ in range(1000): p.step(free_heave=False)
    p.zh, p.vh, p.zc, p.vc = p.z, 0.0, p.z, 0.0
    he = {s_: [M2.noisy(p.eta_ahead(s_[0], p.t - DT * i, s_[1]), rng, 0.0) for i in range(5 * M2.NH)][::-1] for s_ in M2.ALLS}
    if ctrl == "MPC":
        mk = lambda cz: SM.MPC2(mdl, k=p.k, c=cz, rigid=False, zref=zref)
        mpcs = {"hard": mk(p.c_crit * z1)}
        if semi: mpcs["soft"] = mk(0.05 * p.c_crit)
        th_h, v_h, u = np.full(SM.NL, p.th), np.zeros(SM.NL), SM.THR
    integ, rows, fail, soft_n = 0.0, [], None, 0
    for k in range(int(T / DT)):
        zh, vh = p.zh, p.vh
        r_ = M2.regs(he, "d3"); efut = r_ @ pred["d3"]["Pe"]; wv = r_ @ pred["d3"]["Pw"]
        mode = "hard"
        if semi:
            sub_now = p.eta_LE() - (p.z - DEPTH); sub_pred = efut[:50] - (p.z - DEPTH)
            if min(sub_now, sub_pred.min()) < 2.2 * C: mode = "soft"; soft_n += 1
            p.c = (0.05 if mode == "soft" else 0.7) * p.c_crit
        if ctrl == "PID":
            e = zref - zh; integ += e * DT
            p.cmd = np.radians(np.clip(VP.TH_REF_DEG + 6.63 * e + 1.18 * integ, -7.5, 7.5))
        else:
            if k % SM.BLK == 0:
                mp = mpcs.get(mode, mpcs["hard"])
                u = mp.solve(np.array([p.th, p.w_servo]), th_h, v_h, wv[:SM.NW][::-1], p.z, p.v, zh, vh, wv[SM.NW:], efut, u)
                for o in mpcs.values(): o.Uprev = mp.Uprev
            th_h = np.r_[p.th, th_h[:-1]]; v_h = np.r_[p.v, v_h[:-1]]; p.cmd = u
        Ds = 0.0; v0 = vh
        for _ in range(p.tick):
            r = p.step(True); Ds += r["Fx"]
        sub = p.eta_LE() - (p.z - DEPTH); D = Ds / p.tick * SPAN
        rows.append(dict(D=D, Dtot=D + GE.STRUT_K * max(sub, 0), sub=sub, zh=p.zh, x=p.zc - p.zh, x2=p.z - p.zc, acc=(p.vh - v0) / DT,
                         E=p.E_odz, th=r["theta_deg"], t=(k + 1) * DT))
        for s_ in he: he[s_] = he[s_][1:] + [M2.noisy(p.eta_ahead(s_[0], p.t, s_[1]), rng, he[s_][-1])]
        if sub < C: fail = "zanurzenie < 1c"; break
        if abs(p.zh - zref) > 0.75: fail = "|z kadluba - z_ref| > 0,75 m"; break
        if not np.isfinite(p.z): fail = "niestabilnosc"; break
    n = len(rows); h = rows[max(0, n - 2000):]; A = lambda q: np.array([x[q] for x in h])
    res = dict(upadek=fail, t_upadek=round(n * DT, 2) if fail else None, upust=round(soft_n / max(1, n), 3))
    if not fail:
        Dcw = json.loads((HERE / "D_CW.json").read_text())["D_cw_N_strip"]; Dcw_tot = Dcw + GE.STRUT_K * DEPTH
        res.update(plat_pct=100 * (A("D").mean() / Dcw - 1), tot_pct=100 * (A("Dtot").mean() / Dcw_tot - 1), acc_kadlub=float(np.sqrt((A("acc") ** 2).mean())),
                   sub_min_c=float(A("sub").min() / C), skok_poduszki=[float(A("x").min()), float(A("x").max())],
                   skok_sprezyny_plata=[float(A("x2").min()), float(A("x2").max())],
                   odzysk_W=float((h[-1]["E"] - h[0]["E"]) / (h[-1]["t"] - h[0]["t"]) * SPAN))
    return res


if __name__ == "__main__":
    t0 = time.time()
    _, pred = pickle.loads((HERE / "MPC_IRR2_MODEL.pkl").read_bytes())
    mdl = SM.phys_fix(pickle.loads((HERE / "MPC_IRR2_MODEL_v2.pkl").read_bytes()))
    rf = HERE / "SUSP3_RESULT.json"; out = dict(opis=__doc__, wyniki={})
    if rf.exists(): out["wyniki"] = json.loads(rf.read_text(encoding="utf-8")).get("wyniki", {})
    SEEDS = (1, 3, 4, 5, 6); ZREF = -0.4
    COMBOS = [(v, c) for c in ("MPC", "PID") for v in VAR]
    for seed in SEEDS:
        for var, ctrl in COMBOS:
            key = f"fala{seed}_{var}_{ctrl}_z{ZREF:+.1f}"
            if key in out["wyniki"]: continue
            r = run(seed, var, ctrl, ZREF, mdl, pred); out["wyniki"][key] = r
            print(f"{key:48s}: " + (f"UPADEK po {r['t_upadek']} s ({r['upadek']})" if r["upadek"] else
                  f"plat {r['plat_pct']:+.0f}% | z wspornikami {r['tot_pct']:+.0f}% | z̈ kadluba {r['acc_kadlub']:.2f} | zanurz. min {r['sub_min_c']:.2f}c | skok sprezyny plata {r['skok_sprezyny_plata'][0]:+.3f}..{r['skok_sprezyny_plata'][1]:+.3f} | odzysk {r['odzysk_W']:.1f} W"), flush=True)
            rf.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    summ = {}
    for var, ctrl in COMBOS:
        rs = [out["wyniki"][f"fala{s}_{var}_{ctrl}_z{ZREF:+.1f}"] for s in SEEDS]; ok = [r for r in rs if not r["upadek"]]
        k_ = f"{var}_{ctrl}"
        summ[k_] = dict(przezyl=f"{len(ok)}/{len(rs)}", tot_pct=round(np.mean([r["tot_pct"] for r in ok]), 1) if ok else None,
                        plat_pct=round(np.mean([r["plat_pct"] for r in ok]), 1) if ok else None, acc=round(np.mean([r["acc_kadlub"] for r in ok]), 2) if ok else None)
        print(f"PODSUMOWANIE {k_:36s}: przezyl {summ[k_]['przezyl']}, z wspornikami {summ[k_]['tot_pct']} %, plat {summ[k_]['plat_pct']} %, z̈ {summ[k_]['acc']}", flush=True)
    out["podsumowanie"] = summ; rf.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("gotowe", round(time.time() - t0), "s")
