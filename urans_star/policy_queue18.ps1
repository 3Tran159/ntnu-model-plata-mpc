# policy_queue18.ps1 - 18.11 19:35 (koordynator, zgoda Julka 19:26/19:30). Czy w URANS opor plata naprawde spada z glebokoscia (krotkie przebiegi 14.11: -18 W na metr)?
# Woda spokojna przy 90 %, 20 s (skrocone 18.11 20:30, zeby zmiescic samouczace MPC przed piatkiem), jak OVS_CALM_90 (z_ref 0), tylko z_ref = -0,3 i -0,6 m. Ten sam setup CALM, te same nastawy PID.
# Czeka na koniec kolejki 17 (zbieznosc siatki). Rdzenie 2-17, kazdy ok. 8 h. Log: queue18.log. Stop: plik STOP w overset_runs\<tag>.
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR
$py = '..\.venv\Scripts\python.exe'
function Log($m){ Add-Content queue18.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
Log 'czekam na koniec kolejki 17'
while (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*policy_queue17*' }) { Start-Sleep 120 }
$calm = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\overset\CALM\GODO_OVERSET_SETUP_CALM.sim'
$common = @('mode=pid','kp_deg_per_m=6.63','ki_deg_per_m_s=1.18','release_s=1.0','inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40',
            't_end_s=20.0','pitch_trim_deg=2.85','mass_kg=28.17007','scenes=0','wall_budget_s=72000')
foreach ($z in @('-0.3', '-0.6')) {
  $tag = "OVS_CALM_90_Z$z"
  if ((Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue) -match '"DONE"') { Log "$tag juz gotowy"; continue }
  Log "start $tag"
  & $py run_k0_ctrl.py $tag $calm ((2..17) -join ',') @common "z_ref_m=$z" 2>&1 | Out-File -Append "overset_runs\queue18_$tag.out" -Encoding utf8
  Log ("end $tag : " + (Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
Log 'koniec kolejki 18'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null

