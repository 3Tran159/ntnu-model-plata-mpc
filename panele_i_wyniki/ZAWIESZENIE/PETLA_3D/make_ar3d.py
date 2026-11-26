"""Krepe platy: ta sama powierzchnia planu co plat Godo (8 m x 0,312 m = 2,496 m2), wydluzenie AR 8 i 4,
jeden plat vs petla (2 platy po pol cieciwy, odstep 1 m, plytka na koncu). Geometria + suma boolowska jak w make_geo3d/make_union3d.
Polowa rozpietosci, symetria y = 0. Agent D, 15.11.2026."""
import json, math
from pathlib import Path
import numpy as np, trimesh, manifold3d as mf
import make_geo3d as G
HERE = Path(__file__).parent; S_FULL = 8.0 * 0.312; GAP = 1.0


def to_mesh(tris):
    v = np.array(tris).reshape(-1, 3); m = trimesh.Trimesh(v, np.arange(len(v)).reshape(-1, 3), process=True)
    m.merge_vertices(); m.update_faces(m.nondegenerate_faces())
    if m.volume < 0: m.invert()
    assert m.is_watertight; return m


def man(m): return mf.Manifold(mf.Mesh(vert_properties=np.asarray(m.vertices, np.float32), tri_verts=np.asarray(m.faces, np.uint32)))


info = {}
for ar in (8, 4):
    b = math.sqrt(ar * S_FULL); h = b / 2; c = S_FULL / b
    defs = {f"P3D_AR{ar}_jeden": {"plat": G.foil(c, 0.0, 0.5, y1=h)},
            f"P3D_AR{ar}_petla": {"gorny": G.foil(c / 2, 0.0, GAP, y1=h), "dolny": G.foil(c / 2, 0.0, 0.0, y1=h), "plytka": G.plate(c / 2, 0.0, 0.0, yc=h)}}
    for case, bodies in defs.items():
        cd = HERE / case; cd.mkdir(exist_ok=True)
        G.write(cd / "domena.stl", G.box(-8.0, 24.0, 0.0, 12.0, -8.0, 9.0))
        u = None
        for m in (to_mesh(t) for t in bodies.values()): u = man(m) if u is None else u + man(m)
        o = u.to_mesh(); V = np.asarray(o.vert_properties)[:, :3].astype(float); F = np.asarray(o.tri_verts); cc = trimesh.Trimesh(V, F, process=False).triangles_center
        if "plytka" in bodies:
            lab = np.where((np.abs(cc[:, 1] - h) < 0.06 * c) & (cc[:, 2] > 0.04 * c) & (cc[:, 2] < GAP - 0.04 * c), "plytka", np.where(cc[:, 2] > GAP / 2, "gorny", "dolny"))
        else: lab = np.full(len(F), "plat")
        G.write(cd / "bryla.stl", {n: [tuple(map(tuple, V[F[i]])) for i in np.where(lab == n)[0]] for n in dict.fromkeys(lab)})
        info[case] = dict(AR=ar, rozpietosc_m=b, pol_rozp_m=h, cieciwa_m=c if "jeden" in case else c / 2, faces=int(len(F)),
                          watertight=bool(trimesh.Trimesh(V, F).is_watertight), patches={k: int((lab == k).sum()) for k in dict.fromkeys(lab)})
(HERE / "GEOMETRIA_AR.json").write_text(json.dumps(info, indent=1)); print(json.dumps(info, indent=1))
