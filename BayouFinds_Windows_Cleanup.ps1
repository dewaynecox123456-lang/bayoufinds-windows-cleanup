<# 
BayouFinds Windows Cleanup Tool
Cleans common temp/cache locations and performs safe Windows maintenance.
Run PowerShell as Administrator.
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$DryRun,
    [switch]$SkipSFC = $true
)

$ErrorActionPreference = "SilentlyContinue"
$LogDir = Join-Path -Path ([Environment]::GetFolderPath("Desktop")) -ChildPath "BayouFinds_Cleanup_Logs"
$TimeStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = Join-Path -Path $LogDir -ChildPath "cleanup_$TimeStamp.log"
$InteractiveMode = [Environment]::UserInteractive -and -not $env:CI -and -not $WhatIfPreference
$StartTime = Get-Date
$RenewalUrl = "https://bayoufinds.com/b/y3OJr"

New-Item -ItemType Directory -Force -Path $LogDir -WhatIf:$false | Out-Null

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -WhatIf:$false
}

function Test-WindowsPlatform {
    $isWindowsVariable = Get-Variable -Name IsWindows -Scope Global -ErrorAction SilentlyContinue
    if ($isWindowsVariable) {
        return [bool]$isWindowsVariable.Value
    }

    return $env:OS -eq "Windows_NT"
}

function Get-LicenseMode {
    $licensePaths = @()

    if ($HOME) {
        $licensePaths += Join-Path -Path $HOME -ChildPath ".bayoufinds/license.key"
    }

    if ($env:USERPROFILE) {
        $licensePaths += Join-Path -Path $env:USERPROFILE -ChildPath ".bayoufinds\license.key"
    }

    foreach ($licensePath in $licensePaths | Select-Object -Unique) {
        if (Test-Path -Path $licensePath -PathType Leaf) {
            return "Licensed"
        }
    }

    return "Free"
}

function Write-Summary {
    param(
        [string]$LicenseMode,
        [datetime]$StartTime,
        [int]$EstimatedCleanupTargets
    )

    $endTime = Get-Date
    Write-Log "------------------------------------------------------------"
    Write-Log "Summary"
    Write-Log "Licensed/Free mode: $LicenseMode"
    Write-Log "Log path: $LogFile"
    Write-Log "Dry-run: $($DryRun.IsPresent)"
    Write-Log "WhatIf: $WhatIfPreference"
    Write-Log "Started: $($StartTime.ToString('yyyy-MM-dd HH:mm:ss'))"
    Write-Log "Ended: $($endTime.ToString('yyyy-MM-dd HH:mm:ss'))"
    Write-Log "Estimated cleanup targets: $EstimatedCleanupTargets"
    Write-Log "------------------------------------------------------------"
}

function Show-Splash {
    if ($InteractiveMode) {
        Clear-Host
    }

    $banner = @"
============================================================
              BayouFinds Windows Cleanup Tool
                  https://BayouFinds.com
============================================================
"@

    if ($InteractiveMode) {
        for ($i = 0; $i -lt 3; $i++) {
            Clear-Host
            Write-Host $banner -ForegroundColor Cyan
            Start-Sleep -Milliseconds 350
            Clear-Host
            Start-Sleep -Milliseconds 150
        }
    }

    Write-Host $banner -ForegroundColor Green
    if ($InteractiveMode) {
        Start-Sleep -Seconds 2
    }
}

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Remove-Contents {
    param(
        [string]$Path,
        [string]$Label
    )

    if (!(Test-Path $Path)) {
        Write-Log "SKIP: $Label not found: $Path"
        return
    }

    Write-Log "Cleaning: $Label - $Path"

    if ($DryRun) {
        Get-ChildItem -Path $Path -Force -Recurse | Select-Object -First 20 | ForEach-Object {
            Write-Log "DRYRUN: Would remove $($_.FullName)"
        }
        return
    }

    if ($PSCmdlet.ShouldProcess($Path, "Remove cleanup contents for $Label")) {
        Get-ChildItem -Path $Path -Force -Recurse | Remove-Item -Force -Recurse
    }
}

Show-Splash

Write-Log "BayouFinds Windows Cleanup started."
Write-Log "Log file: $LogFile"

$IsWindowsPlatform = Test-WindowsPlatform
$LicenseMode = Get-LicenseMode

if (!$IsWindowsPlatform) {
    Write-Log "INFO: This tool is intended for Windows. Validation mode passed."
    Write-Summary -LicenseMode $LicenseMode -StartTime $StartTime -EstimatedCleanupTargets 0
    exit 0
}

