# 22.11 17:30 (Julek 17:15: "to licz i archiwizuj dane"): kopia mpc_cel_bridge.py -> mpc_cel_bridge_zapis.py.
# MPC BEZ ZMIAN. Dodane tylko: zapis serii czasowych (z'', z', w, u) i czlon od poziomej predkosci fali (Lean: sufit_z_pozioma).
from pathlib import Path
d = Path(__file__).parent
s = (d / "mpc_cel_bridge.py").read_text(encoding="utf-8")
a1 = 'rows.append((p.t, Pd / p.tick, (Ls / p.tick + MK.BUOY) / FP.MASS - MK.G, p.z, float(np.mean(g[1]))))'
assert s.count(a1) == 1
s = s.replace(a1, 'rows.append((p.t, Pd / p.tick, (Ls / p.tick + MK.BUOY) / FP.MASS - MK.G, p.z, float(np.mean(g[1])), p.v, float(np.mean(g[0]))))')
a2 = '        if SEA:\n            PC = 57.056'
assert s.count(a2) == 1
ins = '''        Mk = FP.MASS * 0.02; uu = b[:, 6]; vv = b[:, 5]; zdd = b[:, 2]; ww = b[:, 4]
        out.update(czlon2_dokl_W=float(Mk * np.mean(uu / (MK.U + uu) * (MK.G + zdd) * (vv - ww))),
                   czlon2_przybl_W=float(Mk * MK.G / MK.U * np.mean((uu - uu.mean()) * (vv - vv.mean()))),
                   u_rms=float(uu.std()), zd_rms=float(vv.std()), kor_u_zd=float(np.corrcoef(uu, vv)[0, 1]) if vv.std() > 0 else None,
                   kor_u_w=float(np.corrcoef(uu, ww)[0, 1]) if ww.std() > 0 else None)
        (d0 := Path(__file__).parent / "seria_zapis").mkdir(exist_ok=True)
        np.save(d0 / ((f"{SEA}_s{SEED}" if SEA else f"T{Tw:g}") + f"_cel{CEL:g}.npy"), b.astype(np.float32))   # kolumny: t, P_drag, z'', z, w, z', u
'''
s = s.replace(a2, ins + a2)
for x in ('"cel_widmo"', '"cel_reg"'):
    assert s.count(x) == 1
s = s.replace('"cel_widmo"', '"cel_widmo_zapis"').replace('"cel_reg"', '"cel_reg_zapis"')
s = "# KOPIA mpc_cel_bridge.py z 22.11 (zrob_kopie_zapis.py): MPC bez zmian, dodany zapis serii i czlon poziomy.\n" + s
(d / "mpc_cel_bridge_zapis.py").write_text(s, encoding="utf-8")
print("OK")
