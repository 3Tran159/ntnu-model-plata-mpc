r"""effects_urans.py - panel "Efekty sterowania": wyniki W URANS (STAR-CCM+) obok przewidywan modelu wirowego.
Czyta overset_runs\<tag>\history.csv, RUN_STATE.json, RUN_RESULT.json. Zapisuje URANS_LIVE.json i EFFECTS_URANS.png.
Wolany z plot_training.py co ok. 5 min (live_monitor.ps1). Opor = srednia P_drag z ostatnich 3 okresow spotkania (5,82 s)."""
import json, os, time
from pathlib import Path
import numpy as np
import matplotlib; matplotlib.use("Agg"); import matplotlib.pyplot as plt

HERE = Path(__file__).parent
OV = Path(r"T:\NTNU_GODO_CONTROL_20261109\70_godo_case\overset_runs")
P_CALM = 61.1          # W na pasek 0,02 m, woda spokojna, URANS
T_ENC = 1.94           # okres spotkania [s]
# tag, nazwa, przewidywanie modelu wirowego [W] (bazowy), przewidywanie modelu poprawionego (opis), Godø (zmiana oporu %)
RUNS = [("OVS_PID1_GODO", "PID1 Godø (wolny)", 41.6, "≈ URANS (−0,4 %)", -11.2),
        ("OVS_PID2_GODO", "PID2 Godø", None, "–", -2.45),
        ("OVS_PID_BASE2", "PID Kp 10", 69.0, "≈ URANS (−1,2 %)", None),
        ("OVS_PID3_GODO", "PID3 Godø (szybki)", 96.2, "≈ URANS (−0,5 %)", 18.0),
        ("OVS_PID_SINE_A2", "kąt sinus ±2° (otwarta pętla)", 58.1, "–", None),
        ("OVS_POL_TD3_GODO", "TD3 (nagroda Godø) – polityka", 0.32 * P_CALM, "płat −33 %", -63.9),
        ("OVS_POL_TD3_C338", "TD3_C338 (wspornik, model popr.)", None, "–", None),
        ("OVS_MPC_WZ2", "MPC liniowy (W_Z 2), most do Pythona", 0.315 * P_CALM, "–", None),
        ("OVS_CALM_Z-0.3", "woda spokojna, z = −0,3 m", None, "płasko", None),
        ("OVS_CALM_Z-0.6", "woda spokojna, z = −0,6 m", None, "płasko", None)]


def hist(tag):
    f = OV / tag / "history.csv"
    if not f.exists(): return None
    try:
        a = np.genfromtxt(f, delimiter=",", names=True, usecols=("time_s", "theta_deg", "z_m", "P_drag_W"), invalid_raise=False)
        return a if a.size > 10 else None
    except Exception:
        return None


def jload(p):
    try: return json.loads(p.read_text())
    except Exception: return None


