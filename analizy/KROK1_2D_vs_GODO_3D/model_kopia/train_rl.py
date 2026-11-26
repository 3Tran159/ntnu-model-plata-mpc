"""train_rl.py - krok 7: TD3 (hiperparametry Godø) i SAC w GodoVortexEnv, z zapisem stanu, wznowieniem i logiem.

Uzycie:  python train_rl.py td3|sac [RUN_TAG] [total_steps]
  katalog runs/TAG/ : ckpt.pt + buffer.npz + meta.json (zapis atomowy co ~5 min, na koncu epizodu),
                        train_log.csv (epizody), eval.csv (co 25 epizodow, 4 fazy fali, deterministycznie),
                        best_actor.pt (najlepsza ocena bez zakonczen), STATUS.json, STOP (plik -> zapis i wyjscie).
Wznowienie: ponowne uruchomienie tej samej komendy (stan i bufor wczytywane automatycznie).

TD3 jak u Godø: aktor/krytyk 2x256 ReLU, Adam lr krytyk 2e-5 / aktor 2e-6, batch 256, gamma 0,999, tau 0,005,
  opoznienie polityki 5, 4 iteracje uczenia na interakcje, przycinanie gradientu 2,0, szum celu 0,2 (clip 0,5) w jednostkach theta_max,
  eksploracja O-U z parametrami losowanymi co epizod; fazy 10/20/70 % (NASZA interpretacja: 10 % sam szum O-U wokol trymu,
  20 % polityka + silny O-U, 70 % polityka + slabnacy O-U).
SAC (nasze ustawienia, nie Godø): 2x256, lr 3e-4, gamma 0,995, tau 0,005, 1 iteracja/interakcje, automatyczna entropia.
"""
import sys, os, json, time, csv
from pathlib import Path
import numpy as np
import torch, torch.nn as nn, torch.nn.functional as Fn

torch.set_num_threads(int(os.environ.get("TORCH_THREADS", "1")))
HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))
from godo_vortex_env import GodoVortexEnv, TH_REF_DEG, TH_MAX_DEG

ALG = sys.argv[1] if len(sys.argv) > 1 else "td3"
TAG = sys.argv[2] if len(sys.argv) > 2 else ALG.upper() + "_A"
RUN = HERE / "runs" / TAG; RUN.mkdir(parents=True, exist_ok=True)
CFG = dict(
    td3=dict(total=1_400_000, lr_c=2e-5, lr_a=2e-6, batch=256, gamma=0.999, tau=0.005, delay=5, iters=4, clip=2.0,
             tnoise=0.2, tclip=0.5, phases=(0.10, 0.20, 0.70), start_learn=5000),
    sac=dict(total=600_000, lr_c=3e-4, lr_a=3e-4, batch=256, gamma=0.995, tau=0.005, iters=1, clip=2.0, start_learn=10000,
             random_steps=10000),
)[ALG]
if len(sys.argv) > 3:
    CFG["total"] = int(float(sys.argv[3]))
if os.environ.get("GODO_TOTAL"):
    CFG["total"] = int(float(os.environ["GODO_TOTAL"]))
BUF = 1_500_000
OD, AD = 5, 1
TRIM = TH_REF_DEG / TH_MAX_DEG


def mlp(i, o, out_act=None):
    L = [nn.Linear(i, 256), nn.ReLU(), nn.Linear(256, 256), nn.ReLU(), nn.Linear(256, o)]
    if out_act: L.append(out_act)
    return nn.Sequential(*L)


class Critic2(nn.Module):
    def __init__(s):
        super().__init__(); s.q1 = mlp(OD + AD, 1); s.q2 = mlp(OD + AD, 1)

    def forward(s, o, a):
        x = torch.cat([o, a], 1); return s.q1(x), s.q2(x)


class SacActor(nn.Module):
    def __init__(s):
        super().__init__(); s.b = nn.Sequential(nn.Linear(OD, 256), nn.ReLU(), nn.Linear(256, 256), nn.ReLU()); s.mu = nn.Linear(256, AD); s.ls = nn.Linear(256, AD)

    def forward(s, o, deterministic=False):
        h = s.b(o); mu = s.mu(h); ls = s.ls(h).clamp(-5, 1); std = ls.exp()
        u = mu if deterministic else mu + std * torch.randn_like(mu)
        a = torch.tanh(u)
        logp = (-0.5 * ((u - mu) / std) ** 2 - ls - 0.5 * np.log(2 * np.pi)).sum(1, keepdim=True) - torch.log(1 - a * a + 1e-6).sum(1, keepdim=True)
        return a, logp


