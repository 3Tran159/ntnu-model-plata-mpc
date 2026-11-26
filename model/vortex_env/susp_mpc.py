"""susp_mpc.py - noc 11/12.11: kombinacje ZAWIESZENIE x STEROWANIE x GLEBOKOSC na fali nieregularnej, model wirowy v2
(biegunowa CD(CL) z URANS + opor wspornikow). Jeden plat, tylko pion.

Fala: 5 realizacji krotkogrzbietowych JONSWAP Hs 1,5 m, Tp 5 s (te same co MPC_IRR2), szum czujnikow 2 cm / 5 % zanikow.
Sterowanie:
  PID   - PID2 Godø na wysokosc KADLUBA (z_ref), kat plata
  MPC   - MPC liniowy (czujnik 3 m + sonda), horyzont 1,94 s; przy zawieszeniu model DWOCH MAS (kadlub + plat na sprezynie z tlumikiem)
Zawieszenie (jak susp_test.py): sztywne | pasywne f_n 1,5 Hz zeta 0,3 | pasywne 0,7 Hz | polaktywne v2:
  twardo (zeta 0,7, odzysk) normalnie; upust (zeta 0,05) gdy ZMIERZONE albo PRZEWIDZIANE w 0,5 s zanurzenie PLATA < 2,2c.
Glebokosc: projektowa 1,09 m albo o 0,4 m glebiej (z_ref = -0,4 m; placi wiecej za wspornik).
Opor raportowany: plat i plat + wsporniki, wzgledem wody spokojnej (PID2, 1,09 m) z wspornikami.
Wynik: SUSP_MPC_RESULT.json.  Wszystko "w modelu wirowym".
"""
import json, sys, time, pickle
from pathlib import Path
import numpy as np
from scipy.optimize import minimize
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import vortex_plant as VP
from vortex_plant import Plant, C, DEPTH, U, SPAN, BUOY
from uvm_step import G
import mpc_irr as M
import mpc_irr2 as M2
import susp_test as S
import godo_vortex_env as GE

DT, H, BLK, NL, NW = 0.01, M.H, M.BLK, M.NL, M.NW
THR, THM = np.radians(VP.TH_REF_DEG), np.radians(7.5)
W_Z, W_DU, W_S = 20.0, 2000.0, 2e4
M_H, M_FA = S.M_H, S.M_F + S.M_A


