# night2_pid13.ps1 - noc 11/12.11: PID1 i PID3 Godø (tab. 3) w fali, URANS, rdzenie 2-17. Zgoda Julka 11.11 20:50.
# Ustawienia jak OVS_PID_BASE2 (trym 3,5 deg, zwolnienie 1 okres, 11,62 s, serwo lag2, inner 8); tylko Kp, Ki inne.
# Wznowienie po przerwie: uruchom ten skrypt ponownie (run_overset_ctrl wznawia z ostatniego checkpointu; gotowe przebiegi pomija).
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' night2: ' + $m) }
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
$runs = @(@('OVS_PID1_GODO', '2.01', '0.196'), @('OVS_PID3_GODO', '22.3', '7.25'))
foreach ($r in $runs) {
  $tag, $kp, $ki = $r
  $res = Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue
  if ($res -and $res -match '"DONE"') { Log "$tag juz DONE"; continue }
  Remove-Item "overset_runs\$tag\RUN_RESULT.json", "overset_runs\$tag\STOP" -EA SilentlyContinue
  Log "start $tag (Kp $kp, Ki $ki)"
  & $py run_overset_ctrl.py $tag $setup ((2..17) -join ',') mode=pid "kp_deg_per_m=$kp" "ki_deg_per_m_s=$ki" pitch_trim_deg=3.5 inner=8 iface_alpha_lo=0.1 cfl_max=1.5 actuator=lag2 servo_wn_rad_s=40 2>&1 | Out-Null
  Log ("end $tag : " + (Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