class Agent:
    def __init__(s):
        s.critic = Critic2(); s.critic_t = Critic2(); s.critic_t.load_state_dict(s.critic.state_dict())
        s.oc = torch.optim.Adam(s.critic.parameters(), lr=CFG["lr_c"])
        if ALG == "td3":
            s.actor = mlp(OD, AD, nn.Tanh()); s.actor_t = mlp(OD, AD, nn.Tanh()); s.actor_t.load_state_dict(s.actor.state_dict())
        else:
            s.actor = SacActor(); s.log_alpha = torch.zeros(1, requires_grad=True); s.oalpha = torch.optim.Adam([s.log_alpha], lr=3e-4)
        s.oa = torch.optim.Adam(s.actor.parameters(), lr=CFG["lr_a"])
        s.n_up = 0

    def act(s, o, deterministic=True):
        with torch.no_grad():
            x = torch.as_tensor(o, dtype=torch.float32).unsqueeze(0)
            a = s.actor(x) if ALG == "td3" else s.actor(x, deterministic)[0]
        return a.numpy()[0]

    def soft(s, net, tgt):
        with torch.no_grad():
            for p, pt in zip(net.parameters(), tgt.parameters()):
                pt.mul_(1 - CFG["tau"]).add_(CFG["tau"] * p)

    def update(s, B):
        o, a, r, o2, d = B; g = CFG["gamma"]
        with torch.no_grad():
            if ALG == "td3":
                nz = (torch.randn_like(a) * CFG["tnoise"]).clamp(-CFG["tclip"], CFG["tclip"])
                a2 = (s.actor_t(o2) + nz).clamp(-1, 1)
                q1t, q2t = s.critic_t(o2, a2); y = r + g * (1 - d) * torch.min(q1t, q2t)
            else:
                a2, lp2 = s.actor(o2); q1t, q2t = s.critic_t(o2, a2)
                y = r + g * (1 - d) * (torch.min(q1t, q2t) - s.log_alpha.exp() * lp2)
        q1, q2 = s.critic(o, a); lc = Fn.mse_loss(q1, y) + Fn.mse_loss(q2, y)
        s.oc.zero_grad(); lc.backward(); nn.utils.clip_grad_norm_(s.critic.parameters(), CFG["clip"]); s.oc.step()
        s.n_up += 1; la = None
        if ALG == "td3":
            if s.n_up % CFG["delay"] == 0:
                la = -s.critic.q1(torch.cat([o, s.actor(o)], 1)).mean()
                s.oa.zero_grad(); la.backward(); nn.utils.clip_grad_norm_(s.actor.parameters(), CFG["clip"]); s.oa.step()
                s.soft(s.critic, s.critic_t); s.soft(s.actor, s.actor_t)
        else:
            an, lp = s.actor(o); q1n, q2n = s.critic(o, an)
            la = (s.log_alpha.exp().detach() * lp - torch.min(q1n, q2n)).mean()
            s.oa.zero_grad(); la.backward(); nn.utils.clip_grad_norm_(s.actor.parameters(), CFG["clip"]); s.oa.step()
            lal = -(s.log_alpha * (lp.detach() + (-AD))).mean()   # cel entropii H* = -dim(A)  (poprawione 11.11: wczesniej +dim(A) -> alfa rosla bez konca)
            s.oalpha.zero_grad(); lal.backward(); s.oalpha.step()
            s.soft(s.critic, s.critic_t)
        return float(lc), (float(la) if la is not None else np.nan)

    def state(s):
        d = dict(critic=s.critic.state_dict(), critic_t=s.critic_t.state_dict(), actor=s.actor.state_dict(), oc=s.oc.state_dict(), oa=s.oa.state_dict(), n_up=s.n_up)
        if ALG == "td3": d["actor_t"] = s.actor_t.state_dict()
        else: d["log_alpha"] = s.log_alpha.detach().clone(); d["oalpha"] = s.oalpha.state_dict()
        return d

    def load(s, d):
        s.critic.load_state_dict(d["critic"]); s.critic_t.load_state_dict(d["critic_t"]); s.actor.load_state_dict(d["actor"])
        s.oc.load_state_dict(d["oc"]); s.oa.load_state_dict(d["oa"]); s.n_up = d["n_up"]
        if ALG == "td3": s.actor_t.load_state_dict(d["actor_t"])
        else:
            with torch.no_grad(): s.log_alpha.copy_(d["log_alpha"])
            s.oalpha.load_state_dict(d["oalpha"])


