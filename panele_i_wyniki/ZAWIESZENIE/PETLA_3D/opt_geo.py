"""Generator geometrii do optymalizacji: petla G2 z trzema parametrami (wydluzenie AR przy stalej powierzchni 2,496 m2,
odstep gora-dol h [m], przesuniecie dolnego platu s [m], + = dolny z tylu) albo plat pojedynczy o danym AR.
Wpis do GEOMETRIA_G2.json (petle) / GEOMETRIA_MONO.json (pojedyncze), ktore czyta run_p3d.py. Agent D, 15.11.2026."""
import json, math
from pathlib import Path
import numpy as np, trimesh
import make_geo3d as G
HERE = Path(__file__).parent; S_FULL = 8.0 * 0.312; ALPHA = G.ALPHA; SEC = G.SEC; NB = 80


def bend_shape():
    s = np.linspace(0, 1, 4001); phi = 2 * math.pi * (s / 2 - np.sin(2 * math.pi * s) / (4 * math.pi)); ds = s[1] - s[0]
    y = np.concatenate([[0], np.cumsum((np.cos(phi[1:]) + np.cos(phi[:-1])) / 2 * ds)])
    z = np.concatenate([[0], np.cumsum((np.sin(phi[1:]) + np.sin(phi[:-1])) / 2 * ds)])
    return s, phi, y, z


NX = 220
def _split():
    S = SEC; iL = int(S[:, 0].argmin())                     # SEC[0] i SEC[-1] = dwa punkty tepej krawedzi splywu (po obcieciu)
    A = S[:iL + 1][::-1]; B = S[iL:]                          # obie strony od LE do TE
    low, up = (A, B) if A[:, 1].mean() < B[:, 1].mean() else (B, A)
    x = 0.5 * (1 - np.cos(np.linspace(0, np.pi, NX))) * min(low[-1, 0], up[-1, 0])
    yl = np.interp(x, low[:, 0], low[:, 1]); yu = np.interp(x, up[:, 0], up[:, 1]); return x, 0.5 * (yu + yl), 0.5 * (yu - yl)
XG, MG, TG = _split()
def section(f, tf=1.0):
    """zamkniety kontur CCW (dol LE->TE, gora TE->LE), ugiecie * f, grubosc * tf"""
    lo = np.column_stack([XG, f * MG - tf * TG]); hi = np.column_stack([XG, f * MG + tf * TG])[::-1]
    return np.vstack([lo, hi[1:-1]]) if TG[0] < 1e-9 else np.vstack([lo, hi])
CAP_TRI = {}
def cap_tri(f, tf=1.0, cf=1.0):
    if (f, tf) not in CAP_TRI: CAP_TRI[(f, tf)] = G.cap(section(f, tf))
    return CAP_TRI[(f, tf)]
def rings_loop(c, half, gap, stag, kt=1.0, kc=1.0, da=0.0, f_up=1.0, s_end=1.0, ext=0.0, tip=0):
    s, phi, yb, zb = bend_shape(); L = gap / zb[-1]; w = L * yb.max(); y0 = half - w
    idx = np.linspace(0, (len(s) - 1) * s_end, NB + 1).round().astype(int)
    st = [(-0.05, 0.0, 0.0)] + [(y0 + L * yb[i], L * zb[i], phi[i]) for i in idx]
    if s_end >= 0.999:
        if f_up > 0.02: st.append((y0 - f_up * (y0 + 0.05), gap, math.pi))
    elif ext > 0 and tip:
        ye, ze, pe = st[-1]
        for eta in np.sin(np.linspace(0, math.pi / 2, 25))[1:]:
            st.append((ye + ext * eta * math.cos(pe), ze + ext * eta * math.sin(pe), pe, max(0.03, math.sqrt(max(0.0, 1 - eta ** 2)))))
    elif ext > 0:
        ye, ze, pe = st[-1]; st.append((ye + ext * math.cos(pe), ze + ext * math.sin(pe), pe))
    xc = 0.25 * c; R = []
    for item in st:
        y, z, ph = item[:3]; sk = item[3] if len(item) > 3 else 1.0
        wl = math.sin(ph) ** 2; cl = c * (1 - (1 - kc) * wl) * sk; sec = section(math.cos(ph), 1 - (1 - kt) * wl)
        xs, ts = sec[:, 0] * cl + 0.25 * (c - cl), sec[:, 1] * cl
        a = ALPHA * math.cos(ph) - math.radians(da) * (1 - math.cos(ph)) / 2; ny, nz = -math.sin(ph), math.cos(ph); dx = stag * (1 - ph / math.pi)
        x = dx + xc + (xs - xc) * math.cos(a) + ts * math.sin(a); t = -(xs - xc) * math.sin(a) + ts * math.cos(a)
        R.append(np.column_stack([x, y + t * ny, z + t * nz]))
    return R, dict(L_luku_m=L, szerokosc_luku_m=w, y_poczatku_luku_m=y0)


