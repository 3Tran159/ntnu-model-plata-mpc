# 23.11 13:10 (Julek 12:55: "znajdz sytuacje co obali nasz wzor"): rozbior przekroczenia T 5 s H 2 m, 0,05 g (zysk 10,4 W, sufit 5,5 W).
# Ten sam MPC. Wylaczane poprawki MODELU (nie MPC): fs_lift (CL x funkcja chwilowego zanurzenia, ciag z pochylenia liczony bez niej) i fs_wave (opor falowy od chwilowego zanurzenia).
# Kazdy wariant: fala H 2 m i woda spokojna (A 1e-4) w tym samym wariancie -> zysk bez mieszania odniesien. Rdzen 0. Wyniki: cel_reg_zapis\T5.00xx_cel0.4905.json, log diag_H2m.log
$w = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort'
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
Set-Location $w
$jobs = @(@('5.0006', '1.0', '', 'bazowy H2m (kontrola)'), @('5.0007', '0.0001', '', 'bazowy spokojna'),
          @('5.0008', '1.0', 'fs_lift', 'bez fs_lift H2m'), @('5.0009', '0.0001', 'fs_lift', 'bez fs_lift spokojna'),
          @('5.0010', '1.0', 'fs_wave', 'bez fs_wave H2m'), @('5.0011', '0.0001', 'fs_wave', 'bez fs_wave spokojna'),
          @('5.0012', '1.0', 'fs_lift,fs_wave', 'bez obu H2m'), @('5.0013', '0.0001', 'fs_lift,fs_wave', 'bez obu spokojna'))
$env:MPC_CORE = '0'; $env:MPC_PROBE_D = '0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'; $env:MPC_WYP = '1'; $env:MPC_ACT_K = '57'; $env:MPC_WA_MAX = '20'; $env:MPC_TEST_SEA = ''; $env:MPC_TEST_OKNO = '20'; $env:MPC_TEST_PER = '31'
foreach ($j in $jobs) {
    "T$([double]$j[0])_cel0.4905 = $($j[3]) (FSOFF '$($j[2])')" | Add-Content "$w\diag_H2m_mapa.txt"
    if (Test-Path "$w\cel_reg_zapis\T$([double]$j[0])_cel0.4905.json") { continue }
    $env:MPC_TEST_T = $j[0]; $env:MPC_TEST_A = $j[1]; $env:MPC_TEST_FSOFF = $j[2]
    Add-Content "$w\diag_H2m.log" ((Get-Date -Format 'HH:mm:ss') + " start $($j[3])")
    $p = Start-Process -FilePath $py -ArgumentList '-W','ignore','mpc_cel_bridge_zapis.py','-','0.4905','0.2','test' -NoNewWindow -PassThru -RedirectStandardOutput "$w\diag_H2m.out" -RedirectStandardError "$w\diag_H2m.err"
    $p.WaitForExit()
    Get-Content "$w\diag_H2m.out" | Select-String -Pattern '^\{' | Out-File -Append "$w\diag_H2m.log" -Encoding utf8
    Get-Content "$w\diag_H2m.err" | Select-String -Pattern 'Error|Traceback' | Out-File -Append "$w\diag_H2m.log" -Encoding utf8
}
Add-Content "$w\diag_H2m.log" ((Get-Date -Format 'HH:mm:ss') + ' KONIEC')
