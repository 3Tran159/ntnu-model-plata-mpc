"""Przeliczenie modelu wirowego na przypadek Godo (c=0.312 m, U=12.35 m/s, zanurzenie 1.09 m), plat zamocowany w pionie."""
import numpy as np, json, time, study
from uvm2d import RHO, G
study.C = 0.312; study.U = 12.3466667; study.DEPTH = 1.09; study.XREF = 0.25 * 0.312; study.CLREF = 0.63
C, U, H = study.C, study.U, 1.5
lamT5 = G * 25 / (2 * np.pi)
res = dict(meta=dict(c=C, U=U, depth=1.09, H=H, xref_c=0.25, xp_c=0.25, xh_c=0.80, rho=RHO, CLref=0.63), cases=[])
for lam in (10, 15, 20, 30, round(lamT5, 2), 60):
    t0 = time.time(); F, wv, runs = study.basis(lam, 1, H=H, N=20, nper=14, keepper=4, wake_waves=5.0, depth=1.09)
    case = dict(lam=lam, heading=1, ome=wv.ome, Te=wv.Te, A=wv.A, alpha_w_deg=float(np.degrees(wv.A / U)), kred=abs(wv.ome) * C / (2 * U))
    for var in 'PF':
        co = study.coefs(F, wv, runs, var); K, phi, pm = study.opt(co)
        co['opt'] = dict(K=float(K), phi_deg=float(np.degrees(phi) % 360), Pnet=float(pm))
        case[var] = co
    res['cases'].append(case)
    print(f"lam={lam} Te={wv.Te:.3f} kred={case['kred']:.3f} aw={case['alpha_w_deg']:.2f} fixed={case['P']['PFx']['a']:.0f} W/m | P K={case['P']['opt']['K']:.2f} phi={case['P']['opt']['phi_deg']:.1f} Pnet={case['P']['opt']['Pnet']:.0f} | F K={case['F']['opt']['K']:.2f} phi={case['F']['opt']['phi_deg']:.1f} Pnet={case['F']['opt']['Pnet']:.0f} | {time.time()-t0:.0f}s", flush=True)
    if abs(lam - lamT5) < 0.1:
        Om = abs(wv.ome); base = study.evaluate(F, wv, runs, 'P', 0, 0, 0.63)
        print("  przypadki walidacyjne (plat, CL0=0.63):")
        for lab, k, p in (('V0 staly', 0, 0), ('V1 K=0.5 w fazie', 0.5, 0), ('V2 K=1 w fazie', 1, 0), ('V3 7.5deg w fazie', 7.5 / case['alpha_w_deg'], 0), ('V4 K=1 przeciwfaza', 1, np.pi)):
            e = study.evaluate(F, wv, runs, 'P', k, p, 0.63); r = e['r']; f = e['f']
            print(f"   {lab:20} amp={np.degrees(np.ptp(f['th'])/2):.2f}deg rate={np.degrees(np.abs(f['thd']).max()):.1f}deg/s Fx={r['Fx'].mean():8.1f} N/m dCL={abs(study.amp(r['t'],r['CL'],Om)):.3f} Mamp={np.ptp(r['Mp'])/2:.1f} Nm/m Pact={np.maximum(r['Pth'],0).mean():.1f} W/m zysk={-(e['PFx']+e['Pact']-base['PFx']):+.0f} W/m")
json.dump(res, open('results_godo.json', 'w'), indent=1)
