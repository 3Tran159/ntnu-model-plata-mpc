# start_mpc.ps1 - 13.11.2026 20:25 (prosba Julka 20:14): "idealny przebieg" MPC z wyrocznia na modelu Faltinsena, widmo S1-S4, 90 %, z oporem wspornika.
# Czeka, az skoncza sie procesy widmo_s1s4.py (rdzenie 18-23), potem 6 procesow mpc_faltinsen.py na tych samych rdzeniach. Wznowienie: uruchom ponownie. Stop: plik STOP.
$here = 'T:\NTNU_GODO_CONTROL_20261109\60_PANELE_I_WYNIKI\MPC_WIDMO'; $py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
Add-Content "$here\mpc.log" ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' start_mpc: czekam na koniec widmo_s1s4')
while (Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -like '*widmo_s1s4.py worker*' }) { Start-Sleep 60 }
Add-Content "$here\mpc.log" ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' start_mpc: 6 procesow')
Start-Process -FilePath $py -ArgumentList 'T:\NTNU_GODO_CONTROL_20261109\20_supervisor\keep_awake_while.py','mpc_faltinsen.py worker','15' -WindowStyle Hidden
foreach ($act in '57','0') {
  $env:MPC_ACT_K = $act; Add-Content "$here\mpc.log" ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + " start_mpc: wariant ACT_K = $act")
  $ps = foreach ($k in 0..5) { Start-Process -FilePath $py -ArgumentList '-W','ignore','-X','utf8',"$here\mpc_faltinsen.py",'worker',"$k",'6' -WorkingDirectory $here -WindowStyle Hidden -PassThru }
  $ps | Wait-Process
}
