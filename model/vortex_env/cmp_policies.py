"""cmp_policies.py - czy dwa pliki polityki (txt dla makra STAR) daja rozne komendy. 13.11 noc: TD3_C338 i TD3_GODO daly identyczna historie w URANS."""
import sys, numpy as np
from pathlib import Path
R = Path(__file__).parent / "runs"

def load(f):
    t = f.read_text().split(); i = 2; sc = np.array(t[3:8], float); i = 8; L = []
    for _ in range(3):
        assert t[i] == "W"; r, c = int(t[i + 1]), int(t[i + 2]); i += 3; W = np.array(t[i:i + r * c], float).reshape(r, c); i += r * c
        assert t[i] == "b"; n = int(t[i + 1]); i += 2; b = np.array(t[i:i + n], float); i += n; L.append((W, b))
    return sc, L

def act(p, o):
    sc, L = p; x = np.clip(o / sc, -5, 5)
    for k, (W, b) in enumerate(L): x = W @ x + b; x = np.maximum(0, x) if k < 2 else np.tanh(x)
    return 7.5 * x[0]

a = load(R / "TD3_GODO" / "policy_TD3_GODO.txt"); b = load(R / "TD3_C338" / "policy_TD3_C338.txt")
print("max |W1 roznica|", np.abs(a[1][0][0] - b[1][0][0]).max())
rng = np.random.default_rng(0)
for o in [np.array([-0.08, -0.54, -0.38, 0.5, 0.57]), *rng.normal(scale=0.3, size=(4, 5))]:
    print(np.round(o, 3), "GODO", round(act(a, o), 4), "C338", round(act(b, o), 4))
