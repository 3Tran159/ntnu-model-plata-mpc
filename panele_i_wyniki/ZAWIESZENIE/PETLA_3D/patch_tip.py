"""Plynne zakonczenie wingletu: na odcinku przedluzenia ext cieciwa maleje eliptycznie c(eta) = c_end*sqrt(1-eta^2) (eta 0..1, min 3 %),
profil skalowany razem z cieciwa (grubosc -> 0), os cwierci cieciwy prosta. tip=1 wlacza, tip=0 = dotychczasowy prosty koniec z plaskim denkiem."""
p = 'opt_geo.py'; t = open(p, encoding='utf-8').read()
R = [
 ('def rings_loop(c, half, gap, stag, kt=1.0, kc=1.0, da=0.0, f_up=1.0, s_end=1.0, ext=0.0):',
  'def rings_loop(c, half, gap, stag, kt=1.0, kc=1.0, da=0.0, f_up=1.0, s_end=1.0, ext=0.0, tip=0):'),
 ('    elif ext > 0:\n        ye, ze, pe = st[-1]; st.append((ye + ext * math.cos(pe), ze + ext * math.sin(pe), pe))\n',
  '    elif ext > 0 and tip:\n'
  '        ye, ze, pe = st[-1]\n'
  '        for eta in np.sin(np.linspace(0, math.pi / 2, 25))[1:]:\n'
  '            st.append((ye + ext * eta * math.cos(pe), ze + ext * eta * math.sin(pe), pe, max(0.03, math.sqrt(max(0.0, 1 - eta ** 2)))))\n'
  '    elif ext > 0:\n        ye, ze, pe = st[-1]; st.append((ye + ext * math.cos(pe), ze + ext * math.sin(pe), pe))\n'),
 ('    for y, z, ph in st:\n        wl = math.sin(ph) ** 2; cl = c * (1 - (1 - kc) * wl);',
  '    for item in st:\n        y, z, ph = item[:3]; sk = item[3] if len(item) > 3 else 1.0\n        wl = math.sin(ph) ** 2; cl = c * (1 - (1 - kc) * wl) * sk;'),
 ('def make_case(name, ar, gap=None, stag=0.0, kt=1.0, kc=1.0, da=0.0, f_up=1.0, s_end=1.0, ext=0.0):',
  'def make_case(name, ar, gap=None, stag=0.0, kt=1.0, kc=1.0, da=0.0, f_up=1.0, s_end=1.0, ext=0.0, tip=0):'),
 ('R, inf = rings_loop(c, half, gap, stag, kt, kc, da, f_up, s_end, ext);', 'R, inf = rings_loop(c, half, gap, stag, kt, kc, da, f_up, s_end, ext, tip);'),
 ('przedluzenie_m=ext,', 'przedluzenie_m=ext, koncowka_eliptyczna=tip,'),
]
for a, b in R:
    if b in t: continue
    assert t.count(a) == 1, a
    t = t.replace(a, b)
open(p, 'w', encoding='utf-8', newline='').write(t)
r = open('otw_p3d.py', encoding='utf-8').read()
R2 = [('LOG = HERE / "otw_p3d.log"', 'LOG = HERE / "tip_p3d.log"'), ('plan_f = HERE / "OTW_PLAN.json"', 'plan_f = HERE / "TIP_PLAN.json"'),
      ('p.get("s_end", 1.0), p.get("ext", 0.0))', 'p.get("s_end", 1.0), p.get("ext", 0.0), p.get("tip", 0))'),
      ('out = HERE / "OTW_WYNIKI.csv"', 'out = HERE / "TIP_WYNIKI.csv"'), ('(HERE / "STOP_OTW")', '(HERE / "STOP_TIP")')]
for a, b in R2:
    assert r.count(a) >= 1, a; r = r.replace(a, b)
open('tip_p3d.py', 'w', encoding='utf-8').write(r)
import json
B = dict(ar=4.72, kt=0.5, kc=0.6, stag=0, s_end=0.5, tip=1)
P = [dict(name="W90_h05_tip", gap=0.6, ext=0.25, **B), dict(name="W90_h07_tip", gap=0.6, ext=0.45, **B), dict(name="W90_h10_tip", gap=1.0, ext=0.6, **B)]
open('TIP_PLAN.json', 'w').write(json.dumps(P, indent=1)); print('ok')
