# 23.11: czy nadwyzka H 2 m to ciag z machania plata (praca serwa)? Kolumny npy: t, P_drag, z'', z, w, z', u, theta[deg], Fx_pot[N/m]
import json, os, numpy as np
D = os.path.dirname(os.path.abspath(__file__)); U, SPAN, M, G = 12.35, 0.02, 28.17007, 9.81
f = np.load(os.path.join(D, "seria_zapis", "T5.0014_cel0.4905.npy")); c = np.load(os.path.join(D, "seria_zapis", "T5.0015_cel0.4905.npy"))
o = json.load(open(os.path.join(D, "cel_reg_zapis", "T5.0014_cel0.4905.json")))
t = f[:, 0]; dt = t[1] - t[0]; th = np.radians(f[:, 7]); thd = np.gradient(th, dt)
zysk = float(c[:, 1].mean() - f[:, 1].mean())
dPot = float(U * SPAN * (c[:, 8].mean() - f[:, 8].mean()))          # zysk w samym czlonie potencjalnym (ciag z sily nosnej + ssanie)
dVisc = zysk - dPot                                                   # reszta: opor lepki/polara/falowy
spec = np.abs(np.fft.rfft(f[:, 7] - f[:, 7].mean())) ** 2; fr = np.fft.rfftfreq(len(f), dt)
fpk = float(fr[np.argmax(spec[1:]) + 1]); hf = float(spec[fr > 1.5].sum() / spec[1:].sum())
ome_e = 3.243; k_red_pk = 2 * np.pi * fpk * 0.312 / (2 * U)
r = dict(zysk=zysk, zysk_potencjalny=dPot, zysk_reszta=dVisc, ciag_wzor=o["ciag_W"], czlon2=o["czlon2_dokl_W"], sufit=o["sufit_W"],
         nadwyzka_potencjalna=dPot - o["ciag_W"] - o["czlon2_dokl_W"], theta_rms_deg=float(np.degrees(th.std())), thetad_rms_deg_s=float(np.degrees(thd.std())),
         f_szczyt_kata_Hz=fpk, f_spotkania_Hz=ome_e / 2 / np.pi, udzial_kata_powyzej_1_5Hz=hf, k_zred_szczytu=k_red_pk, z_fala=float(f[:, 3].mean()), z_spokojna=float(c[:, 3].mean()))
for k, v in r.items(): print(f"{k:28s} {v:9.3f}")
json.dump(r, open(os.path.join(D, "DIAG_H2M2.json"), "w"), indent=1)
