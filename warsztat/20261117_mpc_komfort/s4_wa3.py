import os, sys, json, time
os.environ["MPC_W_A"] = "3"
import psutil; psutil.Process().cpu_affinity([20]); psutil.Process().nice(psutil.BELOW_NORMAL_PRIORITY_CLASS)
sys.argv = ["x"]
import mpc_komfort as MK
m = MK.model(MK.plant("S1", 0)[1]); MK.RES.mkdir(exist_ok=True)
t0 = time.time(); r = MK.run("S4", 0, m); (MK.RES / "S4__s0.json").write_text(json.dumps(r), encoding="utf-8")
print("S4 gotowe", round(time.time() - t0), "s", r["P_foil_W"], r["acc_rms"])
