"""
uvm2d.py - 2D niestacjonarny model wirowy plata (lumped-vortex + slad), liniowy.
Plat na z=0, x w dol strumienia, krawedz natarcia x=0. Wir zwiazany w 1/4 panelu,
kolokacja w 3/4. Slad plaski na stalej siatce (krok U*dt). Swobodna powierzchnia:
granica wysokich liczb Froude'a (phi=0) -> odbicie lustrzane o tym samym znaku cyrkulacji.
Znaki: Gamma>0 daje sile nosna w gore; theta>0 nos do gory; delta>0 krawedz splywu w dol.
Jednostki SI, sily na 1 m rozpietosci.
"""
import numpy as np

RHO = 1025.0
G = 9.81


class Wave:
    """Fala Airy'ego na glebokiej wodzie w ukladzie plata. heading=+1: fala z dziobu."""
    def __init__(s, H=0.10, lam=10.0, U=18.0, depth=2.0, heading=+1):
        s.a = H / 2; s.k = 2 * np.pi / lam; s.om = np.sqrt(G * s.k)
        s.sg = heading; s.ome = s.om + s.sg * s.k * U      # czestosc spotkaniowa (ze znakiem)
        s.A = s.a * s.om * np.exp(-s.k * depth)            # amplituda predkosci orbitalnej
        s.Te = 2 * np.pi / abs(s.ome)

    def psi(s, x, t):
        return s.sg * s.k * x - s.ome * t

    def uw(s, x, t):
        p = s.psi(x, t)
        return s.sg * s.A * np.cos(p), s.A * np.sin(p)


