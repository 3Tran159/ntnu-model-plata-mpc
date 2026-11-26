# 22.11 17:35 (Julek 17:15: "to licz i archiwizuj dane"): powtorzenie serii jednego MPC (wypadkowa) z zapisem serii czasowych i czlonem poziomej predkosci fali.
# mpc_cel_bridge_zapis.py = mpc_cel_bridge.py BEZ ZMIAN w MPC (sprawdzone: T5 cel 0,05 g daje identyczny JSON). Fale regularne T5 (Godo) i T4: 20 okresow.
# Widma S1-S4 seed 0: 300 s. 6 robotnikow na rdzeniach 18-23 z priorytetem Idle (rdzenie zajete przez KORAB - bierzemy tylko wolne cykle).
# Wyniki: cel_reg_zapis\, cel_widmo_zapis\, seria_zapis\*.npy. Log: cel_zapis_<k>.log. Uruchom: -K 0..5
param([int]$K = 0)
$w = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort'
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
Set-Location $w
$cele = @('0','0.4905','0.981','1.4715','1.962','2.4525','2.943','3.4335','-1')
$jobs = @()
foreach ($c in $cele) { foreach ($f in @('5.0:0.727','4.0:0.5')) { $jobs += ,@('reg', $f, $c) } }
foreach ($c in $cele) { foreach ($s in @('S1','S2','S3','S4')) { $jobs += ,@('sea', $s, $c) } }
$env:MPC_CORE = "$(18 + $K)"; $env:MPC_PROBE_D = '0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'; $env:MPC_WYP = '1'; $env:MPC_ACT_K = '57'; $env:MPC_WA_MAX = '20'
for ($i = 0; $i -lt $jobs.Count; $i++) {
    if ($i % 6 -ne $K) { continue }
    $j = $jobs[$i]
    if ($j[0] -eq 'reg') {
        $T = $j[1].Split(':')[0]; if (Test-Path "$w\cel_reg_zapis\T$([double]$T)_cel$($j[2]).json") { continue }
        $env:MPC_TEST_SEA = ''; $env:MPC_TEST_T = $T; $env:MPC_TEST_A = $j[1].Split(':')[1]; $env:MPC_TEST_PER = '20'
    } else {
        if (Test-Path "$w\cel_widmo_zapis\$($j[1])_s0_cel$($j[2]).json") { continue }
        $env:MPC_TEST_SEA = $j[1]; $env:MPC_TEST_SEED = '0'; $env:MPC_TEST_TSIM = '300'
    }
    Add-Content "$w\cel_zapis_$K.log" ((Get-Date -Format 'HH:mm:ss') + " start $($j -join ' ')")
    $p = Start-Process -FilePath $py -ArgumentList '-W','ignore','mpc_cel_bridge_zapis.py','-',$j[2],'0.2','test' -NoNewWindow -PassThru -RedirectStandardOutput "$w\cel_zapis_$K.out" -RedirectStandardError "$w\cel_zapis_$K.err"
    try { $p.PriorityClass = 'Idle' } catch {}
    $p.WaitForExit()
    Get-Content "$w\cel_zapis_$K.out" | Select-String -Pattern '^\{' | Out-File -Append "$w\cel_zapis_$K.log" -Encoding utf8
    Get-Content "$w\cel_zapis_$K.err" | Select-String -Pattern 'Error|Traceback' | Out-File -Append "$w\cel_zapis_$K.log" -Encoding utf8
}
Add-Content "$w\cel_zapis_$K.log" ((Get-Date -Format 'HH:mm:ss') + ' KONIEC')
