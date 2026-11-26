"""run_validation.py - kolejka walidacji modelu wirowego na przypadku Godo (overset, plat zamocowany w pionie).
usage: python run_validation.py SETUP_SIM cores|gpu [pitch_trim_deg=3.5] [dt_s=1e-3] ...
Kolejnosc: V0 (plat staly) -> dopasowanie fazy fali z history.csv -> V1..V4. Bez nadzoru; kazdy przypadek ma wlasny
restart z punktu kontrolnego (mechanizm run_overset_ctrl). Przerwanie: plik STOP w folderze przypadku.
Wynik: runs/<TAG>/history.csv, potem python analyze_validation.py"""
import json, math, subprocess, sys, time
from pathlib import Path
import numpy as np
VV = Path(__file__).resolve().parent
geo = json.loads((VV.parent / "GEOMETRY_GODO.json").read_text())
TE = geo["encounter_period_s"]; OME = geo["encounter_omega_rad_s"]; AW = geo["inflow_angle_amp_deg"]
setup, where = sys.argv[1], sys.argv[2]
extra = sys.argv[3:]
RELEASE = TE            # rozwoj przeplywu przed ruchem
TICK_S = 10 * 1e-3      # tick_steps * dt (domyslne)
PHI_DEG = 5.3           # optymalne wyprzedzenie z modelu wirowego
CASES = [("V0_fixed", 0.0, None, RELEASE + 4 * TE),
         ("V1_K05_inphase", 0.5 * AW, 0.0, RELEASE + 6 * TE),
         ("V2_K10_inphase", 1.0 * AW, 0.0, RELEASE + 6 * TE),
         ("V3_7p5deg_inphase", 7.5, 0.0, RELEASE + 6 * TE),
         ("V4_K10_antiphase", 1.0 * AW, 180.0, RELEASE + 6 * TE)]

def log(m):
    with open(VV / "validation_queue.log", "a") as f:
        f.write(time.strftime("%Y-%m-%d %H:%M:%S ") + m + "\n")

def wave_phase_beta():
    """eta_LE(t) = a*cos(OME*t - beta): dopasowanie 1. harmonicznej z przypadku V0 po czasie RELEASE."""
    import csv
    t, eta = [], []
    with open(VV / "runs" / "V0_fixed" / "history.csv") as f:
        for row in csv.DictReader(f):
            if float(row["time_s"]) >= RELEASE:
                t.append(float(row["time_s"])); eta.append(float(row["GODO_eta_at_LE"]))
    t, eta = np.array(t), np.array(eta)
    n = int(len(t) // round(TE / (t[1] - t[0]))) * int(round(TE / (t[1] - t[0])))   # pelne okresy
    t, eta = t[-n:], eta[-n:]
    z = 2 * np.mean((eta - eta.mean()) * np.exp(-1j * OME * t))
    return float(-np.angle(z)), float(abs(z))

def run(tag, props):
    cmd = [sys.executable, str(VV / "run_vv_ctrl.py"), tag, setup, where] + ["%s=%s" % kv for kv in props.items()] + extra
    log("start %s %s" % (tag, props)); rc = subprocess.call(cmd); log("koniec %s rc=%s" % (tag, rc))
    rr = VV / "runs" / tag / "RUN_RESULT.json"
    return json.loads(rr.read_text())["result"] if rr.exists() else None

subprocess.check_call([sys.executable, str(VV / "prepare.py")])
beta = None
for tag, amp, dphi, tend in CASES:
    props = {"mode": "hold_sine", "release_s": RELEASE, "t_end_s": tend, "exc_amp_deg": amp, "exc_period_s": TE, "ramp_s": TE}
    if dphi is not None:
        if beta is None:
            beta, a = wave_phase_beta(); log("faza fali: beta=%.2f deg, amplituda eta=%.4f m" % (math.degrees(beta), a))
            (VV / "WAVE_PHASE.json").write_text(json.dumps({"beta_rad": beta, "eta_amp_m": a}))
        # theta' = amp*sin(psi - phi), psi = -(OME*t - beta)  ->  amp*sin(OME*t - beta + phi + pi); tt = t - RELEASE; + kompensacja opoznienia ticku
        ph = OME * RELEASE - beta + math.radians(PHI_DEG + dphi) + math.pi + OME * 0.75 * TICK_S
        props["exc_phase_deg"] = math.degrees(ph) % 360.0
    res = run(tag, props)
    if res != "DONE":
        log("STOP kolejki: %s zakonczony wynikiem %s" % (tag, res)); break
log("kolejka zakonczona")
