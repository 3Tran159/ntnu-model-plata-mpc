"""TD3 as in Godø et al. (2024): Fujimoto TD3 + 4 inner updates/env step + 3-phase training + O-U exploration noise.

usage: python train_td3.py <seed> [total_env_steps=300000] [tag=TD3]
Logs (read by the live dashboard): 50_learning/runs/<tag>_s<seed>/{progress.csv, policy_snapshot.json, config.json, actor.pt}
Hyper-parameters = Godø App. C, except gamma, which is rescaled so that the discount horizon is the same number of
encounter periods (Godø: gamma 0.999 at 80 Hz, T_e 1.93 s -> horizon ~6.5 periods... here we keep 1/(1-gamma)=2.5 periods
as a conservative, documented choice: gamma = 1 - 1/(2.5*91)).
"""
import copy, csv, json, math, os, sys, time
from pathlib import Path
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as F

torch.set_num_threads(int(os.environ.get("RL_THREADS", "1")))
sys.path.insert(0, str(Path(__file__).parent))
from flap_env import FlapEnv, TICKS_PER_PERIOD, EP_TICKS, D_MAX, CL_TARGET, CD_REF

SEED = int(sys.argv[1]) if len(sys.argv) > 1 else 0
TOTAL = int(sys.argv[2]) if len(sys.argv) > 2 else 300_000
TAG = sys.argv[3] if len(sys.argv) > 3 else "TD3"
CFG = dict(algo="TD3 (Godø-modified)", seed=SEED, total_env_steps=TOTAL, hidden=256, critic_lr=2e-5, actor_lr=2e-6,
           tau=0.005, policy_delay=5, batch=256, gamma=1 - 1 / (2.5 * TICKS_PER_PERIOD), grad_clip=2.0,
           target_noise=0.2, target_noise_clip=0.5, inner_iters=4, phase1=0.10, phase2=0.20,
           ou_theta_mean=0.04, ou_theta_std=0.01, ou_sigma_mean=0.05, ou_sigma_std=0.0125,
           lr_override=os.environ.get("RL_LR_SCALE", "1"))
s = float(CFG["lr_override"]); CFG["critic_lr"] *= s; CFG["actor_lr"] *= s
OUT = Path(__file__).parent / "runs" / ("%s_s%d" % (TAG, SEED)); OUT.mkdir(parents=True, exist_ok=True)
(OUT / "config.json").write_text(json.dumps(CFG, indent=1))
torch.manual_seed(SEED); np.random.seed(SEED); rng = np.random.default_rng(SEED)


def mlp(i, o, h, out_act=None):
    layers = [nn.Linear(i, h), nn.ReLU(), nn.Linear(h, h), nn.ReLU(), nn.Linear(h, o)]
    return nn.Sequential(*(layers + ([out_act] if out_act else [])))


class Agent:
    def __init__(s, od, ad):
        s.actor = mlp(od, ad, CFG["hidden"], nn.Tanh()); s.actor_t = copy.deepcopy(s.actor)
        s.q1, s.q2 = mlp(od + ad, 1, CFG["hidden"]), mlp(od + ad, 1, CFG["hidden"])
        s.q1_t, s.q2_t = copy.deepcopy(s.q1), copy.deepcopy(s.q2)
        s.aopt = torch.optim.Adam(s.actor.parameters(), CFG["actor_lr"])
        s.qopt = torch.optim.Adam(list(s.q1.parameters()) + list(s.q2.parameters()), CFG["critic_lr"])
        s.it = 0

    def act(s, o):
        with torch.no_grad():
            return s.actor(torch.tensor(o)[None]).numpy()[0]

    def update(s, B):
        o, a, r, o2, d = B
        with torch.no_grad():
            n = (torch.randn_like(a) * CFG["target_noise"]).clamp(-CFG["target_noise_clip"], CFG["target_noise_clip"])
            a2 = (s.actor_t(o2) + n).clamp(-1, 1)
            y = r + CFG["gamma"] * (1 - d) * torch.min(s.q1_t(torch.cat([o2, a2], 1)), s.q2_t(torch.cat([o2, a2], 1)))
        oa = torch.cat([o, a], 1)
        ql = F.mse_loss(s.q1(oa), y) + F.mse_loss(s.q2(oa), y)
        s.qopt.zero_grad(); ql.backward()
        nn.utils.clip_grad_norm_(list(s.q1.parameters()) + list(s.q2.parameters()), CFG["grad_clip"]); s.qopt.step()
        s.it += 1
        if s.it % CFG["policy_delay"] == 0:
            al = -s.q1(torch.cat([o, s.actor(o)], 1)).mean()
            s.aopt.zero_grad(); al.backward(); nn.utils.clip_grad_norm_(s.actor.parameters(), CFG["grad_clip"]); s.aopt.step()
            for net, tgt in ((s.actor, s.actor_t), (s.q1, s.q1_t), (s.q2, s.q2_t)):
                for p, pt in zip(net.parameters(), tgt.parameters()):
                    pt.data.mul_(1 - CFG["tau"]).add_(CFG["tau"] * p.data)
        return ql.item()


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