class Buffer:
    def __init__(s):
        s.o = np.zeros((BUF, OD), np.float32); s.a = np.zeros((BUF, AD), np.float32); s.r = np.zeros((BUF, 1), np.float32)
        s.o2 = np.zeros((BUF, OD), np.float32); s.d = np.zeros((BUF, 1), np.float32); s.n = 0; s.i = 0

    def add(s, o, a, r, o2, d):
        s.o[s.i], s.a[s.i], s.r[s.i], s.o2[s.i], s.d[s.i] = o, a, r, o2, d
        s.i = (s.i + 1) % BUF; s.n = min(s.n + 1, BUF)

    def sample(s, rng, k):
        j = rng.integers(0, s.n, k)
        return tuple(torch.as_tensor(x[j]) for x in (s.o, s.a, s.r, s.o2, s.d))

    def save(s, p):
        np.savez(p, o=s.o[:s.n], a=s.a[:s.n], r=s.r[:s.n], o2=s.o2[:s.n], d=s.d[:s.n], i=s.i)

    def load(s, p):
        z = np.load(p); s.n = len(z["r"]); s.i = int(z["i"])
        for k in ("o", "a", "r", "o2", "d"): getattr(s, k)[:s.n] = z[k]


class OU:
    def __init__(s, rng): s.rng = rng; s.x = 0.0; s.theta, s.sigma = 0.15, 0.2

    def reset(s, sig_lo, sig_hi):
        s.x = 0.0; s.theta = s.rng.uniform(0.05, 0.3); s.sigma = s.rng.uniform(sig_lo, sig_hi)

    def __call__(s):
        s.x += s.theta * (0 - s.x) + s.sigma * s.rng.standard_normal(); return s.x


def evaluate(agent, env, phases=(0.0, np.pi / 2, np.pi, 1.5 * np.pi)):
    out = []
    for ph in phases:
        o, _ = env.reset(options={"phase": ph}); done = False; R = 0; D = []; Z = []; A = []; term = False
        while not done:
            o, r, term, trunc, info = env.step(agent.act(o, True)); R += r; done = term or trunc
            D.append(info["D"]); Z.append(info["z"]); A.append(info["acc"])
        n = len(D); h = slice(max(0, n - 4 * 194), n)   # ostatnie ~4 okresy
        out.append(dict(R=R, term=term, n=n, D_rel=float(np.mean(D[h]) / env.D_cw - 1), zmin=float(np.min(Z)), zmax=float(np.max(Z)),
                        acc_rms=float(np.sqrt(np.mean(np.square(A[h]))))))
    return out


def _atomic(path, obj):
    tmp = path.with_suffix(".tmp"); tmp.write_text(json.dumps(obj), encoding="utf-8"); os.replace(tmp, path)


def write_live(agent, env, meta, TR, mode, sigma, R, term, lc, la):
    """biezacy epizod treningowy (z szumem eksploracji) do podgladu na zywo"""
    try:
        alpha = float(agent.log_alpha.exp()) if ALG == "sac" else None
        _atomic(RUN / "live_ep.json", dict(alg=ALG, episode=meta["episode"] + 1, step=meta["step"], mode=mode, sigma=round(float(sigma), 3), R=round(float(R), 1),
                                           done=term is not None, term=bool(term) if term is not None else None, loss_c=None if lc != lc else round(float(lc), 4),
                                           loss_a=None if la != la else round(float(la), 3), alpha=alpha, D_cw=env.D_cw, dt=0.01, **TR, time=time.strftime("%H:%M:%S")))
    except Exception as e:
        print("live:", e, flush=True)


