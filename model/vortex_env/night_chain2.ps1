$here = "T:\NTNU_GODO_CONTROL_20261109\50_learning\vortex_env"; Set-Location $here
$py = "T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe"
function RunPinned($args_, $out, $mask) { $p = Start-Process -FilePath $py -ArgumentList $args_ -WorkingDirectory $here -NoNewWindow -PassThru -RedirectStandardOutput $out -RedirectStandardError "$out.err"
  Start-Sleep 2; foreach ($q in @($p) + @(Get-CimInstance Win32_Process | ? { $_.ParentProcessId -eq $p.Id } | % { Get-Process -Id $_.ProcessId })) { try { $q.ProcessorAffinity = [IntPtr]$mask; $q.PriorityClass = 'BelowNormal' } catch {} }; $p.WaitForExit() }
$env:TORCH_THREADS = '1'
while (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? { $_.CommandLine -like '*susp_mpc.py*' }) { Start-Sleep 60 }
RunPinned @('-X','utf8','robust_test.py','TD3_GODO','td3') "$here\robust_TD3_GODO.out" (1 -shl 21)
RunPinned @('-X','utf8','robust_test.py','SAC_B','sac') "$here\robust_SAC_B.out" (1 -shl 21)
while (-not (Test-Path "$here\runs\SAC_C\DONE")) { Start-Sleep 120 }
RunPinned @('-X','utf8','robust_test.py','SAC_C','sac') "$here\robust_SAC_C.out" (1 -shl 20)
RunPinned @('-X','utf8','export_policy.py','SAC_C','sac','best') "$here\export_SAC_C.out" (1 -shl 20)
RunPinned @('-X','utf8','eval_v2.py') "$here\eval_v2_final.out" (1 -shl 20)
Add-Content "$here\night_chain.log" ((Get-Date -f s) + " robust + export + eval_v2 gotowe")
