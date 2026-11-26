"""plot_training.py - podglad treningu w modelu wirowym: krzywe uczenia + jeden epizod aktualnej polityki vs PID2.
Wynik: TRAINING_VIEW.png.  Wszystko "w modelu wirowym"."""
import sys, csv, os
from pathlib import Path
import numpy as np
os.environ.setdefault("TORCH_THREADS", "1")
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import torch
torch.set_num_threads(1)
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt
from godo_vortex_env import GodoVortexEnv, pid_policy, rollout, DEPTH, C, TH_MAX_DEG

RUNS = [("TD3_GODO", "td3", "#1f77b4"), ("TD3_C338", "td3", "#9467bd"), ("TD3_R", "td3", "#ff7f0e")]   # 12.11 18:05: aktualne agenty
try:   # panel URANS (Efekty sterowania) - niezaleznie od treningu
    import effects_urans; effects_urans.main()
except Exception as _e:
    print("effects_urans:", _e, flush=True)


def read(p):
    if not p.exists(): return {}
    first = open(p).readline()
    names = None
    if not first.startswith("episode"):     # plik bez naglowka (wznowienie) - nazwy kolumn jak w train_rl.py
        names = (["episode", "step", "R_mean", "n_term", "D_rel_mean", "D_rel_min", "D_rel_max", "z_min", "z_max", "acc_rms"] if "eval" in p.name else
                 ["episode", "step", "ret", "len", "term", "D_rel", "z_min", "z_max", "loss_c", "loss_a", "sigma", "wall_s"])
    rows = list(csv.DictReader(open(p), fieldnames=names))
    return {k: np.array([float(r[k]) if r[k] not in ("", None) else np.nan for r in rows]) for k in rows[0]} if rows else {}


def actor_fn(tag, alg):
    """najlepsza dotad polityka (best_actor.pt = najnizszy opor w ocenie bez upadku), a jesli jej brak - aktualna"""
    best, ck = HERE / "runs" / tag / "best_actor.pt", HERE / "runs" / tag / "ckpt.pt"
    if not best.exists() and not ck.exists(): return None, ""
    sys.argv = ["x", alg, tag]
    import importlib, train_rl; importlib.reload(train_rl)
    ag = train_rl.Agent()
    if best.exists(): ag.actor.load_state_dict(torch.load(best, weights_only=False)); kind = "najlepsza"
    else: ag.actor.load_state_dict(torch.load(ck, weights_only=False)["agent"]["actor"]); kind = "aktualna (jeszcze nie przezyla oceny)"
    return (lambda env, o: ag.act(o, True)), kind


def metrics(rows, term):
    n = len(rows); h = slice(max(0, n - 4 * 194), n); a = lambda k: np.array([x[k] for x in rows])[h]
    if term: return dict(ok=False, upadek_s=round(n * 0.01, 1))
    return dict(ok=True, opor_pct=round(100 * (a("D").mean() / env.D_cw - 1), 1), P_drag_W=round(float(a("P_drag_W").mean()), 1),
                z=[round(float(a("z").min()), 2), round(float(a("z").max()), 2)], zanurzenie_min_c=round(float(a("sub").min()) / C, 2),
                kat=[round(float(a("theta_deg").min()), 1), round(float(a("theta_deg").max()), 1)], predkosc_kata_max=round(float(np.abs(a("rate")).max())),
                acc_rms=round(float(np.sqrt((a("acc") ** 2).mean())), 2))


def smooth(y, n=10):
    if len(y) < n: return y
    return np.convolve(y, np.ones(n) / n, mode="valid")


env = GodoVortexEnv(random_phase=False)
fig = plt.figure(figsize=(13, 10))
gs = fig.add_gridspec(3, 2, height_ratios=[1, 1, 1.3])
axL, axD, axE = fig.add_subplot(gs[0, 0]), fig.add_subplot(gs[0, 1]), fig.add_subplot(gs[1, :])
axP = fig.add_subplot(gs[2, :])
for tag, alg, col in RUNS:
    L = read(HERE / "runs" / tag / "train_log.csv")
    if not L: continue
    st = L["step"] / 1e3
    axL.plot(st, L["len"] / 100, ".", ms=2, color=col, alpha=0.3); axL.plot(st[len(st) - len(smooth(L["len"])):], smooth(L["len"]) / 100, color=col, label=tag)
    ok = L["term"] == 0
    axD.plot(st[ok], 100 * L["D_rel"][ok], ".", ms=3, color=col, label=tag)
    E = read(HERE / "runs" / tag / "eval.csv")
    if E: axE.plot(E["step"] / 1e3, 100 * E["D_rel_mean"], "o-", color=col, label=f"{tag} (ocena, 4 fazy; puste = upadek)", mfc="none")
