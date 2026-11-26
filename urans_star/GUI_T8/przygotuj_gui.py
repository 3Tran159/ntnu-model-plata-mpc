"""26.11 (Julek 10:27: "przygotuj w GUI tej symulki na MPC URANS wykresy, sceny, wszystkie bajery pod samodzielne ogladanie").
1) historia OVS_CEL_005g_T8_90 -> HISTORIA_T8_005g.csv (bez duplikatow po wznowieniach, wybrane kolumny, naglowki bez znakow specjalnych)
2) kopia END_t36.0000.sim -> uruchomienie makra PrzygotujGUI.java (sceny, tabela, wykresy XY, PNG) -> OVS_CEL_005g_T8_90_GUI.sim. Rdzenie 18-19, np 1.
Oryginalny przebieg nietkniety."""
import csv, sys, json, shutil
from pathlib import Path
H = Path(__file__).parent; RUN = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs\OVS_CEL_005g_T8_90")
K = [("time_s", "czas_s"), ("z_m", "z_m"), ("v_m_s", "zd_m_s"), ("theta_deg", "kat_deg"), ("theta_cmd_deg", "kat_zadany_deg"), ("P_drag_W", "moc_oporu_W"),
     ("AF_CL", "CL"), ("GODO_lift_over_weight", "sila_nosna_do_ciezaru"), ("GODO_eta_at_LE", "eta_nad_LE_m"), ("GODO_eta_x-3.0", "eta_3m_przed_m"), ("GODO_interfaceCFL", "CFL_powierzchni")]
r = list(csv.reader(open(RUN / "history.csv"))); h = r[0]; idx = [h.index(a) for a, _ in K]
rows = {}
for x in r[1:]:
    if len(x) < len(h): continue
    try: t = float(x[0]); rows[round(t, 6)] = [x[i] for i in idx]
    except ValueError: pass
ts = sorted(rows)
out = [[b for _, b in K] + ["zdd_m_s2"]]
for i, t in enumerate(ts):
    a = 0.0
    if 0 < i < len(ts) - 1: a = (float(rows[ts[i + 1]][2]) - float(rows[ts[i - 1]][2])) / (ts[i + 1] - ts[i - 1])
    out.append(rows[t] + [f"{a:.6g}"])
with open(H / "HISTORIA_T8_005g.csv", "w", newline="") as f: csv.writer(f).writerows(out)
print("wiersze", len(out) - 1, flush=True)
shutil.copy2(RUN / "END_t36.0000.sim", H / "input.sim")
sys.path.insert(0, r"T:\NTNU_GODO_CONTROL_20261109\20_supervisor")
import starrun
res = starrun.launch(H / "input.sim", H / "PrzygotujGUI.java", H, cpus=(18, 19), np_=1, timeout_s=3600)
(H / "launch_result.json").write_text(json.dumps(res, indent=1, default=str))
print("gui sim:", (H / "OVS_CEL_005g_T8_90_GUI.sim").exists(), flush=True)
