# policy_queue29.ps1 - 24.11 14:25 (Julek 14:11: "zrob test"). Plat NIERUCHOMY na fali Godo (T 5 s, H 1,454 m) na 3 glebokosciach:
# czy dodatek oporu URANS wzgledem modelu Faltinsena (OVS_FIX_TRIM 13.11: +8,6 W na pasek, dCD +0,0015) bierze sie z nieliniowej powierzchni
# (plat blisko doliny: przy 1,09 m nad platem zostaje w dolinie 0,36 m = 1,2 cieciwy) - wtedy maleje z glebokoscia - czy z lepkosci/siatki (zostaje).
# OVS_FIX_L109_90: setup B1.0 (poziom 1,09 m); OVS_FIX_L139_90 / OVS_FIX_L169_90: overset\FIX_LEVEL\GODO_OVERSET_SETUP_B1.0_L139/L169.sim (SetLevelFixL*.java).
# mode=hold: kat = trym 2,338 st (90 %), nurzanie zablokowane caly czas (release 99 s). t_end 13,56 s = 7 okresow spotkania (1,9368 s); analiza: ostatnie 4 okresy + kazdy okres osobno (dryf).
# Uwaga: raporty eta_* w setupach L139/L169 odejmuja nadal 1,09 m (eta przesuniete o +0,3 / +0,6 m) - przy analizie odjac.
# Czeka na koniec OVS_CEL_005g_T8_90 (kolejka 28). Rdzenie 2-17, ok. 3,5-4 h na przebieg. Log: queue29.log. Stop: plik STOP w overset_runs\<tag>. Wznowienie: uruchom ponownie (pomija skonczone).
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
function Log($m){ Add-Content queue29.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
function Done($tag){ $r = Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue; return ($r -and $r -match '"(DONE|HOLD_LIMIT|HOLD_STOP_FILE|HOLD_CFL|HOLD_NAN)"') }
Log 'czekam na koniec OVS_CEL_005g_T8_90 (kolejka 28)'
while (Get-CimInstance Win32_Process | Where-Object { $_.ProcessId -ne $PID -and ($_.CommandLine -like '*policy_queue28*' -or $_.CommandLine -like '*run_mpcf_ctrl*OVS_CEL_005g_T8_90*') }) { Start-Sleep 30 }
Start-Sleep 60
# 26.11 11:15 (Julek 11:02: "rowna jazda na chama - nie praktyczny sterownik, ale referencja"): NAJPIERW OVS_K0_100_T8_90 - fala T 8 s (domena T8),
# kasowanie fali 100 % (k0_gain 1,0: kat -= deg(w_wody_na_placie/U)) + sztywny PID wysokosci (kp 10 st/m, ki 2 st/(m s)), t_end 36 s, ok. 9-10 h.
$t8 = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\WAVE_T8\GODO_OVERSET_SETUP_T8.sim'; $tagk = 'OVS_K0_100_T8_90'; $casek = "T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs\$tagk"
if (-not (Done $tagk)) {
    New-Item -ItemType Directory -Force $casek | Out-Null; Remove-Item "$casek\STOP" -EA SilentlyContinue
    $ck = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','mass_kg=28.17007','t_end_s=36.0','scenes=0','wake_gauges=-3.0','wave_period_s=8.0','encounter_period_s=4.0228','k0_gain=1.0')
    Log "start $tagk (rowna jazda na sile: kasowanie 100 % + sztywny PID, fala T 8 s)"
    & $py run_mpcf_ctrl.py $tagk $t8 ((2..17) -join ',') mode=k0 kp_deg_per_m=10 ki_deg_per_m_s=2 release_s=10.0 pitch_trim_deg=2.338 @ck 2>&1 | Out-File -Append "overset_runs\queue29_$tagk.out" -Encoding utf8
    Log ("end $tagk : " + (Get-Content "$casek\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
$base = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
$jobs = @(@('OVS_FIX_L109_90', $base), @('OVS_FIX_L139_90', 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\FIX_LEVEL\GODO_OVERSET_SETUP_B1.0_L139.sim'),
          @('OVS_FIX_L169_90', 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\FIX_LEVEL\GODO_OVERSET_SETUP_B1.0_L169.sim'))
$c = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','mass_kg=28.17007','t_end_s=13.5576','scenes=0','wake_gauges=-3.0','wave_period_s=5.0','encounter_period_s=1.9368')
foreach ($j in $jobs) {
    $tag = $j[0]; $setup = $j[1]
    if (Done $tag) { Log "$tag juz gotowy"; continue }
    if (-not (Test-Path $setup)) { Log "BRAK setupu $setup - pomijam $tag"; continue }
    $free = (Get-PSDrive T).Free/1GB; if ($free -lt 8) { Log ("za malo miejsca na T: {0:N1} GB - stop" -f $free); break }
    $case = "T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs\$tag"; New-Item -ItemType Directory -Force $case | Out-Null; Remove-Item "$case\STOP" -EA SilentlyContinue
    Log "start $tag (plat nieruchomy, kat 2,338 st, $setup)"
    & $py run_mpcf_ctrl.py $tag $setup ((2..17) -join ',') mode=hold release_s=99 pitch_trim_deg=2.338 @c 2>&1 | Out-File -Append "overset_runs\queue29_$tag.out" -Encoding utf8
    Log ("end $tag : " + (Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
Log 'koniec kolejki 29'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null
