"""Unified URANS trajectory dataset for surrogate / DRL work (Mini-VOF sealed flap, Stokes V, U=18, H=0.1, L=10).

All sources start from the same WAVE/FIXED checkpoint lineage (t0 = 3.923 s, dt = 5e-4 s, 25 617 cells),
so the analytic wave phase at the hinge uses one time base:
    phi_foil(t) = 2*pi*x_h/lambda - 2*pi*t/T_e      (from XFOIL_URANS_CORRECTION.json "phase_at_foil")
Columns of DATASET.csv:
    traj, t, phi, sinphi, cosphi, d_cmd, d_meas, CL, CD, Fx, Mh, pflap
Output: 50_learning/DATASET.csv + DATASET_MANIFEST.json (source, rows, time range, amplitude, role)
Only ACTIVE/FIXED wave cases at U=18 m/s are used; calm-water and U=14 runs are excluded (different condition).
"""
import csv, json, math
from pathlib import Path

OUT = Path(r"T:\NTNU_GODO_CONTROL_20261109\50_learning")
CAL = Path(r"H:\NTNU_RESEARCH_ARCHIVE\Active_Flaps\URANS_XFOIL_CALIBRATION_20261107\runs")
OWN = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_runs")
T_E, LAM, XH = 0.4555125731921526, 10.0, 0.952
DT = 5e-4


def phi(t):
    return 2 * math.pi * XH / LAM - 2 * math.pi * t / T_E


def rows_cal(folder):
    with open(folder / "history.csv", encoding="utf8") as f:
        for r in csv.DictReader(f):
            try:
                yield dict(t=float(r["time_s"]), d_cmd=float(r["delta_command_deg"]), d_meas=float(r["delta_measured_deg"]),
                           CL=float(r["CL"]), CD=float(r["CD"]), Fx=float(r["Fx"]), Mh=float(r["Mh"]), pflap=float(r["pflap"]))
            except (ValueError, KeyError, TypeError):
                return


def rows_own(folder):
    with open(folder / "history.csv", encoding="utf8") as f:
        for r in csv.DictReader(f):
            try:
                yield dict(t=float(r["time_s"]), d_cmd=float(r["cmd_deg"]), d_meas=float(r["meas_deg"]), CL=float(r["CL"]),
                           CD=float(r["CD"]), Fx=float(r["Fx_N"]), Mh=float(r["Mh_Nm"]), pflap=float(r["pFlapAbsMin_Pa"]))
            except (ValueError, KeyError, TypeError):
                return


SOURCES = [  # (traj name, folder, reader, role)
    ("cal_A0p5_ph0", CAL / "XFOIL_CAL_A0p5_PHASE0_20261107_193240", rows_cal, "sine"),
    ("cal_A1_ph90", CAL / "XFOIL_CAL_PHASE90_A1_20261107_095134", rows_cal, "sine"),
    ("cal_A1_ph180", CAL / "XFOIL_CAL_PHASE180_A1_20261107_133449", rows_cal, "sine"),
    ("cal_A1_ph270", CAL / "XFOIL_CAL_PHASE270_A1_20261107_162450", rows_cal, "sine"),
    ("cal_A2_ph0", CAL / "XFOIL_CAL_A2p0_PHASE0_20261107_235230", rows_cal, "sine"),
    ("cal_A2_ph90", CAL / "XFOIL_CAL_A2p0_PHASE90_R1_20261108_195240", rows_cal, "sine"),
]
for prefix, role in (("INT_SCRIPTED", "steps"), ("INT_FIXED", "fixed"), ("FIXED_REF", "fixed"),
                     ("PI_KP08", "pi_chatter"), ("PI_LP_KP05", "pi_lp"), ("FIXED_LONG", "fixed"),
                     ("MAP_FF180", "map"), ("MAP_FF", "map"), ("PRBS1", "broadband"), ("PRBS2", "broadband")):
    for d in sorted(OWN.glob(prefix + "_2*")):
        if (d / "history.csv").exists() and d.name.split("_2026")[0] == prefix:
            SOURCES.append((d.name.split("_2026")[0] + "_" + d.name[-6:], d, rows_own, role))


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    manifest = []
    with open(OUT / "DATASET.csv", "w", newline="", encoding="utf8") as f:
        w = csv.writer(f)
        w.writerow(["traj", "t", "phi", "sinphi", "cosphi", "d_cmd", "d_meas", "CL", "CD", "Fx", "Mh", "pflap"])
        for name, folder, reader, role in SOURCES:
            if not (folder / "history.csv").exists():
                continue
            rs = [r for r in reader(folder) if all(map(math.isfinite, r.values()))]
            keep = [rs[0]] if rs else []
            for r in rs[1:]:
                if abs(r["t"] - keep[-1]["t"] - DT) > 1e-7:
                    break
                keep.append(r)
            if len(keep) < 50:
                continue
            for r in keep:
                p = phi(r["t"])
                w.writerow([name, r["t"], p, math.sin(p), math.cos(p), r["d_cmd"], r["d_meas"], r["CL"], r["CD"],
                            r["Fx"], r["Mh"], r["pflap"]])
            dm = [r["d_meas"] for r in keep]
            manifest.append(dict(traj=name, role=role, source=str(folder), rows=len(keep), t0=keep[0]["t"], t1=keep[-1]["t"],
                                 delta_min=min(dm), delta_max=max(dm),
                                 max_rate_deg_s=max(abs(b - a) / DT for a, b in zip(dm, dm[1:])) if len(dm) > 1 else 0))
    (OUT / "DATASET_MANIFEST.json").write_text(json.dumps(manifest, indent=1))
    for m in manifest:
        print("%-22s %-10s rows=%5d t=[%.4f, %.4f] delta=[%.3f, %.3f] max_rate=%.1f deg/s" % (
            m["traj"], m["role"], m["rows"], m["t0"], m["t1"], m["delta_min"], m["delta_max"], m["max_rate_deg_s"]))


if __name__ == "__main__":
    main()