class Foil:
    def __init__(s, c=1.19, U=18.0, N=50, xp=0.25, xh=0.80, h=2.0, free_surface=True,
                 dt=None, wake_len=40 * 1.19, rho=RHO):
        s.c, s.U, s.N, s.h, s.rho, s.fs = c, U, N, h, rho, free_surface
        s.dx = c / N
        s.dt = s.dx / U if dt is None else dt
        xe = np.linspace(0, c, N + 1)
        s.xv = xe[:-1] + 0.25 * s.dx; s.xc = xe[:-1] + 0.75 * s.dx; s.xm = xe[:-1] + 0.5 * s.dx
        s.xp = xp * c; s.xh = xh * c
        s.flap = (s.xm > s.xh).astype(float)
        D = U * s.dt
        s.Nw = int(np.ceil(wake_len / D))
        s.xw = c + (0.25 + np.arange(s.Nw)) * D
        # macierze wplywu
        s.Abb = s.Kw(s.xc, s.xv); s.Abw = s.Kw(s.xc, s.xw)
        M = np.zeros((N + 1, N + 1)); M[:N, :N] = s.Abb; M[:N, N] = s.Abw[:, 0]; M[N, :] = 1.0
        s.Minv = np.linalg.inv(M)
        s.Wvb = s.Kw(s.xv, s.xv, direct=False); s.Wvw = s.Kw(s.xv, s.xw)
        s.Uvb = s.Ku(s.xv, s.xv); s.Uvw = s.Ku(s.xv, s.xw)

    def Kw(s, xi, xj, direct=True):
        d = xi[:, None] - xj[None, :]
        K = np.zeros_like(d)
        if direct:
            K += -1.0 / (2 * np.pi * d)
        if s.fs:
            K += -d / (2 * np.pi * (d ** 2 + 4 * s.h ** 2))
        return K

    def Ku(s, xi, xj):
        d = xi[:, None] - xj[None, :]
        if not s.fs:
            return np.zeros_like(d)
        return -2 * s.h / (2 * np.pi * (d ** 2 + 4 * s.h ** 2))

    def steady(s, CL0):
        """Stan sredni: rozklad Gamma0 dajacy zadane CL0 (kat theta0)."""
        g1 = np.linalg.solve(s.Abb, -s.U * np.ones(s.N))          # na 1 rad
        a = s.rho * s.U * g1.sum(); b = s.rho * (s.Uvb @ g1) @ g1
        Lt = CL0 * 0.5 * s.rho * s.U ** 2 * s.c
        th = Lt / a if abs(b) < 1e-12 else (-a + np.sqrt(a * a + 4 * b * Lt)) / (2 * b)
        g0 = g1 * th
        return dict(theta0=th, G0=g0, w0=s.Wvb @ g0, u0=s.Uvb @ g0)

    def simulate(s, nsteps, theta=None, delta=None, heave_rate=None, gust=None, keep=None):
        """Odpowiedz zaburzeniowa (bez stanu sredniego). theta/delta: f(t)->(q,qdot);
        heave_rate: f(t)->hdot (w dol +); gust: f(x,t)->(u,w). Zwraca pola z ostatnich `keep` krokow."""
        N = s.N; z = lambda t: (0.0, 0.0)
        theta = theta or z; delta = delta or z
        keep = keep or nsteps
        gw = np.zeros(s.Nw); Gprev = 0.0
        ph = np.zeros((3, N))
        out = {k: np.zeros((keep, N)) for k in ('G', 'w', 'u', 'Nu', 'wb')}
        sc = {k: np.zeros(keep) for k in ('t', 'th', 'thd', 'de', 'ded', 'hd')}
        for n in range(nsteps):
            t = (n + 1) * s.dt
            th, thd = theta(t); de, ded = delta(t)
            hd = heave_rate(t) if heave_rate else 0.0
            rhs = -s.U * th - thd * (s.xc - s.xp) - (s.U * de + ded * (s.xc - s.xh)) * s.flap - hd
            if gust:
                rhs = rhs - gust(s.xc, t)[1]
            gw[1:] = gw[:-1]; gw[0] = 0.0
            b = np.empty(N + 1); b[:N] = rhs - s.Abw @ gw; b[N] = Gprev
            sol = s.Minv @ b
            Gb = sol[:N]; gw[0] = sol[N]; Gprev = Gb.sum()
            ph[2] = ph[1]; ph[1] = ph[0]; ph[0] = np.cumsum(Gb)
            dphi = (3 * ph[0] - 4 * ph[1] + ph[2]) / (2 * s.dt) if n >= 2 else (ph[0] - ph[1]) / s.dt
            i = n - (nsteps - keep)
            if i >= 0:
                w = s.Wvb @ Gb + s.Wvw @ gw; u = s.Uvb @ Gb + s.Uvw @ gw
                if gust:
                    ug, wg = gust(s.xv, t); u = u + ug; w = w + wg
                out['wb'][i] = hd + thd * (s.xv - s.xp) + ded * (s.xv - s.xh) * s.flap; sc['hd'][i] = hd
                out['G'][i] = Gb; out['w'][i] = w; out['u'][i] = u; out['Nu'][i] = s.rho * s.dx * dphi
                sc['t'][i] = t; sc['th'][i] = th; sc['thd'][i] = thd; sc['de'][i] = de; sc['ded'][i] = ded
        out.update(sc)
        return out

    def forces(s, f, mean=None):
        """Sily z pol (liniowych) + stan sredni. Zwraca slownik szeregow czasowych."""
        N = s.N
        m = mean or dict(theta0=0.0, G0=np.zeros(N), w0=np.zeros(N), u0=np.zeros(N))
        Gt = m['G0'] + f['G']; w = m['w0'] + f['w'] + f['wb'];  # w wzgledem wiru (ruch plata)
        u = m['u0'] + f['u']
        Lc = s.rho * (s.U + u) * Gt
        Nu = f['Nu']
        L = Lc.sum(1) + Nu.sum(1)
        slope = (m['theta0'] + f['th'])[:, None] + f['de'][:, None] * s.flap[None, :]
        Fx = -s.rho * (Gt * w).sum(1) + (Nu * slope).sum(1)
        Mp = -(Lc * (s.xv - s.xp)).sum(1) - (Nu * (s.xm - s.xp)).sum(1)
        Mh = -(Lc * (s.xv - s.xh) * s.flap).sum(1) - (Nu * (s.xm - s.xh) * s.flap).sum(1)
        Pth = -Mp * f['thd']; Pde = -Mh * f['ded']
        return dict(t=f['t'], Ph=L * f['hd'], Gsum=f['G'].sum(1), L=L, Fx=Fx, Mp=Mp, Mh=Mh, Pth=Pth, Pde=Pde,
                    CL=L / (0.5 * s.rho * s.U ** 2 * s.c))


def combine(fields, coefs):
    """Superpozycja liniowa pol z kilku przebiegow."""
    out = {}
    for k in fields[0]:
        if k == 't':
            out[k] = fields[0][k]
        else:
            out[k] = sum(c * f[k] for c, f in zip(coefs, fields))
    return out


def ramp(t, T):
    """Gladkie narastanie 0->1 w czasie T; zwraca (r, rdot)."""
    if t >= T:
        return 1.0, 0.0
    x = t / T
    return 0.5 * (1 - np.cos(np.pi * x)), 0.5 * np.pi / T * np.sin(np.pi * x)
