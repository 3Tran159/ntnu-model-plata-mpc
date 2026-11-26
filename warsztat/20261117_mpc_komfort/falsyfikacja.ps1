# 22.11 22:15 (Julek 22:03: "sprobuj znalezc kiedy ten wzor nie dziala"): proby obalenia wzoru w modelu, JEDEN MPC bez zmian (mpc_cel_bridge_zapis.py = MPC + zapis serii).
# Zmienia sie tylko fala. Szukamy: (1) dlugich fal czolowych, gdzie czlon poziomy g/(U*w_e) rosnie (T 8 s: 0,42; T 10 s: 0,71 wobec 0,25 przy T 5 s),
# (2) krotkich fal o duzej czestosci zredukowanej (T 2,5 s: k = 0,13), gdzie rosna efekty niestacjonarne, (3) duzej amplitudy przy T 5 s (nieliniowosc, plat blisko powierzchni).
# Rdzen 0 (jedyny wolny), priorytet Normal. Wyniki: cel_reg_zapis\T<T>_cel<cel>.json + seria_zapis\*.npy. Mapa nazw: falsyfikacja_mapa.txt. Log: falsyfikacja.log
$w = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort'
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
Set-Location $w
$fale = @(@('2.5','0.165','T 2,5 s, H 0,33 m (k zred. 0,13)'), @('3.0','0.235','T 3 s, H 0,47 m'), @('4.0001','0.415','T 4 s, H 0,83 m'),
          @('6.0','0.75','T 6 s, H 1,5 m'), @('8.0','0.75','T 8 s, H 1,5 m (g/(U*we) 0,42)'), @('10.0','0.75','T 10 s, H 1,5 m (g/(U*we) 0,71)'),
          @('5.0003','0.25','T 5 s, H 0,5 m'), @('5.0004','0.5','T 5 s, H 1,0 m'), @('5.0005','1.0','T 5 s, H 2,0 m (plat blisko powierzchni)'))
$jobs = @(); foreach ($f in $fale) { foreach ($c in @('0.4905', '1.962', '-1')) { $jobs += ,@($f[0], $f[1], $c, $f[2]) } }
$env:MPC_CORE = '0'; $env:MPC_PROBE_D = '0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'; $env:MPC_WYP = '1'; $env:MPC_ACT_K = '57'; $env:MPC_WA_MAX = '20'; $env:MPC_TEST_SEA = ''; $env:MPC_TEST_OKNO = '20'
foreach ($j in $jobs) {
    "T$([double]$j[0])_cel$($j[2]) = $($j[3]), cel $($j[2])" | Add-Content "$w\falsyfikacja_mapa.txt"
    if (Test-Path "$w\cel_reg_zapis\T$([double]$j[0])_cel$($j[2]).json") { continue }
    $env:MPC_TEST_T = $j[0]; $env:MPC_TEST_A = $j[1]; $T = [double]$j[0]; $k = (2*[math]::PI/$T)*(2*[math]::PI/$T)/9.81; $we = 2*[math]::PI/$T + $k*12.35; $env:MPC_TEST_PER = [string][math]::Max(20, [math]::Ceiling(60.0*$we/(2*[math]::PI)))
    Add-Content "$w\falsyfikacja.log" ((Get-Date -Format 'HH:mm:ss') + " start $($j[3]) cel $($j[2])")
    $p = Start-Process -FilePath $py -ArgumentList '-W','ignore','mpc_cel_bridge_zapis.py','-',$j[2],'0.2','test' -NoNewWindow -PassThru -RedirectStandardOutput "$w\falsyfikacja.out" -RedirectStandardError "$w\falsyfikacja.err"
    $p.WaitForExit()
    Get-Content "$w\falsyfikacja.out" | Select-String -Pattern '^\{' | Out-File -Append "$w\falsyfikacja.log" -Encoding utf8
    Get-Content "$w\falsyfikacja.err" | Select-String -Pattern 'Error|Traceback' | Out-File -Append "$w\falsyfikacja.log" -Encoding utf8
}
Add-Content "$w\falsyfikacja.log" ((Get-Date -Format 'HH:mm:ss') + ' KONIEC')

