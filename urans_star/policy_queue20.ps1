# policy_queue20.ps1 - 19.11 09:10 (koordynator, zgoda Julka 09:08 "spokojna woda na koniec").
# Spokojna woda 90 % na gestej siatce GF, z_ref 0, te same nastawy PID co OVS_CALM_90 -> uczciwe procenty oporu dla OVS_K0_85_90_GF.
# t_end 14 s (porownanie w oknach 5,81-13,56 s jak zbieznosc). Czeka na koniec kolejki 19. Rdzenie 2-17. Log: queue20.log. Stop: plik STOP w overset_runs\<tag>.
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR
$py = '..\.venv\Scripts\python.exe'
function Log($m){ Add-Content queue20.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
Log 'czekam na koniec kolejek 17, 18 i 19'
while (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -match 'policy_queue(1[789]|21)' }) { Start-Sleep 120 }
$tag = 'OVS_CALM_90_GF'
if ((Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue) -match '"DONE"') { Log "$tag juz gotowy"; exit }
$calm = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\CALM_GF\GODO_OVERSET_SETUP_CALM.sim'
if (-not (Test-Path $calm)) {
  Log 'budowa setupu spokojnej wody GF'
  & $py overset\CALM_GF\zrob_setup.py 2>&1 | Out-File -Append 'overset\CALM_GF\setup.out' -Encoding utf8
  if (-not (Test-Path $calm)) { Log 'BLAD: brak GODO_OVERSET_SETUP_CALM.sim dla GF - koniec'; exit }
  Log ('setup gotowy: ' + (Get-Content 'overset\CALM_GF\SET_CALM.txt' -Raw -EA SilentlyContinue))
}
$common = @('mode=pid','kp_deg_per_m=6.63','ki_deg_per_m_s=1.18','release_s=1.0','inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40',
            't_end_s=14.0','pitch_trim_deg=2.85','mass_kg=28.17007','scenes=0','wall_budget_s=72000')
Log "start $tag"
& $py run_k0_ctrl.py $tag $calm ((2..17) -join ',') @common 2>&1 | Out-File -Append "overset_runs\queue20_$tag.out" -Encoding utf8
Log ("end $tag : " + (Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue))
Log 'koniec kolejki 20'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null

