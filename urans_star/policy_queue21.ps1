# policy_queue21.ps1 - 19.11 13:50 (koordynator, prosba Julka 13:34 "lec z tym nowym przebiegiem ... chcemy bez oscylacji").
# OVS_LEVEL_90: ODNIESIENIE "FALA, KADLUB BEZ BUJANIA" - to samo adaptacyjne MPC co OVS_MPCA_90 (mpc_adapt_bridge.py, KI 0,2, sonda 3 m, ta sama siatka i fala Godo),
# ale z waga komfortu W_A = 20 (zamiast 2,2): w modelu daje z'' RMS 0,17 m/s2 i moc ciagu z fali 0,2 W (praktycznie zero), z sr. -0,38 m.
# Cel: opor na fali przy (prawie) stalej sile nosnej -> zysk sterownikow liczony wzgledem tego, a nie wzgledem wody spokojnej (test wzoru M<z''w>).
# t_end 12 s (okno porownania 6-12 s z OVS_MPCA_90 / K0 / PID1 w tych samych chwilach). Czeka na koniec kolejki 18. Rdzenie 2-17, ok. 7 h. Log: queue21.log.
# Z-0.6 z kolejki 18 przelozone (znacznik DONE w RUN_RESULT.json - usunac, zeby policzyc). Stop: plik STOP w overset_runs\OVS_LEVEL_90.
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
function Log($m){ Add-Content queue21.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
Log 'czekam na koniec kolejki 18'
while (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*policy_queue18*' }) { Start-Sleep 60 }
$tag = 'OVS_LEVEL_90'; $case = "T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset_runs\$tag"
if ((Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue) -match '"DONE"') { Log "$tag juz gotowy"; exit }
New-Item -ItemType Directory -Force $case | Out-Null
Remove-Item "$case\MPC_STOP" -EA SilentlyContinue; Remove-Item "$case\STOP" -EA SilentlyContinue
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
$br = 'T:\NTNU_GODO_CONTROL_20261109\95_WARSZTAT_KOORDYNATOR\warsztat\20261117_mpc_komfort\mpc_adapt_bridge.py'
$env:MPC_PROBE_D = '3.0'; $env:MPC_ADAPT = '1'; $env:MPC_BAD_LIFT = '1.0'
$bp = Start-Process -FilePath $py -ArgumentList '-W','ignore','-X','utf8',$br,$case,'20','0.2' -WindowStyle Hidden -PassThru -RedirectStandardError "$case\bridge.err"
Log "start $tag, most adaptacyjny W_A 20, pid $($bp.Id)"
$c = @('inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','mass_kg=28.17007','t_end_s=12.0','scenes=0','mpc_timeout_s=180','wake_gauges=-3.0','mpc_probe=GODO_eta_x-3.0')
& $py run_mpcf_ctrl.py $tag $setup ((2..17) -join ',') mode=mpc_bridge kp_deg_per_m=2.01 ki_deg_per_m_s=0.196 release_s=1.9367999917313226 pitch_trim_deg=2.338 @c 2>&1 | Out-File -Append "overset_runs\queue21_LEVEL.out" -Encoding utf8
Log ("end $tag : " + (Get-Content "$case\RUN_RESULT.json" -Raw -EA SilentlyContinue))
New-Item -ItemType File -Force "$case\MPC_STOP" | Out-Null
Log 'koniec kolejki 21'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null
