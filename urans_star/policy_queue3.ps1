# policy_queue3.ps1 - polityki RL w URANS na noc 12/13.11 (decyzja Julka 14:55-14:57: najpierw zwykly TD3 jak u Godø, bez bramki testu kruchosci).
# Kolejnosc: TD3_GODO (nagroda Godø: tylko plat) -> TD3_C338 (wspornik z CFD, model poprawiony, gdy DONE) -> TD3_C (jesli zostanie czas)
# -> potem wspornik h = 0,7 / 1,5 m na GPU. Zastepuje policy_queue.ps1 i policy_queue2.ps1. Wznowienie: uruchom ponownie. Log: overnight_chain.log
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'; $V = 'T:\NTNU_GODO_CONTROL_20261109\40_MODEL_WIROWY_I_STEROWANIE\vortex_env'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' policy3: ' + $m) }
function Done($tag){ $r = Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue; return ($r -and $r -match '"(DONE|HOLD_LIMIT|HOLD_STOP_FILE|HOLD_CFL|HOLD_NAN)"') }
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
while (-not (Done 'OVS_PID2_GODO')) { Start-Sleep 120 }
Log 'PID2 gotowy - start kolejki polityk (TD3_GODO, TD3_C338, TD3_C)'
Start-Process -FilePath $py -ArgumentList '..\20_supervisor\keep_awake_while.py','run_overset_ctrl','30' -WindowStyle Hidden
foreach ($job in @(@('TD3_GODO','OVS_POL_TD3_GODO'), @('TD3_C338','OVS_POL_TD3_C338'), @('CALM','OVS_CALM_Z-0.3'), @('CALM','OVS_CALM_Z-0.6'), @('TD3_C','OVS_POL_TD3_C'))) {
  $tag, $run = $job
  if (Done $run) { Log "$run juz skonczony"; continue }
  if ($tag -eq 'CALM') {   # 12.11 15:11 Julek: opor w wodzie spokojnej vs wysokosc lotu (PID2 na z_ref, 8 s, srednia z ostatnich 2 s; PID3 przeregulowuje do -0,85 m w modelu)
    $zr = $run.Substring(10); $calm = 'T:\NTNU_GODO_CONTROL_20261109\70_godo_case\overset\CALM\GODO_OVERSET_SETUP_CALM.sim'
    Log "start $run (woda spokojna, z_ref $zr m)"
    & $py run_overset_ctrl.py $run $calm ((2..17) -join ',') mode=pid kp_deg_per_m=6.63 ki_deg_per_m_s=1.18 "z_ref_m=$zr" t_end_s=8.0 release_s=1.0 pitch_trim_deg=3.5 inner=8 iface_alpha_lo=0.1 cfl_max=1.5 actuator=lag2 servo_wn_rad_s=40 2>&1 | Out-Null
    Log ("end $run : " + (Get-Content "overset_runs\$run\RUN_RESULT.json" -Raw -EA SilentlyContinue)); continue
  }
  if ($tag -eq 'TD3_C338') {
    while (-not (Test-Path "$V\runs\$tag\DONE")) { Start-Sleep 300 }
    if (-not (Test-Path "$V\runs\$tag\best_actor.pt") -and (Test-Path "$V\runs\$tag\best_any_actor.pt")) { Copy-Item "$V\runs\$tag\best_any_actor.pt" "$V\runs\$tag\best_actor.pt"; Log "${tag} - brak best_actor, uzyty best_any_actor" }
  }
  Start-Process -FilePath 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe' -ArgumentList '-X','utf8','export_policy.py',$tag,'td3','best' -WorkingDirectory $V -Wait -NoNewWindow
  $pol = "$V\runs\$tag\policy_$tag.txt"
  if (-not (Test-Path $pol)) { Log "$tag eksport nieudany"; continue }
  Remove-Item "overset_runs\$run\STOP" -EA SilentlyContinue
  Log "start $run (polityka $pol)"
  & $py ..\30_URANS_STAR\run_policy_ctrl.py $run $setup ((2..17) -join ',') mode=policy "policy_file=$($pol -replace '\\','/')" pitch_trim_deg=3.5 inner=8 iface_alpha_lo=0.1 cfl_max=1.5 actuator=lag2 servo_wn_rad_s=40 2>&1 | Out-Null
  Log ("end $run : " + (Get-Content "overset_runs\$run\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
$S = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\strut_calm'
Add-Content "$S\strut_chain.log" ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' polityki skonczone - start h=0.7, 1.5')
$p = Start-Process -FilePath 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe' -ArgumentList '-X','utf8','strut_chain.py','0.7,1.5' -WorkingDirectory $S -WindowStyle Hidden -PassThru
Start-Sleep 2; try { $p.ProcessorAffinity = [IntPtr](1 -shl 23) } catch {}
Log 'kolejka polityk koniec (wspornik h0.7/1.5 wystartowany)'
