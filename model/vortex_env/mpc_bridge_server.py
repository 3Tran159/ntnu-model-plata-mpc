"""mpc_bridge_server.py - MPC liniowy (mpc_linear.LinMPC, model zidentyfikowany na modelu wirowym) jako serwer dla makra STAR.
12.11.2026 22:15, decyzja Julka: "MPC na CFD" - wersja 1 (model z modelu wirowego, jak w tabeli: -69 % w modelu wirowym).

Protokol (pliki w katalogu przebiegu, zapis atomowy przez .tmp + move):
  makro -> MPC_REQ.txt : "seq t z v th_deg rate_deg_s eta_LE free"   (co takt sterowania 10 ms)
  serwer -> MPC_RESP.txt: "seq cmd_deg"
Odtwarza dokladnie mpc_linear.mpc_episode: rozwiazanie co BLK = 5 taktow (50 ms), historia th/v z poprzednich taktow,
faza fali beta dopasowana na biezaco do zmierzonego eta przy LE (eta = A cos(-ome t + beta), konwencja vortex_plant).
Uzycie: python mpc_bridge_server.py CASE_DIR [W_Z=2] [W_DU=2000] [test]   (test = harness z modelem wirowym w tym samym procesie)
Log: CASE_DIR/mpc_bridge.log.  Konczy sie, gdy w CASE_DIR pojawi sie RUN_RESULT.json z wynikiem koncowym albo MPC_STOP."""
import sys, time, os, json, pickle, math
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import mpc_linear as ML

CASE = Path(sys.argv[1]); ML.W_Z = float(sys.argv[2]) if len(sys.argv) > 2 else 2.0; ML.W_DU = float(sys.argv[3]) if len(sys.argv) > 3 else 2000.0
OME = 2 * np.pi / 5.0 + (2 * np.pi / 5.0) ** 2 / 9.81 * 12.3467      # jak vortex_plant (T 5 s, U)
AMP = 0.73


def log(m):
    with open(CASE / "mpc_bridge.log", "a") as f: f.write(time.strftime("%H:%M:%S ") + m + "\n")


class Bridge:
    def __init__(s):
        mdl = pickle.loads((HERE / "MPC_ID_MODEL.pkl").read_bytes())
        s.mpc = ML.LinMPC(mdl, ome=OME, amp=AMP); s.reset()

    def reset(s):
        s.th_h = None; s.v_h = None; s.u = None; s.k_free = 0; s.last_seq = None; s.mpc.Uprev = None; s.T, s.E = [], []

    def beta(s):
        t = np.array(s.T[-200:]); e = np.array(s.E[-200:])          # ostatnie ~2 s (takty co 10 ms)
        if len(t) < 30: return 0.0, 0.0
        X = np.c_[np.cos(-OME * t), np.sin(-OME * t)]; c1, c2 = np.linalg.lstsq(X, e, rcond=None)[0]
        return math.atan2(-c2, c1), math.hypot(c1, c2)

    def step(s, seq, t, z, v, th_deg, rate_deg_s, eta, free):
        th, w = math.radians(th_deg), math.radians(rate_deg_s)
        if s.last_seq is not None and seq <= s.last_seq - 1:
            log(f"seq {seq} <= poprzedni {s.last_seq}: restart makra z checkpointu - zeruje historie MPC"); s.reset()
        s.last_seq = seq
        if s.th_h is None: s.th_h, s.v_h = np.full(ML.NL, th), np.zeros(ML.NL); s.u = th
        s.T.append(t); s.E.append(eta)
        if free:
            if s.k_free % ML.BLK == 0:
                b, A = s.beta(); t0 = time.time()
                s.u = s.mpc.solve(np.array([th, w]), s.th_h, s.v_h, z, v, t, b, s.u)
                if s.k_free % (ML.BLK * 20) == 0:
                    log(f"t {t:.3f} z {z:+.3f} v {v:+.3f} th {th_deg:+.2f} eta {eta:+.3f} | fala A {A:.3f} beta {math.degrees(b):+.1f} deg | cmd {math.degrees(s.u):+.2f} deg | {time.time()-t0:.2f} s")
            s.k_free += 1
        else:
            s.u = th
        s.th_h = np.r_[th, s.th_h[:-1]]; s.v_h = np.r_[v, s.v_h[:-1]]
        return math.degrees(s.u)


def put(p, txt):
    # 13.11 05:45: os.replace na Windows rzuca PermissionError, gdy makro STAR akurat czyta plik -> serwer padal (HOLD_MPC). Ponawiaj.
    t = p.with_suffix(".tmp")
    for _ in range(2000):
        try:
            t.write_text(txt); os.replace(t, p); return
        except OSError:
            time.sleep(0.002)
    log("put: nie udalo sie zapisac odpowiedzi po 2000 probach")


if __name__ == "__main__":
    br = Bridge()
    if "test" in sys.argv:   # harness: model wirowy zamiast STAR, ten sam protokol w pamieci -> czy daje to samo co mpc_episode (-69 %)
        from godo_vortex_env import GodoVortexEnv
        env = GodoVortexEnv(random_phase=False); o, _ = env.reset(options={"phase": 0.0}); p = env.plant; rows = []; done = False; seq = 0
        t_rel = 0.0
        while not done:
            cmd = br.step(seq, p.t, p.z, p.v, math.degrees(p.th), math.degrees(p.w_servo), p.eta_LE(), True); seq += 1
            o, r, term, trunc, info = env.step(np.array([math.radians(cmd) / ML.THM])); rows.append(info); done = term or trunc
        n = len(rows); h = slice(n - 4 * 194, n); a = lambda k: np.array([x[k] for x in rows])[h]
        print("TEST harness: term", term, "plat %", round(100 * (a("D").mean() / env.D_cw - 1), 1), "z", round(a("z").min(), 2), round(a("z").max(), 2), flush=True)
        sys.exit()
    log(f"start: W_Z {ML.W_Z}, W_DU {ML.W_DU}, ome {OME:.4f}, amp {AMP}")
    req, resp = CASE / "MPC_REQ.txt", CASE / "MPC_RESP.txt"
    seen = None
    while True:
        if (CASE / "MPC_STOP").exists(): log("MPC_STOP - koniec"); break
        rr = CASE / "RUN_RESULT.json"
        if rr.exists() and time.time() - rr.stat().st_mtime < 3600 and req.exists() and rr.stat().st_mtime > req.stat().st_mtime + 5:
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
            log(f"BLAD {e!r} - odsylam poprzednia komende"); cmd = math.degrees(br.u) if br.u is not None else thd
        try:
            put(resp, f"{seq} {cmd:.6f}")
        except Exception as e:
            log(f"BLAD zapisu odpowiedzi {e!r}")
        if seq % 50 == 0: log(f"takt {seq} t {t:.3f} free {int(free)} cmd {cmd:+.3f}")