def reference_controller(env, amp, off):
    """Phase-2 helper (Godø used randomly tuned PID): a first-harmonic wave-phase feedforward with random amplitude/phase."""
    return amp * math.cos(env.phi(env.k + 1) + off) / D_MAX


_BASE = {}


def surrogate_fixed_cd():
    """Mean CD of the SAME surrogate with the flap held at 0 (the like-for-like FIXED reference; the surrogate's own
    bias against URANS FIXED is ~1 %, comparable to the effects we look for, so CD_REF must not be used for deltas)."""
    if "cd" not in _BASE:
        env = FlapEnv(seed=12345, random_start=False); env.reset()
        for _ in range(EP_TICKS):
            env.step(np.zeros(1))
        L = np.array(env.log)[-4 * TICKS_PER_PERIOD:]
        _BASE["cd"], _BASE["cl"] = float(L[:, 4].mean()), float(L[:, 3].mean())
    return _BASE["cd"]


def evaluate(agent):
    cd0 = surrogate_fixed_cd()
    env = FlapEnv(seed=12345, random_start=False); o = env.reset(); R = 0
    for _ in range(EP_TICKS):
        o, r, d, _ = env.step(agent.act(o)); R += r
    L = np.array(env.log)[-4 * TICKS_PER_PERIOD:]           # last 4 periods
    ph = (np.degrees(-L[:, 0]) % 360)                       # phase at hinge, 0 = crest over the hinge, increasing in time
    bins = np.linspace(0, 360, 37); c = 0.5 * (bins[1:] + bins[:-1])
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
    n1, n2 = int(CFG["phase1"] * TOTAL), int((CFG["phase1"] + CFG["phase2"]) * TOTAL)
    f = open(OUT / "progress.csv", "w", newline=""); w = csv.writer(f)
    w.writerow(["env_steps", "ep_return", "mean_CL", "mean_CD", "cfd_periods", "phase", "train_return", "dCD_pct", "P_act_W", "wall_s"])
    o = env.reset(); ep_r, x_ou = 0.0, 0.0
    th = max(1e-3, rng.normal(CFG["ou_theta_mean"], CFG["ou_theta_std"])); sg = max(1e-4, rng.normal(CFG["ou_sigma_mean"], CFG["ou_sigma_std"]))
    amp, off = rng.uniform(0, 1.5), rng.uniform(0, 2 * math.pi)
    t0, ep = time.time(), 0
    for k in range(1, TOTAL + 1):
        x_ou += -th * x_ou + sg * rng.normal()
        if k <= n1:
            a = np.array([x_ou])
        elif k <= n2:
            a = np.array([reference_controller(env, amp, off) + x_ou])
        else:
            a = agent.act(o) + x_ou
        a = np.clip(a, -1, 1).astype(np.float32)
        o2, r, done, info = env.step(a)
        buf.add(o, a, r, o2, float(done)); o = o2; ep_r += r
        if k > n1:
            for _ in range(CFG["inner_iters"]):
                agent.update(buf.sample(CFG["batch"]))
        if done:
            ep += 1
            if ep % 4 == 0 or k == TOTAL:
                R, snap = evaluate(agent)
                w.writerow([k, R, snap["mean_CL"], snap["mean_CD"], 0, 1 if k <= n1 else (2 if k <= n2 else 3), ep_r,
                            snap["dCD_vs_FIXED_pct"], snap["mean_P_act_W"], round(time.time() - t0)]); f.flush()
                snap.update({"env_steps": k, "phase": 1 if k <= n1 else (2 if k <= n2 else 3)})
                (OUT / "policy_snapshot.json").write_text(json.dumps(snap))
                torch.save(agent.actor.state_dict(), OUT / "actor.pt")
            o = env.reset(); ep_r, x_ou = 0.0, 0.0
            th = max(1e-3, rng.normal(CFG["ou_theta_mean"], CFG["ou_theta_std"])); sg = max(1e-4, rng.normal(CFG["ou_sigma_mean"], CFG["ou_sigma_std"]))
            amp, off = rng.uniform(0, 1.5), rng.uniform(0, 2 * math.pi)
    f.close()


if __name__ == "__main__":
    main()
