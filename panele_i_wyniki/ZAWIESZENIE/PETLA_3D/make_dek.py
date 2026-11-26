"""1) Dekalaz: gorny plat z innym katem niz dolny (da [deg], + = nos gornego w gore wzgledem dolnego), przejscie po luku (1-cos phi)/2.
2) Runner dek_p3d.py (czeka na te_p3d.py) + DEK_PLAN.json.  3) run_post_pelny.py: komplet scen PostPelny3D dla podanych przypadkow.
da = 0 daje geometrie bez zmian. Agent D, 16.11.2026."""
import json
from pathlib import Path
H = Path(__file__).parent
t = (H / "opt_geo.py").read_text(encoding="utf-8")
R = [('def rings_loop(c, half, gap, stag, kt=1.0, kc=1.0):', 'def rings_loop(c, half, gap, stag, kt=1.0, kc=1.0, da=0.0):'),
     ('        a = ALPHA * math.cos(ph);', '        a = ALPHA * math.cos(ph) - math.radians(da) * (1 - math.cos(ph)) / 2;'),
     ('def make_case(name, ar, gap=None, stag=0.0, kt=1.0, kc=1.0):', 'def make_case(name, ar, gap=None, stag=0.0, kt=1.0, kc=1.0, da=0.0):'),
     ('R, inf = rings_loop(c, half, gap, stag, kt, kc);', 'R, inf = rings_loop(c, half, gap, stag, kt, kc, da);'),
     ('luk_grubosc=kt, luk_cieciwa=kc,', 'luk_grubosc=kt, luk_cieciwa=kc, dekalaz_deg=da,')]
for a, b in R:
    if b in t: continue
    assert t.count(a) == 1, a; t = t.replace(a, b)
(H / "opt_geo.py").write_text(t, encoding="utf-8")
r = (H / "luk_p3d.py").read_text(encoding="utf-8")
R2 = [('LOG = HERE / "luk_p3d.log"', 'LOG = HERE / "dek_p3d.log"'), ('plan_f = HERE / "LUK_PLAN.json"', 'plan_f = HERE / "DEK_PLAN.json"'),
      ('while alive("chain_g2.py")', 'while alive("luk_p3d.py") or alive("te_p3d.py")'),
      ('p.get("kt", 1.0), p.get("kc", 1.0))', 'p.get("kt", 1.0), p.get("kc", 1.0), p.get("da", 0.0))'),
      ('out = HERE / "LUK_WYNIKI.csv"', 'out = HERE / "DEK_WYNIKI.csv"'), ('(HERE / "STOP_LUK")', '(HERE / "STOP_DEK")'),
      ('kc=p.get("kc", 1.0), AR=p["ar"],', 'kc=p.get("kc", 1.0), da=p.get("da", 0.0), AR=p["ar"],'),
      ('fieldnames=["name", "kt", "kc", "AR",', 'fieldnames=["name", "kt", "kc", "da", "AR",')]
for a, b in R2:
    assert r.count(a) >= 1, a; r = r.replace(a, b)
(H / "dek_p3d.py").write_text(r, encoding="utf-8")
P = [dict(name="D27_da+1", ar=4.72, gap=1.07, stag=-0.28, da=1.0), dict(name="D27_da+2", ar=4.72, gap=1.07, stag=-0.28, da=2.0),
     dict(name="D27_da-1", ar=4.72, gap=1.07, stag=-0.28, da=-1.0), dict(name="D27_h080_da+1.5", ar=4.72, gap=0.80, stag=-0.28, da=1.5),
     dict(name="D27_h080_s+0.3_da+1.5", ar=4.72, gap=0.80, stag=+0.30, da=1.5), dict(name="D27_c06_da+1.5", ar=4.72, gap=1.07, stag=-0.28, kc=0.6, da=1.5)]
(H / "DEK_PLAN.json").write_text(json.dumps(P, indent=1))
(H / "run_post_pelny.py").write_text('''"""Komplet scen PostPelny3D.java (natywne, zapisane w PETLA_KONIEC.sim) dla podanych przypadkow. CPU rdzen 22. Zamyka tylko wlasne procesy."""
import sys, json, time
from pathlib import Path
import psutil
sys.path.insert(0, r"T:\\\\NTNU_GODO_CONTROL_20261109\\\\20_supervisor")
import starrun
HERE = Path(__file__).parent; G = json.loads((HERE / "GEOMETRIA_G2.json").read_text())
for case in sys.argv[1].split(","):
    cd = HERE / case; g = G[case]
    (cd / "post.properties").write_text(f"hs={g['pol_rozp_m']}\\ngap={g['odstep_m']}\\nc={g['cieciwa_platu_m']}\\nyluk={g['pol_rozp_m']}\\nU=12.347\\nrho=997.561\\n")
    (cd / "PostPelny3D.java").write_bytes((HERE / "PostPelny3D.java").read_bytes())
    r = starrun.launch(cd / "PETLA_KONIEC.sim", cd / "PostPelny3D.java", cd, cpus=(22,), np_=1, timeout_s=3600, gpu=False)
    time.sleep(5)
    for pid, _n in r.get("bound") or []:
        try: psutil.Process(int(pid)).kill()
        except Exception: pass
    print(case, r.get("returncode"), flush=True)
''', encoding="utf-8")
print("ok")
