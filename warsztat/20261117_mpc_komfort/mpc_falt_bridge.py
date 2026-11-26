"""mpc_falt_bridge.py - MPC z kara za komfort (mpc_komfort.MPC, model zidentyfikowany na modelu Faltinsena B, obciazenie 90 %)
jako serwer dla makra STAR (tryb policy/MPC jak OVS_MPC_WZ2), fala regularna Godo H 1,5 m, T 5 s. 17.11.2026, prosba Julka:
"waliduj MPC w URANS lokalnie".
Protokol jak mpc_bridge_server.py (pliki w katalogu przebiegu): makro -> MPC_REQ.txt "seq t z v th_deg rate_deg_s eta_LE free",
serwer -> MPC_RESP.txt "seq cmd_deg". Przyszla fala: faza i amplituda dopasowane na biezaco do zmierzonego eta przy LE
(eta = A cos(-ome t + beta), konwencja FaltinsenPlant); predkosc pionowa wody na placie jak wf_at w mpc_komfort.
Dodatkowo powolna calka po z (KI) - kasuje staly blad sily nosnej modelu MPC wzgledem URANS (inny trym).
Uzycie: python mpc_falt_bridge.py CASE_DIR W_A [KI=1.0] | python mpc_falt_bridge.py - W_A [KI] test   (test = Faltinsen B w miejsce STAR)."""
import sys, os, time, json, math
from pathlib import Path
import numpy as np
os.environ["MPC_W_A"] = sys.argv[2] if len(sys.argv) > 2 else "1"
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import mpc_komfort as MK
KI = float(sys.argv[3]) if len(sys.argv) > 3 and sys.argv[3] != "test" else 1.0
FP, U, DT, NL, NW = MK.FP, MK.U, MK.DT, MK.NL, MK.NW
P0 = MK.Z.FaltinsenPlant(wave_amp=0.73, **MK.Z.VB); OME, K, OM0 = P0.ome, P0.k, P0.om0
CASE = None if sys.argv[1] == "-" else Path(sys.argv[1])
PROBE_D = float(os.environ.get("MPC_PROBE_D", "0")); DT_PROBE = K * PROBE_D / OME     # sonda d przed LE: fala dochodzi do LE po k d / we (0,15 s przy 3 m)


def log(m):
    if CASE is None: print(m, flush=True); return
    with open(CASE / "mpc_bridge.log", "a", encoding="utf-8") as f: f.write(time.strftime("%H:%M:%S ") + m + "\n")


class Bridge:
    def __init__(s):
        s.m = MK.model(None); s.H = int(round(P0.Te / DT)); s.BLK = 5; s.mpc = MK.MPC(s.m, s.H, s.BLK); s.reset()

    def reset(s):
        s.th_h = None; s.v_h = None; s.u = None; s.k_free = 0; s.last_seq = None; s.mpc.Uprev = None; s.T, s.E = [], []; s.ie = 0.0
        if CASE is not None and (CASE / "history.csv").exists():      # 17.11: po wznowieniu z checkpointu - historia fali z history.csv (bez 0,5 s slepej fazy)
            try:
                import csv
                r = list(csv.reader(open(CASE / "history.csv"))); h = r[0]; it, ie_ = h.index("time_s"), h.index("GODO_eta_at_LE")
                d = sorted({float(x[it]): float(x[ie_]) for x in r[1:] if len(x) == len(h)}.items())[-3000:][::10]
                s.T, s.E = [a for a, _ in d], [b for _, b in d]; log(f"historia fali z history.csv: {len(s.T)} probek do t {s.T[-1]:.3f}")
            except Exception as e:
                log(f"historia fali: blad {e!r}")

    def wave(s):
        t = np.array(s.T[-300:]); e = np.array(s.E[-300:])
        if len(t) < 50: return 0.0, 0.73
        X = np.c_[np.cos(-OME * t), np.sin(-OME * t), np.ones_like(t)]; c1, c2, _ = np.linalg.lstsq(X, e, rcond=None)[0]   # 17.11: + stala (dolina od plata nad LE nie wchodzi w amplitude/faze)
        return math.atan2(-c2, c1), math.hypot(c1, c2)         # a cos(-ome t + b) = a cos b cos(-ome t) - a sin b sin(-ome t) -> c2 = -a sin b

    def step(s, seq, t, z, v, th_deg, rate_deg_s, eta, free):
        th, w = math.radians(th_deg), math.radians(rate_deg_s)
        if s.last_seq is not None and seq <= s.last_seq - 1:
            log(f"seq {seq} <= {s.last_seq}: restart makra - zeruje historie MPC"); s.reset()
        s.last_seq = seq
        if s.th_h is None: s.th_h, s.v_h = np.full(NL, th), np.zeros(NL); s.u = th
        s.T.append(t + DT_PROBE); s.E.append(eta)                    # probka z sondy = wzniesienie przy LE w chwili t + DT_PROBE
        if free:
            s.ie = float(np.clip(s.ie - z * DT, -0.5, 0.5))
            if s.k_free % s.BLK == 0:
                b, A = s.wave(); t0 = time.time()
                wf = lambda tt: A * OM0 * np.exp(-K * MK.DEPTH) * np.sin(K * MK.XQ - OME * tt + b)
                wf_h = wf(t - DT * np.arange(NW)); tf = t + DT * np.arange(1, s.H + 1)
                s.u = s.mpc.solve(np.array([th, w]), s.th_h, s.v_h, wf_h, z, v, wf(tf), A * np.cos(-OME * tf + b), s.u)
                if s.k_free % (s.BLK * 40) == 0:
                    log(f"t {t:.3f} z {z:+.3f} v {v:+.3f} th {th_deg:+.2f} eta {eta:+.3f} | fala A {A:.3f} b {math.degrees(b):+.1f} | ie {s.ie:+.3f} | cmd {math.degrees(s.u):+.2f} | {time.time()-t0:.2f} s")
            s.k_free += 1
            cmd = float(np.clip(s.u + math.radians(KI) * s.ie, -MK.THM, MK.THM))
        else:
            s.u = th; cmd = th
        s.th_h = np.r_[th, s.th_h[:-1]]; s.v_h = np.r_[v, s.v_h[:-1]]
        return math.degrees(cmd)


