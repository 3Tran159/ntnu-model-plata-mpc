# policy_queue2.ps1 - po policy_queue.ps1: TD3_C338 (TD3_C dostrojony: wspornik z CFD 338 N/m, model poprawiony z URANS, losowanie) w URANS,
# potem wspornik h = 0,7 i 1,5 m na GPU (zastepuje strut_after_policies.ps1). Log: overnight_chain.log
Set-Location T:\NTNU_GODO_CONTROL_20261109\70_godo_case
$py = '..\.venv\Scripts\python.exe'; $V = 'T:\NTNU_GODO_CONTROL_20261109\40_MODEL_WIROWY_I_STEROWANIE\vortex_env'
function Log($m){ Add-Content overnight_chain.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' policy2: ' + $m) }
function Done($tag){ $r = Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue; return ($r -and $r -match '"DONE"') }
while (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*policy_queue.ps1*' }) { Start-Sleep 300 }
$setup = (Get-ChildItem overset -Directory -Filter 'OV_SHORT30*' | Select-Object -Last 1).FullName + '\GODO_OVERSET_SETUP_B1.0.sim'
$tag = 'TD3_C338'; $run = 'OVS_POL_TD3_C338'
if (-not (Done $run)) {
  while (-not (Test-Path "$V\runs\$tag\DONE")) { Start-Sleep 300 }
  if (-not (Test-Path "$V\runs\$tag\best_actor.pt") -and (Test-Path "$V\runs\$tag\best_any_actor.pt")) { Copy-Item "$V\runs\$tag\best_any_actor.pt" "$V\runs\$tag\best_actor.pt"; Log "${tag} - brak best_actor - uzyty best_any_actor" }
  $env:GODO_RESIDUAL = "$V\mbpo_residual.pkl"; $env:GODO_STRUT_K = '85.5'; $env:TORCH_THREADS = '1'
  Start-Process -FilePath 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe' -ArgumentList '-X','utf8','robust_test.py',$tag,'td3' -WorkingDirectory $V -Wait -NoNewWindow -RedirectStandardOutput "$V\robust_${tag}_resid.out" -RedirectStandardError "$V\robust_${tag}_resid.err"
  Copy-Item "$V\runs\$tag\ROBUST.json" "$V\runs\$tag\ROBUST_model_poprawiony.json" -Force
  $rob = Get-Content "$V\runs\$tag\ROBUST_model_poprawiony.json" -Raw -EA SilentlyContinue
  if ($rob -and $rob -match '"nominal"\s*:\s*\{\s*"przezyl"\s*:\s*"4/4"') {
    Start-Process -FilePath 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe' -ArgumentList '-X','utf8','export_policy.py',$tag,'td3','best' -WorkingDirectory $V -Wait -NoNewWindow
    $pol = "$V\runs\$tag\policy_$tag.txt"
    if (Test-Path $pol) {
      Start-Process -FilePath $py -ArgumentList '..\20_supervisor\keep_awake_while.py','run_overset_ctrl','30' -WindowStyle Hidden
      Log "start $run (polityka $pol)"
      & $py ..\30_URANS_STAR\run_policy_ctrl.py $run $setup ((2..17) -join ',') mode=policy "policy_file=$($pol -replace '\\','/')" pitch_trim_deg=3.5 inner=8 iface_alpha_lo=0.1 cfl_max=1.5 actuator=lag2 servo_wn_rad_s=40 2>&1 | Out-Null
      Log ("end $run : " + (Get-Content "overset_runs\$run\RUN_RESULT.json" -Raw -EA SilentlyContinue))
    } else { Log "$tag eksport nieudany" }
  } else { Log "$tag nie przezywa nominalnie w modelu poprawionym - pomijam URANS" }
}
$S = 'T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR\strut_calm'
Add-Content "$S\strut_chain.log" ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' polityki skonczone - start h=0.7, 1.5')
$p = Start-Process -FilePath 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe' -ArgumentList '-X','utf8','strut_chain.py','0.7,1.5' -WorkingDirectory $S -WindowStyle Hidden -PassThru
Start-Sleep 2; try { $p.ProcessorAffinity = [IntPtr](1 -shl 23) } catch {}
Log 'kolejka 2 koniec (wspornik h0.7/1.5 wystartowany)'
