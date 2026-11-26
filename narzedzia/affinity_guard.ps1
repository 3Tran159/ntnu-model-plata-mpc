# affinity_guard.ps1 - pilnuje przypiecia procesow co 60 s (12.11: TD3_C trafil na rdzenie STAR 2-17 z priorytetem High,
# a STAR wspornika na GPU chodzil bez przypiecia na wszystkich 24 rdzeniach -> URANS PID2 11 s/krok zamiast ~1,1 s).
# Zasady: train_rl <TAG> -> rdzenie z runs\<TAG>\supervise.ps1 (maska), priorytet BelowNormal; STAR wspornika (strut_calm) -> rdzen 23.
# Log: 20_NARZEDZIA\affinity_guard.log.  Konczy sie sam, gdy nie ma ani train_rl, ani STAR.
$R = 'T:\NTNU_GODO_CONTROL_20261109'; $V = "$R\40_MODEL_WIROWY_I_STEROWANIE\vortex_env"
$mask = @{ 'TD3_C' = 0x0C0000; 'TD3_R' = 0x100000; 'SAC_R' = 0x400000 }
function L($m){ Add-Content "$R\20_NARZEDZIA\affinity_guard.log" ((Get-Date -f 'yyyy-MM-dd HH:mm:ss') + ' ' + $m) }
while ($true) {
  $all = @(Get-CimInstance Win32_Process)
  $any = $false
  foreach ($p in $all) {
    $cl = [string]$p.CommandLine
    if ($cl -match 'train_rl\.py\s+\w+\s+(\w+)') {
      $any = $true; $tag = $Matches[1]
      if ($mask.ContainsKey($tag)) {
        try { $g = Get-Process -Id $p.ProcessId -EA Stop
          if ([int64]$g.ProcessorAffinity -ne $mask[$tag]) { L ("{0} {1}: 0x{2:X6} -> 0x{3:X6}" -f $tag,$p.ProcessId,[int64]$g.ProcessorAffinity,$mask[$tag]); $g.ProcessorAffinity = [IntPtr]$mask[$tag]; $g.PriorityClass = 'BelowNormal' } } catch {}
      }
    }
    if ($p.Name -eq 'star-ccm+.exe' -and $cl -match 'encoded-session\s+(\S+)') {
      $any = $true
      try { $sess = [Text.Encoding]::UTF8.GetString([Convert]::FromBase64String($Matches[1])) } catch { $sess = '' }
      if ($sess -match 'strut_calm') {
        try { $g = Get-Process -Id $p.ProcessId -EA Stop
          if ([int64]$g.ProcessorAffinity -ne 0x800000) { L ("strut STAR {0}: 0x{1:X6} -> 0x800000" -f $p.ProcessId,[int64]$g.ProcessorAffinity); $g.ProcessorAffinity = [IntPtr]0x800000 } } catch {}
      }
    }
  }
  if (-not $any) { L 'nic do pilnowania - koniec'; break }
  Start-Sleep 60
}
