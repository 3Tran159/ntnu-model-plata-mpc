"""SAC baseline (Haarnoja et al. 2018, automatic entropy tuning) on the SAME surrogate env, observations, reward,
actuator limits, evaluation and step budget as train_td3.py. Separates "algorithm" from "model" in TD3 vs MBPO:
TD3 vs SAC = effect of the algorithm; SAC vs MBPO (SAC inside) = effect of the model loop.
usage: python train_sac.py <seed> [total_env_steps=300000] [tag=SAC]
Standard SAC hyper-parameters (lr 3e-4, tau 0.005, batch 256, 2x256 ReLU, UTD 1, 5000 random warm-up steps);
gamma identical to the TD3 run. Logs in the same format (progress.csv, policy_snapshot.json) for the dashboard.
"""
import copy, csv, json, math, os, sys, time
from pathlib import Path
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as F

torch.set_num_threads(int(os.environ.get("RL_THREADS", "1")))
sys.path.insert(0, str(Path(__file__).parent))
from flap_env import FlapEnv, TICKS_PER_PERIOD, EP_TICKS, D_MAX

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 0
TOTAL = int(sys.argv[2]) if len(sys.argv) > 2 else 300_000
TAG = sys.argv[3] if len(sys.argv) > 3 else "SAC"
CFG = dict(algo="SAC (auto-alpha)", seed=SEED, total_env_steps=TOTAL, hidden=256, lr=3e-4, tau=0.005, batch=256,
           gamma=1 - 1 / (2.5 * TICKS_PER_PERIOD), warmup=5000, utd=1)
OUT = Path(__file__).parent / "runs" / ("%s_s%d" % (TAG, SEED)); OUT.mkdir(parents=True, exist_ok=True)
(OUT / "config.json").write_text(json.dumps(CFG, indent=1))
torch.manual_seed(SEED); np.random.seed(SEED); rng = np.random.default_rng(SEED)


def mlp(i, o, h):
    return nn.Sequential(nn.Linear(i, h), nn.ReLU(), nn.Linear(h, h), nn.ReLU(), nn.Linear(h, o))


class Actor(nn.Module):
    def __init__(s, od, ad, h):
        super().__init__(); s.f = mlp(od, 2 * ad, h)

    def forward(s, o, deterministic=False):
        mu, ls = s.f(o).chunk(2, -1); ls = ls.clamp(-20, 2); std = ls.exp()
        u = mu if deterministic else mu + std * torch.randn_like(mu)
        a = torch.tanh(u)
        logp = (-0.5 * ((u - mu) / std) ** 2 - ls - 0.5 * math.log(2 * math.pi)).sum(-1, keepdim=True) \
            - torch.log(1 - a.pow(2) + 1e-6).sum(-1, keepdim=True)
        return a, logp


class Agent:
    def __init__(s, od, ad):
        h = CFG["hidden"]
        s.actor = Actor(od, ad, h); s.q1, s.q2 = mlp(od + ad, 1, h), mlp(od + ad, 1, h)
        s.q1_t, s.q2_t = copy.deepcopy(s.q1), copy.deepcopy(s.q2)
        s.log_alpha = torch.zeros(1, requires_grad=True); s.target_ent = -float(ad)
        s.aopt = torch.optim.Adam(s.actor.parameters(), CFG["lr"])
        s.qopt = torch.optim.Adam(list(s.q1.parameters()) + list(s.q2.parameters()), CFG["lr"])
        s.alopt = torch.optim.Adam([s.log_alpha], CFG["lr"])

    def act(s, o, deterministic=True):
        with torch.no_grad():
            return s.actor(torch.tensor(o)[None], deterministic)[0].numpy()[0]

    def update(s, B):
        o, a, r, o2, d = B; alpha = s.log_alpha.exp().detach()
        with torch.no_grad():
            a2, lp2 = s.actor(o2)
            q_t = torch.min(s.q1_t(torch.cat([o2, a2], 1)), s.q2_t(torch.cat([o2, a2], 1))) - alpha * lp2
            y = r + CFG["gamma"] * (1 - d) * q_t
        oa = torch.cat([o, a], 1)
        ql = F.mse_loss(s.q1(oa), y) + F.mse_loss(s.q2(oa), y)
        s.qopt.zero_grad(); ql.backward(); s.qopt.step()
        an, lp = s.actor(o); qn = torch.min(s.q1(torch.cat([o, an], 1)), s.q2(torch.cat([o, an], 1)))
        al = (alpha * lp - qn).mean(); s.aopt.zero_grad(); al.backward(); s.aopt.step()
        ll = -(s.log_alpha * (lp.detach() + s.target_ent)).mean(); s.alopt.zero_grad(); ll.backward(); s.alopt.step()
        for net, tgt in ((s.q1, s.q1_t), (s.q2, s.q2_t)):
            for p, pt in zip(net.parameters(), tgt.parameters()):
                pt.data.mul_(1 - CFG["tau"]).add_(CFG["tau"] * p.data)


