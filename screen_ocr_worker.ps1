$ErrorActionPreference = 'Stop'
$ProgressPreference = 'SilentlyContinue'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
try {
    Add-Type -AssemblyName System.Runtime.WindowsRuntime
    $null = [Windows.Storage.StorageFile,Windows.Storage,ContentType=WindowsRuntime]
    $null = [Windows.Graphics.Imaging.BitmapDecoder,Windows.Graphics.Imaging,ContentType=WindowsRuntime]
    $null = [Windows.Media.Ocr.OcrEngine,Windows.Foundation,ContentType=WindowsRuntime]
    $asTask = [System.WindowsRuntimeSystemExtensions].GetMethods() | Where-Object { $_.Name -eq 'AsTask' -and $_.IsGenericMethod -and $_.GetParameters().Count -eq 1 -and $_.GetParameters()[0].ParameterType.Name -eq 'IAsyncOperation`1' } | Select-Object -First 1
    function Await($Operation, [Type]$ResultType) {
        $task = $asTask.MakeGenericMethod($ResultType).Invoke($null, @($Operation))
        $task.Wait()
        $task.Result
    }
    $engine = [Windows.Media.Ocr.OcrEngine]::TryCreateFromUserProfileLanguages()
    if (-not $engine) { throw 'OCR language unavailable' }
    [Console]::WriteLine('{"status":"ready","protocol":1}')
    while ($null -ne ($line = [Console]::ReadLine())) {
        $request = $null
        try {
            $request = $line | ConvertFrom-Json
            if ($request.operation -eq 'close') { break }
            if ($request.operation -ne 'recognize' -or -not ($request.path -is [string])) { throw 'Invalid request' }
            $file = Await ([Windows.Storage.StorageFile]::GetFileFromPathAsync($request.path)) ([Windows.Storage.StorageFile])
            $stream = Await ($file.OpenReadAsync()) ([Windows.Storage.Streams.IRandomAccessStreamWithContentType])
            try {
                $decoder = Await ([Windows.Graphics.Imaging.BitmapDecoder]::CreateAsync($stream)) ([Windows.Graphics.Imaging.BitmapDecoder])
                if ($decoder.PixelWidth -gt [Windows.Media.Ocr.OcrEngine]::MaxImageDimension -or $decoder.PixelHeight -gt [Windows.Media.Ocr.OcrEngine]::MaxImageDimension) { throw 'Image too large' }
                $bitmap = Await ($decoder.GetSoftwareBitmapAsync()) ([Windows.Graphics.Imaging.SoftwareBitmap])
                try {
                    $result = Await ($engine.RecognizeAsync($bitmap)) ([Windows.Media.Ocr.OcrResult])
                    $words = @($result.Lines | ForEach-Object { $_.Words | ForEach-Object {
                        @{text=$_.Text; x=$_.BoundingRect.X; y=$_.BoundingRect.Y; width=$_.BoundingRect.Width; height=$_.BoundingRect.Height}
                    } })
                    @{id=$request.id; status='available'; text=$result.Text; words=$words; language=$engine.RecognizerLanguage.LanguageTag} | ConvertTo-Json -Depth 5 -Compress | ForEach-Object { [Console]::WriteLine($_) }
                } finally { if ($bitmap) { $bitmap.Dispose() } }
            } finally { $stream.Dispose() }
        } catch {
            @{id=$request.id; status='unavailable'; reason='Local OCR could not read this image'} | ConvertTo-Json -Compress | ForEach-Object { [Console]::WriteLine($_) }
        }
    }
} catch {
    [Console]::WriteLine('{"status":"unavailable","reason":"Windows OCR session could not initialize"}')
    exit 1
}