def write_policy_map(agent, env, meta):
    """mapa polityki: komenda kata [deg] i ocena krytyka Q w funkcji fazy fali (eta, w) i wysokosci z (v = 0, poprz. komenda = trym)"""
    try:
        from godo_vortex_env import OBS_SCALE
        p = env.plant; ph = np.linspace(0, 2 * np.pi, 37); zz = np.linspace(-0.75, 0.75, 31)
        P, Zg = np.meshgrid(ph, zz)
        eta = p.a * np.cos(P); w = p.a * 2 * np.pi / 5.0 * np.sin(P)
        O = np.stack([Zg, 0 * Zg, eta, w, 0 * Zg + TRIM], -1).reshape(-1, 5) / OBS_SCALE; O[:, 4] = TRIM
        with torch.no_grad():
            x = torch.as_tensor(O, dtype=torch.float32)
            A = agent.actor(x) if ALG == "td3" else agent.actor(x, True)[0]
            Q = torch.min(*agent.critic(x, A))
        _atomic(RUN / "live_policy.json", dict(episode=meta["episode"], step=meta["step"], phase_deg=np.degrees(ph).round(1).tolist(), z=zz.round(3).tolist(),
                                               theta_deg=(A.numpy().reshape(Zg.shape) * TH_MAX_DEG).round(2).tolist(), Q=Q.numpy().reshape(Zg.shape).round(1).tolist(),
                                               time=time.strftime("%H:%M:%S")))
    except Exception as e:
        print("policy map:", e, flush=True)


def save_ckpt(agent, buf, meta):
    tmp = RUN / "ckpt.tmp.pt"; torch.save(dict(agent=agent.state(), rng=meta.pop("_rng")), tmp); os.replace(tmp, RUN / "ckpt.pt")
    buf.save(RUN / "buffer.tmp.npz"); os.replace(RUN / "buffer.tmp.npz", RUN / "buffer.npz")
    (RUN / "meta.tmp.json").write_text(json.dumps(meta, indent=1)); os.replace(RUN / "meta.tmp.json", RUN / "meta.json")


