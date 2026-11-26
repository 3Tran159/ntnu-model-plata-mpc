"""Overset geometry for the Godø reproduction with a ROTATING WHOLE FOIL and free heave (quasi-2D, 0.02 m span).

Two watertight STLs (geometry only; volume meshes are native STAR-CCM+ Directed Mesh operations):
  GodoBackground.stl : the full wave tank (same extents as the fixed-foil case), no foil.  Patches Inlet/Outlet/Bottom/Top/Span0/Span1
  GodoOverset.stl    : rectangular overset block around the foil, foil cut out.          Patches Overset/Foil/Span0/Span1

Foil section (Godø Table 1: thickness NACA 66(1)-012, camber line NACA a = 0.8 (mod)):
  thickness: our NACA66-012 MOD thickness distribution (from the verified Mini outline, flap sealed -> one smooth section)
  camber   : NACA a = 0.8 mean line (standard formula, Abbott & von Doenhoff eq. 4.26), design CL_i = CLI (see below)
  -> documented approximation: 66-012 MOD thickness instead of 66(1)-012, unmodified a = 0.8 line instead of a = 0.8 (mod).
Design lift: Godø's 12.5 t vessel on one main foil, S = AR*c^2 = 25.6*0.312^2 = 2.49 m^2 -> CL_req = W/(q S) = 0.63 at 24 kn.
  CL_i = 0.63 is used so the foil flies near its ideal angle at the design point, as in Godø's Fig. 2 discussion.
"""
import json, math, sys
from pathlib import Path
import numpy as np
import triangle

OUT = Path(__file__).parent
sys.path.insert(0, str(OUT.parent))
REF = Path(r"F:\ntnu\flap_control\exploration_lab\MINI_POC_2D_20261103\mini_vof_20261103\COMEBACK_20261104"
           r"\WALL_FUNCTIONS_AUDIT\ACTIVE_GAP25_PRISM_20261104\SEALED_SHARP_MATCHED_OUTER\plot_mesh.npz")
GEO = json.loads((OUT.parent / "GEOMETRY_GODO.json").read_text())
C, SPAN = GEO["chord_m"], GEO["span_m"]
X0, X1 = GEO["domain_x_m"]; Y0, Y1 = GEO["domain_y_m"]
U, RHO, G = GEO["U_m_s"], 1025.0, 9.81
AR, MASS = 25.6, 12500.0
CLI = 0.63
PIVOT = (0.25 * C, 0.0)
BLOCK = (-0.10, 0.46, -0.11, 0.11)          # x0, x1, y0, y1 of the overset block [m]
N = 161                                     # stations per side (cosine spacing)

# ---- thickness distribution from the Mini outline ------------------------------------------------------------
d = np.load(REF); xy = d["xy"]
edges = np.vstack([d["main"], d["flap"]]).astype(int)
pts = xy[np.unique(edges)] * (C / 1.19)
xle, xte = pts[:, 0].min(), pts[:, 0].max()
xs = (pts[:, 0] - xle) / (xte - xle)
up, lo = pts[pts[:, 1] >= 0], pts[pts[:, 1] < 0]


def side(p):
    o = np.argsort(p[:, 0]); x = (p[o, 0] - xle) / (xte - xle)
    x, i = np.unique(x, return_index=True)
    return x, p[o, 1][i] / C


xu, yu = side(up); xl, yl = side(lo)
beta = np.linspace(0, math.pi, N); xc = 0.5 * (1 - np.cos(beta))
t_half = 0.5 * (np.interp(xc, xu, yu) - np.interp(xc, xl, yl))
t_half[0] = 0.0


# ---- NACA a = 0.8 mean line ----------------------------------------------------------------------------------
def meanline(x, a=0.8, cli=CLI):
    x = np.clip(x, 1e-9, 1 - 1e-9)
    g = -1 / (1 - a) * (a * a * (0.5 * math.log(a) - 0.25) + 0.25)
    h = 1 / (1 - a) * (0.5 * (1 - a) ** 2 * math.log(1 - a) - 0.25 * (1 - a) ** 2) + g
    am = np.abs(a - x)
    t1 = 0.5 * (a - x) ** 2 * np.log(np.where(am > 1e-12, am, 1e-12)) - 0.5 * (1 - x) ** 2 * np.log(1 - x) \
        + 0.25 * (1 - x) ** 2 - 0.25 * (a - x) ** 2
    return cli / (2 * math.pi * (a + 1)) * (t1 / (1 - a) - x * np.log(x) + g - h * x)


