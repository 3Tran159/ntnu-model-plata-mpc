"""V3a: plat pojedynczy vs podzielony na dwa poziomy, woda spokojna (agent D, 14.11.2026).
Kopia logiki 30_URANS_STAR/make_geometry.py (tylko odczyt oryginalu), z dwiema zmianami:
 - plat obrocony o kat trymu alpha (nos w gore) wokol c/4,
 - wariant 'split': dwa platy o cieciwie c/2, LE na y = 0 (dolny) i y = DY (gorny), powierzchnia YFS.
Patche: Main / Flap obejmuja oba platy (sila calkowita), reszta jak w oryginale.
usage: python make_geometry_split.py single|split alpha_deg
"""
import json, math, sys
from pathlib import Path
import numpy as np
import triangle

OUT = Path(__file__).parent
REF = Path(r"F:\ntnu\flap_control\exploration_lab\MINI_POC_2D_20261103\mini_vof_20261103\COMEBACK_20261104"
           r"\WALL_FUNCTIONS_AUDIT\ACTIVE_GAP25_PRISM_20261104\SEALED_SHARP_MATCHED_OUTER\plot_mesh.npz")
VAR = sys.argv[1]; ALPHA = math.radians(float(sys.argv[2]))
C_MINI, C = 1.19, 0.312
H, T, G = 1.5, 5.0, 9.81
LAM = G * T ** 2 / (2 * math.pi)
if VAR == "single":
    FOILS = [(1.0, 0.0)]            # (skala cieciwy, y LE)
    YFS = 1.09
else:
    DY = 1.0
    FOILS = [(0.5, 0.0), (0.5, DY)]
    YFS = DY + 0.70                 # gorny plat 0,70 m pod powierzchnia, dolny 1,70 m
X0, X1, Y0 = -1.2 * LAM, 2.8 * LAM, -1.0 * LAM
Y1 = YFS + 3.0
SPAN = 0.02

d = np.load(REF)
xy = d["xy"]
adj, lab = {}, {}
for name, e in (("Main", d["main"]), ("Flap", d["flap"])):
    for a, b in e:
        a, b = int(a), int(b)
        adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
        lab[tuple(sorted((a, b)))] = name
assert all(len(v) == 2 for v in adj.values()), "foil outline is not a single simple loop"
start = next(iter(adj)); loop = [start]; prev = None
while True:
    nxt = [n for n in adj[loop[-1]] if n != prev][0]
    if nxt == start:
        break
    prev = loop[-1]; loop.append(nxt)
base = xy[loop] * (C / C_MINI)                      # LE (0,0), cieciwa 0,312 m wzdluz +x
base_lab = [lab[tuple(sorted((loop[i], loop[(i + 1) % len(loop)])))] for i in range(len(loop))]


def place(scale, y_le):
    """skala cieciwy, obrot o ALPHA nos w gore wokol c/4, przesuniecie LE na (0, y_le)"""
    p = base * scale; xc = 0.25 * C * scale
    x = xc + (p[:, 0] - xc) * math.cos(ALPHA) + p[:, 1] * math.sin(ALPHA)
    y = -(p[:, 0] - xc) * math.sin(ALPHA) + p[:, 1] * math.cos(ALPHA)
    hx = xc + (0.5 * C * scale - xc) * math.cos(ALPHA); hy = -(0.5 * C * scale - xc) * math.sin(ALPHA)
    return np.column_stack([x, y + y_le]), [hx, hy + y_le]


outer = np.array([[X0, Y0], [X1, Y0], [X1, Y1], [X0, Y1]])
verts = [outer]; segs, marks, holes = [], [], []
for i, m in enumerate((3, 2, 4, 1)):           # bottom, outlet, top, inlet
    segs.append([i, (i + 1) % 4]); marks.append(m)
n0 = 4
for sc, yle in FOILS:
    f, h = place(sc, yle); verts.append(f); holes.append(h)
    for i, name in enumerate(base_lab):
        segs.append([n0 + i, n0 + (i + 1) % len(f)]); marks.append(10 if name == "Main" else 11)
    n0 += len(f)
tri = triangle.triangulate({"vertices": np.vstack(verts), "segments": np.array(segs),
                            "segment_markers": np.array(marks)[:, None], "holes": holes}, "pq25a40")
V, F = tri["vertices"], tri["triangles"]
BS, BM = tri["segments"], tri["segment_markers"].ravel()
names = {1: "Inlet", 2: "Outlet", 3: "Bottom", 4: "Top", 10: "Main", 11: "Flap"}


def ccw(a, b, c):
    return (V[b, 0] - V[a, 0]) * (V[c, 1] - V[a, 1]) - (V[c, 0] - V[a, 0]) * (V[b, 1] - V[a, 1]) > 0


def p3(i, z):
    return (float(V[i, 0]), float(V[i, 1]), z)


patches = {k: [] for k in ("Span0", "Span1", "Main", "Flap", "Inlet", "Outlet", "Bottom", "Top")}
directed = set()
for a, b, c in F:
    if not ccw(a, b, c):
        b, c = c, b
    patches["Span0"].append((p3(a, 0), p3(c, 0), p3(b, 0)))
    patches["Span1"].append((p3(a, SPAN), p3(b, SPAN), p3(c, SPAN)))
    directed.update({(a, b), (b, c), (c, a)})
for (u, v), m in zip(BS, BM):
    if (u, v) not in directed:
        u, v = v, u
    assert (u, v) in directed
    a, b, c, e = p3(u, 0), p3(v, 0), p3(v, SPAN), p3(u, SPAN)
    patches[names[int(m)]].extend([(a, b, c), (a, c, e)])

stl = OUT / ("GodoFluidDomain_%s.stl" % VAR)
with open(stl, "w", newline="\n") as f:
    for name, faces in patches.items():
        assert faces, name
        f.write("solid %s\n" % name)
        for a, b, c in faces:
            n = np.cross(np.subtract(b, a), np.subtract(c, a)); n = n / np.linalg.norm(n)
            f.write("  facet normal %.9g %.9g %.9g\n    outer loop\n" % tuple(n))
            for q in (a, b, c):
                f.write("      vertex %.17g %.17g %.17g\n" % q)
            f.write("    endloop\n  endfacet\n")
        f.write("endsolid %s\n" % name)

U = 24 * 1852 / 3600
info = {"variant": VAR, "alpha_deg": math.degrees(ALPHA), "foils_scale_yLE": FOILS, "free_surface_y_m": YFS,
        "depths_LE_m": [YFS - y for _, y in FOILS], "chord_ref_m": C, "lambda_deep_m": LAM, "U_m_s": U,
        "domain_x_m": [X0, X1], "domain_y_m": [Y0, Y1], "span_m": SPAN,
        "foil_area_m2_total": 0.00795948899616472 * sum(s * s for s, _ in FOILS),
        "patch_triangles": {k_: len(v) for k_, v in patches.items()}}
(OUT / ("GEOMETRY_%s.json" % VAR)).write_text(json.dumps(info, indent=1))
print(json.dumps(info, indent=1))
