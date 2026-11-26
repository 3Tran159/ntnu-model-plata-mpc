# 20.11 14:25: pula zadan jednego MPC z kryterium na WYPADKOWEJ (mpc_cel_bridge.py, MPC_WYP=1). 6 robotnikow na rdzeniach 18-23, robotnik k bierze zadania i % 6 == k.
# Fale regularne T5 (Godo) i T4: 20 okresow (okno ostatnie 8). Widma S1-S4 seed 0: 90 s (okno 30-90 s - krotkie, pierwszy przeglad). Cele wypadkowej 0 ... 0,35 g + bez limitu.
# Wyniki: MPC_CEL_MODEL.json (fale regularne - zapis z blokada), cel_widmo\*.json. Log: cel_pula_<k>.log. Uruchom: -K 0..5
param([int]$K = 0)
$w = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort'
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
Set-Location $w
$cele = @('0','0.4905','0.981','1.4715','1.962','2.4525','2.943','3.4335','-1')
$jobs = @()
foreach ($c in $cele) { foreach ($f in @('5.0:0.727','4.0:0.5')) { $jobs += ,@('reg', $f, $c) } }
foreach ($c in $cele) { foreach ($s in @('S1','S2','S3','S4')) { $jobs += ,@('sea', $s, $c) } }
$env:MPC_CORE = "$(18 + $K)"; $env:MPC_PROBE_D = '0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'; $env:MPC_WYP = '1'
for ($i = 0; $i -lt $jobs.Count; $i++) {
    if ($i % 6 -ne $K) { continue }
    $j = $jobs[$i]
    if ($j[0] -eq 'reg') { $env:MPC_TEST_SEA = ''; $env:MPC_TEST_T = $j[1].Split(':')[0]; $env:MPC_TEST_A = $j[1].Split(':')[1]; $env:MPC_TEST_PER = '20' }
    else { if (Test-Path "$w\cel_widmo\$($j[1])_s0_cel$($j[2]).json") { continue }; $env:MPC_TEST_SEA = $j[1]; $env:MPC_TEST_SEED = '0'; $env:MPC_TEST_TSIM = '90' }
    Add-Content "$w\cel_pula_$K.log" ((Get-Date -Format 'HH:mm:ss') + " start $($j -join ' ')")
    & $py -W ignore mpc_cel_bridge.py - $j[2] 0.2 test 2>&1 | Select-String -Pattern '^\{|Error|Traceback' | Out-File -Append "$w\cel_pula_$K.log" -Encoding utf8
}
Add-Content "$w\cel_pula_$K.log" ((Get-Date -Format 'HH:mm:ss') + ' KONIEC')