class MPC2:
    """MPC z modelem dwoch mas; kz, cz = sprezyna i tlumik (na 1 m); rigid=True -> model jednej masy (jak mpc_irr)."""
    def __init__(s, mdl, k=0.0, c=0.0, rigid=True, zref=0.0):
        s.m, s.k, s.c, s.rigid, s.zref = mdl, k, c, rigid, zref
        s.nb = H // BLK + (H % BLK > 0)
        s.Fu = np.zeros((s.nb, H, 6)); s.Zfu = np.zeros((s.nb, H)); s.Zhu = np.zeros((s.nb, H))
        for j in range(s.nb):
            Uv = np.zeros(H); Uv[j * BLK:(j + 1) * BLK] = 1.0
            s.Fu[j], s.Zfu[j], s.Zhu[j] = s.sim(np.zeros(2), np.zeros(NL), np.zeros(NL), np.zeros(NW), 0, 0, 0, 0, Uv, np.zeros(H), homog=True)
        s.Uprev = None

    def sim(s, xs, th_h, v_h, wf_h, zf, vf, zh, vh, Uv, wfut, homog=False):
        m = s.m; a = m["arx"]; th_h, v_h, wf_h, xs = th_h.copy(), v_h.copy(), wf_h.copy(), xs.copy()
        f = np.zeros((H, 6)); Zf = np.zeros(H); Zh = np.zeros(H)
        for kk in range(H):
            th_h = np.r_[xs[0], th_h[:-1]]; v_h = np.r_[vf, v_h[:-1]]; wf_h = np.r_[wfut[kk], wf_h[:-1]]
            L = (0.0 if homog else a[0]) + a[1:1 + NL] @ th_h + a[1 + NL:1 + 2 * NL] @ v_h + a[1 + 2 * NL:] @ wf_h
            f[kk] = [xs[0] - (0.0 if homog else THR), xs[1], vf, wf_h[0], wf_h[8], L - (0.0 if homog else m["l0"])]
            Zf[kk], Zh[kk] = zf, zh
            if s.rigid:
                vf = vf + DT * (L + (0.0 if homog else BUOY - VP.MASS * G)) / VP.MASS; zf = zf + DT * vf; zh, vh = zf, vf
            else:
                Fs = (0.0 if homog else M_H * G) + s.k * (zf - zh) + s.c * (vf - vh)
                vh = vh + DT * (Fs - (0.0 if homog else M_H * G)) / M_H; zh = zh + DT * vh
                vf = vf + DT * (L + (0.0 if homog else BUOY - S.M_F * G) - Fs) / M_FA; zf = zf + DT * vf
            xs = m["As"] @ xs + m["Bs"] * Uv[kk]
        return f, Zf, Zh

    def solve(s, xs, th_h, v_h, wf_h, zf, vf, zh, vh, wfut, etafut, u_last):
        f0, zf0, zh0 = s.sim(xs, th_h, v_h, wf_h, zf, vf, zh, vh, np.zeros(H), wfut)
        Mq, p = s.m["M"], s.m["p"]; Fm = s.Fu.transpose(1, 0, 2)
        eh = zh0 - s.zref
        g = np.einsum("kjf,f->j", Fm, p) + 2 * np.einsum("kjf,fg,kg->j", Fm, Mq, f0) + 2 * W_Z * s.Zhu @ eh
        Hs = 2 * np.einsum("kjf,fg,kig->ji", Fm, Mq, Fm) + 2 * W_Z * s.Zhu @ s.Zhu.T
        Dm = np.eye(s.nb) - np.eye(s.nb, k=-1); Hs += 2 * W_DU * Dm.T @ Dm
        e0 = np.zeros(s.nb); e0[0] = u_last; g += -2 * W_DU * Dm.T @ e0
        w, V = np.linalg.eigh(0.5 * (Hs + Hs.T)); w = np.maximum(w, 1e-3 * w.max()); Hs = (V * w) @ V.T
        zfmax = etafut + DEPTH - 2 * C; zhmax, zhmin = s.zref + 0.5, s.zref - 0.5
        ZF, ZH = s.Zfu.T, s.Zhu.T

        def fun(x):
            zf_ = zf0 + ZF @ x; zh_ = zh0 + ZH @ x
            e1 = np.maximum(0, zf_ - zfmax); e2 = np.maximum(0, zh_ - zhmax); e3 = np.maximum(0, zhmin - zh_)
            J = 0.5 * x @ Hs @ x + g @ x + W_S * (e1 @ e1 + e2 @ e2 + e3 @ e3)
            return J, Hs @ x + g + 2 * W_S * (ZF.T @ e1 + ZH.T @ (e2 - e3))
        x0 = np.full(s.nb, u_last) if s.Uprev is None else np.r_[s.Uprev[1:], s.Uprev[-1]]
        res = minimize(fun, x0, jac=True, method="L-BFGS-B", bounds=[(-THM, THM)] * s.nb)
        s.Uprev = res.x; return res.x[0]


SUSP = {"sztywne": None, "pasywne_1.5Hz": (1.5, 0.3), "pasywne_0.7Hz": (0.7, 0.3), "polaktywne_v2": (0.7, 0.7)}


