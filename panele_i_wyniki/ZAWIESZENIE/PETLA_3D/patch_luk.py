"""Luk z innego profilu: grubosc kt i cieciwa kc na srodku luku (phi = 90 st.), przejscie sin^2(phi) -> plynnie (G2) do platow.
kt = kc = 1 daje dotychczasowa geometrie bez zmian. Os cwierci cieciwy zachowana. Agent D, 16.11.2026."""
p = 'opt_geo.py'; t = open(p, encoding='utf-8').read()
R = [
 ('def section(f):\n    """zamkniety kontur CCW (dol LE->TE, gora TE->LE), ugiecie * f"""\n    lo = np.column_stack([XG, f * MG - TG]); hi = np.column_stack([XG, f * MG + TG])[::-1]',
  'def section(f, tf=1.0):\n    """zamkniety kontur CCW (dol LE->TE, gora TE->LE), ugiecie * f, grubosc * tf"""\n    lo = np.column_stack([XG, f * MG - tf * TG]); hi = np.column_stack([XG, f * MG + tf * TG])[::-1]'),
 ('def rings_loop(c, half, gap, stag):', 'def rings_loop(c, half, gap, stag, kt=1.0, kc=1.0):'),
 ('        sec = section(math.cos(ph)); xs, ts = sec[:, 0] * c, sec[:, 1] * c\n',
  '        wl = math.sin(ph) ** 2; cl = c * (1 - (1 - kc) * wl); sec = section(math.cos(ph), 1 - (1 - kt) * wl)\n'
  '        xs, ts = sec[:, 0] * cl + 0.25 * (c - cl), sec[:, 1] * cl\n'),
 ('def make_case(name, ar, gap=None, stag=0.0):', 'def make_case(name, ar, gap=None, stag=0.0, kt=1.0, kc=1.0):'),
 ('R, inf = rings_loop(c, half, gap, stag);', 'R, inf = rings_loop(c, half, gap, stag, kt, kc);'),
 ('info = dict(AR=ar, odstep_m=gap, przesuniecie_m=stag,', 'info = dict(AR=ar, odstep_m=gap, przesuniecie_m=stag, luk_grubosc=kt, luk_cieciwa=kc,'),
]
for a, b in R:
    assert t.count(a) == 1, a
    t = t.replace(a, b)
open(p, 'w', encoding='utf-8', newline='').write(t); print('ok')
