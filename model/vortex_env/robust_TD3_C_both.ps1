# test kruchosci TD3_C (best_actor) w modelu bazowym i w modelu poprawionym z URANS; rdzen 18
$V = 'T:\NTNU_GODO_CONTROL_20261109\40_MODEL_WIROWY_I_STEROWANIE\vortex_env'; Set-Location $V
$py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
function RunPinned($out) { $p = Start-Process -FilePath $py -ArgumentList '-X','utf8','robust_test.py','TD3_C','td3' -WorkingDirectory $V -NoNewWindow -PassThru -RedirectStandardOutput $out -RedirectStandardError "$out.err"
  Start-Sleep 2; foreach ($q in @($p) + @(Get-CimInstance Win32_Process | ? { $_.ParentProcessId -eq $p.Id } | % { Get-Process -Id $_.ProcessId })) { try { $q.ProcessorAffinity = [IntPtr](1 -shl 18); $q.PriorityClass = 'BelowNormal' } catch {} }; $p.WaitForExit() }
$env:TORCH_THREADS = '1'; Remove-Item Env:GODO_RANDOMIZE -EA SilentlyContinue; Remove-Item Env:GODO_RESIDUAL -EA SilentlyContinue
RunPinned "$V\robust_TD3_C_base.out"; Copy-Item "$V\runs\TD3_C\ROBUST.json" "$V\runs\TD3_C\ROBUST_model_bazowy.json" -Force
$env:GODO_RESIDUAL = "$V\mbpo_residual.pkl"
RunPinned "$V\robust_TD3_C_resid.out"; Copy-Item "$V\runs\TD3_C\ROBUST.json" "$V\runs\TD3_C\ROBUST_model_poprawiony.json" -Force
