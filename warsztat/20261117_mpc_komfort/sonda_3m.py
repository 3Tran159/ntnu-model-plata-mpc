# 17.11 15:15 (komentarz Julka: "niech ma np. 3 m przed platem sonde"): MPC w URANS dostaje wzniesienie fali z natywnej sondy 3 m przed LE
# (GODO_eta_x-3.0, ta sama budowa co GODO_eta_at_LE), a nie znad plata. Most przesuwa probke w czasie o czas dobiegu fali do LE (k d / we).
from pathlib import Path
j = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\makro_mpcf\GodoOversetRun.java"); s = j.read_text(encoding="utf-8")
a = 'String rq=String.format(Locale.ROOT,"%d %.6f %.8f %.8f %.8f %.8f %.8f %d",kTick,t,z,v,th,sd("wA",0),etaNow,free?1:0);'
b = ('String mpcP=cfg.getProperty("mpc_probe","");double etaReq=mpcP.isEmpty()?etaNow:rv(mpcP);if(!Double.isFinite(etaReq))etaReq=etaNow;   // 17.11: sonda przed platem\n'
     '       String rq=String.format(Locale.ROOT,"%d %.6f %.8f %.8f %.8f %.8f %.8f %d",kTick,t,z,v,th,sd("wA",0),etaReq,free?1:0);')
assert s.count(a) == 1; j.write_text(s.replace(a, b), encoding="utf-8")
p = Path(r"T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort\mpc_falt_bridge.py"); t = p.read_text(encoding="utf-8")
a1 = "CASE = None if sys.argv[1] == \"-\" else Path(sys.argv[1])\n"
b1 = a1 + "PROBE_D = float(os.environ.get(\"MPC_PROBE_D\", \"0\")); DT_PROBE = K * PROBE_D / OME     # sonda d przed LE: fala dochodzi do LE po k d / we (0,15 s przy 3 m)\n"
a2 = "        s.T.append(t); s.E.append(eta)\n"
b2 = "        s.T.append(t + DT_PROBE); s.E.append(eta)                    # probka z sondy = wzniesienie przy LE w chwili t + DT_PROBE\n"
a3 = '    log(f"start: W_A {MK.W_A}, KI {KI}, ome {OME:.4f}, H {br.H}")'
b3 = '    log(f"start: W_A {MK.W_A}, KI {KI}, ome {OME:.4f}, H {br.H}, sonda {PROBE_D} m przed LE (wyprzedzenie {DT_PROBE:.3f} s)")'
for x, y in ((a1, b1), (a2, b2), (a3, b3)):
    assert t.count(x) == 1, x[:40]; t = t.replace(x, y)
p.write_text(t, encoding="utf-8")
q = Path(r"T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\policy_queue14.ps1"); u = q.read_text(encoding="utf-8")
u = u.replace("'mpc_timeout_s=180')", "'mpc_timeout_s=180','wake_gauges=-3.0','mpc_probe=GODO_eta_x-3.0')")
u = u.replace("$bp = Start-Process", "$env:MPC_PROBE_D = '3.0'\n$bp = Start-Process")
assert "mpc_probe=GODO_eta_x-3.0" in u and "MPC_PROBE_D" in u
q.write_text(u, encoding="utf-8"); print("ok")
