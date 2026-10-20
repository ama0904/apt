param([string]$ListFile, [string]$OutFile)
Add-Type -AssemblyName System.Runtime.WindowsRuntime
[Windows.Media.Ocr.OcrEngine, Windows.Foundation, ContentType=WindowsRuntime] | Out-Null
[Windows.Graphics.Imaging.BitmapDecoder, Windows.Graphics.Imaging, ContentType=WindowsRuntime] | Out-Null
[Windows.Storage.Streams.InMemoryRandomAccessStream, Windows.Storage.Streams, ContentType=WindowsRuntime] | Out-Null
[Windows.Globalization.Language, Windows.Globalization, ContentType=WindowsRuntime] | Out-Null

$asTaskGeneric = @([System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' })[0]
function Await($WinRtTask, $ResultType) {
  $asTask = $asTaskGeneric.MakeGenericMethod($ResultType)
  $netTask = $asTask.Invoke($null, @($WinRtTask))
  $netTask.Wait(-1) | Out-Null
  $netTask.Result
}
$lang = New-Object Windows.Globalization.Language 'zh-Hant-TW'
$engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromLanguage($lang)
if ($null -eq $engine) { throw "no zh-Hant-TW OCR engine" }
$results = New-Object System.Collections.ArrayList
foreach ($raw in Get-Content $ListFile) {
  $path = $raw.ToString().Trim()
  if (-not (Test-Path -LiteralPath $path)) { continue }
  try {
    $bytes = [System.IO.File]::ReadAllBytes($path)
    $ms = New-Object System.IO.MemoryStream(,$bytes)
    $ras = [System.IO.WindowsRuntimeStreamExtensions]::AsRandomAccessStream($ms)
    $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($ras)) ([Windows.Graphics.Imaging.BitmapDecoder])
    $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
    $ocr = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
    $lines = New-Object System.Collections.ArrayList
    foreach ($line in $ocr.Lines) {
      $x1 = 1e9; $y1 = 1e9; $x2 = 0; $y2 = 0
      foreach ($w in $line.Words) { $r = $w.BoundingRect; if ($r.X -lt $x1) { $x1 = $r.X }; if ($r.Y -lt $y1) { $y1 = $r.Y }; if (($r.X + $r.Width) -gt $x2) { $x2 = $r.X + $r.Width }; if (($r.Y + $r.Height) -gt $y2) { $y2 = $r.Y + $r.Height } }
      [void]$lines.Add([pscustomobject]@{ text = $line.Text; x = [int]$x1; y = [int]$y1; w = [int]($x2 - $x1); h = [int]($y2 - $y1) })
    }
    [void]$results.Add([pscustomobject]@{ path = $path; width = $bitmap.PixelWidth; height = $bitmap.PixelHeight; lines = $lines.ToArray() })
    $ms.Dispose()
  } catch {
    $e = $_.Exception
    if ($e.InnerException) { $e = $e.InnerException }
    [void]$results.Add([pscustomobject]@{ path = $path; error = $e.Message; lines = @() })
  }
}
ConvertTo-Json -InputObject $results.ToArray() -Depth 5 | Out-File -Encoding utf8 $OutFile
Write-Output ("ocr done: " + $results.Count)
