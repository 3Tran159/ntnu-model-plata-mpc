"""study.py - fala + sterowanie harmoniczne q(t) = K * alpha_w(t + phi/omega_e), q = theta (plat) lub delta (flap).
Wynik: wspolczynniki form kwadratowych sredniej mocy i amplitudy zespolone -> results.json"""
import numpy as np, json, sys, time
from uvm2d import Foil, Wave, combine, ramp, RHO

C, U, DEPTH, XREF = 1.19, 18.0, 2.0, 0.25 * 1.19
CLREF = 0.3

def amp(t, y, Om): return 2 * np.mean((y - y.mean()) * np.exp(-1j * Om * t))

def basis(lam, heading, H=0.10, N=None, nper=16, keepper=4, wake_waves=6.0, depth=DEPTH):
    wv = Wave(H, lam, U, depth, heading)
    if N is None:
        N = 40 if wv.Te / (C / 40 / U) < 800 else 20
    spp = int(round(wv.Te / (C / N / U))); dt = wv.Te / spp
    F = Foil(c=C, U=U, N=N, h=depth, dt=dt, wake_len=max(40 * C, wake_waves * U * wv.Te))
    ns, keep = nper * spp, keepper * spp
    aw = wv.A / U
    def cmd(ph):
        def f(t):
            r, rd = ramp(t, wv.Te); arg = wv.psi(XREF, t) - ph
            return r * aw * np.sin(arg), rd * aw * np.sin(arg) + r * aw * (-wv.ome) * np.cos(arg)
        return f
    def gust(x, t):
        r, _ = ramp(t, wv.Te); u, w = wv.uw(x, t); return r * u, r * w
    fW = F.simulate(ns, gust=gust, keep=keep)
    runs = dict(W=fW)
    for nm, kw in (('P', 'theta'), ('F', 'delta')):
        runs[nm + '1'] = F.simulate(ns, keep=keep, **{kw: cmd(0.0)})
        runs[nm + '2'] = F.simulate(ns, keep=keep, **{kw: cmd(np.pi / 2)})
    return F, wv, runs

def evaluate(F, wv, runs, var, K, phi, CL0=CLREF):
    f = combine([runs['W'], runs[var + '1'], runs[var + '2']], [1.0, K * np.cos(phi), K * np.sin(phi)])
    r = F.forces(f, F.steady(CL0))
    P = r['Pth'] if var == 'P' else r['Pde']
    return dict(PFx=U * r['Fx'].mean(), Pact=P.mean(), Pact_pos=np.maximum(P, 0).mean(), r=r, f=f)

def coefs(F, wv, runs, var):
    out = {}
    for key in ('PFx', 'Pact'):
        q0 = evaluate(F, wv, runs, var, 0, 0)[key]
        q1, q2, q3 = (evaluate(F, wv, runs, var, 1, p)[key] for p in (0, np.pi / 2, np.pi))
        d = 0.5 * (q1 + q3) - q0
        out[key] = dict(a=q0, b=0.5 * (q1 - q3), c=q2 - q0 - d, d=d)
    # amplitudy zespolone (wzgledem exp(i*Om*t)), afiniczne w CL0
    Om = abs(wv.ome); amps = {}
    for cl in (0.0, CLREF):
        m = F.steady(cl)
        A = {}
        for nm, co in (('W', (1, 0, 0)), ('1', (0, 1, 0)), ('2', (0, 0, 1))):
            f = combine([runs['W'], runs[var + '1'], runs[var + '2']], co)
            r = F.forces(f, m); t = r['t']
            M = r['Mp'] if var == 'P' else r['Mh']
            qd = f['thd'] if var == 'P' else f['ded']; q = f['th'] if var == 'P' else f['de']
            A[nm] = dict(CL=amp(t, r['CL'], Om), M=amp(t, M, Om), qd=amp(t, qd, Om), q=amp(t, q, Om), M0=M.mean(), CLm=r['CL'].mean())
        amps[cl] = A
    cz = lambda z: [float(np.real(z)), float(np.imag(z))]
    out['amp'] = {nm: dict(CL0=cz(amps[0.0][nm]['CL']), CL1=cz((amps[CLREF][nm]['CL'] - amps[0.0][nm]['CL']) / CLREF),
                           M0=cz(amps[0.0][nm]['M']), M1=cz((amps[CLREF][nm]['M'] - amps[0.0][nm]['M']) / CLREF),
                           qd=cz(amps[0.0][nm]['qd']), q=cz(amps[0.0][nm]['q'])) for nm in ('W', '1', '2')}
    out['Mmean_per_CL'] = float((amps[CLREF]['W']['M0'] - amps[0.0]['W']['M0']) / CLREF)
    return out

def opt(co):
    """min a + bX + cY + d(X^2+Y^2) dla sumy PFx+Pact"""
    a, b, c, d = (co['PFx'][k] + co['Pact'][k] for k in 'abcd')
    K = np.hypot(b, c) / (2 * d); phi = np.arctan2(-c, -b)
    return K, phi, a - (b * b + c * c) / (4 * d)

if __name__ == '__main__':
    res = dict(meta=dict(c=C, U=U, depth=DEPTH, H=0.10, xref_c=0.25, xp_c=0.25, xh_c=0.80, rho=RHO, CLref=CLREF), cases=[])
    lams = [5, 7.5, 10, 15, 20, 30, 40]
    for hd in (+1, -1):
        for lam in lams:
            t0 = time.time(); F, wv, runs = basis(lam, hd)
            case = dict(lam=lam, heading=hd, ome=wv.ome, Te=wv.Te, A=wv.A, alpha_w_deg=float(np.degrees(wv.A / U)),
                        kred=abs(wv.ome) * C / (2 * U))
            for var in 'PF':
                co = coefs(F, wv, runs, var); K, phi, pm = opt(co)
                e = evaluate(F, wv, runs, var, K, phi)
                co['opt'] = dict(K=float(K), phi_deg=float(np.degrees(phi) % 360), Pnet=float(pm), PFx=float(e['PFx']), Pact=float(e['Pact']),
                                 Pact_pos=float(e['Pact_pos']), check=float(e['PFx'] + e['Pact'] - pm))
                case[var] = co
            res['cases'].append(case)
            print(f"lam={lam:5} hd={hd:+d} kred={case['kred']:.3f} a_w={case['alpha_w_deg']:.4f}deg | fixed PFx={case['P']['PFx']['a']:8.3f} W/m |"
                  f" PLAT K={case['P']['opt']['K']:.3f} phi={case['P']['opt']['phi_deg']:6.1f} Pnet={case['P']['opt']['Pnet']:8.3f} (Pact {case['P']['opt']['Pact']:.2f}, +{case['P']['opt']['Pact_pos']:.2f}) |"
                  f" FLAP K={case['F']['opt']['K']:.3f} phi={case['F']['opt']['phi_deg']:6.1f} Pnet={case['F']['opt']['Pnet']:8.3f} (Pact {case['F']['opt']['Pact']:.2f}, +{case['F']['opt']['Pact_pos']:.2f}) | {time.time()-t0:.0f}s", flush=True)
    json.dump(res, open('results.json', 'w'), indent=1)
