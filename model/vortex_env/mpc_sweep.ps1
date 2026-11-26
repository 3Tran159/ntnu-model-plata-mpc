# mpc_sweep.ps1 - przeglad wagi pozycji pionowej W_Z w MPC (rdzen 21), po kolei.
$here = "T:\NTNU_GODO_CONTROL_20261109\50_learning\vortex_env"; Set-Location $here
$py = "T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe"

Start-Sleep 20
foreach ($wz in @("2", "20")) {
  $p = Start-Process -FilePath $py -ArgumentList '-X','utf8','mpc_linear.py',$wz,'2000' -WorkingDirectory $here -NoNewWindow -PassThru -RedirectStandardOutput "$here\mpc_WZ$wz.out" -RedirectStandardError "$here\mpc_WZ$wz.err"
  $p.ProcessorAffinity = [IntPtr](1 -shl 21); $p.PriorityClass = 'BelowNormal'; $p.WaitForExit()
}