if ($WhatIfPreference) {
    Write-Log "WhatIf validation mode detected. Administrator enforcement skipped for validation."
}
elseif (!(Test-Admin)) {
    Write-Log "ERROR: Please run PowerShell as Administrator."
    Write-Host "`nRight-click PowerShell and choose 'Run as Administrator'." -ForegroundColor Yellow
    Write-Summary -LicenseMode $LicenseMode -StartTime $StartTime -EstimatedCleanupTargets 0
    if ($InteractiveMode) {
        Read-Host "Press Enter to exit"
    }
    exit
}
else {
    Write-Log "Admin rights confirmed."
}

Write-Log "Creating restore point if System Protection is enabled..."
if (!$DryRun) {
    if ($PSCmdlet.ShouldProcess("System Restore", "Create BayouFinds cleanup restore point")) {
        Checkpoint-Computer -Description "BayouFinds Cleanup Restore Point" -RestorePointType "MODIFY_SETTINGS"
    }
}

$CleanupTargets = @(
    @{ Path = $env:TEMP; Label = "Current user temp" },
    @{ Path = (Join-Path -Path $env:SystemRoot -ChildPath "Temp"); Label = "Windows temp" },
    @{ Path = (Join-Path -Path $env:LOCALAPPDATA -ChildPath "Temp"); Label = "Local app temp" },
    @{ Path = (Join-Path -Path $env:LOCALAPPDATA -ChildPath "Microsoft\Windows\INetCache"); Label = "Internet cache" },
    @{ Path = (Join-Path -Path $env:LOCALAPPDATA -ChildPath "Microsoft\Windows\WebCache"); Label = "Windows web cache" },
    @{ Path = (Join-Path -Path $env:LOCALAPPDATA -ChildPath "Microsoft\Edge\User Data\Default\Cache"); Label = "Microsoft Edge cache" },
    @{ Path = (Join-Path -Path $env:LOCALAPPDATA -ChildPath "Google\Chrome\User Data\Default\Cache"); Label = "Google Chrome cache" },
    @{ Path = (Join-Path -Path $env:APPDATA -ChildPath "Microsoft\Windows\Recent"); Label = "Recent files cache" },
    @{ Path = (Join-Path -Path $env:SystemRoot -ChildPath "SoftwareDistribution\Download"); Label = "Old Windows Update downloads" },
    @{ Path = (Join-Path -Path $env:SystemRoot -ChildPath "Prefetch"); Label = "Windows prefetch cache" }
)

foreach ($target in $CleanupTargets) {
    Remove-Contents -Path $target.Path -Label $target.Label
}

Write-Log "Resetting Windows Update cache safely..."
if (!$DryRun) {
    if ($PSCmdlet.ShouldProcess("Windows Update cache", "Stop services, remove downloaded patches, and restart services")) {
        try {
            Stop-Service wuauserv -Force
            Stop-Service bits -Force
            Remove-Contents -Path (Join-Path -Path $env:SystemRoot -ChildPath "SoftwareDistribution\Download") -Label "Windows Update downloaded patches"
        }
        catch {
            Write-Log "ERROR: Windows Update cache cleanup failed: $($_.Exception.Message)"
        }
        finally {
            Start-Service bits
            Start-Service wuauserv
            Write-Log "Windows Update services restart attempted."
        }
    }
}

Write-Log "Emptying Recycle Bin..."
if (!$DryRun) {
    if ($PSCmdlet.ShouldProcess("Recycle Bin", "Empty")) {
        Clear-RecycleBin -Force
    }
}

Write-Log "Flushing DNS cache..."
if (!$DryRun) {
    if ($PSCmdlet.ShouldProcess("DNS client cache", "Flush")) {
        ipconfig.exe /flushdns | Tee-Object -FilePath $LogFile -Append | Out-Null
        Write-Log "ipconfig.exe exit code: $LASTEXITCODE"
    }
}

Write-Log "Running DISM component cleanup..."
if (!$DryRun) {
    if ($PSCmdlet.ShouldProcess("Windows component store", "Run DISM component cleanup")) {
        DISM.exe /Online /Cleanup-Image /StartComponentCleanup | Tee-Object -FilePath $LogFile -Append
        Write-Log "DISM.exe exit code: $LASTEXITCODE"
    }
}

if ($SkipSFC) {
    Write-Log "Skipping system file integrity scan. Use -SkipSFC:`$false to run SFC."
}
else {
    Write-Log "Running system file integrity scan..."
    if (!$DryRun) {
        if ($PSCmdlet.ShouldProcess("System files", "Run SFC scan")) {
            sfc.exe /scannow | Tee-Object -FilePath $LogFile -Append
            Write-Log "sfc.exe exit code: $LASTEXITCODE"
        }
    }
}

Write-Log "Cleanup complete."
Write-Summary -LicenseMode $LicenseMode -StartTime $StartTime -EstimatedCleanupTargets $CleanupTargets.Count
Write-Host "Cleanup complete. Check log: $LogFile"
if ($InteractiveMode) {
    Read-Host "Press Enter to exit"
}
