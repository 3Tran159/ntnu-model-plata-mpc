# run_pid2_wave.ps1 - PID2 Godø (tab. 3: Kp 6.63, Ki 1.18) w fali, URANS overset, rdzenie 2-17. Zgoda Julka 12.11 11:14 ("jest ok na star").
# Ustawienia jak OVS_PID1/PID3 (trym 3,5 deg, 11,62 s, serwo lag2, inner 8). Wznowienie: uruchom ponownie (wznawia z ostatniego CP).
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' pid2: ' + $m) }
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
$tag = 'OVS_PID2_GODO'
$res = Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue
if ($res -and $res -match '"DONE"') { Log "$tag juz DONE"; exit }
Remove-Item "overset_runs\$tag\RUN_RESULT.json", "overset_runs\$tag\STOP" -EA SilentlyContinue
Start-Process -FilePath $py -ArgumentList '..\20_supervisor\keep_awake_while.py','run_overset_ctrl','30' -WindowStyle Hidden
Log "start $tag (Kp 6.63, Ki 1.18)"
& $py run_overset_ctrl.py $tag $setup ((2..17) -join ',') mode=pid "kp_deg_per_m=6.63" "ki_deg_per_m_s=1.18" pitch_trim_deg=3.5 inner=8 iface_alpha_lo=0.1 cfl_max=1.5 actuator=lag2 servo_wn_rad_s=40 2>&1 | Out-Null
Log ("end $tag : " + (Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue))
