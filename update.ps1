# 인하대 특강 AR 갤러리 자동 갱신(11/4 작업 스케줄러가 5분마다 부른다)
#   연수용 제출 폴더를 다시 읽어 works/·index.html 을 만들고, 바뀐 것이 있을 때만 커밋·푸시한다.
#   기록: update.log (git 제외)
$ErrorActionPreference = 'Continue'
$env:PYTHONIOENCODING = 'utf-8'
$OutputEncoding = [Console]::OutputEncoding = New-Object System.Text.UTF8Encoding $false   # 11/4 PowerShell 5 에서 커밋 메시지·기록 한글이 깨지던 것
Set-Location -LiteralPath $PSScriptRoot
$log = Join-Path $PSScriptRoot 'update.log'
function Log($m) { Add-Content -LiteralPath $log -Value ("{0:MM-dd HH:mm:ss}  {1}" -f (Get-Date), $m) -Encoding utf8 }

$lock = Join-Path $PSScriptRoot '.update.lock'
if ((Test-Path $lock) -and ((Get-Date) - (Get-Item $lock).LastWriteTime).TotalMinutes -lt 15) { Log '앞 갱신이 아직 도는 중이라 건너뜀'; exit }
Set-Content -LiteralPath $lock -Value $PID
try {
  $out = & python build.py 2>&1 | Out-String
  Log ($out.Trim() -split "`n" | Select-Object -First 1)
  $changed = (& git status --porcelain) -ne $null
  if ($changed) {
    & git add -A 2>&1 | Out-Null
    & git commit -q -m ("작품 갱신 {0:MM-dd HH:mm}" -f (Get-Date)) 2>&1 | Out-Null
    $p = & git push -q 2>&1 | Out-String
    if ($LASTEXITCODE -eq 0) { Log '바뀐 작품 올림(1~2분 뒤 사이트 반영)' } else { Log ('푸시 실패: ' + $p.Trim()) }
  } else { Log '바뀐 것 없음' }
} catch { Log ('오류: ' + $_.Exception.Message) }
finally { Remove-Item -LiteralPath $lock -ErrorAction SilentlyContinue }
