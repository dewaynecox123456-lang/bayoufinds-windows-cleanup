<# 
BayouFinds Windows Cleanup Tool
Cleans common temp/cache locations and performs safe Windows maintenance.
Run PowerShell as Administrator.
#>

param(
    [switch]$DryRun
)

$ErrorActionPreference = "SilentlyContinue"
$LogDir = "$env:USERPROFILE\Desktop\BayouFinds_Cleanup_Logs"
$TimeStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogFile = "$LogDir\cleanup_$TimeStamp.log"

New-Item -ItemType Directory -Force -Path $LogDir | Out-Null

function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line
}

function Show-Splash {
    Clear-Host
    $banner = @"
██████╗  █████╗ ██╗   ██╗ ██████╗ ██╗   ██╗███████╗██╗███╗   ██╗██████╗ ███████╗
██╔══██╗██╔══██╗╚██╗ ██╔╝██╔═══██╗██║   ██║██╔════╝██║████╗  ██║██╔══██╗██╔════╝
██████╔╝███████║ ╚████╔╝ ██║   ██║██║   ██║█████╗  ██║██╔██╗ ██║██║  ██║███████╗
██╔══██╗██╔══██║  ╚██╔╝  ██║   ██║██║   ██║██╔══╝  ██║██║╚██╗██║██║  ██║╚════██║
██████╔╝██║  ██║   ██║   ╚██████╔╝╚██████╔╝██║     ██║██║ ╚████║██████╔╝███████║
╚═════╝ ╚═╝  ╚═╝   ╚═╝    ╚═════╝  ╚═════╝ ╚═╝     ╚═╝╚═╝  ╚═══╝╚═════╝ ╚══════╝

                         https://BayouFinds.com
"@

    for ($i = 0; $i -lt 3; $i++) {
        Clear-Host
        Write-Host $banner -ForegroundColor Cyan
        Start-Sleep -Milliseconds 350
        Clear-Host
        Start-Sleep -Milliseconds 150
    }

    Write-Host $banner -ForegroundColor Green
    Start-Sleep -Seconds 2
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

    Get-ChildItem -Path $Path -Force -Recurse | Remove-Item -Force -Recurse
}

Show-Splash

Write-Log "BayouFinds Windows Cleanup started."
Write-Log "Log file: $LogFile"

if (!(Test-Admin)) {
    Write-Log "ERROR: Please run PowerShell as Administrator."
    Write-Host "`nRight-click PowerShell and choose 'Run as Administrator'." -ForegroundColor Yellow
    pause
    exit
}

Write-Log "Admin rights confirmed."

Write-Log "Creating restore point if System Protection is enabled..."
if (!$DryRun) {
    Checkpoint-Computer -Description "BayouFinds Cleanup Restore Point" -RestorePointType "MODIFY_SETTINGS"
}

$CleanupTargets = @(
    @{ Path = "$env:TEMP"; Label = "Current user temp" },
    @{ Path = "C:\Windows\Temp"; Label = "Windows temp" },
    @{ Path = "$env:LOCALAPPDATA\Temp"; Label = "Local app temp" },
    @{ Path = "$env:LOCALAPPDATA\Microsoft\Windows\INetCache"; Label = "Internet cache" },
    @{ Path = "$env:LOCALAPPDATA\Microsoft\Windows\WebCache"; Label = "Windows web cache" },
    @{ Path = "$env:LOCALAPPDATA\Microsoft\Edge\User Data\Default\Cache"; Label = "Microsoft Edge cache" },
    @{ Path = "$env:LOCALAPPDATA\Google\Chrome\User Data\Default\Cache"; Label = "Google Chrome cache" },
    @{ Path = "$env:APPDATA\Microsoft\Windows\Recent"; Label = "Recent files cache" },
    @{ Path = "C:\Windows\SoftwareDistribution\Download"; Label = "Old Windows Update downloads" },
    @{ Path = "C:\Windows\Prefetch"; Label = "Windows prefetch cache" }
)

foreach ($target in $CleanupTargets) {
    Remove-Contents -Path $target.Path -Label $target.Label
}

Write-Log "Resetting Windows Update cache safely..."
if (!$DryRun) {
    Stop-Service wuauserv -Force
    Stop-Service bits -Force
    Remove-Contents -Path "C:\Windows\SoftwareDistribution\Download" -Label "Windows Update downloaded patches"
    Start-Service bits
    Start-Service wuauserv
}

Write-Log "Emptying Recycle Bin..."
if (!$DryRun) {
    Clear-RecycleBin -Force
}

Write-Log "Flushing DNS cache..."
if (!$DryRun) {
    ipconfig /flushdns | Out-Null
}

Write-Log "Running DISM component cleanup..."
if (!$DryRun) {
    DISM.exe /Online /Cleanup-Image /StartComponentCleanup | Tee-Object -FilePath $LogFile -Append
}

Write-Log "Running system file integrity scan..."
if (!$DryRun) {
    sfc /scannow | Tee-Object -FilePath $LogFile -Append
}

Write-Log "Cleanup complete."
Write-Host "Cleanup complete. Check log: $LogFile"
pause
