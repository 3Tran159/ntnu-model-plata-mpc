# 23.11 22:10: blizniak modelu dla URANS OVS_CEL_005g_S1L_R10_90 - ta sama realizacja S1 (seed 0, 59 skladowych 2-7,5 s), plat 1,39 m pod powierzchnia, MPC startuje przy t 10 s, 65 s, cel 0,05 g. Ten sam MPC.
# Wynik: cel_widmo_zapis\S1_s0_cel0.4905_blizniakURANS.json + seria_zapis\S1_s0_cel0.4905_blizniakURANS.npy (okno t > 30 s jak w widmach; do porownania z URANS liczyc z serii w tym samym oknie co URANS).
$w = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort'; Set-Location $w
$env:MPC_CORE = '0'; $env:MPC_PROBE_D = '3.0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'; $env:MPC_WYP = '1'; $env:MPC_ACT_K = '57'; $env:MPC_WA_MAX = '20'
$env:MPC_TEST_SEA = 'S1'; $env:MPC_TEST_SEED = '0'; $env:MPC_TEST_TSIM = '65'; $env:MPC_TEST_DEPTH = '1.39'; $env:MPC_TEST_TRUNC = '1'; $env:MPC_TEST_REL = '10'; $env:MPC_TEST_TAG = '_blizniakURANS'; $env:MPC_TEST_FSOFF = ''
Add-Content "$w\blizniak_S1.log" ((Get-Date -Format 'HH:mm:ss') + ' start')
& 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe' -W ignore mpc_cel_bridge_zapis.py - 0.4905 0.2 test 2>&1 | Select-String -Pattern '^\{|Error|Traceback' | Out-File -Append "$w\blizniak_S1.log" -Encoding utf8
Add-Content "$w\blizniak_S1.log" ((Get-Date -Format 'HH:mm:ss') + ' KONIEC')
