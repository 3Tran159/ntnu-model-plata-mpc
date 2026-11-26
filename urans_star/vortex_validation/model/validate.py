import numpy as np
from scipy.special import hankel2, jv
from uvm2d import Foil, RHO

def C(k): return hankel2(1, k) / (hankel2(1, k) + 1j * hankel2(0, k))
def amp(t, y, om): return 2 * np.mean(y * np.exp(-1j * om * t))

c, U = 1.19, 18.0; b = c / 2
print("== stan ustalony ==")
for N in (25, 50):
    F = Foil(N=N, free_surface=False)
    g = np.linalg.solve(F.Abb, -U * np.ones(N)); print(N, "CL_alpha/2pi =", RHO*U*g.sum()/(0.5*RHO*U*U*c)/(2*np.pi))
    g = np.linalg.solve(F.Abb, -U * F.flap); print(N, "CL_delta =", RHO*U*g.sum()/(0.5*RHO*U*U*c), "(teoria 3.4551)")

for kr in (0.2, 0.456, 1.0):
    om = kr * U / b; T = 2 * np.pi / om
    N = 50; spp = int(round(T / (c / N / U))); dt = T / spp
    F = Foil(N=N, free_surface=False, dt=dt, wake_len=60 * c)
    nper = 14; ns = nper * spp; keep = 4 * spp
    a0 = np.radians(1.0); a = -0.5
    # pitch wokol c/4
    f = F.simulate(ns, theta=lambda t: (a0*np.cos(om*t), -a0*om*np.sin(om*t)), keep=keep)
    r = F.forces(f)
    al, ald, aldd = a0, 1j*om*a0, -om*om*a0
    Lt = np.pi*RHO*b*b*(U*ald - b*a*aldd) + 2*np.pi*RHO*U*b*C(kr)*(U*al + b*(0.5-a)*ald)
    Mt = np.pi*RHO*b*b*(-U*b*(0.5-a)*ald - b*b*(1/8+a*a)*aldd) + 2*np.pi*RHO*U*b*b*(a+0.5)*C(kr)*(U*al+b*(0.5-a)*ald)
    Ln, Mn = amp(r['t'], r['L'], om), amp(r['t'], r['Mp'], om)
    print(f"k={kr}: PITCH  |L| num/teor = {abs(Ln)/abs(Lt):.4f}, dfaza = {np.degrees(np.angle(Ln/Lt)):+.2f} deg;"
          f"  |M| = {abs(Mn)/abs(Mt):.4f}, dfaza = {np.degrees(np.angle(Mn/Mt)):+.2f} deg; "
          f"sr.Fx={r['Fx'].mean():.4e} N/m, sr.P_act={r['Pth'].mean():.4e} W/m, W/|G|^2={(r['Pth'].mean()+U*r['Fx'].mean())/abs(amp(r['t'],r['Gsum'],om))**2:.4f}")
    # plunge + ciag Garricka
    h0 = 0.01
    f = F.simulate(ns, heave_rate=lambda t: -h0*om*np.sin(om*t), keep=keep)
    r = F.forces(f)
    hd, hdd = 1j*om*h0, -om*om*h0
    Lt = np.pi*RHO*b*b*hdd + 2*np.pi*RHO*U*b*C(kr)*hd
    Ln = amp(r['t'], r['L'], om)
    Tg = np.pi*RHO*b*om**2*h0**2*abs(C(kr))**2
    print(f"k={kr}: PLUNGE |L| = {abs(Ln)/abs(Lt):.4f}, dfaza = {np.degrees(np.angle(Ln/Lt)):+.2f} deg; ciag/Garrick = {-r['Fx'].mean()/Tg:.4f}; W/|G|^2={(r['Ph'].mean()+U*r['Fx'].mean())/abs(amp(r['t'],r['Gsum'],om))**2:.4f}")
    f = F.simulate(ns, delta=lambda t: (a0*np.cos(om*t), -a0*om*np.sin(om*t)), keep=keep); r = F.forces(f)
    print(f"k={kr}: FLAP   sr.Fx={r['Fx'].mean():.4e}, sr.P_act={r['Pde'].mean():.4e}, W/|G|^2={(r['Pde'].mean()+U*r['Fx'].mean())/abs(amp(r['t'],r['Gsum'],om))**2:.4f}")
    # podmuch Searsa
    w0 = 0.05
    gust = lambda x, t: (0*x, w0*np.cos(om*(t - (x - b)/U)))
    f = F.simulate(ns, gust=gust, keep=keep); r = F.forces(f)
    S = (jv(0, kr) - 1j*jv(1, kr))*C(kr) + 1j*jv(1, kr)
    Lt = 2*np.pi*RHO*U*b*w0*S; Ln = amp(r['t'], r['L'], om)
    print(f"k={kr}: SEARS  |L| = {abs(Ln)/abs(Lt):.4f}, dfaza = {np.degrees(np.angle(Ln/Lt)):+.2f} deg")
