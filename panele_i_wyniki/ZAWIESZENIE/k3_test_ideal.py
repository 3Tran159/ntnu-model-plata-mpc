"""k3_test_ideal.py - kontrola: K0P z idealna wiedza (preview='ideal') ma dac to samo co K0_85 koordynatora; 40 s, S1, seed 0 - jak k3_widmo.py test."""
import sys
from pathlib import Path
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
import k3_widmo as KW
KW.W.T_SIM, KW.W.T_SKIP = 40.0, 10.0
KW.CASES["K0P_85_idealny"] = dict(rigid=dict(k_wave=0.85, preview="ideal"))
r = KW.run("K0P_85_idealny", "S1", 0); print("K0P_85_idealny", {k: round(r[k], 3) for k in ("P_W", "acc_rms", "MSI_2h_pct", "rate_rms_deg_s")})
r = KW.W.run("K0_85", "S1", 0); print("K0_85 koordynatora", {k: round(r[k], 3) for k in ("P_W", "acc_rms", "MSI_2h_pct")})
r = KW.W.run("PID1_sztywny", "S1", 0); print("PID1_sztywny", {k: round(r[k], 3) for k in ("P_W", "acc_rms", "MSI_2h_pct")})
