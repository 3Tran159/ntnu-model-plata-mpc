# backup_to_gdrive.ps1 - kopia malych plikow projektu Godo na Google Drive (bez .sim/.simh/.venv, pliki <= 50 MB).
# Niczego nie kasuje ani w zrodle, ani w kopii (robocopy /E, bez /MIR i /PURGE). Log: 00_START\backup_to_gdrive.log
$src='T:\NTNU_GODO_CONTROL_20261109'; $dst='G:\My Drive\20_PROJEKTY\NTNU\NTNU_GODO_CONTROL_BACKUP'; $log="$src\00_START\backup_to_gdrive.log"
if(-not (Test-Path 'G:\My Drive')){ Add-Content $log ((Get-Date -f 'yyyy-MM-dd HH:mm:ss')+' BRAK G: - pominieto'); exit 1 }
(Get-Process -Id $PID).PriorityClass='BelowNormal'
Add-Content $log ((Get-Date -f 'yyyy-MM-dd HH:mm:ss')+' start')
robocopy $src $dst /E /XJD /XD .venv __pycache__ .git /XF *.sim *.simh *.sim~ *.trk *.ccm *.zip *.7z /MAX:52428800 /R:1 /W:2 /NFL /NDL /NJH /NP /IPG:2 | Select-Object -Last 9 | Add-Content $log
Add-Content $log ((Get-Date -f 'yyyy-MM-dd HH:mm:ss')+" koniec, kod robocopy $LASTEXITCODE (0-7 = OK)")