def put(p, txt):
    t = p.with_suffix(".tmp")
    for _ in range(2000):
        try:
            t.write_text(txt); os.replace(t, p); return
        except OSError:
            time.sleep(0.002)
    log("put: nie udalo sie zapisac odpowiedzi")


if __name__ == "__main__":
    br = Bridge()
    if "test" in sys.argv:      # harness: Faltinsen B regularna fala, 90 %, ten sam protokol
        Z = MK.Z; p = Z.FaltinsenPlant(wave_amp=0.727, wave_phase=0.4, **Z.VB)
        cl_eq = (FP.MASS * MK.G - MK.BUOY) / p.q; trim = FP.TH_REF_DEG + float(np.degrees((cl_eq - FP.CL_REF) / (p.slope * p.dcl)))
        p.reset(theta_deg=trim); rows = []; seq = 0; T_REL = 1.9368
        for k in range(int(15 * p.Te / DT)):
            free = p.t >= T_REL - 0.5e-3
            cmd = br.step(seq, p.t, p.z, p.v, math.degrees(p.th), math.degrees(p.w_servo), p.eta_LE(), free); seq += 1
            p.cmd = math.radians(cmd); Ls = Pd = 0.0
            for _ in range(p.tick):
                r = p.step(free_heave=free); Ls += r["L"]; Pd += r["P_drag_W_strip"]
            rows.append((p.t, Pd / p.tick, (Ls / p.tick + MK.BUOY) / FP.MASS - MK.G, p.z, math.degrees(p.th), r["sub_true"]))
        a = np.array(rows); b = a[a[:, 0] > a[-1, 0] - 4 * p.Te]
        print(json.dumps(dict(W_A=MK.W_A, KI=KI, dP_pct=round(100 * (b[:, 1].mean() / 57.03 - 1), 2), acc_rms=round(float(b[:, 2].std()), 3),
                              z=[round(float(b[:, 3].min()), 3), round(float(b[:, 3].max()), 3)], th=[round(float(b[:, 4].min()), 2), round(float(b[:, 4].max()), 2)],
                              sub_min=round(float(b[:, 5].min()), 3))), flush=True)
        sys.exit()
    log(f"start: W_A {MK.W_A}, KI {KI}, ome {OME:.4f}, H {br.H}, sonda {PROBE_D} m przed LE (wyprzedzenie {DT_PROBE:.3f} s)")
    req, resp = CASE / "MPC_REQ.txt", CASE / "MPC_RESP.txt"; seen = None
    while True:
        if (CASE / "MPC_STOP").exists(): log("MPC_STOP - koniec"); break
        rr = CASE / "RUN_RESULT.json"
        if rr.exists() and req.exists() and rr.stat().st_mtime > req.stat().st_mtime + 5:
            try:
                if json.loads(rr.read_text())["result"] in ("DONE", "HOLD_LIMIT", "HOLD_CFL", "HOLD_NAN"): log("RUN_RESULT - koniec"); break
            except Exception: pass
        try:
            txt = req.read_text().split()
        except Exception:
            time.sleep(0.005); continue
        if len(txt) < 8 or txt[0] == seen: time.sleep(0.005); continue
        try:
            seq = int(txt[0]); t, z, v, thd, rate, eta = map(float, txt[1:7]); free = txt[7] == "1"
        except Exception:
            time.sleep(0.005); continue
        seen = txt[0]
        try:
            cmd = br.step(seq, t, z, v, thd, rate, eta, free)
        except Exception as e:
            log(f"BLAD {e!r} - poprzednia komenda"); cmd = math.degrees(br.u) if br.u is not None else thd
        put(resp, f"{seq} {cmd:.6f}")
        if seq % 100 == 0: log(f"takt {seq} t {t:.3f} free {int(free)} cmd {cmd:+.3f}")
