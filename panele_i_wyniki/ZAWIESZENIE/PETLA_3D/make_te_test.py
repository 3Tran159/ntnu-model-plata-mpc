"""Test krawedzi splywu: obciecie przy 97 % (zamiast 98,5 %) + min. rozmiar siatki powierzchni c/1200 (zamiast c/200).
Przypadki: AR4_jeden_TE (plat pojedynczy AR 4) i OPT27_TE (petla jak OPT_27). Startuje po zakonczeniu luk_p3d.py.
Domyslne wartosci (98,5 %, c/200) zostaja bez zmian dla wszystkich innych przypadkow. Agent D, 16.11.2026."""
import json
from pathlib import Path
H = Path(__file__).parent
def patch(p, R):
    t = (H / p).read_text(encoding="utf-8")
    for a, b in R:
        if b in t: continue
        assert t.count(a) >= 1, (p, a); t = t.replace(a, b)
    (H / p).write_text(t, encoding="utf-8")
patch("make_geo3d.py", [("XCUT = 0.985 ", "import os\nXCUT = float(os.environ.get('P3D_XCUT', 0.985)) ")])
patch("BuildPetla3D.java", [("100*C/200/B", '100*C/d("min_div",200)/B')])
patch("run_p3d.py", [('"cells_per_chord": 40,', '"cells_per_chord": 40, "min_div": 1200 if case.endswith("_TE") else 200,')])
t = (H / "opt_p3d.py").read_text(encoding="utf-8")
R = [('import opt_geo', 'import os\nos.environ["P3D_XCUT"] = "0.97"\nimport opt_geo'),
     ('LOG = HERE / "opt_p3d.log"', 'LOG = HERE / "te_p3d.log"'), ('plan_f = HERE / "OPT_PLAN.json"', 'plan_f = HERE / "TE_PLAN.json"'),
     ('while alive("chain_g2.py")', 'while alive("luk_p3d.py")'), ('out = HERE / "OPT_WYNIKI.csv"', 'out = HERE / "TE_WYNIKI.csv"'),
     ('(HERE / "STOP_OPT")', '(HERE / "STOP_TE")')]
for a, b in R:
    assert t.count(a) >= 1, a; t = t.replace(a, b)
(H / "te_p3d.py").write_text(t, encoding="utf-8")
(H / "TE_PLAN.json").write_text(json.dumps([dict(name="AR4_jeden_TE", ar=4, gap=None, stag=0), dict(name="OPT27_TE", ar=4.72, gap=1.07, stag=-0.28)], indent=1))
print("ok")