axL.axhline(15.49, color="k", ls=":", lw=1); axL.set_ylabel("dlugosc epizodu [s]\n(15,5 s = przezyl caly)"); axL.set_xlabel("interakcje [tys.]"); axL.legend(fontsize=8)
axL.set_title("Czy plat utrzymuje sie w zakresie |z| < 0,75 m?")
axD.axhline(0, color="k", lw=0.8); axD.set_ylabel("opor vs woda spokojna [%]"); axD.set_xlabel("interakcje [tys.]")
axD.set_title("Opor w epizodach pelnych (ponizej 0 = mniej niz w wodzie spokojnej)")
act, stt = pid_policy(); Rp, rows_p, _ = rollout(env, act, 0.0, stt)
n = len(rows_p); dp = 100 * (np.mean([x["D"] for x in rows_p[n - 776:]]) / env.D_cw - 1)
axE.axhline(dp, color="k", ls="--", lw=1, label=f"PID2 Godø: {dp:+.0f}%"); axE.axhline(0, color="gray", lw=0.6)
axE.set_ylabel("opor vs woda spokojna [%]"); axE.set_xlabel("interakcje [tys.]"); axE.legend(fontsize=8); axE.set_title("Ocena polityki deterministycznej (ostatnie 4 okresy)")
# epizod fizycznie: powierzchnia wody nad platem i polozenie plata
t = np.arange(n) * 0.01
axP.fill_between(t, [x["eta"] for x in rows_p], -2.0, color="#cfe8ff", step=None)
axP.plot(t, [x["eta"] for x in rows_p], color="#3a7bd5", lw=1, label="powierzchnia wody nad nosem plata")
axP.plot(t, np.array([x["z"] for x in rows_p]) - DEPTH, color="k", lw=1.5, label=f"plat, PID2 (opor {dp:+.0f}%)")
EP = {"PID2": (rows_p, False, "k")}
RES = {"PID2 Godø": metrics(rows_p, False)}
mf = HERE / "MPC_EP_phase0.json"
if mf.exists():
    mj = __import__("json").loads(mf.read_text()); EP["MPC"] = (mj["rows"], mj["term"], "#2ca02c"); RES["MPC (liniowy, 1 okres)"] = metrics(mj["rows"], mj["term"])
    axP.plot(np.arange(len(mj["rows"])) * 0.01, np.array([x["z"] for x in mj["rows"]]) - DEPTH, color="#2ca02c", lw=1.2, label="plat, MPC")
for tag, alg, col in RUNS:
    f, kind = actor_fn(tag, alg)
    if f is None: continue
    R, rows, term = rollout(env, f, 0.0)
    tt = np.arange(len(rows)) * 0.01; nn_ = len(rows)
    lab = f"plat, {tag} {kind}" + (f" - UPADEK po {tt[-1]:.1f} s" if term else f" (opor {100*(np.mean([x['D'] for x in rows[nn_-776:]])/env.D_cw-1):+.0f}%)")
    axP.plot(tt, np.array([x["z"] for x in rows]) - DEPTH, color=col, lw=1.2, label=lab)
    EP[tag] = (rows, term, col); RES[f"{tag} ({kind})"] = metrics(rows, term)
(HERE / "RESULTS_LIVE.tmp.json").write_text(__import__("json").dumps(dict(czas=__import__("time").strftime("%H:%M"), D_cw_N=env.D_cw, wyniki=RES), ensure_ascii=False), encoding="utf-8")
os.replace(HERE / "RESULTS_LIVE.tmp.json", HERE / "RESULTS_LIVE.json")
axP.axhline(-DEPTH - 0.75, color="r", ls=":", lw=1); axP.axhline(-DEPTH + 0.75, color="r", ls=":", lw=1, label="granice |z| = 0,75 m (koniec epizodu)")
axP.set_ylim(-2.0, 0.9); axP.set_xlabel("t [s]"); axP.set_ylabel("wysokosc [m] (0 = srednia woda)")
axP.set_title("Co sie dzieje fizycznie: plat pod fala (faza 0)"); axP.legend(fontsize=8, loc="lower right", ncol=2)
fig.suptitle("Trening w MODELU WIROWYM (nie URANS) - stan " + __import__("time").strftime("%H:%M"), fontsize=13)
fig.tight_layout(); fig.savefig(HERE / "TRAINING_VIEW.tmp.png", dpi=100); os.replace(HERE / "TRAINING_VIEW.tmp.png", HERE / "TRAINING_VIEW.png")
plt.close(fig)