def run(seed, susp, ctrl, zref, mdl, pred, T=30.0):
    rng = np.random.default_rng(4000 + seed)
    rigid = SUSP[susp] is None
    p = Plant() if rigid else S.SuspPlant(fn=SUSP[susp][0], zeta=SUSP[susp][1])
    M2.irr(p, seed); p.reset(theta_deg=VP.TH_REF_DEG, z=zref); p.cmd = THR
    for _ in range(1000): p.step(free_heave=False)
    if not rigid: p.zh, p.vh = p.z, 0.0
    he = {s_: [M2.noisy(p.eta_ahead(s_[0], p.t - DT * i, s_[1]), rng, 0.0) for i in range(5 * M2.NH)][::-1] for s_ in M2.ALLS}
    if ctrl == "MPC":
        mk = lambda cz: MPC2(mdl, k=0 if rigid else p.k, c=cz, rigid=rigid, zref=zref)
        mpcs = {"hard": mk(0 if rigid else p.c_crit * SUSP[susp][1])}
        if susp == "polaktywne_v2": mpcs["soft"] = mk(0.05 * p.c_crit)
        th_h, v_h, u = np.full(NL, p.th), np.zeros(NL), THR
    integ, rows, fail, soft_n = 0.0, [], None, 0
    for k in range(int(T / DT)):
        zh = p.z if rigid else p.zh; vh = p.v if rigid else p.vh
        r_ = M2.regs(he, "d3"); efut = r_ @ pred["d3"]["Pe"]; wv = r_ @ pred["d3"]["Pw"]
        mode = "hard"
        if susp == "polaktywne_v2":
            sub_now = p.eta_LE() - (p.z - DEPTH); sub_pred = efut[:50] - (p.z - DEPTH)
            if min(sub_now, sub_pred.min()) < 2.2 * C: mode = "soft"; soft_n += 1
            p.c = (0.05 if mode == "soft" else 0.7) * p.c_crit
        if ctrl == "PID":
            e = zref - zh; integ += e * DT
            p.cmd = np.radians(np.clip(VP.TH_REF_DEG + 6.63 * e + 1.18 * integ, -7.5, 7.5))
        else:
            if k % BLK == 0:
                mp = mpcs.get(mode, mpcs["hard"])
                u = mp.solve(np.array([p.th, p.w_servo]), th_h, v_h, wv[:NW][::-1], p.z, p.v, zh, vh, wv[NW:], efut, u)
                for o in mpcs.values(): o.Uprev = mp.Uprev
            th_h = np.r_[p.th, th_h[:-1]]; v_h = np.r_[p.v, v_h[:-1]]; p.cmd = u
        Ds = 0.0; v0 = vh
        for _ in range(p.tick):
            r = p.step(True); Ds += r["Fx"]
        zh2 = p.z if rigid else p.zh; vh2 = p.v if rigid else p.vh
        sub = p.eta_LE() - (p.z - DEPTH); D = Ds / p.tick * SPAN
        rows.append(dict(D=D, Dtot=D + GE.STRUT_K * max(sub, 0), sub=sub, zh=zh2, x=0.0 if rigid else p.z - p.zh, acc=(vh2 - v0) / DT,
                         E=0.0 if rigid else p.E_odz, th=r["theta_deg"], t=(k + 1) * DT))
        for s_ in he: he[s_] = he[s_][1:] + [M2.noisy(p.eta_ahead(s_[0], p.t, s_[1]), rng, he[s_][-1])]
        if sub < C: fail = "zanurzenie < 1c"; break
        if abs(zh2 - zref) > 0.75: fail = "|z kadluba - z_ref| > 0,75 m"; break
        if not np.isfinite(p.z): fail = "niestabilnosc"; break
    n = len(rows); h = rows[max(0, n - 2000):]; A = lambda q: np.array([x[q] for x in h])
    res = dict(upadek=fail, t_upadek=round(n * DT, 2) if fail else None, upust=round(soft_n / max(1, n), 3))
    if not fail:
        Dcw = json.loads((HERE / "D_CW.json").read_text())["D_cw_N_strip"]; Dcw_tot = Dcw + GE.STRUT_K * DEPTH
        res.update(plat_pct=100 * (A("D").mean() / Dcw - 1), tot_pct=100 * (A("Dtot").mean() / Dcw_tot - 1), acc_kadlub=float(np.sqrt((A("acc") ** 2).mean())),
                   sub_min_c=float(A("sub").min() / C), skok=[float(A("x").min()), float(A("x").max())], th=[float(A("th").min()), float(A("th").max())],
                   odzysk_W=float((h[-1]["E"] - h[0]["E"]) / (h[-1]["t"] - h[0]["t"]) * SPAN) if not rigid else 0.0)
    return res


