# Kopia mpc_faltinsen.py z polki (60_PANELE_I_WYNIKI\MPC_WIDMO) z kara za przyspieszenie kadluba W_A * acc^2 -> MPC z komfortem.
import shutil
from pathlib import Path
SRC = Path(r"T:\NTNU_GODO_CONTROL_20261109\60_PANELE_I_WYNIKI\MPC_WIDMO"); DST = Path(__file__).parent
shutil.copy2(SRC / "MPC_FALT_MODEL.pkl", DST / "MPC_FALT_MODEL.pkl")
s = (SRC / "mpc_faltinsen.py").read_text(encoding="utf-8")
rep = [
    ('HERE = Path(__file__).parent; ROOT = HERE.parents[1];', 'HERE = Path(__file__).parent; ROOT = Path(r"T:\\NTNU_GODO_CONTROL_20261109");'),
    ('SEEDS, T_EP, T_SKIP, DT = range(3)', 'SEEDS, T_EP, T_SKIP, DT = range(2)'),
    ('VAR = "act%d" % round(ACT_K)', 'SEAS_RUN = ("S1", "S2", "S3")\nW_A = float(os.environ.get("MPC_W_A", "0"))      # kara za komfort: W_A * acc^2 [N na (m/s2)^2], dodana 17.11\nCORE0 = int(os.environ.get("MPC_CORE0", "6"))\nVAR = "act%d_wa%g" % (round(ACT_K), W_A)'),
    ('M[1, 1] += ACT_K / U', 'M[1, 1] += ACT_K / U; M[5, 5] += W_A / MASS ** 2'),
    ('me.cpu_affinity([18 + k])', 'me.cpu_affinity([CORE0 + k])'),
    ('jobs = [(s, sd) for sd in SEEDS for s in SEAS]', 'jobs = [(s, sd) for sd in SEEDS for s in SEAS_RUN]'),
]
for a, b in rep:
    assert s.count(a) == 1, a
    s = s.replace(a, b)
(DST / "mpc_komfort.py").write_text(s, encoding="utf-8")
print("ok")
