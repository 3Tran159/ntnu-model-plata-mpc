# chain_mpc3.ps1 - po zakonczeniu mpc_irr2 (przeglad czujnikow) uruchamia mpc_irr3 (kaskada) na rdzeniu 21
$here = "T:\NTNU_GODO_CONTROL_20261109\50_learning\vortex_env"; Set-Location $here
$py = "T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe"
while (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | ? { $_.CommandLine -like '*mpc_irr2.py*' }) { Start-Sleep 20 }
$p = Start-Process -FilePath $py -ArgumentList '-X','utf8','mpc_irr3.py' -WorkingDirectory $here -NoNewWindow -PassThru -RedirectStandardOutput "$here\mpc_irr3.out" -RedirectStandardError "$here\mpc_irr3.err"
$p.ProcessorAffinity = [IntPtr](1 -shl 21); $p.PriorityClass = 'BelowNormal'
