"""Uklady otwarte z tej samej rodziny G2: f_up = czesc rozpietosci gornego platu liczona od konca (1 = pelna petla, 0 = hak 180 st.),
s_end = koniec luku (1 = 180 st., 0.5 = 90 st. -> winglet pionowy), ext = przedluzenie prostego konca [m] w kierunku stycznej.
Powierzchnia rzutu stala S = 2,496 m2: cieciwa c = S/(b (1+f_up)) dla luku 180 st., c = S/b dla wingletu. Domyslne = petla bez zmian."""
p = 'opt_geo.py'; t = open(p, encoding='utf-8').read()
R = [
 ('def rings_loop(c, half, gap, stag, kt=1.0, kc=1.0, da=0.0):', 'def rings_loop(c, half, gap, stag, kt=1.0, kc=1.0, da=0.0, f_up=1.0, s_end=1.0, ext=0.0):'),
 ('    idx = np.linspace(0, len(s) - 1, NB + 1).round().astype(int)\n    st = [(-0.05, 0.0, 0.0)] + [(y0 + L * yb[i], L * zb[i], phi[i]) for i in idx] + [(-0.05, gap, math.pi)]\n',
  '    idx = np.linspace(0, (len(s) - 1) * s_end, NB + 1).round().astype(int)\n'
  '    st = [(-0.05, 0.0, 0.0)] + [(y0 + L * yb[i], L * zb[i], phi[i]) for i in idx]\n'
  '    if s_end >= 0.999:\n'
  '        if f_up > 0.02: st.append((y0 - f_up * (y0 + 0.05), gap, math.pi))\n'
  '    elif ext > 0:\n'
  '        ye, ze, pe = st[-1]; st.append((ye + ext * math.cos(pe), ze + ext * math.sin(pe), pe))\n'),
 ('def make_case(name, ar, gap=None, stag=0.0, kt=1.0, kc=1.0, da=0.0):', 'def make_case(name, ar, gap=None, stag=0.0, kt=1.0, kc=1.0, da=0.0, f_up=1.0, s_end=1.0, ext=0.0):'),
 ('        c = S_FULL / b / 2; R, inf = rings_loop(c, half, gap, stag, kt, kc, da); T, lab, wt = tri(R, ("dolny", "luk", "gorny"), (cap_tri(1.0), cap_tri(-1.0)))',
  '        c = S_FULL / b / (1 + f_up) if s_end >= 0.999 else S_FULL / b\n'
  '        R, inf = rings_loop(c, half, gap, stag, kt, kc, da, f_up, s_end, ext); pe = math.pi if s_end >= 0.999 else math.pi * s_end\n'
  '        T, lab, wt = tri(R, ("dolny", "luk", "gorny"), (cap_tri(1.0), cap_tri(round(math.cos(pe), 6), round(1 - (1 - kt) * math.sin(pe) ** 2, 6), round(1 - (1 - kc) * math.sin(pe) ** 2, 6))))'),
 ('luk_grubosc=kt, luk_cieciwa=kc, dekalaz_deg=da,', 'luk_grubosc=kt, luk_cieciwa=kc, dekalaz_deg=da, gorny_czesc=f_up, luk_koniec=s_end, przedluzenie_m=ext,'),
 ('CAP_TRI = {}\ndef cap_tri(f):\n    if f not in CAP_TRI: CAP_TRI[f] = G.cap(section(f))\n    return CAP_TRI[f]',
  'CAP_TRI = {}\ndef cap_tri(f, tf=1.0, cf=1.0):\n    if (f, tf) not in CAP_TRI: CAP_TRI[(f, tf)] = G.cap(section(f, tf))\n    return CAP_TRI[(f, tf)]'),
]
for a, b in R:
    if b in t: continue
    assert t.count(a) == 1, a
    t = t.replace(a, b)
open(p, 'w', encoding='utf-8', newline='').write(t); print('ok')
