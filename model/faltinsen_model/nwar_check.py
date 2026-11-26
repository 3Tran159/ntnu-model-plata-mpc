"""nwar_check.py - krok dodatkowy zlecenia C: czy staly dodatek oporu w fali (dCD ~ 0,0016, przypadek Godo, fit_polar.py) to to samo co F_rest z NWAR.
Dane NWAR (w URANS): NWAR_mech.csv = kopia H:\\NTNU_RESEARCH_ARCHIVE\\NWAR_onepage_v2_20261113\\mech.csv (tabela "Case matrix" z NWAR_onepage_v2.pdf):
  14 przypadkow fali regularnej z dziobu, plat nieruchomy, kat 0 deg, U = 18 m/s, c = 1,19 m, h = 2,0 m, pasek 0,02 m, woda spokojna Fx = 27,0 N, Fz = 1217 N,
  qS = 0,5 rho U^2 c 0,02 m = 3856 N.  dFx, dFz = srednia na fali - woda spokojna;  tilt = -mean(dFz alfa_eff);  rest = dFx - tilt.
W modelu B (ten sam solver co FaltinsenPlant: (6.180)+(6.182), pozioma predkosc fali, obraz (6.144), opor falowy (6.145)) liczone te same przypadki,
  te same definicje tilt i rest (alfa_eff = pionowa predkosc fali w 1/4 cieciwy / U, teoria liniowa).
Wynik: NWAR_CHECK.json, NWAR_CHECK.png"""
import csv, json, sys
from pathlib import Path
import numpy as np
HERE = Path(__file__).parent; sys.path.insert(0, str(HERE))
from uvm2d import Foil, G
from faltinsen_plant import Stepper
import faltinsen_eqs as FE
RHO, U, C, H0, SPAN, CL0, CD0 = 1000.0, 18.0, 1.19, 2.0, 0.02, 0.3157, 0.00700
QS = 0.5 * RHO * U * U * C * SPAN


def run(Hw, lam, N=20, dt=1e-3, nper=8, wave_u=True):
    k = 2 * np.pi / lam; om0 = np.sqrt(G * k); ome = om0 + k * U; Te = 2 * np.pi / ome; a = Hw / 2
    F = Foil(c=C, U=U, N=N, h=H0, dt=dt, wake_len=3 * U * Te, rho=RHO); q = 0.5 * RHO * U * U * C
    g1 = np.linalg.solve(F.Abb, -U * np.ones(N)); dcl = RHO * U * g1.sum() / q; th_m = CL0 / dcl
    S = Stepper(F, dict(theta0=th_m, G0=g1 * th_m, w0=F.Wvb @ (g1 * th_m), u0=F.Uvb @ (g1 * th_m)))
    n = int(round(nper * Te / dt)); t = (np.arange(n) + 1) * dt; Fz = np.zeros(n); Fx = np.zeros(n); al = np.zeros(n)
    A = a * om0 * np.exp(-k * H0)
    for i in range(n):
        gu = lambda x: (A * np.cos(k * x - ome * t[i]), A * np.sin(k * x - ome * t[i]))
        ug, wg = gu(F.xv); uc, wc = gu(F.xc)
        r = S.step(0.0, 0.0, 0.0, gust_c=wc, gust_v=(ug, wg), u_c=uc if wave_u else None, u_v=ug if wave_u else None)
        cl = CL0 + r["L_lin"] / q; h = max(0.05, H0 + a * np.cos(-ome * t[i]))
        cl *= float(FE.cl_ratio_high_fn(h, C) / FE.cl_ratio_high_fn(H0, C))
        fx = r["Fx"] + CD0 * q + float(FE.wave_resistance(FE.gamma_from_cl(cl, U, C), h, U) - FE.wave_resistance(FE.gamma_from_cl(CL0, U, C), H0, U))
        Fz[i] = cl * q * SPAN; Fx[i] = fx * SPAN; al[i] = gu(np.array([0.25 * C]))[1][0] / U
    w = t > t[-1] - 4 * Te; dFz = Fz[w] - CL0 * QS; z1 = 2 * np.mean(dFz * np.exp(-1j * ome * t[w])); za = 2 * np.mean(al[w] * np.exp(-1j * ome * t[w]))
    return dict(theta_a_deg=float(np.degrees(A / U)), sigma=float(ome * C / (2 * U)), dFx=float(Fx[w].mean() - CD0 * QS), dFz=float(dFz.mean()), Lamp=float(abs(z1)),
                lag_deg=float(np.degrees(np.angle(za / z1))), tilt=float(-np.mean(dFz * al[w])))


if __name__ == "__main__":
    rows = list(csv.DictReader(open(HERE / "NWAR_mech.csv"))); out = []
    for r in rows:
        Hw, lam = float(r["H"]), float(r["lam"]); m = run(Hw, lam); m["rest"] = m["dFx"] - m["tilt"]
        u = {k: float(r[k]) for k in ("dFx", "dFz", "Lamp", "tilt", "rest", "th_deg", "sig")}
        o = dict(case=r["case"], H_m=Hw, lambda_m=lam, theta_a_deg=u["th_deg"], sigma=u["sig"], URANS=u, model_B=m,
                 dCD_rest_URANS=u["rest"] / QS, dCD_URANS_minus_model=(u["dFx"] - m["dFx"]) / QS, Lamp_URANS_over_model=u["Lamp"] / m["Lamp"])
        out.append(o)
        print(f"{r['case']:5s} H {Hw:4.2f} lam {lam:4.0f} th_a {u['th_deg']:.2f} | URANS dFx {u['dFx']:6.2f} tilt {u['tilt']:6.2f} rest {u['rest']:+5.2f} | model dFx {m['dFx']:6.2f} tilt {m['tilt']:6.2f} rest {m['rest']:+5.2f} | "
              f"URANS-model dFx {u['dFx']-m['dFx']:+5.2f} N = dCD {o['dCD_URANS_minus_model']:+.5f} | dCD_rest {o['dCD_rest_URANS']:+.5f} | Lamp U/M {o['Lamp_URANS_over_model']:.3f} lag model {m['lag_deg']:.1f} | dFz U {u['dFz']:.1f} M {m['dFz']:.1f}", flush=True)
    (HERE / "NWAR_CHECK.json").write_text(json.dumps(dict(QS_N=QS, cases=out), indent=1))
