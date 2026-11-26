# 20.11: seria jednego MPC (mpc_cel_bridge.py) w modelu, cel z'' RMS od 0 do maksa co 0,05 g, fala Godo (T 5 s) i fala T 4 s. Rdzen 22. Log: mpc_cel_seria.log, wynik: MPC_CEL_MODEL.json
# Model: fala mierzona przy krawedzi natarcia (MPC_PROBE_D = 0); w URANS sonda 3 m przed plata (MPC_PROBE_D = 3).
param([string]$Lista = '0,0.4905,0.981,1.4715,1.962,2.4525,2.943,3.4335,-1', [string]$Fale = '5.0:0.727,4.0:0.5', [string]$Per = '30')
$w = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort'
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
Set-Location $w
$env:MPC_CORE = '22'; $env:MPC_PROBE_D = '0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'; $env:MPC_TEST_PER = $Per
foreach ($fala in $Fale.Split(',')) {
    $env:MPC_TEST_T = $fala.Split(':')[0]; $env:MPC_TEST_A = $fala.Split(':')[1]
    foreach ($c in $Lista.Split(',')) {
        & $py -W ignore mpc_cel_bridge.py - $c 0.2 test 2>&1 | Select-String -Pattern '^\{|Error|Traceback' | Out-File -Append "$w\mpc_cel_seria.log" -Encoding utf8
    }
}
Add-Content "$w\mpc_cel_seria.log" 'KONIEC'