def tri(R, names, caps=(None, None)):
    n = len(R[0]); T, lab = [], []
    for k in range(len(R) - 1):
        part = names[0] if k == 0 else (names[2] if k == len(R) - 2 else names[1])
        for i in range(n):
            j = (i + 1) % n; T += [(R[k][i], R[k + 1][j], R[k][j]), (R[k][i], R[k + 1][i], R[k + 1][j])]; lab += [part, part]
    c0 = caps[0] if caps[0] is not None else G.TRI_CAP; c1 = caps[1] if caps[1] is not None else G.TRI_CAP
    for a, b, cc in c0: T.append((R[0][a], R[0][b], R[0][cc])); lab.append(names[0])
    for a, b, cc in c1: T.append((R[-1][a], R[-1][cc], R[-1][b])); lab.append(names[2])
    m = trimesh.Trimesh(np.array(T).reshape(-1, 3), np.arange(3 * len(T)).reshape(-1, 3), process=True); m.merge_vertices()
    if m.volume < 0: T = [(a, cc, b) for a, b, cc in T]
    return T, np.array(lab), bool(m.is_watertight)


def make_case(name, ar, gap=None, stag=0.0, kt=1.0, kc=1.0, da=0.0, f_up=1.0, s_end=1.0, ext=0.0, tip=0):
    b = math.sqrt(ar * S_FULL); half = b / 2; cd = HERE / name; cd.mkdir(exist_ok=True)
    G.write(cd / "domena.stl", G.box(-8.0, 24.0, 0.0, 12.0, -8.0, 9.0))
    if gap is None:                                          # plat pojedynczy, cieciwa S/b, srodek na z = 0,5
        c = S_FULL / b; xs, ts = SEC[:, 0] * c, SEC[:, 1] * c; xc = 0.25 * c; R = []
        for y in (-0.05, half):
            x = xc + (xs - xc) * math.cos(ALPHA) + ts * math.sin(ALPHA); z = 0.5 - (xs - xc) * math.sin(ALPHA) + ts * math.cos(ALPHA)
            R.append(np.column_stack([x, np.full_like(x, y), z]))
        T, lab, wt = tri(R, ("plat", "plat", "plat")); f = HERE / "GEOMETRIA_MONO.json"
        info = dict(AR=ar, pol_rozp_m=half, cieciwa_m=c, watertight=wt)
    else:
        c = S_FULL / b / (1 + f_up) if s_end >= 0.999 else S_FULL / b
        R, inf = rings_loop(c, half, gap, stag, kt, kc, da, f_up, s_end, ext, tip); pe = math.pi if s_end >= 0.999 else math.pi * s_end
        T, lab, wt = tri(R, ("dolny", "luk", "gorny"), (cap_tri(1.0), cap_tri(round(math.cos(pe), 6), round(1 - (1 - kt) * math.sin(pe) ** 2, 6), round(1 - (1 - kc) * math.sin(pe) ** 2, 6)))); f = HERE / "GEOMETRIA_G2.json"
        info = dict(AR=ar, odstep_m=gap, przesuniecie_m=stag, luk_grubosc=kt, luk_cieciwa=kc, dekalaz_deg=da, gorny_czesc=f_up, luk_koniec=s_end, przedluzenie_m=ext, koncowka_eliptyczna=tip, pol_rozp_m=half, cieciwa_platu_m=c, watertight=wt, **inf)
    G.write(cd / "bryla.stl", {k: [T[i] for i in np.where(lab == k)[0]] for k in dict.fromkeys(lab)})
    allg = json.loads(f.read_text()) if f.exists() else {}; allg[name] = info; f.write_text(json.dumps(allg, indent=1))
    return info
