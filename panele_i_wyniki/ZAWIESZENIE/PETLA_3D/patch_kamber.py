"""Poprawka opt_geo.py: profil jest UGIETY (CL ok. 0,3 przy 0 st.), wiec w petli nie wolno go odwracac razem ze sciezka.
Rozklad na linie szkieletowa m(x) i grubosc t(x); w stacji sciezki ugiecie * cos(phi): dol +1, luk przechodzi przez 0, gora -1
w ukladzie lokalnym (= ugiecie w gore w ukladzie swiata). Ta sama liczba punktow we wszystkich stacjach."""
p = 'opt_geo.py'; t = open(p, encoding='utf-8').read()
a = 'def rings_loop(c, half, gap, stag):'
b = '''NX = 220
def _split():
    S = SEC; i0 = int(S[:, 0].argmin()); S = np.roll(S, -i0, axis=0)          # start na LE, CCW: najpierw strona dolna do TE
    iT = int(S[:, 0].argmax()); low = S[:iT + 1]; up = np.vstack([S[iT:], S[:1]])[::-1]
    x = 0.5 * (1 - np.cos(np.linspace(0, np.pi, NX))) * S[:, 0].max()
    yl = np.interp(x, low[:, 0], low[:, 1]); yu = np.interp(x, up[:, 0], up[:, 1]); return x, 0.5 * (yu + yl), 0.5 * (yu - yl)
XG, MG, TG = _split()
def section(f):
    """zamkniety kontur CCW (dol LE->TE, gora TE->LE), ugiecie * f"""
    lo = np.column_stack([XG, f * MG - TG]); hi = np.column_stack([XG, f * MG + TG])[::-1]
    return np.vstack([lo, hi[1:-1]]) if TG[0] < 1e-9 else np.vstack([lo, hi])
CAP_TRI = {}
def cap_tri(f):
    if f not in CAP_TRI: CAP_TRI[f] = G.cap(section(f))
    return CAP_TRI[f]
def rings_loop(c, half, gap, stag):'''
assert t.count(a) == 1; t = t.replace(a, b, 1)
a2 = "    xs, ts = SEC[:, 0] * c, SEC[:, 1] * c; xc = 0.25 * c; R = []\n    for y, z, ph in st:\n        a = ALPHA * math.cos(ph)"
b2 = "    xc = 0.25 * c; R = []\n    for y, z, ph in st:\n        sec = section(math.cos(ph)); xs, ts = sec[:, 0] * c, sec[:, 1] * c\n        a = ALPHA * math.cos(ph)"
assert t.count(a2) == 1; t = t.replace(a2, b2)
a3 = "def tri(R, names):\n    n = len(SEC); T, lab = [], []"
b3 = "def tri(R, names, caps=(None, None)):\n    n = len(R[0]); T, lab = [], []"
assert t.count(a3) == 1; t = t.replace(a3, b3)
a4 = "    for a, b, cc in G.TRI_CAP:\n        T.append((R[0][a], R[0][b], R[0][cc])); lab.append(names[0]); T.append((R[-1][a], R[-1][cc], R[-1][b])); lab.append(names[2])"
b4 = ("    c0 = caps[0] if caps[0] is not None else G.TRI_CAP; c1 = caps[1] if caps[1] is not None else G.TRI_CAP\n"
      "    for a, b, cc in c0: T.append((R[0][a], R[0][b], R[0][cc])); lab.append(names[0])\n"
      "    for a, b, cc in c1: T.append((R[-1][a], R[-1][cc], R[-1][b])); lab.append(names[2])")
assert t.count(a4) == 1; t = t.replace(a4, b4)
a5 = 'R, inf = rings_loop(c, half, gap, stag); T, lab, wt = tri(R, ("dolny", "luk", "gorny"))'
b5 = 'R, inf = rings_loop(c, half, gap, stag); T, lab, wt = tri(R, ("dolny", "luk", "gorny"), (cap_tri(1.0), cap_tri(-1.0)))'
assert t.count(a5) == 1; t = t.replace(a5, b5)
open(p, 'w', encoding='utf-8', newline='').write(t); print('ok')
