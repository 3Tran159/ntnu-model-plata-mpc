# start_k3_po_mpc.ps1 - koordynator 13.11 20:50: uruchamia k3_widmo.py agenta D (8 przypadkow x S1-S4 x 5 realizacji) na rdzeniach 18-23,
# gdy skoncza sie: widmo_s1s4 (koordynator) i oba warianty MPC (start_mpc.ps1). Wznowienie: uruchom ponownie (k3_widmo pomija gotowe). Stop: K3_WIDMO\STOP.
$here = 'T:\NTNU_GODO_CONTROL_20261109\60_PANELE_I_WYNIKI\ZAWIESZENIE'; $py = 'T:\NTNU_GODO_CONTROL_20261109\.venv\Scripts\python.exe'
New-Item -ItemType Directory -Force "$here\K3_WIDMO" | Out-Null
Add-Content "$here\K3_WIDMO\k3_widmo.log" ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' koordynator: czekam na koniec widmo_s1s4 i MPC')
function Busy(){ return [bool](Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*widmo_s1s4.py worker*' -or $_.CommandLine -like '*mpc_faltinsen.py worker*' -or $_.CommandLine -like '*start_mpc.ps1*' }) }
while (Busy) { Start-Sleep 60 }
Add-Content "$here\K3_WIDMO\k3_widmo.log" ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' koordynator: start 6 procesow k3_widmo (rdzenie 18-23)')
Start-Process -FilePath $py -ArgumentList 'T:\NTNU_GODO_CONTROL_20261109\20_supervisor\keep_awake_while.py','k3_widmo.py worker','15' -WindowStyle Hidden
foreach ($k in 0..5) { Start-Process -FilePath $py -ArgumentList '-W','ignore','-X','utf8',"$here\k3_widmo.py",'worker',"$k",'6','18' -WorkingDirectory $here -WindowStyle Hidden }
