# 17.11: makro MPC dla URANS = kopia makro_k0 (sceny, H1) + blok mpc_bridge z OVS_MPC_WZ2; runner = kopia run_k0_ctrl.py wskazujaca to makro.
# Oryginaly na polce nieruszane: piszemy do 30_URANS_STAR\makro_mpcf\ (nowy folder) i 30_URANS_STAR\run_mpcf_ctrl.py (nowy plik).
from pathlib import Path
U = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR")
k0 = (U / "makro_k0" / "GodoOversetRun.java").read_text(encoding="utf-8", errors="replace")
wz = (U / "overset_runs" / "OVS_MPC_WZ2" / "GodoOversetRun.java").read_text(encoding="utf-8", errors="replace").splitlines()
i0 = next(i for i, l in enumerate(wz) if 'if(mode.equals("mpc_bridge"))' in l)
i1 = next(i for i in range(i0, len(wz)) if wz[i].strip() == "}else")
blk = "\n".join(wz[i0:i1 + 1]) + "\n"
anchor = '      if(mode.equals("policy")&&free){'
assert k0.count(anchor) == 1
out = k0.replace(anchor, blk + anchor)
(U / "makro_mpcf").mkdir(exist_ok=True)
(U / "makro_mpcf" / "GodoOversetRun.java").write_text(out, encoding="utf-8")
r = (U / "run_k0_ctrl.py").read_text(encoding="utf-8")
r = r.replace('"""run_k0_ctrl.py - KOPIA', '"""run_mpcf_ctrl.py (17.11: makro_mpcf = makro_k0 + mpc_bridge) - KOPIA')
r = r.replace('if "mode.equals(\\"k0\\")" not in src:', 'if "mode.equals(\\"mpc_bridge\\")" not in src:')
r = r.replace(r'30_URANS_STAR\makro_k0\GodoOversetRun.java"), case / "GodoOversetRun.java")  # KOPIA z trybem k0', r'30_URANS_STAR\makro_mpcf\GodoOversetRun.java"), case / "GodoOversetRun.java")  # KOPIA z trybem mpc_bridge + sceny')
assert "makro_mpcf" in r and 'mpc_bridge\\")" not in src' in r
(U / "run_mpcf_ctrl.py").write_text(r, encoding="utf-8")
print("blok", i1 - i0 + 1, "linii; ok")
