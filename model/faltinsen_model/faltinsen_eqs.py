"""faltinsen_eqs.py - wzory zamkniete z: O. M. Faltinsen, Hydrodynamics of High-Speed Marine Vehicles, Cambridge 2005, rozdz. 6.
Kazda funkcja = jedno rownanie ksiazki (numer i strona w opisie). Jednostki SI, sily 2D na 1 m rozpietosci.
Niczego tu nie dopasowano do URANS."""
import numpy as np
from scipy.special import hankel2, ellipk, ellipe

G = 9.81


def fn_h(U, h):
    """(6.139) s.199: liczba Froude'a zanurzenia Fn_h = U / sqrt(g h)"""
    return U / np.sqrt(G * h)


def biplane_valid(U, h, c):
    """warunek stosowania (6.144), s.199-200: Fn_h > 10 / sqrt(h/c)"""
    return fn_h(U, h) > 10.0 / np.sqrt(h / c)


def cl_ratio_high_fn(h, c):
    """(6.144) s.200: CL(h/c) / CL(nieskonczona glebia) = (1 + 16 (h/c)^2) / (2 + 16 (h/c)^2), Fn_h duze (phi = 0 na powierzchni)"""
    r = 16.0 * (np.asarray(h, float) / c) ** 2
    return (1.0 + r) / (2.0 + r)


def cl_ratio_low_fn(h, c):
    """(6.143) s.200: CL(h/c) / CL(inf) = 1 + (1/16) (c/h)^2, Fn_h -> 0 (sztywna sciana); tylko do kontroli"""
    return 1.0 + (c / np.asarray(h, float)) ** 2 / 16.0


def wave_resistance(Gamma, h, U, rho=1000.0):
    """(6.145) s.200: opor falowy 2D od sily nosnej R_W = rho g Gamma^2 / U^2 * exp(-2 / Fn_h^2)  [N/m]"""
    h = np.maximum(h, 0.0)
    return rho * G * Gamma ** 2 / U ** 2 * np.exp(-2.0 * G * h / U ** 2)


def gamma_from_cl(CL, U, c):
    """(6.147) s.201: CL^2 = Gamma^2 / (0.25 U^2 c^2)  ->  |Gamma| = 0.5 U c CL"""
    return 0.5 * U * c * CL


def far_wave_amplitude(CL, c, h, U):
    """(6.169) s.205: fala za platem zeta = -CL c exp(-g h / U^2) sin(g x / U^2); zwraca amplitude [m] i dlugosc fali (6.140) [m]"""
    return CL * c * np.exp(-G * h / U ** 2), 2 * np.pi * U ** 2 / G


def theodorsen(kf):
    """(6.189) s.211: C(kf) = H1(2)(kf) / (H1(2)(kf) + i H0(2)(kf)),  kf = omega c / (2 U)  (6.188)"""
    kf = np.asarray(kf, float)
    return hankel2(1, kf) / (hankel2(1, kf) + 1j * hankel2(0, kf))


def lift_theodorsen(h0, d0, om, U, c, rho=1000.0):
    """(6.187) s.211: zespolona amplituda sily nosnej plaskiego plata, nurzanie h = Re{h0 e^{i om t}} (srodek cieciwy, + w gore),
    kat delta = Re{d0 e^{i om t}}, ugiecie linii szkieletowej eta = h - delta x (obrot wokol srodka cieciwy):
    L = -rho 0.25 pi c^2 (h'' - U delta') - rho pi U c C(kf) (h' - U delta - 0.25 c delta')"""
    kf = om * c / (2 * U); C = theodorsen(kf); io = 1j * om
    return -rho * 0.25 * np.pi * c ** 2 * (io * io * h0 - U * io * d0) - rho * np.pi * U * c * C * (io * h0 - U * d0 - 0.25 * c * io * d0)


def encounter(om0, U):
    """(6.199) s.213: omega_e = omega_0 + omega_0^2 U / g (fala z dziobu);  k = omega_0^2 / g"""
    return om0 + om0 ** 2 * U / G, om0 ** 2 / G


def wave_w(om0, zeta_a, h):
    """(6.198)/(6.200) s.213: amplituda pionowej predkosci fali na glebokosci h: omega_0 zeta_a exp(-k h)"""
    return om0 * zeta_a * np.exp(-om0 ** 2 / G * h)


def froude_kriloff(area, om0, zeta_a, h, rho=1000.0):
    """(6.202) s.213: amplituda sily Froude'a-Kryłowa F = rho Omega omega_0^2 zeta_a exp(-k h)  (Omega = pole przekroju na 1 m)"""
    return rho * area * om0 ** 2 * zeta_a * np.exp(-om0 ** 2 / G * h)


def cl_lifting_line(alpha, AR):
    """(6.130) s.197: plat eliptyczny CL = 2 pi alpha / (1 + 2 / Lambda)"""
    return 2 * np.pi * alpha / (1.0 + 2.0 / AR)


def cd_induced(CL, AR):
    """(6.138) s.198: CD = CL^2 / (pi Lambda)"""
    return CL ** 2 / (np.pi * AR)


def sigma_fs(h, s):
    """(6.152) s.202: sigma(lambda), lambda = 2 h / s (s = rozpietosc)"""
    lam = 2.0 * h / s; m = 1.0 / (1.0 + lam * lam)        # scipy: parametr m = k^2
    return 1.0 - 4.0 / np.pi * lam * np.sqrt(1 + lam * lam) * (ellipk(m) - ellipe(m))


def cd_induced_fs(CL, AR, h, s):
    """(6.151) s.202: CD / CL^2 = 1/(pi Lambda) + sigma(lambda)/(pi Lambda), Fn_h -> inf (plat 3D pod powierzchnia swobodna)"""
    return CL ** 2 * (1.0 + sigma_fs(h, s)) / (np.pi * AR)
