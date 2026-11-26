import subprocess, json, sys
for r in ("OVS_PID_BASE2","OVS_PID_PRBS1","OVS_PID_SINE_A2"):
    subprocess.run([sys.executable,"-X","utf8","test_step5.py",r],capture_output=True)
    j=json.load(open(f"TEST_STEP5_{r}.json")); d=j["drag_power_mean_W_strip"]; h=j["heave_h1_amp_m"]
    print(f"{r}: opor URANS {d['URANS']:.1f} model {d['model']:.1f} W ({d['diff_pct']:+.1f}%) | nurzanie {h['URANS']:.3f} vs {h['model']:.3f} m ({h['diff_pct']:+.1f}%) | PASS {j['PASS_15pct']}", flush=True)
from godo_vortex_env import GodoVortexEnv
e=GodoVortexEnv(random_phase=False); print("D_cw model (sam plat) [W]", round(e.D_cw*12.3466667,2), " z wspornikami", round(e.D_cw_tot*12.3466667,2))
