# policy_queue17.ps1 - 18.11 17:40 (koordynator, zgoda Julka 17:24 "dzialaj"). Zbieznosc siatki overset dla K0 85 % (czy resztka sily po kasowaniu fali to numeryka URANS).
# Czeka na koniec kolejki 16 (OVS_PID1_T4_90). Potem: budowa siatek overset rzadkiej (B 1,414) i gestej (B 0,707) jak OV_SHORT30 (ta sama domena, ten sam input MEDIUM, tylko Base Size),
# potem K0 85 % na fali God0 przy 90 %, t_end 14 s (6,2 okresu po zwolnieniu): OVS_K0_85_90_GC (rzadka), OVS_K0_85_90_GF (gesta). Odniesienie: OVS_K0_85_90_H1 (srednia, do 30 s).
# Rdzenie 2-17. Log: queue17.log. Stop: plik STOP w overset_runs\<tag>.
Add-Type -Namespace W -Name P -MemberDefinition '[DllImport("kernel32.dll")] public static extern uint SetThreadExecutionState(uint f);'
[W.P]::SetThreadExecutionState([uint32]2147483649) | Out-Null
Set-Location T:\NTNU_GODO_CONTROL_20261109\30_URANS_STAR
$py = '..\.venv\Scripts\python.exe'
function Log($m){ Add-Content queue17.log ((Get-Date -Format 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
Log 'czekam na koniec kolejki 16'
while (Get-CimInstance Win32_Process | Where-Object { $_.CommandLine -like '*policy_queue16*' }) { Start-Sleep 60 }
Log 'kolejka 16 skonczona'
$cores = (2..17) -join ','
$build = @('x0_m=-31.2261998346299','band_x1_m=46.8392997519448','travel_cell_pct=3.0','bg_stl=GodoBackground_-0.8L_2L.stl','mass_kg=31.300080128205128')
$k0 = @('mode=k0','k0_gain=0.85','k0_est=h1','inner=8','iface_alpha_lo=0.1','cfl_max=1.5','actuator=lag2','servo_wn_rad_s=40','pitch_trim_deg=2.338','mass_kg=28.17007',
        'kp_deg_per_m=2.01','ki_deg_per_m_s=0.196','release_s=1.9367999917313226','t_end_s=14.0','scenes=0','wall_budget_s=72000')
foreach ($g in @(@('GC','1.41421356'), @('GF','0.70710678'))) {
  $tag = "OVS_K0_85_90_$($g[0])"
  if ((Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue) -match '"DONE"') { Log "$tag juz gotowy"; continue }
  $setup = Get-ChildItem overset -Directory -Filter "OVG_$($g[0])_*" -EA SilentlyContinue | Sort-Object Name | Select-Object -Last 1 | ForEach-Object { Get-ChildItem $_.FullName -Filter 'GODO_OVERSET_SETUP_B*.sim' } | Select-Object -First 1
  if (-not $setup) {
    Log "budowa siatki $($g[0]) B $($g[1])"
    & $py run_overset_build.py "OVG_$($g[0])" mesh $cores 'mode=mesh' "base_size_m=$($g[1])" @build 2>&1 | Out-File -Append "queue17_build_$($g[0]).out" -Encoding utf8
    $setup = Get-ChildItem overset -Directory -Filter "OVG_$($g[0])_*" | Sort-Object Name | Select-Object -Last 1 | ForEach-Object { Get-ChildItem $_.FullName -Filter 'GODO_OVERSET_SETUP_B*.sim' } | Select-Object -First 1
    if (-not $setup) { Log "BLAD: brak setupu $($g[0]) - pomijam"; continue }
    $info = Get-Content (Join-Path $setup.DirectoryName 'GODO_OVERSET.json') -Raw -EA SilentlyContinue
    Log "siatka $($g[0]) gotowa: $($setup.FullName) | $info"
  }
  Log "start $tag"
  & $py run_k0_ctrl.py $tag $setup.FullName $cores @k0 2>&1 | Out-File -Append "overset_runs\queue17_$tag.out" -Encoding utf8
  Log ("end $tag : " + (Get-Content "overset_runs\$tag\RUN_RESULT.json" -Raw -EA SilentlyContinue))
}
Log 'koniec kolejki 17'
[W.P]::SetThreadExecutionState([uint32]2147483648) | Out-Null
