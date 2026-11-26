"""Overset geometry for the GodÃ¸ case (whole-foil rotation + free heave), quasi-2D 0.02 m span.

Two watertight STL parts with named patches (volume meshes are generated natively in STAR-CCM+):
  GodoBackground.stl : full domain without foil   -> Inlet, Outlet, Bottom, Top, Span0, Span1
  GodoOverset.stl    : rectangle around the foil  -> Overset, Main, Flap, Span0, Span1
Foil, domain and conditions are identical to make_geometry.py (LE at (0,0), calm surface at y = 1.09 m).
Overset box: x -0.20..0.55 m, y -0.15..0.15 m (foil c = 0.312 m; pivot c/4 = 0.078 m; +-7.5 deg keeps >= 0.1 m clearance).
"""
import json, math
from pathlib import Path
import numpy as np
import triangle

OUT = Path(__file__).parent
REF = Path(r"F:\ntnu\flap_control\exploration_lab\MINI_POC_2D_20261103\mini_vof_20261103\COMEBACK_20261104"
           r"\WALL_FUNCTIONS_AUDIT\ACTIVE_GAP25_PRISM_20261104\SEALED_SHARP_MATCHED_OUTER\plot_mesh.npz")
C_MINI, C = 1.19, 0.312
S = C / C_MINI
geo = json.loads((OUT / "GEOMETRY_GODO.json").read_text())
import sys
X0, X1 = geo["domain_x_m"]; Y0, Y1 = geo["domain_y_m"]
LAM = geo["lambda_deep_m"]
if len(sys.argv) > 2:                       # shortened background: python make_geometry_overset.py x0_over_lambda x1_over_lambda
    X0, X1 = float(sys.argv[1]) * LAM, float(sys.argv[2]) * LAM
BG_NAME = "GodoBackground.stl" if len(sys.argv) <= 2 else "GodoBackground_%gL_%gL.stl" % (float(sys.argv[1]), float(sys.argv[2]))
SPAN = geo["span_m"]
OX0, OX1, OY0, OY1 = -0.20, 0.55, -0.15, 0.15

d = np.load(REF)
xy = d["xy"]
adj, lab = {}, {}
for name, e in (("Main", d["main"]), ("Flap", d["flap"])):
    for a, b in e:
        a, b = int(a), int(b)
        adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
        lab[tuple(sorted((a, b)))] = name
start = next(iter(adj)); loop = [start]; prev = None
while True:
    nxt = [n for n in adj[loop[-1]] if n != prev][0]
    if nxt == start:
        break
    prev = loop[-1]; loop.append(nxt)
foil = xy[loop] * S
foil_lab = [lab[tuple(sorted((loop[i], loop[(i + 1) % len(loop)])))] for i in range(len(loop))]


def build(outer, outer_names, with_foil, fname, area):
    verts = [np.asarray(outer)]
    segs, marks = [], []
    n = len(outer)
    for i in range(n):
        segs.append([i, (i + 1) % n]); marks.append(i + 1)
    holes = []
    names = {i + 1: outer_names[i] for i in range(n)}
    if with_foil:
        verts.append(foil)
        for i, name in enumerate(foil_lab):
            segs.append([n + i, n + (i + 1) % len(foil)]); marks.append(10 if name == "Main" else 11)
        holes = [[0.5 * C, 0.0]]
        names.update({10: "Main", 11: "Flap"})
    tri_in = {"vertices": np.vstack(verts), "segments": np.array(segs), "segment_markers": np.array(marks)[:, None]}
    if holes:
        tri_in["holes"] = holes
    tri = triangle.triangulate(tri_in, "pq25a%g" % area)
    V, F = tri["vertices"], tri["triangles"]
    BS, BM = tri["segments"], tri["segment_markers"].ravel()

    def ccw(a, b, c):
        return (V[b, 0] - V[a, 0]) * (V[c, 1] - V[a, 1]) - (V[c, 0] - V[a, 0]) * (V[b, 1] - V[a, 1]) > 0

    def p3(i, z):
        return (float(V[i, 0]), float(V[i, 1]), z)

    patches = {k: [] for k in ["Span0", "Span1"] + sorted(set(names.values()))}
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
    with open(OUT / fname, "w", newline="\n") as f:
        for name, faces in patches.items():
            assert faces, name
            f.write("solid %s\n" % name)
            for a, b, c in faces:
                nn = np.cross(np.subtract(b, a), np.subtract(c, a)); nn = nn / np.linalg.norm(nn)
                f.write("  facet normal %.9g %.9g %.9g\n    outer loop\n" % tuple(nn))
                for q in (a, b, c):
                    f.write("      vertex %.17g %.17g %.17g\n" % q)
                f.write("    endloop\n  endfacet\n")
            f.write("endsolid %s\n" % name)
    return {k: len(v) for k, v in patches.items()}


bg = build([[X0, Y0], [X1, Y0], [X1, Y1], [X0, Y1]], ["Bottom", "Outlet", "Top", "Inlet"], False, BG_NAME, 40)
ov = build([[OX0, OY0], [OX1, OY0], [OX1, OY1], [OX0, OY1]], ["Overset", "Overset", "Overset", "Overset"], True, "GodoOverset.stl", 0.002)
info = {"background_stl": BG_NAME, "domain_x_m": [X0, X1], "overset_box_m": [OX0, OX1, OY0, OY1], "pivot_m": [0.25 * C, 0.0], "background_patches": bg, "overset_patches": ov,
        "note": "pivot at quarter chord (GodÃ¸ does not state the rotation axis); flap sealed at 0 deg, rotates with the foil"}
(OUT / ("GEOMETRY_GODO_OVERSET.json" if len(sys.argv) <= 2 else BG_NAME.replace(".stl", ".json"))).write_text(json.dumps(info, indent=1))
print(json.dumps(info, indent=1))