yc = meanline(xc); yc[0] = 0.0; yc[-1] = 0.0
dyc = np.gradient(yc, xc); th = np.arctan(dyc)
xu2, yu2 = xc - t_half * np.sin(th), yc + t_half * np.cos(th)
xl2, yl2 = xc + t_half * np.sin(th), yc - t_half * np.cos(th)
# closed loop: TE -> upper -> LE -> lower -> TE (TE thickness of the MOD section kept as a short base if present)
loop = np.vstack([np.c_[xu2[::-1], yu2[::-1]], np.c_[xl2[1:], yl2[1:]]]) * C
if np.hypot(*(loop[0] - loop[-1])) < 1e-6:
    loop = loop[:-1]
foil = loop
max_camber = float(yc.max())


def tri_stl(outer, outer_names, hole, path, names):
    verts = [outer]; segs = []; marks = []
    n0 = len(outer)
    for i in range(n0):
        segs.append([i, (i + 1) % n0]); marks.append(outer_names[i])
    holes = []
    if hole is not None:
        verts.append(hole)
        for i in range(len(hole)):
            segs.append([n0 + i, n0 + (i + 1) % len(hole)]); marks.append(99)
        holes = [[0.4 * C, float(np.interp(0.4, xc, yc)) * C]]
    V = np.vstack(verts)
    arg = {"vertices": V, "segments": np.array(segs), "segment_markers": np.array(marks)[:, None]}
    if holes:
        arg["holes"] = holes
    t = triangle.triangulate(arg, "pq28")
    V, F = t["vertices"], t["triangles"]
    BS, BM = t["segments"], t["segment_markers"].ravel()

    def p3(i, z):
        return (float(V[i, 0]), float(V[i, 1]), z)

    patches = {k: [] for k in names.values()}
    patches["Span0"] = []; patches["Span1"] = []
    directed = set()
    for a, b, c in F:
        if (V[b, 0] - V[a, 0]) * (V[c, 1] - V[a, 1]) - (V[c, 0] - V[a, 0]) * (V[b, 1] - V[a, 1]) < 0:
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
    with open(path, "w", newline="\n") as f:
        for name, faces in patches.items():
            assert faces, name
            f.write("solid %s\n" % name)
            for a, b, c in faces:
                nrm = np.cross(np.subtract(b, a), np.subtract(c, a)); nrm = nrm / np.linalg.norm(nrm)
                f.write("  facet normal %.9g %.9g %.9g\n    outer loop\n" % tuple(nrm))
                for q in (a, b, c):
                    f.write("      vertex %.17g %.17g %.17g\n" % q)
                f.write("    endloop\n  endfacet\n")
            f.write("endsolid %s\n" % name)
    return {k: len(v) for k, v in patches.items()}


bg = np.array([[X0, Y0], [X1, Y0], [X1, Y1], [X0, Y1]])
bg_tri = tri_stl(bg, [3, 2, 4, 1], None, OUT / "GodoBackground.stl", {1: "Inlet", 2: "Outlet", 3: "Bottom", 4: "Top"})
bx0, bx1, by0, by1 = BLOCK
blk = np.array([[bx0, by0], [bx1, by0], [bx1, by1], [bx0, by1]])
ov_tri = tri_stl(blk, [5, 5, 5, 5], foil, OUT / "GodoOverset.stl", {5: "Overset", 99: "Foil"})

# section properties (per 0.02 m span strip)
area = 0.5 * abs(np.dot(foil[:, 0], np.roll(foil[:, 1], 1)) - np.dot(foil[:, 1], np.roll(foil[:, 0], 1)))
b_span = AR * C
S_ref = b_span * C
q = 0.5 * RHO * U ** 2
info = {"section": "66-012 MOD thickness + NACA a=0.8 mean line", "CL_i": CLI, "max_camber_over_c": max_camber,
        "pivot_m": PIVOT, "overset_block_m": BLOCK, "foil_points": int(len(foil)),
        "foil_area_m2": float(area), "foil_buoyancy_strip_N": float(RHO * G * area * SPAN),
        "vessel_mass_kg": MASS, "foil_span_m": b_span, "foil_area_ref_m2": S_ref,
        "CL_required_3D": MASS * G / (q * S_ref),
        "strip_mass_kg": MASS / b_span * SPAN, "strip_weight_N": MASS / b_span * SPAN * G,
        "q_c_span_N": q * C * SPAN, "triangles_background": bg_tri, "triangles_overset": ov_tri}
(OUT / "GEOMETRY_OVERSET.json").write_text(json.dumps(info, indent=1))
np.savetxt(OUT / "foil_section_godo.csv", foil, delimiter=",", header="x_m,y_m", comments="")
print(json.dumps(info, indent=1))