def phys_fix(mdl):
    """Wzmocnienia statyczne ARX z fizyki modelu wirowego (ksztalt odpowiedzi w czasie zostaje z identyfikacji).
    Powod: wspolliniowe regresory + regularyzacja zanizaly dL/dtheta ok. 4,6x i tlumienie nurzania ok. 4x (11.11 wieczor)."""
    p = Plant(); q, dcl, cal = p.q, p.dcl, p.cal; a = mdl["arx"].copy()
    l0_old = mdl["l0"]
    G_th = cal["k_pitch"] * q * dcl; G_v = -cal["k_heave"] * q * dcl / U; G_w = cal["k_wave"] * q * dcl / U
    sl = {"th": slice(1, 1 + NL), "v": slice(1 + NL, 1 + 2 * NL), "w": slice(1 + 2 * NL, 1 + 2 * NL + NW)}
    info = {key: (round(float(a[sl[key]].sum())), round(float(Gp))) for key, Gp in (("th", G_th), ("v", G_v), ("w", G_w))}
    # model fizyczny (jak kalibracja wariantu G): wzmocnienie x opoznienie; heave bez opoznienia (lekki plat - jak SuspPlant)
    a[:] = 0.0
    a[1 + int(round(cal["d_pitch_s"] / DT))] = G_th
    a[1 + NL + 0] = G_v
    a[1 + 2 * NL + int(round(cal["d_wave_s"] / DT))] = G_w
    a[0] = l0_old - THR * G_th
    m2 = dict(mdl); m2["arx"] = a; m2["l0"] = l0_old; m2["phys_fix"] = info
    print("phys_fix (ARX -> fizyka) [suma przed, po]:", info, flush=True)
    return m2


if __name__ == "__main__":
    t0 = time.time()
    mf = HERE / "MPC_IRR2_MODEL_v2.pkl"
    _, pred = pickle.loads((HERE / "MPC_IRR2_MODEL.pkl").read_bytes())
    if mf.exists(): mdl = pickle.loads(mf.read_bytes())
    else: mdl = M.identify(M2.collect_spread()); mf.write_bytes(pickle.dumps(mdl))
    mdl = phys_fix(mdl)
    print(f"model MPC (v2): R2 sila {mdl['r2L']:.4f}, R2 opor {mdl['r2D']:.4f}", flush=True)
    rf = HERE / "SUSP_MPC_RESULT.json"; out = dict(opis=__doc__, wyniki={})
    if rf.exists(): out["wyniki"] = json.loads(rf.read_text(encoding="utf-8")).get("wyniki", {})
    SEEDS = (1, 3, 4, 5, 6)
    COMBOS = [(s_, c_, z_) for z_ in (0.0, -0.4) for c_ in ("PID", "MPC") for s_ in SUSP]
    for seed in SEEDS:
        for susp, ctrl, zref in COMBOS:
            key = f"fala{seed}_{susp}_{ctrl}_z{zref:+.1f}"
            if key in out["wyniki"]: continue
            r = run(seed, susp, ctrl, zref, mdl, pred); out["wyniki"][key] = r
            print(f"{key:40s}: " + (f"UPADEK po {r['t_upadek']} s ({r['upadek']})" if r["upadek"] else
                  f"plat {r['plat_pct']:+.0f}% | z wspornikami {r['tot_pct']:+.0f}% | z̈ kadluba {r['acc_kadlub']:.2f} | zanurz. min {r['sub_min_c']:.2f}c | skok {r['skok'][0]:+.2f}..{r['skok'][1]:+.2f} | odzysk {r['odzysk_W']:.1f} W | upust {100*r['upust']:.0f}%"), flush=True)
            rf.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    summ = {}
    for susp, ctrl, zref in COMBOS:
        rs = [out["wyniki"][f"fala{s}_{susp}_{ctrl}_z{zref:+.1f}"] for s in SEEDS]; ok = [r for r in rs if not r["upadek"]]
        k_ = f"{susp}_{ctrl}_z{zref:+.1f}"
        summ[k_] = dict(przezyl=f"{len(ok)}/{len(rs)}", tot_pct=round(np.mean([r["tot_pct"] for r in ok]), 1) if ok else None,
                        plat_pct=round(np.mean([r["plat_pct"] for r in ok]), 1) if ok else None, acc=round(np.mean([r["acc_kadlub"] for r in ok]), 2) if ok else None)
        print(f"PODSUMOWANIE {k_:32s}: przezyl {summ[k_]['przezyl']}, z wspornikami {summ[k_]['tot_pct']} %, plat {summ[k_]['plat_pct']} %, z̈ {summ[k_]['acc']}", flush=True)
    out["podsumowanie"] = summ; rf.write_text(json.dumps(out, indent=1, ensure_ascii=False), encoding="utf-8")
    print("gotowe", round(time.time() - t0), "s")
