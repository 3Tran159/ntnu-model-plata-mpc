# 17.11 16:00: pelne RLS na 41 wspolczynnikach ARX dryfowalo w zla strone (fala regularna = jedna czestosc, th/v/wf wspolliniowe w petli).
# Wersja 2: adaptujemy tylko 2 liczby: przesuniecie sily c0 i mnoznik czesci dynamicznej c1 (L = c0 + c1 * ARX_dyn) - dobrze uwarunkowane.
from pathlib import Path
f = Path(r"T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort\mpc_adapt_bridge.py"); s = f.read_text(encoding="utf-8")
old_init = s[s.index("        s.a0 = s.m[\"arx\"].copy()"):s.index("    def set_arx(s, a):")]
new_init = ('        s.a0 = s.m["arx"].copy(); s.ab = s.a0.copy(); s.ab[1:] *= BAD; s.c = np.array([s.ab[0], 1.0]); s.set_arx(s.cur())\n'
            '        s.P = np.diag([1000.0 ** 2, 0.3 ** 2]) / SIG ** 2                    # a priori: przesuniecie +-1000 N/m, mnoznik +-30 %\n'
            '        s.TH, s.V, s.WF = [], [], []; s.n_upd = 0; s.err2 = []\n\n'
            '    def cur(s):\n        a = s.ab.copy(); a[0] = s.c[0]; a[1:] *= s.c[1]; return a\n\n')
s = s.replace(old_init, new_init)
old_rls = s[s.index("    def rls(s, phi, y):"):s.index("    def step(s, seq")]
new_rls = ('    def rls(s, phi, y):\n'
           '        x = np.array([1.0, phi[1:] @ s.ab[1:]]); e = y - x @ s.c\n'
           '        Pp = s.P @ x; k = Pp / (LAM + x @ Pp); c = s.c + k * e; s.P = (s.P - np.outer(k, Pp)) / LAM\n'
           '        if not np.all(np.isfinite(c)) or not (0.5 <= c[1] <= 2.0):\n'
           '            FB.log(f"RLS: odrzucam krok (mnoznik {c[1]:.3f})"); return\n'
           '        s.c = c; s.m["arx"] = s.cur(); s.err2.append(e * e)\n\n')
s = s.replace(old_rls, new_rls)
s = s.replace('FB.log(f"RLS t {t:.2f}: suma dL/dth {a[1:1+NL].sum():.0f} (baza {s.a0[1:1+NL].sum():.0f}), suma dL/dwf {a[1+2*NL:].sum():.0f} (baza {s.a0[1+2*NL:].sum():.0f}), "',
              'FB.log(f"RLS t {t:.2f}: mnoznik sily dynamicznej {s.c[1]:.3f}, przesuniecie {s.c[0]-s.a0[0]:+.0f} N/m, suma dL/dth {a[1:1+NL].sum():.0f} (Faltinsen {s.a0[1:1+NL].sum():.0f}), "')
s = s.replace('dLdth_koniec=round(float(br.m["arx"][1:1 + NL].sum()))', 'mnoznik_koniec=round(float(br.c[1]), 3), dLdth_koniec=round(float(br.m["arx"][1:1 + NL].sum()))')
f.write_text(s, encoding="utf-8"); print("ok")
