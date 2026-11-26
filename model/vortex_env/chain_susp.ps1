$here = "T:\NTNU_GODO_CONTROL_20261109\50_learning\vortex_env"; Set-Location $here
$py = "T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe"
Start-Sleep 30
while (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? { $_.CommandLine -like '*mpc_irr2.py*' -or $_.CommandLine -like '*mpc_irr3.py*' }) { Start-Sleep 20 }
$p = Start-Process -FilePath $py -ArgumentList '-X','utf8','susp_test.py' -WorkingDirectory $here -NoNewWindow -PassThru -RedirectStandardOutput "$here\susp.out" -RedirectStandardError "$here\susp.err"
$p.ProcessorAffinity = [IntPtr](1 -shl 21); $p.PriorityClass = 'BelowNormal'
