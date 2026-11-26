# policy_queue.ps1 - polityka RL w URANS (zgoda Julka 12.11: "do jutra puscimy td3 na uransie").
# 1) czeka, az PID2 w fali skonczy (rdzenie 2-17 wolne)
# 2) TD3_C (best_actor): warunek - w modelu POPRAWIONYM przezywa 4/4 nominalnie (ROBUST_model_poprawiony.json); eksport -> URANS OVS_POL_TD3_C
# 3) SAC_R (gdy DONE i przezywa 4/4 w modelu poprawionym) -> URANS OVS_POL_SAC_R
# Wznowienie: uruchom ponownie (gotowe przebiegi pomija, przerwane wznawia z checkpointu). Log: overnight_chain.log
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'; $V = 'T:\NTNU_GODO_CONTROL_20261109\40_MODEL_WIROWY_I_STEROWANIE\vortex_env'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' policy: ' + $m) }
function Done($tag){ $r = Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue; return ($r -and $r -match '"DONE"') }
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
while (-not (Done 'OVS_PID2_GODO')) { Start-Sleep 120 }
Log 'PID2 gotowy - start kolejki polityk'
Start-Process -FilePath $py -ArgumentList '..\20_supervisor\keep_awake_while.py','run_overset_ctrl','30' -WindowStyle Hidden
foreach ($job in @(@('TD3_C','td3','best','OVS_POL_TD3_C'), @('SAC_R','sac','best','OVS_POL_SAC_R'))) {
  $tag, $alg, $which, $run = $job
  if (Done $run) { Log "$run juz DONE"; continue }
  if ($tag -eq 'SAC_R') { while (-not (Test-Path "$V\runs\SAC_R\DONE")) { Start-Sleep 300 }
    if (-not (Test-Path "$V\runs\SAC_R\best_actor.pt")) { Log 'SAC_R bez best_actor (zadna ocena bez upadkow) - pomijam'; continue }
    $env:GODO_RESIDUAL = "$V\mbpo_residual.pkl"
    $p = Start-Process -FilePath 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe' -ArgumentList '-X','utf8','robust_test.py','SAC_R','sac' -WorkingDirectory $V -Wait -PassThru -NoNewWindow -RedirectStandardOutput "$V\robust_SAC_R_resid.out" -RedirectStandardError "$V\robust_SAC_R_resid.err"
    Copy-Item "$V\runs\SAC_R\ROBUST.json" "$V\runs\SAC_R\ROBUST_model_poprawiony.json" -Force; Remove-Item Env:GODO_RESIDUAL -EA SilentlyContinue }
  $rob = Get-Content "$V\runs\$tag\ROBUST_model_poprawiony.json" -Raw -EA SilentlyContinue
  if (-not $rob -or $rob -notmatch '"nominal"\s*:\s*\{\s*"przezyl"\s*:\s*"4/4"') { Log "$tag nie przezywa nominalnie w modelu poprawionym - pomijam"; continue }
  $pp = Start-Process -FilePath 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe' -ArgumentList '-X','utf8','export_policy.py',$tag,$alg,$which -WorkingDirectory $V -Wait -PassThru -NoNewWindow
  $pol = "$V\runs\$tag\policy_$tag.txt"
  if (-not (Test-Path $pol)) { Log "$tag eksport nieudany"; continue }
  Remove-Item "overset_runs\$run\STOP" -EA SilentlyContinue
  Log "start $run (polityka $pol)"
  & $py ..\30_URANS_STAR\run_policy_ctrl.py $run $setup ((2..17) -join ',') mode=policy "policy_file=$($pol -replace '\\','/')" pitch_trim_deg=3.5 inner=8 iface_alpha_lo=0.1 cfl_max=1.5 actuator=lag2 servo_wn_rad_s=40 2>&1 | Out-Null
  Log ("end $run : " + (Get-Content "overset_runs\$run\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
Log 'kolejka polityk koniec'
