"""Tworzy luk_p3d.py z opt_p3d.py: inny plan (LUK_PLAN.json), wyniki LUK_WYNIKI.csv, log luk_p3d.log, parametry luku kt/kc."""
import json
from pathlib import Path
H = Path(__file__).parent
t = (H / "opt_p3d.py").read_text(encoding="utf-8")
R = [('LOG = HERE / "opt_p3d.log"', 'LOG = HERE / "luk_p3d.log"'),
     ('plan_f = HERE / "OPT_PLAN.json"', 'plan_f = HERE / "LUK_PLAN.json"'),
     ('opt_geo.make_case(p["name"], p["ar"], p["gap"], p["stag"])', 'opt_geo.make_case(p["name"], p["ar"], p["gap"], p["stag"], p.get("kt", 1.0), p.get("kc", 1.0))'),
     ('out = HERE / "OPT_WYNIKI.csv"', 'out = HERE / "LUK_WYNIKI.csv"'),
     ('(HERE / "STOP_OPT")', '(HERE / "STOP_LUK")'),
     ('r = dict(name=p["name"], AR=p["ar"],', 'r = dict(name=p["name"], kt=p.get("kt", 1.0), kc=p.get("kc", 1.0), AR=p["ar"],'),
     ('fieldnames=["name", "AR",', 'fieldnames=["name", "kt", "kc", "AR",')]
for a, b in R:
    n = t.count(a); assert n >= 1, a; t = t.replace(a, b)
t = t.replace('"""Optymalizacja petli G2', '"""Luk z innego profilu (kt grubosc, kc cieciwa na srodku luku), na bazie optymalizacji petli G2', 1)
(H / "luk_p3d.py").write_text(t, encoding="utf-8")
P = [dict(name="L27_h060", ar=4.72, gap=0.60, stag=-0.28), dict(name="L27_h080", ar=4.72, gap=0.80, stag=-0.28),
     dict(name="L27_t05", ar=4.72, gap=1.07, stag=-0.28, kt=0.5), dict(name="L27_c06", ar=4.72, gap=1.07, stag=-0.28, kc=0.6),
     dict(name="L27_t05c06", ar=4.72, gap=1.07, stag=-0.28, kt=0.5, kc=0.6), dict(name="L27_h080_t05c06", ar=4.72, gap=0.80, stag=-0.28, kt=0.5, kc=0.6),
     dict(name="L09_t05c06", ar=4.83, gap=0.624, stag=0.338, kt=0.5, kc=0.6)]
(H / "LUK_PLAN.json").write_text(json.dumps(P, indent=1)); print("ok", len(P))
