"""Runner otw_p3d.py (uklady otwarte: C-wing, hak, winglet pionowy + plat pojedynczy AR 4,72 jako odniesienie CFD). Czeka na dek_p3d.py."""
import json
from pathlib import Path
H = Path(__file__).parent
r = (H / "luk_p3d.py").read_text(encoding="utf-8")
R = [('LOG = HERE / "luk_p3d.log"', 'LOG = HERE / "otw_p3d.log"'), ('plan_f = HERE / "LUK_PLAN.json"', 'plan_f = HERE / "OTW_PLAN.json"'),
     ('while alive("chain_g2.py")', 'while alive("dek_p3d.py") or alive("luk_p3d.py") or alive("te_p3d.py")'),
     ('p.get("kt", 1.0), p.get("kc", 1.0))', 'p.get("kt", 1.0), p.get("kc", 1.0), p.get("da", 0.0), p.get("f_up", 1.0), p.get("s_end", 1.0), p.get("ext", 0.0))'),
     ('out = HERE / "LUK_WYNIKI.csv"', 'out = HERE / "OTW_WYNIKI.csv"'), ('(HERE / "STOP_LUK")', '(HERE / "STOP_OTW")'),
     ('kc=p.get("kc", 1.0), AR=p["ar"],', 'kc=p.get("kc", 1.0), f_up=p.get("f_up", 1.0), s_end=p.get("s_end", 1.0), ext=p.get("ext", 0.0), AR=p["ar"],'),
     ('fieldnames=["name", "kt", "kc", "AR",', 'fieldnames=["name", "kt", "kc", "f_up", "s_end", "ext", "AR",')]
for a, b in R:
    assert r.count(a) >= 1, a; r = r.replace(a, b)
(H / "otw_p3d.py").write_text(r, encoding="utf-8")
B = dict(ar=4.72, kt=0.5, kc=0.6)
P = [dict(name="M472", ar=4.72, gap=None, stag=0),
     dict(name="O_f075", gap=1.07, stag=-0.28, f_up=0.75, **B), dict(name="O_f05", gap=1.07, stag=-0.28, f_up=0.5, **B),
     dict(name="O_f025", gap=1.07, stag=-0.28, f_up=0.25, **B), dict(name="O_hak", gap=0.8, stag=0, f_up=0.0, **B),
     dict(name="W90_h05", gap=0.6, stag=0, s_end=0.5, ext=0.2, **B), dict(name="W90_h10", gap=1.0, stag=0, s_end=0.5, ext=0.5, **B)]
(H / "OTW_PLAN.json").write_text(json.dumps(P, indent=1)); print("ok")