def main():
    env = GodoVortexEnv(random_phase=True, seed=1); eenv = GodoVortexEnv(random_phase=False)
    agent, buf = Agent(), Buffer()
    rng = np.random.default_rng(12345); torch.manual_seed(0)
    meta = dict(alg=ALG, cfg=CFG, step=0, episode=0, best=None, D_cw=env.D_cw, started=time.strftime("%Y-%m-%d %H:%M:%S"))
    if (RUN / "ckpt.pt").exists() and (RUN / "meta.json").exists():
        d = torch.load(RUN / "ckpt.pt", weights_only=False); agent.load(d["agent"]); rng.bit_generator.state = d["rng"]["np"]
        torch.set_rng_state(d["rng"]["torch"]); (buf.load(RUN / "buffer.npz") if (RUN / "buffer.npz").exists() else print("bez bufora - start z pustym buforem (dostrajanie)", flush=True)); meta = json.loads((RUN / "meta.json").read_text())
        print(f"wznowienie: krok {meta['step']}, epizod {meta['episode']}", flush=True)
        env._rng = np.random.default_rng(1000 + meta["episode"])
    ou = OU(rng); T = CFG["total"]
    newlog = not (RUN / "train_log.csv").exists()
    flog = open(RUN / "train_log.csv", "a", newline=""); wl = csv.writer(flog)
    if newlog: wl.writerow(["episode", "step", "ret", "len", "term", "D_rel", "z_min", "z_max", "loss_c", "loss_a", "sigma", "wall_s"])
    feval = open(RUN / "eval.csv", "a", newline=""); we = csv.writer(feval)
    if newlog: we.writerow(["episode", "step", "R_mean", "n_term", "D_rel_mean", "D_rel_min", "D_rel_max", "z_min", "z_max", "acc_rms"])
    t_ck, t0, step0 = time.time(), time.time(), meta["step"]
    while meta["step"] < T:
        frac = meta["step"] / T
        if ALG == "td3":
            p1, p2, _ = CFG["phases"]
            if frac < p1: mode, sig = "noise", (0.15, 0.45)
            elif frac < p1 + p2: mode, sig = "pol", (0.10, 0.30)
            else:
                s_ = 0.10 * (1 - (frac - p1 - p2) / (1 - p1 - p2)) + 0.02; mode, sig = "pol", (0.5 * s_, s_)
            ou.reset(*sig)
        else:
            mode = "rand" if meta["step"] < CFG["random_steps"] else "pol"; ou.reset(0.15, 0.45)
        o, _ = env.reset(); done = False; R = 0; L = 0; D = []; Z = []; lc = la = np.nan
        TR = dict(z=[], th=[], cmd=[], eta=[], sub=[], D=[], r=[])
        while not done:
            if mode == "noise": a = np.array([np.clip(TRIM + ou(), -1, 1)])
            elif mode == "rand": a = np.array([np.clip(TRIM + ou(), -1, 1)])
            elif ALG == "td3": a = np.clip(agent.act(o) + ou(), -1, 1)
            else: a = agent.act(o, deterministic=False)
            o2, r, term, trunc, info = env.step(a)
            buf.add(o, a, r, o2, float(term)); o = o2; R += r; L += 1; done = term or trunc
            D.append(info["D"]); Z.append(info["z"]); meta["step"] += 1
            for k_, v_ in (("z", info["z"]), ("th", info["theta_deg"]), ("cmd", float(a[0]) * TH_MAX_DEG), ("eta", info["eta"]), ("sub", info["sub"]), ("D", info["D"]), ("r", r)):
                TR[k_].append(round(float(v_), 4))
            if buf.n >= CFG["start_learn"]:
                for _ in range(CFG["iters"]):
                    c_, a_ = agent.update(buf.sample(rng, CFG["batch"])); lc = c_; la = a_ if not np.isnan(a_) else la
            if L % 50 == 0 or done:
                write_live(agent, env, meta, TR, mode, ou.sigma, R, term if done else None, lc, la)
        meta["episode"] += 1
        if meta["episode"] % 5 == 0:
            write_policy_map(agent, env, meta)
        wl.writerow([meta["episode"], meta["step"], round(R, 2), L, int(term), round(float(np.mean(D)) / env.D_cw - 1, 4), round(min(Z), 3), round(max(Z), 3),
                     round(lc, 5) if lc == lc else "", round(la, 4) if la == la else "", round(ou.sigma, 3), round(time.time() - t0)]); flog.flush()
        if meta["episode"] % 25 == 0 and mode != "noise" and mode != "rand":
            ev = evaluate(agent, eenv); Dr = [e["D_rel"] for e in ev]; nt = sum(e["term"] for e in ev)
            we.writerow([meta["episode"], meta["step"], round(np.mean([e["R"] for e in ev]), 1), nt, round(np.mean(Dr), 4), round(min(Dr), 4), round(max(Dr), 4),
                         round(min(e["zmin"] for e in ev), 3), round(max(e["zmax"] for e in ev), 3), round(np.mean([e["acc_rms"] for e in ev]), 3)]); feval.flush()
            if nt == 0 and (meta["best"] is None or np.mean(Dr) < meta["best"]["D_rel_mean"]):
                meta["best"] = dict(episode=meta["episode"], step=meta["step"], D_rel_mean=float(np.mean(Dr)), evals=ev)
                torch.save(agent.actor.state_dict(), RUN / "best_actor.pt")
            # zapas (12.11): najlepsza ocena wg (najmniej upadkow, potem najwyzsza nagroda) - gdy zadna ocena nie jest bez upadkow (SAC_C)
            Rm = float(np.mean([e["R"] for e in ev])); ba = meta.get("best_any")
            if ba is None or (nt, -Rm) < (ba["n_term"], -ba["R_mean"]):
                meta["best_any"] = dict(episode=meta["episode"], step=meta["step"], n_term=int(nt), R_mean=Rm, D_rel_mean=float(np.mean(Dr)))
                torch.save(agent.actor.state_dict(), RUN / "best_any_actor.pt")
        stop = (RUN / "STOP").exists()
        if time.time() - t_ck > 300 or stop or meta["step"] >= T:
            meta["_rng"] = dict(np=rng.bit_generator.state, torch=torch.get_rng_state()); meta["saved"] = time.strftime("%Y-%m-%d %H:%M:%S")
            save_ckpt(agent, buf, meta); t_ck = time.time()
        (RUN / "STATUS.json").write_text(json.dumps(dict(step=meta["step"], total=T, episode=meta["episode"], last_ret=R, best=(meta["best"] or {}).get("D_rel_mean"),
                                                         time=time.strftime("%H:%M:%S"), steps_per_s=round((meta["step"] - step0) / max(1, time.time() - t0), 1))))
        if stop:
            print("STOP", flush=True); break
    torch.save(agent.actor.state_dict(), RUN / "final_actor.pt")
    if meta["step"] >= T:
        (RUN / "DONE").write_text(time.strftime("%Y-%m-%d %H:%M:%S"))
    print("koniec", meta["step"], flush=True)


if __name__ == "__main__":
    main()