# ---- animacja: plat pod fala w ukladzie zwiazanym z platem (woda plynie w lewo z U), co 0,1 s ----
from matplotlib.animation import FuncAnimation, PillowWriter
from godo_vortex_env import S1
pl = env.plant; k, ome, a = pl.k, pl.ome, pl.a
X = np.linspace(-4, 4, 200)
fig2, axA = plt.subplots(figsize=(9, 4.2))
axA.set_xlim(-4, 4); axA.set_ylim(-2.0, 1.0); axA.set_aspect("equal"); axA.set_xlabel("x [m] (plyw ->, plat nieruchomo, woda 12,3 m/s)"); axA.set_ylabel("y [m]")
water = axA.fill_between(X, -2, 0 * X, color="#cfe8ff")
surf, = axA.plot([], [], color="#3a7bd5", lw=1.5)
two_c, = axA.plot([], [], color="#3a7bd5", lw=0.8, ls="--")
axA.axhline(-DEPTH - 0.75, color="r", ls=":", lw=0.8); axA.axhline(-DEPTH + 0.75, color="r", ls=":", lw=0.8)
lines, texts = {}, {}
for i, (tag, (rows, term, col)) in enumerate(EP.items()):
    lines[tag], = axA.plot([], [], color=col, lw=4 if tag != "PID2" else 2.5, alpha=1.0 if tag != "PID2" else 0.45, solid_capstyle="round", label=tag)
    texts[tag] = axA.text(-3.9, 0.85 - 0.17 * i, "", color=col, fontsize=8, va="top")
tt_ = axA.text(3.9, 0.85, "", ha="right", va="top", fontsize=9)
axA.legend(loc="lower right", fontsize=8)
axA.set_title("W modelu wirowym: aktualne polityki vs PID2 (faza 0); przerywana = 2c pod powierzchnia", fontsize=9)
nfr = max(len(r[0]) for r in EP.values()) // 10
beta = 0.0


def draw(fi):
    j = fi * 10; t = (j + 1) * 0.01 + 1.0
    eta = a * np.cos(k * X - ome * t + beta)
    surf.set_data(X, eta); two_c.set_data(X, eta - S1)
    global water
    water.remove(); water = axA.fill_between(X, -2, eta, color="#cfe8ff", zorder=0)
    for tag, (rows, term, col) in EP.items():
        if j < len(rows):
            r = rows[j]; y0 = r["z"] - DEPTH; th = np.radians(r["theta_deg"])
            xs = np.array([-0.25 * C, 0.75 * C]); ys = y0 + np.array([0.25 * C, -0.75 * C]) * np.sin(th)   # nos w lewo (pod prad), obrot wokol c/4
            lines[tag].set_data(xs * np.cos(th), ys)
            nn_ = max(1, j - 194)
            texts[tag].set_text(f"{tag}: kat {r['theta_deg']:+.1f}°, z {r['z']:+.2f} m, zanurzenie {r['sub']/C:.1f}c, opor {100*(np.mean([q['D'] for q in rows[nn_:j+1]])/env.D_cw-1):+.0f}% (ost. okres)")
        else:
            texts[tag].set_text(f"{tag}: UPADEK po {len(rows)*0.01:.1f} s"); lines[tag].set_data([], [])
    tt_.set_text(f"t = {j*0.01:5.1f} s")
    return []


anim = FuncAnimation(fig2, draw, frames=nfr, blit=False)
anim.save(HERE / "LIVE_EPISODE.tmp.gif", writer=PillowWriter(fps=10), dpi=80)
os.replace(HERE / "LIVE_EPISODE.tmp.gif", HERE / "LIVE_EPISODE.gif")
print("ok")
