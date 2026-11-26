"""greenfs.py - 2D funkcja Greena powierzchni swobodnej (liniowa, skonczona liczba Froude'a) dla wiru pod powierzchnia - jak modul
"Green Function part" w NDLL Godø (tam 3D linie wirowe, tablicowane po predkosci i zanurzeniu), tu wersja 2D, quasi-stacjonarna.

Wir o cyrkulacji Gamma na glebokosci h, przeplyw U, warunek U^2 u_x + g w = 0 na y = 0, fale za wirem (warunek radiacji).
Predkosc indukowana na wirze przez powierzchnie = [czesc Fn->inf (lustro, juz jest w modelu wirowym)] + [czesc falowa].
Z twierdzenia Kutty-Zukowskiego:
  opor falowy     D_w = rho * Gamma * w_fs = rho g Gamma^2 / U^2 * exp(-2 g h / U^2)   (sprawdzone numerycznie z calka Fouriera: zgodnosc < 0,1 %)
  zmiana sily nosnej dL = rho * Gamma * (u_fs - u_inf) ~ 0,2 % L przy h = 1,09 m (pomijalna)
W modelu (opcja Plant.fs_wave): Fx += D_w(Gamma(t), h(t)) - D_w(Gamma_ref, DEPTH)   (stala czesc siedzi juz w CD0 dopasowanym do URANS przy h = 1,09 m)
"""
import numpy as np

G = 9.81


def wave_drag(Gamma, h, U, rho=1000.0):
    """opor falowy 2D wiru [N/m] (Lamb / Wehausen-Laitone), h > 0 zanurzenie wiru"""
    return rho * G * Gamma * Gamma / (U * U) * np.exp(-2.0 * G * np.maximum(h, 0.0) / (U * U))


def induced_numeric(h, U, Gamma=1.0, gg=G, n=600000):
    """kontrola: predkosc (u, w) indukowana na wirze przez powierzchnie swobodna, calka Fouriera z tlumieniem Rayleigha"""
    nu = gg / U ** 2; mu = 1e-3 * nu
    ks = np.concatenate([np.linspace(1e-8, nu * 0.9, 20000), np.linspace(nu * 0.9, nu * 1.1, 400001), np.linspace(nu * 1.1, 60 / h, 200000)])
    def A(k):
        uv = -(Gamma / 2) * np.exp(-abs(k) * h); wv = -1j * (Gamma / 2) * np.sign(k) * np.exp(-abs(k) * h)
        return -(U ** 2 * 1j * k * uv + gg * wv) / (abs(k) * (gg - U ** 2 * abs(k)) + 1j * mu * U ** 2 * k)
    fu = lambda k: 1j * k * A(k) * np.exp(-abs(k) * h); fw = lambda k: abs(k) * A(k) * np.exp(-abs(k) * h)
    return (np.trapezoid(fu(ks) + fu(-ks), ks) / (2 * np.pi)).real, (np.trapezoid(fw(ks) + fw(-ks), ks) / (2 * np.pi)).real


if __name__ == "__main__":
    U = 12.3466667
    for h in (0.312, 0.6, 1.09, 1.39, 1.69):
        u, w = induced_numeric(h, U)
        print(f"h {h:4.2f} m: rho*w (Gamma=1) = {1000*w:7.3f} N/m, wzor {wave_drag(1.0, h, U):7.3f} N/m")
    Gam = 0.5 * U * 0.312 * 0.642
    for z in (0.0, -0.3, -0.6):
        print(f"plat z = {z:+.1f} m (h = {1.09 - z:.2f} m): D_w = {wave_drag(Gam, 1.09 - z, U):6.1f} N/m = {wave_drag(Gam, 1.09 - z, U) * U * 0.02:5.2f} W/pasek")
