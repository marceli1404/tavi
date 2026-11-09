#Requires -Version 5.1
<#
.SYNOPSIS
Inspect or explicitly stop a leftover Codex Windows Computer Use capture helper.
.DESCRIPTION
Default is read-only. This is an opt-in workaround for a Codex desktop
capture-lifecycle bug, not an automatic idle detector and not an upstream fix.
Only use -Stop after checking that ALL Codex Computer Use turns are finished.
Does not change Windows capture permissions or touch other helper processes.
.EXAMPLE
.\scripts\fix-codex-yellow-border.ps1
.EXAMPLE
.\scripts\fix-codex-yellow-border.ps1 -Stop -NoActiveComputerUse
.EXAMPLE
.\scripts\fix-codex-yellow-border.ps1 -Stop -NoActiveComputerUse -ProcessId 34140
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [switch] $Stop,
    [switch] $NoActiveComputerUse,
    [ValidateRange(1, 2147483647)]
    [int] $ProcessId = 0
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if ($Stop -and -not $NoActiveComputerUse) {
    throw 'Refusing to stop any helper. First verify ALL Codex Computer Use tasks are finished, then pass -NoActiveComputerUse.'
}

function Get-CodexHelperEvidence {
    param([Parameter(Mandatory = $true)] $Candidate)

    $executable = [string] $Candidate.ExecutablePath
    $sameName = (-not [string]::IsNullOrWhiteSpace($executable)) -and
        ([IO.Path]::GetFileName($executable) -ieq 'codex-computer-use.exe')
    $parentName = 'not-running-or-inaccessible'
    $parentOkay = $true
    if ($Candidate.ParentProcessId -gt 0) {
        $parent = Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f [int] $Candidate.ParentProcessId) -ErrorAction SilentlyContinue
        if ($null -ne $parent) {
            $parentName = [string] $parent.Name
            $parentOkay = ($parentName -ieq 'ChatGPT.exe') -or ($parentName -ieq 'Codex.exe')
        }
    }

    $signature = 'unavailable'
    $officialSignature = $false
    if ($sameName) {
        try {
            $sig = Get-AuthenticodeSignature -LiteralPath $executable -ErrorAction Stop
            $signature = [string] $sig.Status
            $signedByOpenAI = ($null -ne $sig.SignerCertificate) -and
                ([string] $sig.SignerCertificate.Subject -match '(?i)OpenAI')
            # A valid Microsoft Store package is also an acceptable origin.
            $fromCodexPackage = $executable -match '(?i)\\WindowsApps\\OpenAI\.Codex_'
            $officialSignature = ($sig.Status -eq 'Valid') -and ($signedByOpenAI -or $fromCodexPackage)
        } catch {
            $signature = 'unavailable'
        }
    }

    [pscustomobject]@{
        Id = [int] $Candidate.ProcessId
        Started = $Candidate.CreationDate
        Parent = $parentName
        Signature = $signature
        Eligible = [bool] ($sameName -and $parentOkay -and $officialSignature)
        ExecutablePath = $executable
        ParentId = [int] $Candidate.ParentProcessId
    }
}

$helpers = @(Get-CimInstance Win32_Process -Filter "Name = 'codex-computer-use.exe'")
if ($ProcessId -ne 0) {
    $helpers = @($helpers | Where-Object { [int] $_.ProcessId -eq $ProcessId })
}
if ($helpers.Count -eq 0) {
    Write-Output 'No matching codex-computer-use.exe helper is running. Nothing to stop.'
    return
}

$evidence = @($helpers | ForEach-Object { Get-CodexHelperEvidence $_ })
$evidence | Select-Object Id, Started, Parent, Signature, Eligible | Format-Table -AutoSize | Out-Host

if (-not $Stop) {
    Write-Output 'Inspection only. Helper presence does not prove it is idle. To stop it, verify no Computer Use task is active and pass -Stop -NoActiveComputerUse.'
    return
}
if ($helpers.Count -ne 1) {
    throw 'Multiple helpers exist. Re-run with -ProcessId to choose the exact helper; never stop all helpers blindly.'
}
if (-not $evidence[0].Eligible) {
    throw 'Refusing to stop an unverified helper (invalid path/signature or unexpected parent). Use Task Manager after manually verifying its identity.'
}

$target = $evidence[0]
if ($PSCmdlet.ShouldProcess("codex-computer-use.exe PID $($target.Id)", 'Terminate confirmed unused capture helper')) {
    # Recheck PID, executable, parent and creation time to avoid a stale or recycled PID.
    $current = Get-CimInstance Win32_Process -Filter ("ProcessId = {0}" -f $target.Id)
    if ($null -eq $current -or
        $current.Name -ine 'codex-computer-use.exe' -or
        [string] $current.ExecutablePath -cne $target.ExecutablePath -or
        [int] $current.ParentProcessId -ne $target.ParentId -or
        $current.CreationDate -ne $target.Started) {
        throw 'Helper changed while waiting for confirmation; nothing was stopped.'
    }
    $newEvidence = Get-CodexHelperEvidence $current
    if (-not $newEvidence.Eligible) {
        throw 'Fresh helper verification failed; nothing was stopped.'
    }
    $process = Get-Process -Id $target.Id -ErrorAction Stop
    Stop-Process -InputObject $process -ErrorAction Stop
    Write-Output "Stopped verified helper PID $($target.Id). Recheck the yellow border. Codex should spawn a new helper next time Computer Use is needed."
}
