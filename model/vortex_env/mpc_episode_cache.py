"""Zapisuje przebieg MPC (W_Z = 2, faza 0) do MPC_EP_phase0.json - do podgladu efektow (bez ponownego liczenia co 5 min)."""
import sys, json
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import pickle, mpc_linear as M
M.W_Z = 2.0
mdl = pickle.loads((HERE / "MPC_ID_MODEL.pkl").read_bytes())
env = M.GodoVortexEnv(random_phase=False)
mpc = M.LinMPC(mdl, ome=env.plant.ome)
R, rows, term = M.mpc_episode(env, mpc, 0.0)
(HERE / "MPC_EP_phase0.json").write_text(json.dumps(dict(term=bool(term), rows=[{k: float(v) for k, v in r.items()} for r in rows])))
print("ok", term, len(rows))
