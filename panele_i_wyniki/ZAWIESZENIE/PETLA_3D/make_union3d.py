"""Suma boolowska brył (manifold3d) -> jedna szczelna bryla 'bryla.stl' z patchami gorny / dolny / plytka / plat (klasyfikacja
po polozeniu scianek), zeby STAR robil tylko Subtract (bez wrappera). Geometria z make_geo3d.py. Agent D, 15.11.2026."""
import json
from pathlib import Path
import numpy as np, trimesh, manifold3d as mf
import make_geo3d as G

HERE = Path(__file__).parent


def to_mesh(tris):
    v = np.array(tris).reshape(-1, 3); f = np.arange(len(v)).reshape(-1, 3)
    m = trimesh.Trimesh(v, f, process=True); m.merge_vertices(); m.update_faces(m.nondegenerate_faces())
    if m.volume < 0: m.invert()
    assert m.is_watertight, "bryla nieszczelna"
    return m


def to_manifold(m): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))


info = {}
for case, bodies in G.CASES.items():
    ms = {k: to_mesh(v) for k, v in bodies.items()}
    u = None
    for k, m in ms.items(): u = to_manifold(m) if u is None else u + to_manifold(m)
    out = u.to_mesh(); V = np.asarray(out.vert_properties)[:, :3].astype(float); F = np.asarray(out.tri_verts)
    um = trimesh.Trimesh(V, F, process=False)
    c = um.triangles_center
    if "plytka" in bodies:
        lab = np.where((np.abs(c[:, 1] - G.B2) < 0.0125) & (c[:, 2] > 0.012) & (c[:, 2] < G.GAP - 0.012), "plytka",
                       np.where(c[:, 2] > G.GAP / 2, "gorny", "dolny"))
    elif "gorny" in bodies: lab = np.where(c[:, 2] > G.GAP / 2, "gorny", "dolny")
    else: lab = np.full(len(F), "plat")
    patches = {n: [tuple(map(tuple, V[F[i]])) for i in np.where(lab == n)[0]] for n in dict.fromkeys(lab)}
    G.write(HERE / case / "bryla.stl", patches)
    info[case] = dict(watertight=bool(um.is_watertight), volume_m3=float(um.volume), faces=int(len(F)),
                      patches={k: len(v) for k, v in patches.items()}, sum_volumes=float(sum(m.volume for m in ms.values())))
(HERE / "BRYLY_3D.json").write_text(json.dumps(info, indent=1)); print(json.dumps(info, indent=1))
