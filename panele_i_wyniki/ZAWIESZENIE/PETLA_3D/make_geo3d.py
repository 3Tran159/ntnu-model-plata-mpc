"""Geometria 3D (polowa rozpietosci, symetria y = 0) dla petli platow: plat pojedynczy, dwuplat, petla, petla z przesunieciem.
Przekroj: ten sam NACA66-012 MOD co w 2D (REF npz, tylko odczyt). Bryly osobno (STL, jedna nazwa patcha na plik),
w STAR odejmowane od domeny operacja Subtract (bryly moga sie przenikac: plytka wchodzi w konce platow).
x z pradem, y rozpietosc, z w gore. Agent D, 15.11.2026.  usage: python make_geo3d.py"""
import json, math
from pathlib import Path
import numpy as np
import triangle

HERE = Path(__file__).parent
REF = Path(r"F:\ntnu\flap_control\exploration_lab\MINI_POC_2D_20261103\mini_vof_20261103\COMEBACK_20261104"
           r"\WALL_FUNCTIONS_AUDIT\ACTIVE_GAP25_PRISM_20261104\SEALED_SHARP_MATCHED_OUTER\plot_mesh.npz")
C_MINI = 1.19
B2 = 4.0                 # pol rozpietosci [m] (pelna 8 m, jak plat Godo)
ALPHA = math.radians(2.9)
GAP = 1.0

d = np.load(REF); xy = d["xy"]; adj = {}
for e in (d["main"], d["flap"]):
    for a, b in e:
        a, b = int(a), int(b); adj.setdefault(a, []).append(b); adj.setdefault(b, []).append(a)
start = next(iter(adj)); loop = [start]; prev = None
while True:
    nxt = [n for n in adj[loop[-1]] if n != prev][0]
    if nxt == start: break
    prev = loop[-1]; loop.append(nxt)
SEC = xy[loop] / C_MINI                       # cieciwa 1, LE (0,0)
if np.sum(SEC[:-1, 0] * SEC[1:, 1] - SEC[1:, 0] * SEC[:-1, 1]) < 0: SEC = SEC[::-1]   # przeciwnie do wskazowek zegara
import os
XCUT = float(os.environ.get('P3D_XCUT', 0.985))     # tepa krawedz splywu: obciecie przy 98,5 % cieciwy (ostra krawedz w 3D daje przecinajace sie scianki po remeshingu)
k = np.where(SEC[:, 0] > XCUT)[0]
if len(k):
    SEC = np.roll(SEC, -(k[-1] + 1), axis=0)                 # ciag punktow za XCUT na koniec listy
    SEC = SEC[SEC[:, 0] <= XCUT]                             # usun je; zamkniecie wielokata daje plaska krawedz splywu



def cap(poly2):
    t = triangle.triangulate({"vertices": poly2, "segments": np.array([[i, (i + 1) % len(poly2)] for i in range(len(poly2))])}, "p")
    assert len(t["vertices"]) == len(poly2), "triangulacja dodala punkty"
    return t["triangles"]


TRI_CAP = cap(SEC)


def body(P0, P1):
    """P0, P1: (n,3) dwa odpowiadajace sobie kontury; zwraca liste trojkatow zamknietej bryly"""
    n = len(P0); T = []
    for i in range(n):
        j = (i + 1) % n
        T += [(P0[i], P0[j], P1[j]), (P0[i], P1[j], P1[i])]
    for a, b, c in TRI_CAP:
        T.append((P0[a], P0[c], P0[b])); T.append((P1[a], P1[b], P1[c]))
    return T


def foil(c, x0, z0, y0=-0.05, y1=B2):
    xs = SEC[:, 0] * c; zs = SEC[:, 1] * c; xc = 0.25 * c
    x = x0 + xc + (xs - xc) * math.cos(ALPHA) + zs * math.sin(ALPHA)
    z = z0 - (xs - xc) * math.sin(ALPHA) + zs * math.cos(ALPHA)
    return body(np.column_stack([x, np.full_like(x, y1), z]), np.column_stack([x, np.full_like(x, y0), z]))


def plate(c, x_bot, x_top, yc=B2, z0=0.0, z1=GAP):
    xs = SEC[:, 0] * c; ts = SEC[:, 1] * c
    return body(np.column_stack([x_bot + xs, yc + ts, np.full_like(xs, z0)]), np.column_stack([x_top + xs, yc + ts, np.full_like(xs, z1)]))


def box(x0, x1, y0, y1, z0, z1):
    v = lambda x, y, z: np.array([x, y, z], float)
    q = lambda a, b, c_, d_: [(a, b, c_), (a, c_, d_)]
    return {"Inlet": q(v(x0, y0, z0), v(x0, y0, z1), v(x0, y1, z1), v(x0, y1, z0)),
            "Outlet": q(v(x1, y0, z0), v(x1, y1, z0), v(x1, y1, z1), v(x1, y0, z1)),
            "Symmetry": q(v(x0, y0, z0), v(x1, y0, z0), v(x1, y0, z1), v(x0, y0, z1)),
            "Side": q(v(x0, y1, z0), v(x0, y1, z1), v(x1, y1, z1), v(x1, y1, z0)),
            "Bottom": q(v(x0, y0, z0), v(x0, y1, z0), v(x1, y1, z0), v(x1, y0, z0)),
            "Top": q(v(x0, y0, z1), v(x1, y0, z1), v(x1, y1, z1), v(x0, y1, z1))}


def write(path, patches):
    with open(path, "w", newline="\n") as f:
        for name, tris in patches.items():
            f.write(f"solid {name}\n")
            for a, b, c in tris:
                n = np.cross(np.subtract(b, a), np.subtract(c, a)); n = n / (np.linalg.norm(n) + 1e-30)
                f.write("  facet normal %.9g %.9g %.9g\n    outer loop\n" % tuple(n))
                for p in (a, b, c): f.write("      vertex %.12g %.12g %.12g\n" % tuple(p))
                f.write("    endloop\n  endfacet\n")
            f.write(f"endsolid {name}\n")


CASES = {"P3D_jeden": {"plat": foil(0.312, 0.0, 0.5)},
         "P3D_dwuplat": {"gorny": foil(0.156, 0.0, GAP), "dolny": foil(0.156, 0.0, 0.0)},
         "P3D_petla": {"gorny": foil(0.156, 0.0, GAP), "dolny": foil(0.156, 0.0, 0.0), "plytka": plate(0.156, 0.0, 0.0)},
         "P3D_petla_s03": {"gorny": foil(0.156, 0.0, GAP), "dolny": foil(0.156, 0.3, 0.0), "plytka": plate(0.156, 0.3, 0.0)}}
info = {}
for case, bodies in CASES.items():
    cd = HERE / case; cd.mkdir(exist_ok=True)
    write(cd / "domena.stl", box(-8.0, 24.0, 0.0, 12.0, -8.0, 9.0))
    for name, tris in bodies.items(): write(cd / f"{name}.stl", {name: tris})
    info[case] = {"bryly": list(bodies), "trojkaty": {k: len(v) for k, v in bodies.items()}}
(HERE / "GEOMETRIA_3D.json").write_text(json.dumps(dict(info=info, pol_rozpietosci_m=B2, alpha_deg=2.9, odstep_m=GAP, punkty_przekroju=len(SEC)), indent=1))
print(json.dumps(info))
