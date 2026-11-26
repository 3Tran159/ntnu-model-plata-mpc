# 20.11 21:50 (Julek 21:46: "nie zmieniamy MPC ... przebiegi na S1-4 na takim samym zakresie ... dziwne ze nie osiagnal 0.000 g"): ten sam jeden MPC (mpc_cel_bridge.py, wypadkowa), BEZ ZMIAN.
# Widma S1-S4 seed 0, 300 s (okno 30-300 s), cele 0 ... 0,35 g + bez limitu (36 przypadkow) + 2 diagnostyki celu 0 na fali Godo: bez kosztu silownika (ACT_K 0) i W_A max 100.
# 6 robotnikow na rdzeniach 18-23. Wyniki: cel_widmo\ (poprzednie 90 s w cel_widmo_90s\), cel_reg\T5.0001_cel0.json, T5.0002_cel0.json. Log: cel_pula2_<k>.log
param([int]$K = 0)
$w = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort'
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
Set-Location $w
$jobs = @(@('diag', '5.0001', '0', 'ACT0'), @('diag', '5.0002', '0', 'WA100'))
foreach ($c in @('0','0.4905','0.981','1.4715','1.962','2.4525','2.943','3.4335','-1')) { foreach ($s in @('S1','S2','S3','S4')) { $jobs += ,@('sea', $s, $c, '') } }
$env:MPC_CORE = "$(18 + $K)"; $env:MPC_PROBE_D = '0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'; $env:MPC_WYP = '1'
for ($i = 0; $i -lt $jobs.Count; $i++) {
    if ($i % 6 -ne $K) { continue }
    $j = $jobs[$i]; $env:MPC_ACT_K = '57'; $env:MPC_WA_MAX = '20'
    if ($j[0] -eq 'diag') { $env:MPC_TEST_SEA = ''; $env:MPC_TEST_T = $j[1]; $env:MPC_TEST_A = '0.727'; $env:MPC_TEST_PER = '20'; if ($j[3] -eq 'ACT0') { $env:MPC_ACT_K = '0' } else { $env:MPC_WA_MAX = '100' } }
    else { if (Test-Path "$w\cel_widmo\$($j[1])_s0_cel$($j[2]).json") { continue }; $env:MPC_TEST_SEA = $j[1]; $env:MPC_TEST_SEED = '0'; $env:MPC_TEST_TSIM = '300' }
    Add-Content "$w\cel_pula2_$K.log" ((Get-Date -Format 'HH:mm:ss') + " start $($j -join ' ')")
    & $py -W ignore mpc_cel_bridge.py - $j[2] 0.2 test 2>&1 | Select-String -Pattern '^\{|Error|Traceback' | Out-File -Append "$w\cel_pula2_$K.log" -Encoding utf8
}
Add-Content "$w\cel_pula2_$K.log" ((Get-Date -Format 'HH:mm:ss') + ' KONIEC')
