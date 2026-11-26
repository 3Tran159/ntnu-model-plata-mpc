"""Geometry for the Godø-condition case (quasi-2D, 0.02 m span) -> watertight STL with named patches.

The STL is only the GEOMETRY (as for the Mini case); the volume mesh is generated natively in STAR-CCM+
(Directed Mesh operation with editable custom controls, all sizes relative to one Base Size -> mesh study).

Foil: our sealed NACA66-012 MOD section with flap at x/c = 0.80 (outline from the Mini reference mesh),
      scaled to Godø's mean chord c = 0.312 m (Godø Table 1; his section NACA 66(1)-0012 + a=0.8 camber,
      whole-foil rotation, no flap - documented difference). Leading edge at (0, 0), chord along +x.
Conditions (Godø 2024 Sec. 2.3): U = 24 kn = 12.347 m/s, regular head waves H = 1.5 m, T = 5.0 s,
      design draft (calm surface above foil) 1.09 m. Deep-water lambda = g T^2 / 2 pi = 39.03 m.
Domain scaled from the Mini layout by lambda (Mini: lambda 10 m, x -12..28, bottom -10, top 2 m above surface):
      x -1.2..+2.8 lambda, bottom -1 lambda, top 3.0 m above the calm surface.
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
DRAFT, H, T = 1.09, 1.5, 5.0
G = 9.81
LAM = G * T ** 2 / (2 * math.pi)
X0, X1, Y0 = -1.2 * LAM, 2.8 * LAM, -1.0 * LAM
YFS = DRAFT
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
assert len(loop) == len(lab)
foil = xy[loop] * S
foil_lab = [lab[tuple(sorted((loop[i], loop[(i + 1) % len(loop)])))] for i in range(len(loop))]

outer = np.array([[X0, Y0], [X1, Y0], [X1, Y1], [X0, Y1]])
verts = np.vstack([outer, foil])
segs, marks = [], []
for i, m in enumerate((3, 2, 4, 1)):           # bottom, outlet, top, inlet
    segs.append([i, (i + 1) % 4]); marks.append(m)
for i, name in enumerate(foil_lab):
    segs.append([4 + i, 4 + (i + 1) % len(foil)]); marks.append(10 if name == "Main" else 11)
tri = triangle.triangulate({"vertices": verts, "segments": np.array(segs), "segment_markers": np.array(marks)[:, None],
                           "holes": [[0.5 * C, 0.0]]}, "pq25a40")
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

with open(OUT / "GodoFluidDomain.stl", "w", newline="\n") as f:
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
w0 = 2 * math.pi / T; k = 2 * math.pi / LAM
info = {"chord_m": C, "scale_from_mini": S, "draft_m": DRAFT, "free_surface_y_m": YFS, "H_m": H, "T_s": T,
        "lambda_deep_m": LAM, "U_m_s": U, "domain_x_m": [X0, X1], "domain_y_m": [Y0, Y1], "span_m": SPAN,
        "hinge_x_m": 0.8 * C, "foil_points": int(len(foil)),
        "foil_x_range": [float(foil[:, 0].min()), float(foil[:, 0].max())],
        "foil_y_range": [float(foil[:, 1].min()), float(foil[:, 1].max())],
        "patch_triangles": {k_: len(v) for k_, v in patches.items()},
        "encounter_omega_rad_s": w0 + k * U, "encounter_period_s": 2 * math.pi / (w0 + k * U),
        "w_at_foil_m_s": 0.5 * H * w0 * math.exp(-k * DRAFT),
        "q_dyn_x_c_x_span_N": 0.5 * 1000 * U ** 2 * C * SPAN}
info["inflow_angle_amp_deg"] = math.degrees(math.atan(info["w_at_foil_m_s"] / U))
info["reduced_frequency_k"] = info["encounter_omega_rad_s"] * C / (2 * U)
info["steepness_H_over_lambda"] = H / LAM
(OUT / "GEOMETRY_GODO.json").write_text(json.dumps(info, indent=1))
print(json.dumps(info, indent=1))