class Buffer:
    def __init__(s, od, ad, n):
        s.o, s.a, s.r, s.o2, s.d = (np.zeros((n, od), np.float32), np.zeros((n, ad), np.float32), np.zeros((n, 1), np.float32),
                                    np.zeros((n, od), np.float32), np.zeros((n, 1), np.float32))
        s.n, s.i, s.full = n, 0, False

    def add(s, o, a, r, o2, d):
        s.o[s.i], s.a[s.i], s.r[s.i], s.o2[s.i], s.d[s.i] = o, a, r, o2, d
        s.i = (s.i + 1) % s.n; s.full = s.full or s.i == 0

    def sample(s, b):
        idx = rng.integers(0, s.n if s.full else s.i, b)
        return tuple(torch.tensor(x[idx]) for x in (s.o, s.a, s.r, s.o2, s.d))


_BASE = {}


def surrogate_fixed_cd():
    if "cd" not in _BASE:
        env = FlapEnv(seed=12345, random_start=False); env.reset()
        for _ in range(EP_TICKS):
            env.step(np.zeros(1))
        _BASE["cd"] = float(np.array(env.log)[-4 * TICKS_PER_PERIOD:, 4].mean())
    return _BASE["cd"]


def evaluate(agent):
    cd0 = surrogate_fixed_cd()
    env = FlapEnv(seed=12345, random_start=False); o = env.reset(); R = 0
    for _ in range(EP_TICKS):
        o, r, d, _ = env.step(agent.act(o)); R += r
    L = np.array(env.log)[-4 * TICKS_PER_PERIOD:]
    ph = (np.degrees(-L[:, 0]) % 360); bins = np.linspace(0, 360, 37); c = 0.5 * (bins[1:] + bins[:-1])
    idx = np.digitize(ph, bins) - 1
    snap = {"phase_deg": c.tolist(),
            "delta_deg": [float(L[idx == i, 2].mean()) if (idx == i).any() else None for i in range(36)],
            "CL": [float(L[idx == i, 3].mean()) if (idx == i).any() else None for i in range(36)],
            "CD": [float(L[idx == i, 4].mean()) if (idx == i).any() else None for i in range(36)],
            "mean_CL": float(L[:, 3].mean()), "mean_CD": float(L[:, 4].mean()),
            "dCD_vs_FIXED_pct": float(100 * (L[:, 4].mean() / cd0 - 1)), "surrogate_fixed_CD": cd0,
            "mean_P_act_W": float(L[:, 6].mean()), "max_ens_spread_CL": float(L[:, 8].max()), "return": R}
    return R, snap


def main():
    env = FlapEnv(seed=SEED); agent = Agent(env.obs_dim, env.act_dim); buf = Buffer(env.obs_dim, env.act_dim, 1_000_000)
    f = open(OUT / "progress.csv", "w", newline=""); w = csv.writer(f)
    w.writerow(["env_steps", "ep_return", "mean_CL", "mean_CD", "cfd_periods", "phase", "train_return", "dCD_pct", "P_act_W", "wall_s"])
    o = env.reset(); ep_r, ep, t0 = 0.0, 0, time.time()
    for k in range(1, TOTAL + 1):
        a = rng.uniform(-1, 1, 1).astype(np.float32) if k <= CFG["warmup"] else agent.act(o, deterministic=False).astype(np.float32)
        o2, r, done, _ = env.step(a); buf.add(o, a, r, o2, float(done)); o = o2; ep_r += r
        if k > CFG["warmup"]:
            for _ in range(CFG["utd"]):
                agent.update(buf.sample(CFG["batch"]))
        if done:
            ep += 1
            if ep % 4 == 0 or k == TOTAL:
                R, snap = evaluate(agent)
                w.writerow([k, R, snap["mean_CL"], snap["mean_CD"], 0, 3, ep_r, snap["dCD_vs_FIXED_pct"], snap["mean_P_act_W"],
                            round(time.time() - t0)]); f.flush()
                snap["env_steps"] = k; (OUT / "policy_snapshot.json").write_text(json.dumps(snap))
                torch.save(agent.actor.state_dict(), OUT / "actor.pt")
            o = env.reset(); ep_r = 0.0
    f.close()


if __name__ == "__main__":
    main()