def main():
    out, series = [], {}
    for tag, name, model_W, corr, godo in RUNS:
        d = OV / tag; res = jload(d / "RUN_RESULT.json"); st = jload(d / "RUN_STATE.json"); h = hist(tag)
        row = dict(tag=tag, nazwa=name, model_pct=None if model_W is None else round(100 * (model_W / P_CALM - 1), 1), poprawiony=corr, godo_pct=godo)
        if h is None:
            row.update(stan="w kolejce"); out.append(row); continue
        t = h["time_s"]; t_end = float(st.get("t_end_s", 11.62)) if st else 11.62
        done = bool(res and res.get("result") == "DONE")
        status = "gotowe" if done else (res["result"] if res and res.get("result") not in (None, "HOLD_STOP_FILE") else f"liczy: {t[-1]:.2f} / {t_end:.2f} s")
        if res and res.get("result") == "HOLD_STOP_FILE" and not (OV / tag / "STOP").exists() and st and abs(st.get("time_s", 0) - t[-1]) > 0.05:
            status = f"liczy: {t[-1]:.2f} / {t_end:.2f} s"
        w = t >= t[-1] - 3 * T_ENC
        row.update(stan=status, t=round(float(t[-1]), 2), t_end=round(t_end, 2), okno_s=round(float(t[w][-1] - t[w][0]), 2),
                   P_drag_W=round(float(np.mean(h["P_drag_W"][w])), 1), opor_pct=round(100 * (np.mean(h["P_drag_W"][w]) / P_CALM - 1), 1),
                   z=[round(float(h["z_m"][w].min()), 2), round(float(h["z_m"][w].max()), 2)],
                   kat=[round(float(h["theta_deg"][w].min()), 1), round(float(h["theta_deg"][w].max()), 1)], pelne_okno=bool(done))
        out.append(row)
        w2 = t >= t[-1] - 2 * T_ENC
        series[name] = (t[w2] - t[w2][0], h["z_m"][w2], h["theta_deg"][w2])
    (HERE / "URANS_LIVE.tmp.json").write_text(json.dumps(dict(czas=time.strftime("%H:%M"), P_calm_W=P_CALM, wyniki=out), ensure_ascii=False), encoding="utf-8")
    os.replace(HERE / "URANS_LIVE.tmp.json", HERE / "URANS_LIVE.json")

    # --- wykres: slupki opor (Godø / model / URANS) + przebiegi z i kat w URANS z ostatnich 2 okresow ---
    fig = plt.figure(figsize=(13, 8.5)); gs = fig.add_gridspec(2, 2, height_ratios=[1, 1.1])
    ax = fig.add_subplot(gs[0, :])
    rows = [r for r in out if r["tag"] in ("OVS_PID1_GODO", "OVS_PID2_GODO", "OVS_PID3_GODO", "OVS_POL_TD3_GODO")]
    x = np.arange(len(rows)); wdt = 0.26
    for i, (key, lab, col, al) in enumerate([("godo_pct", "Godø, NDLL 3D", "#bbbbbb", 1), ("model_pct", "mój model wirowy", "#777777", 1), ("opor_pct", "URANS (moje)", "#1f6fd1", 1)]):
        vals = [r.get(key) for r in rows]
        for j, v in enumerate(vals):
            xx = x[j] + (i - 1) * wdt
            if v is None:
                if key == "opor_pct": ax.text(xx, 2, "w kolejce" if rows[j].get("stan") == "w kolejce" else "", ha="center", fontsize=8, rotation=90, va="bottom", color="#1f6fd1")
                continue
            hatch = None if (key != "opor_pct" or rows[j].get("pelne_okno")) else "//"
            ax.bar(xx, v, wdt, color=col, alpha=al, hatch=hatch, edgecolor="white" if hatch is None else "#1f6fd1", label=lab if j == 0 or (lab not in [t.get_label() for t in ax.patches]) else None)
            ax.text(xx, v + (2 if v >= 0 else -2), f"{v:+.0f}", ha="center", va="bottom" if v >= 0 else "top", fontsize=9, fontweight="bold" if key == "opor_pct" else "normal")
    h_, l_ = ax.get_legend_handles_labels(); uniq = dict(zip(l_, h_)); ax.legend(uniq.values(), uniq.keys(), fontsize=9, loc="upper left")
    ax.axhline(0, color="k", lw=0.8); ax.set_xticks(x); ax.set_xticklabels([r["nazwa"] for r in rows], fontsize=10)
    ax.set_ylabel("zmiana oporu płata vs woda spokojna [%]")
    ax.set_title("Opór płata w fali: Godø vs mój model wirowy vs URANS (kreskowane = przebieg jeszcze trwa, średnia z tego, co jest)", fontsize=10)
    for k, (nm, idx) in enumerate([("wysokość z [m]", 1), ("kąt płata [°]", 2)]):
        a2 = fig.add_subplot(gs[1, k])
        for name, s in series.items():
            if not any(q in name for q in ("PID1", "PID3", "TD3", "PID2")): continue
            col = "#1f6fd1" if "TD3" in name else ("#999999" if "PID3" in name else ("#333333" if "PID1" in name else "#d08a00"))
            a2.plot(s[0], s[idx], color=col, lw=1.6, label=name)
        if idx == 1: a2.axhline(-0.75, color="r", ls=":", lw=1, label="granica −0,75 m")
        if idx == 2: a2.axhline(7.5, color="r", ls=":", lw=1, label="granica 7,5°")
        a2.set_xlabel("t [s] (ostatnie 2 okresy spotkania)"); a2.set_ylabel(nm); a2.grid(alpha=0.3); a2.legend(fontsize=8)
        a2.set_title(("Jak płat się porusza" if idx == 1 else "Co robi sterownik") + " – W URANS", fontsize=10)
    fig.suptitle("Efekty sterowania W URANS (STAR-CCM+) – stan " + time.strftime("%H:%M"), fontsize=13)
    fig.tight_layout(); fig.savefig(HERE / "EFFECTS_URANS.tmp.png", dpi=100); os.replace(HERE / "EFFECTS_URANS.tmp.png", HERE / "EFFECTS_URANS.png"); plt.close(fig)


if __name__ == "__main__":
    main(); print("ok")
