"""Test kroku 1: FoilStepper (krokowy) == Foil.simulate + Foil.forces na danych OVS_PID_BASE2 (te same wejscia co replay_history)."""
import csv, json, sys, time
from pathlib import Path
import numpy as np
sys.path.insert(0, str(Path(__file__).parent))
from uvm_step import FoilStepper, mean_state, Foil, G

H = Path(r"T:\NTNU_GODO_CONTROL_20261109\70_godo_case\overset_runs\OVS_PID_BASE2\history.csv")
rho, c, U, depth, T, N = 1000.0, 0.312, 12.3466667, 1.09, 5.0, 20
R = {}
for r in csv.DictReader(open(H)):
    R[round(float(r["time_s"]), 6)] = r
t = np.array(sorted(R)); col = lambda k: np.array([float(R[x][k]) for x in t])
nmax = int(sys.argv[1]) if len(sys.argv) > 1 else 3000
t = t[:nmax]
th = np.radians(col("theta_deg"))[:nmax]; thd = np.radians(col("theta_rate_deg_s"))[:nmax]; v = col("v_m_s")[:nmax]; z = col("z_m")[:nmax]
dt = float(np.median(np.diff(t)))
om = 2 * np.pi / T; k = om * om / G; ome = om + k * U; Te = 2 * np.pi / ome
a, beta, A0 = 0.73, 0.3, 0.73 * om          # dowolna fala (test zgodnosci arytmetyki, nie walidacja)
F = Foil(c=c, U=U, N=N, h=depth, dt=dt, wake_len=3 * U * Te, rho=rho)
idx = lambda tt: min(len(t) - 1, max(0, int(round(tt / dt)) - 1))
def gust(x, tt):
    psi = k * x - ome * tt + beta; A = A0 * np.exp(-k * (depth - z[idx(tt)]))
    return A * np.cos(psi), A * np.sin(psi)
thm = th.mean(); th_ref = np.radians(3.0)
mean, g1 = mean_state(F, th_ref)
t0 = time.time()
f = F.simulate(len(t), theta=lambda tt: (th[idx(tt)] - thm, thd[idx(tt)]), heave_rate=lambda tt: -v[idx(tt)], gust=gust)
f["th"] = f["th"]  # zaburzenie
ref = F.forces(f, mean); t_batch = time.time() - t0
S = FoilStepper(F, mean); out = {k_: [] for k_ in ("L", "Fx", "Mp", "CL")}
t0 = time.time()
for n in range(len(t)):
    tt = (n + 1) * F.dt; i = idx(tt)
    ug, wg = gust(F.xv, tt); _, wc = gust(F.xc, tt)
    r = S.step(th[i] - thm, thd[i], -v[i], gust_c=wc, gust_v=(ug, wg))
    for k_ in out: out[k_].append(r[k_])
t_step = time.time() - t0
res = {}
for k_ in out:
    a_ = np.array(out[k_]); b_ = ref[k_]
    res[k_] = dict(max_abs_diff=float(np.abs(a_ - b_).max()), rel_to_std=float(np.abs(a_ - b_).max() / (b_.std() + 1e-30)))
res["steps"] = len(t); res["dt"] = dt; res["s_batch"] = t_batch; res["s_step"] = t_step; res["us_per_step"] = 1e6 * t_step / len(t)
res["PASS"] = all(res[k_]["rel_to_std"] < 1e-9 for k_ in out)
Path(__file__).with_name("TEST_STEP1.json").write_text(json.dumps(res, indent=1)); print(json.dumps(res, indent=1))
