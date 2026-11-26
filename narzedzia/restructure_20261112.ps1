# restructure_20261112.ps1 - porzadek folderu (zgoda Julka 12.11 11:05: "stare checkpointy do usuniecia ... przeniesc foldery do struktury")
# 1) kasuje kwarantanne 99_DO_UPORZADKOWANIA\_DO_USUNIECIA + stare checkpointy/duplikaty w overset_runs (z RETENTION_PLAN.csv)
# 2) przenosi foldery do nowych kategorii; w starym miejscu zostaje UKRYTE dowiazanie (junction) -> stare sciezki w skryptach dzialaja
# Dziennik: 00_START\MIGRACJA.csv
$ErrorActionPreference = 'Stop'
$R = 'T:\NTNU_GODO_CONTROL_20261109'; Set-Location $R
$log = "$R\00_START\MIGRACJA.csv"
function L($a,$s,$n,$gb,$why){ Add-Content $log ("{0};{1};{2};{3};{4};{5}" -f (Get-Date -f 'yyyy-MM-dd HH:mm'),$a,$s,$n,$gb,$why) -Encoding UTF8 }

# --- 1. kasowanie
$plan = Import-Csv "$R\00_START\RETENTION_PLAN.csv" -Delimiter ';'
$freed = 0.0
foreach ($row in $plan | ? { $_.akcja -eq 'CHRONIONE' }) {
  $f = Join-Path $R $row.plik
  if (Test-Path $f) { $gb = [double]($row.GB -replace ',','.'); Remove-Item $f -Force; $freed += $gb; L 'usuniety' $row.plik '' $gb $row.powod }
}
$q = "$R\99_DO_UPORZADKOWANIA\_DO_USUNIECIA"
if (Test-Path $q) {
  $gb = [math]::Round(((Get-ChildItem $q -Recurse -File | Measure Length -Sum).Sum / 1e9), 2)
  Remove-Item $q -Recurse -Force; $freed += $gb; L 'usunieta_kwarantanna' '99_DO_UPORZADKOWANIA\_DO_USUNIECIA' '' $gb 'zgoda Julka 12.11'
}
Write-Host ("zwolniono {0:N2} GB" -f $freed)

# --- 2. nowa struktura
$map = [ordered]@{
  '00_source'    = '01_BRIEF_I_ZRODLA'
  '05_literature'= '02_LITERATURA'
  '10_macros'    = '10_STAR_MAKRA'
  '20_supervisor'= '20_NARZEDZIA'
  '70_godo_case' = '30_URANS_STAR'
  '50_learning'  = '40_MODEL_WIROWY_I_STEROWANIE'
  '40_analysis'  = '50_ANALIZY'
  '60_dashboard' = '60_PANELE_I_WYNIKI'
  '30_runs'      = '90_ARCHIWUM\MINI_VOF_2026-11-09'
}
foreach ($k in $map.Keys) {
  $src = "$R\$k"; $dst = "$R\" + $map[$k]
  $it = Get-Item $src -Force -EA SilentlyContinue
  if (-not $it -or ($it.Attributes -band [IO.FileAttributes]::ReparsePoint)) { continue }
  New-Item -ItemType Directory -Force (Split-Path $dst -Parent) | Out-Null
  Move-Item $src $dst
  cmd /c mklink /J "$src" "$dst" | Out-Null
  attrib +h +s "$src" /L
  L 'przeniesiony' $k $map[$k] '' 'stara sciezka = ukryte dowiazanie'
}
foreach ($d in '70_RAPORTY_SVERRE','99_DO_UPORZADKOWANIA') { New-Item -ItemType Directory -Force "$R\$d" | Out-Null }
# luzne pliki w korzeniu
Get-ChildItem $R -File | ? { $_.Name -like 'pip_*' } | % { Move-Item $_.FullName "$R\99_DO_UPORZADKOWANIA\" -Force; L 'przeniesiony' $_.Name ('99_DO_UPORZADKOWANIA\' + $_.Name) '' 'log instalacji' }
Get-ChildItem $R -File -Filter 'RESUME_after_move*.ps1' | % { Move-Item $_.FullName "$R\00_START\" -Force; L 'przeniesiony' $_.Name ('00_START\' + $_.Name) '' 'skrypt wznowienia' }
Write-Host 'gotowe'
Get-ChildItem $R | Select Name, Attributes | Format-Table -AutoSize
