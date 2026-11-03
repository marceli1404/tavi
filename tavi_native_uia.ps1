# Read-only, foreground-window-only Microsoft UI Automation observation worker.
# Windows PowerShell 5.1/.NET Framework; reads "capture" JSON lines, emits JSON.
# No input injection, InvokePattern, clicks, keypresses, values, or screenshots.
$ErrorActionPreference = 'Stop'
[Console]::InputEncoding = New-Object System.Text.UTF8Encoding($false)
[Console]::OutputEncoding = New-Object System.Text.UTF8Encoding($false)
Add-Type -AssemblyName UIAutomationClient
Add-Type -AssemblyName UIAutomationTypes
Add-Type -TypeDefinition @'
using System;
using System.Runtime.InteropServices;
public static class TaviForeground {
  [StructLayout(LayoutKind.Sequential)]
  public struct RECT {
    public int Left; public int Top; public int Right; public int Bottom;
  }
  [DllImport("user32.dll")] public static extern IntPtr GetForegroundWindow();
  [DllImport("user32.dll")] public static extern bool GetWindowRect(IntPtr hwnd, out RECT rect);
  [DllImport("user32.dll")] public static extern uint GetWindowThreadProcessId(IntPtr hwnd, out uint processId);
}
'@

function Read-Foreground {
    $hwnd = [TaviForeground]::GetForegroundWindow()
    if ($hwnd -eq [IntPtr]::Zero) { throw 'No interactive foreground window' }
    $pidValue = [uint32]0
    [void][TaviForeground]::GetWindowThreadProcessId($hwnd, [ref]$pidValue)
    $rect = New-Object TaviForeground+RECT
    if (-not [TaviForeground]::GetWindowRect($hwnd, [ref]$rect)) {
        throw 'Unable to read window geometry'
    }
    $width = $rect.Right - $rect.Left
    $height = $rect.Bottom - $rect.Top
    if ($pidValue -eq 0 -or $width -le 0 -or $height -le 0 -or
        $width -gt 16384 -or $height -gt 16384) {
        throw 'Invalid foreground window'
    }
    return @{
        hwnd = [long]$hwnd.ToInt64()
        process_id = [int]$pidValue
        rect = @([int]$rect.Left,[int]$rect.Top,[int]$width,[int]$height)
    }
}

$roles = @{
    'ControlType.Button'='button'
    'ControlType.Hyperlink'='link'
    'ControlType.TabItem'='tab'
    'ControlType.CheckBox'='checkbox'
    'ControlType.RadioButton'='radio'
    'ControlType.MenuItem'='menuitem'
    'ControlType.Edit'='textbox'
    'ControlType.ComboBox'='combobox'
}
$groups = @('ControlType.Group','ControlType.Pane','ControlType.ToolBar',
            'ControlType.Tab','ControlType.Menu','ControlType.Window')
$walker = [System.Windows.Automation.TreeWalker]::ControlViewWalker

function Read-WindowControls {
    param([int]$MaximumNodes)
    $start = Read-Foreground
    $root = [System.Windows.Automation.AutomationElement]::FromHandle([IntPtr]$start.hwnd)
    if ($null -eq $root) { throw 'Foreground window has no UI Automation root' }
    $queue = New-Object 'System.Collections.Generic.Queue[object]'
    $first = $walker.GetFirstChild($root)
    if ($null -ne $first) { $queue.Enqueue(@{ element=$first; depth=1; context='' }) }
    $controls = New-Object 'System.Collections.Generic.List[object]'
    $ids = New-Object 'System.Collections.Generic.HashSet[string]'
    $visited = 0
    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    while ($queue.Count -gt 0) {
        if ($stopwatch.ElapsedMilliseconds -gt 3000) { throw 'UI Automation traversal exceeded time limit' }
        if (++$visited -gt $MaximumNodes) { throw 'UI Automation node budget exceeded' }
        $item = $queue.Dequeue()
        $element = $item.element
        $depth = [int]$item.depth
        $context = [string]$item.context
        try {
            $info = $element.Current
            # Do not inspect password controls or any descendants of them.
            if ($info.IsPassword) { continue }
            $type = [string]$info.ControlType.ProgrammaticName
            $name = [string]$info.Name
            if ($name.Length -gt 160) { $name = $name.Substring(0,160) }
            $name = [regex]::Replace($name,'\s+',' ').Trim()
            if ($groups -contains $type -and $name.Length -gt 0) {
                $context = $name.Substring(0,[Math]::Min(100,$name.Length))
            }
            if ($roles.ContainsKey($type) -and $name.Length -gt 0) {
                $bounds = $info.BoundingRectangle
                $x = [double]$bounds.X - $start.rect[0]
                $y = [double]$bounds.Y - $start.rect[1]
                $width = [double]$bounds.Width
                $height = [double]$bounds.Height
                if (-not ([Double]::IsNaN($x) -or [Double]::IsInfinity($x) -or
                    [Double]::IsNaN($y) -or [Double]::IsInfinity($y) -or
                    [Double]::IsNaN($width) -or [Double]::IsInfinity($width) -or
                    [Double]::IsNaN($height) -or [Double]::IsInfinity($height))) {
                    $rid = $element.GetRuntimeId()
                    if ($null -eq $rid -or $rid.Length -eq 0) {
                        throw 'UI Automation element lacks a runtime identity'
                    }
                    $id = 'uia-' + [string]::Join('-', [string[]]$rid)
                    if (-not $ids.Add($id)) { throw 'Duplicate UI Automation runtime identity' }
                    $controls.Add(@{
                        id=$id
                        label=$name
                        role=$roles[$type]
                        context=$context
                        visible=(-not [bool]$info.IsOffscreen)
                        enabled=[bool]$info.IsEnabled
                        bounds=@($x,$y,$width,$height)
                    })
                }
            }
            if ($depth -lt 16) {
                $child = $walker.GetFirstChild($element)
                if ($null -ne $child) {
                    $queue.Enqueue(@{element=$child;depth=$depth+1;context=$context})
                }
            }
            # Keep all siblings, but never traverse the root's siblings.
            $sibling = $walker.GetNextSibling($element)
            if ($null -ne $sibling) {
                $queue.Enqueue(@{element=$sibling;depth=$depth;context=[string]$item.context})
            }
        } catch [System.Windows.Automation.ElementNotAvailableException] {
            throw 'UI Automation tree changed; recapture required'
        }
    }
    $after = Read-Foreground
    if ($after.hwnd -ne $start.hwnd -or
        $after.process_id -ne $start.process_id -or
        ([string]::Join(',', $after.rect) -ne [string]::Join(',', $start.rect))) {
        throw 'Foreground window changed during observation'
    }
    return @{
        status='captured'
        window_binding=$start
        viewport=@([int]$start.rect[2],[int]$start.rect[3])
        controls=@($controls.ToArray())
        visited_nodes=$visited
    }
}

while ($null -ne ($line = [Console]::ReadLine())) {
    try {
        if ($line.Length -gt 1024) { throw 'Worker request too large' }
        $request = ConvertFrom-Json -InputObject $line
        if ($null -eq $request -or $request.op -cne 'capture' -or
            @($request.PSObject.Properties).Count -ne 1) {
            throw 'Only capture observations are supported'
        }
        $result = Read-WindowControls -MaximumNodes 1600
        [Console]::Out.WriteLine((ConvertTo-Json -InputObject $result -Depth 6 -Compress))
    } catch {
        # Never echo OS/UI text or internal error messages to a planner.
        [Console]::Out.WriteLine('{"status":"error","error":"native_observation_unavailable"}')
    }
}
