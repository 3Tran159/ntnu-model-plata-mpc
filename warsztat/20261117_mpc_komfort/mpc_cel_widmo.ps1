# 20.11 14:00 (Julek 13:55: "daj te przebiegi mpc tez na falach S1-4 na takim samym zakresie"): jeden MPC (mpc_cel_bridge.py), widmo S1-S4, seed 0, 180 s (okno 30-180 s),
# cele 0 ... 0,35 g co 0,05 g + bez limitu. Jeden proces na rdzen ($Rdzen), lista morz w $Morza. Wyniki: cel_widmo\<morze>_s0_cel<cel>.json, log: cel_widmo_<rdzen>.log
param([string]$Morza = 'S1', [string]$Rdzen = '18')
$w = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort'
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
Set-Location $w
$env:MPC_CORE = $Rdzen; $env:MPC_PROBE_D = '0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'; $env:MPC_TEST_SEED = '0'; $env:MPC_TEST_TSIM = '180'
foreach ($sea in $Morza.Split(',')) {
    $env:MPC_TEST_SEA = $sea
    foreach ($c in @('0','0.4905','0.981','1.4715','1.962','2.4525','2.943','3.4335','-1')) {
        if (Test-Path "$w\cel_widmo\${sea}_s0_cel$c.json") { continue }
        & $py -W ignore mpc_cel_bridge.py - $c 0.2 test 2>&1 | Select-String -Pattern '^\{|Error|Traceback' | Out-File -Append "$w\cel_widmo_$Rdzen.log" -Encoding utf8
    }
}
Add-Content "$w\cel_widmo_$Rdzen.log" 'KONIEC'
