# 23.11 13:20: H 2 m, 0,05 g jeszcze raz (bazowy model, ten sam MPC) z zapisem kata plata i Fx_pot (ciag z teorii wirowej) -> czy nadwyzka to praca serwa (ciag z machania).
$w = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort'
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
Set-Location $w
$jobs = @(@('5.0014', '1.0', 'H2m z katem'), @('5.0015', '0.0001', 'spokojna z katem'))
$env:MPC_CORE = '0'; $env:MPC_PROBE_D = '0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'; $env:MPC_WYP = '1'; $env:MPC_ACT_K = '57'; $env:MPC_WA_MAX = '20'; $env:MPC_TEST_SEA = ''; $env:MPC_TEST_OKNO = '20'; $env:MPC_TEST_PER = '31'; $env:MPC_TEST_FSOFF = ''
foreach ($j in $jobs) {
    $env:MPC_TEST_T = $j[0]; $env:MPC_TEST_A = $j[1]
    Add-Content "$w\diag_H2m2.log" ((Get-Date -Format 'HH:mm:ss') + " start $($j[2])")
    $p = Start-Process -FilePath $py -ArgumentList '-W','ignore','mpc_cel_bridge_zapis.py','-','0.4905','0.2','test' -NoNewWindow -PassThru -RedirectStandardOutput "$w\diag_H2m2.out" -RedirectStandardError "$w\diag_H2m2.err"
    $p.WaitForExit()
    Get-Content "$w\diag_H2m2.err" | Select-String -Pattern 'Error|Traceback' | Out-File -Append "$w\diag_H2m2.log" -Encoding utf8
}
Add-Content "$w\diag_H2m2.log" ((Get-Date -Format 'HH:mm:ss') + ' KONIEC')
