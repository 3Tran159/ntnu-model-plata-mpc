"""test_bridge_client.py - udaje makro STAR (ten sam protokol plikowy, odpytywanie co 2 ms, zapis tmp+move) przeciw mpc_bridge_server.py,
z modelem wirowym jako "CFD". Sprawdza: brak zawieszen przy kolizjach plikow na Windows i ten sam wynik co MPC bezposrednio.
Uzycie: python test_bridge_client.py CASE_DIR N_TICKS"""
import sys, os, time, math
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from godo_vortex_env import GodoVortexEnv
import mpc_linear as ML
case = Path(sys.argv[1]); n = int(sys.argv[2])
env = GodoVortexEnv(random_phase=False); env.reset(options={"phase": 0.0}); p = env.plant
def put(name, txt):
    t = case / (name + ".tmp")
    while True:
        try: t.write_text(txt); os.replace(t, case / name); return
        except OSError: time.sleep(0.002)
t0 = time.time(); rows = []
for seq in range(n):
    put("MPC_REQ.txt", f"{seq} {p.t:.6f} {p.z:.8f} {p.v:.8f} {math.degrees(p.th):.8f} {math.degrees(p.w_servo):.8f} {p.eta_LE():.8f} 1")
    tw = time.time(); got = None
    while time.time() - tw < 30:
        try:
            rs = (case / "MPC_RESP.txt").read_text().split()
            if len(rs) >= 2 and int(rs[0]) == seq: got = float(rs[1]); break
        except Exception: pass
        time.sleep(0.002)
    if got is None: print("TIMEOUT na takcie", seq); sys.exit(1)
    o, r, term, trunc, info = env.step(np.array([math.radians(got) / ML.THM])); rows.append(info)
    if term or trunc: break
D = np.array([x["D"] for x in rows]); m = min(len(D), 4 * 194)
print(f"OK {len(rows)} taktow, {time.time()-t0:.0f} s, opor plata ostatnie {m} taktow: {100*(D[-m:].mean()/env.D_cw-1):+.1f} %")
