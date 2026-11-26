# 23.11: rozbior przekroczenia H 2 m. Zysk liczony wzgledem wody spokojnej W TYM SAMYM wariancie modelu (nie 57,03 W).
import json, os, numpy as np
D = os.path.dirname(os.path.abspath(__file__)); M = 28.17007
par = [("bazowy", "5.0006", "5.0007"), ("bez fs_lift", "5.0008", "5.0009"), ("bez fs_wave", "5.0010", "5.0011"), ("bez obu", "5.0012", "5.0013")]
out = {}
print(f"{'wariant':12s} {'P_spok':>7s} {'z_spok':>7s} {'P_fala':>7s} {'z_fala':>7s} {'zysk':>6s} {'ciag':>6s} {'czl2':>6s} {'sufit':>6s} {'nadwyzka':>9s}")
for nm, tf, tc in par:
    try:
        o = json.load(open(os.path.join(D, "cel_reg_zapis", f"T{float(tf):g}_cel0.4905.json"))); bc = np.load(os.path.join(D, "seria_zapis", f"T{float(tc):g}_cel0.4905.npy"))
        bf = np.load(os.path.join(D, "seria_zapis", f"T{float(tf):g}_cel0.4905.npy"))
    except Exception as e: print(nm, "brak", e); continue
    Pc, Pf = float(bc[:, 1].mean()), float(bf[:, 1].mean()); zysk = Pc - Pf
    r = dict(P_spokojna=Pc, z_spokojna=float(bc[:, 3].mean()), P_fala=Pf, z_fala=float(bf[:, 3].mean()), zysk=zysk, ciag=o["ciag_W"], czlon2=o["czlon2_dokl_W"],
             sufit=o["sufit_W"], nadwyzka=zysk - o["ciag_W"] - o["czlon2_dokl_W"], acc=o["acc_rms"], W_A=o["W_A_koniec"])
    out[nm] = r
    print(f"{nm:12s} {Pc:7.2f} {r['z_spokojna']:7.3f} {Pf:7.2f} {r['z_fala']:7.3f} {zysk:6.2f} {r['ciag']:6.2f} {r['czlon2']:6.2f} {r['sufit']:6.2f} {r['nadwyzka']:9.2f}")
json.dump(out, open(os.path.join(D, "DIAG_H2M.json"), "w"), indent=1)

