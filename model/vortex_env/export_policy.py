"""export_policy.py - krok 9: eksport sieci aktora (TD3 lub SAC, deterministycznie) do JSON i do prostego pliku tekstowego dla makra STAR.
usage: python export_policy.py RUN_TAG [td3|sac] [best|final|ckpt]
Wynik: runs/TAG/policy_TAG.json i policy_TAG.txt
  txt: 'GODO_POLICY v1', 'obs_scale 5 liczb', potem 3 warstwy: 'W rows cols' + wartosci wierszami, 'b n' + wartosci.
  Wyjscie: a = tanh(W3 relu(W2 relu(W1 o + b1) + b2) + b3), theta_cmd = 7,5 deg * a;  o = [z, dz/dt, eta_LE, w_surface, a_prev] / obs_scale, clip +-5.
"""
import sys, json
from pathlib import Path
import numpy as np, torch
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from godo_vortex_env import OBS_SCALE, TH_MAX_DEG

tag = sys.argv[1]; alg = sys.argv[2] if len(sys.argv) > 2 else ("sac" if "SAC" in tag else "td3"); which = sys.argv[3] if len(sys.argv) > 3 else "best"
run = HERE / "runs" / tag
f = {"best": run / "best_actor.pt", "final": run / "final_actor.pt"}.get(which)
sd = torch.load(f, weights_only=False) if f else torch.load(run / "ckpt.pt", weights_only=False)["agent"]["actor"]
if alg == "td3": keys = [("0.weight", "0.bias"), ("2.weight", "2.bias"), ("4.weight", "4.bias")]
else: keys = [("b.0.weight", "b.0.bias"), ("b.2.weight", "b.2.bias"), ("mu.weight", "mu.bias")]
layers = [(sd[w].numpy().astype(float), sd[b].numpy().astype(float)) for w, b in keys]
js = dict(tag=tag, alg=alg, which=which, obs=["z_m", "zdot_m_s", "eta_LE_m", "w_surface_m_s", "a_prev"], obs_scale=OBS_SCALE.tolist(), clip=5.0,
          act="tanh", theta_max_deg=TH_MAX_DEG, layers=[dict(W=W.tolist(), b=b.tolist()) for W, b in layers])
(run / f"policy_{tag}.json").write_text(json.dumps(js))
with open(run / f"policy_{tag}.txt", "w") as fo:
    fo.write("GODO_POLICY v1\n")
    fo.write("obs_scale " + " ".join(f"{x:.9g}" for x in OBS_SCALE) + "\n")
    for W, b in layers:
        fo.write(f"W {W.shape[0]} {W.shape[1]}\n")
        for row in W: fo.write(" ".join(f"{x:.9g}" for x in row) + "\n")
        fo.write(f"b {len(b)}\n" + " ".join(f"{x:.9g}" for x in b) + "\n")
# kontrola: ta sama siec w numpy vs torch na losowych obserwacjach
o = np.random.default_rng(0).normal(size=(20, 5))
def fwd(x):
    h = np.maximum(0, layers[0][0] @ x + layers[0][1]); h = np.maximum(0, layers[1][0] @ h + layers[1][1]); return np.tanh(layers[2][0] @ h + layers[2][1])[0]
sys.argv = ["x", alg, tag]
import train_rl
ag = train_rl.Agent(); ag.actor.load_state_dict(sd)
err = max(abs(fwd(x) - ag.act(x.astype(np.float32), True)[0]) for x in o)
print(f"zapisano {run / f'policy_{tag}.txt'}; max roznica numpy vs torch = {err:.2e}")
