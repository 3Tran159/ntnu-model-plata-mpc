# policy_queue16.ps1 - 18.11 11:10 (koordynator, prosba Julka 11:03: "druga symulka na piatek").
# OVS_PID1_T4_90: PID1 przy 90 % na DRUGIEJ fali: T 4 s, H 1,0 m (lambda 24,97 m, okres spotkania 1,343 s), ta sama siatka i ustawienia co OVS_PID1_90.
# Cel: walidacja modelu Faltinsena B na drugiej czestotliwosci (k_f 0,059 zamiast 0,041). Odniesienie: OVS_CALM_90 (woda spokojna, ten sam czas).
# Rdzenie 2-17, ok. 1 s/krok -> 30 s ok. 8,5 h. Wznowienie: uruchom ponownie. Stop: overset_runs\OVS_PID1_T4_90\STOP.
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR
$py = '..\.venv\Scripts\python.exe'
function Log($m){ Add-Content queue16.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
$tag = 'OVS_PID1_T4_90'
Remove-Item "overset_runs\$tag\STOP" -EA SilentlyContinue
$setup = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\WAVE_T4\GODO_OVERSET_SETUP_T4.sim'
$args16 = @('mode=pid','inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','pitch_trim_deg=2.338','mass_kg=28.17007',
            'kp_deg_per_m=2.01','ki_deg_per_m_s=0.196','release_s=1.9367999917313226','t_end_s=30.0','scenes=1','scene_every_steps=100',
            'wave_period_s=4.0','encounter_period_s=1.3433','wall_budget_s=72000')
Log "start $tag"
& $py run_k0_ctrl.py $tag $setup ((2..17) -join ',') @args16 2>&1 | Out-File -Append "overset_runs\queue16_$tag.out" -Encoding utf8
Log ("end $tag : " + (Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue))
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null
