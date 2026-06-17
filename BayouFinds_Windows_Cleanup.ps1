<# 
BayouFinds Windows Cleanup Tool
Cleans common temp/cache locations and performs safe Windows maintenance.
Run PowerShell as Administrator.
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$DryRun,
    [switch]$SkipSFC = $true,
    [ValidateSet("Preview", "SafeCleanup", "LicenseCheck", "BackupBookmarks")]
    [string]$Mode,
    [switch]$NoMenu,
    [string]$OutputDir,
    [string]$SessionId = ([guid]::NewGuid().ToString())
)

#region Configuration
$ErrorActionPreference = "SilentlyContinue"
$ToolVersion = "1.1.0"
if ($OutputDir) {
    $LogDir = $OutputDir
}
else {
    $LogDir = Join-Path -Path ([Environment]::GetFolderPath("Desktop")) -ChildPath "BayouFinds_Cleanup_Logs"
}
$TimeStamp = Get-Date -Format "yyyyMMdd_HHmmss"
$SafeSessionId = $SessionId -replace '[^\w-]', '_'
$LogFile = Join-Path -Path $LogDir -ChildPath "cleanup_${TimeStamp}_${SafeSessionId}.log"
$HtmlReport = Join-Path -Path $LogDir -ChildPath "cleanup_report_${TimeStamp}_${SafeSessionId}.html"
$JsonReport = Join-Path -Path $LogDir -ChildPath "cleanup_report_${TimeStamp}_${SafeSessionId}.json"
$BrowserBackupDir = Join-Path -Path (Join-Path -Path $LogDir -ChildPath "Browser_Backups") -ChildPath $SafeSessionId
$InteractiveMode = [Environment]::UserInteractive -and -not $env:CI -and -not $WhatIfPreference
$StartTime = Get-Date
$RenewalUrl = "https://bayoufinds.com/b/y3OJr"
$script:EffectiveDryRun = $DryRun.IsPresent
$script:CleanupReport = $null
$script:PendingReportNotes = @()

New-Item -ItemType Directory -Force -Path $LogDir -WhatIf:$false | Out-Null
#endregion Configuration

#region Logging and reporting
function Write-Log {
    param([string]$Message)
    $line = "$(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')  $Message"
    Write-Host $line
    Add-Content -Path $LogFile -Value $line -WhatIf:$false
}

function New-CleanupReportModel {
    param(
        [object]$LicenseInfo,
        [string]$RunMode
    )

    return [ordered]@{
        ToolVersion = $ToolVersion
        SessionId = $SessionId
        RunMode = $RunMode
        ComputerName = $env:COMPUTERNAME
        Username = $env:USERNAME
        StartedAt = $StartTime.ToString("o")
        EndedAt = $null
        DryRun = $script:EffectiveDryRun
        WhatIf = [bool]$WhatIfPreference
        License = [ordered]@{
            Mode = $LicenseInfo.Mode
            Source = $LicenseInfo.Source
            Path = $LicenseInfo.Path
            Message = $LicenseInfo.Message
            Product = $LicenseInfo.Product
            ExpiresAt = $LicenseInfo.ExpiresAt
        }
        Paths = [ordered]@{
            Log = $LogFile
            HtmlReport = $HtmlReport
            JsonReport = $JsonReport
            BrowserBackupDir = $BrowserBackupDir
        }
        CleanupTargetsEstimated = 0
        CleanupCategoriesProcessed = @()
        CleanupCategories = @()
        BrowserBackups = @()
        ItemsSkipped = @()
        Notes = @($script:PendingReportNotes)
    }
}

function Add-ReportCategory {
    param([string]$Label)

    if ($script:CleanupReport -and $Label) {
        $script:CleanupReport.CleanupCategoriesProcessed += $Label
    }
}

function Add-ReportSkippedItem {
    param(
        [string]$Label,
        [string]$Path,
        [string]$Reason
    )

    if ($script:CleanupReport) {
        $script:CleanupReport.ItemsSkipped += [ordered]@{
            Label = $Label
            Path = $Path
            Reason = $Reason
        }
    }
}

function Add-ReportNote {
    param([string]$Message)

    if ($script:CleanupReport -and $Message) {
        $script:CleanupReport.Notes += $Message
    }
    elseif ($Message) {
        $script:PendingReportNotes += $Message
    }
}

function Add-ReportCleanupCategory {
    param([object]$Category)

    if ($script:CleanupReport -and $Category) {
        $script:CleanupReport.CleanupCategories += $Category
    }
}

function Add-ReportBrowserBackup {
    param([object]$BackupResult)

    if ($script:CleanupReport -and $BackupResult) {
        $script:CleanupReport.BrowserBackups += $BackupResult
    }
}

function Write-CleanupJsonReport {
    if (!$script:CleanupReport) {
        return
    }

    $script:CleanupReport.EndedAt = (Get-Date).ToString("o")
    $script:CleanupReport.DryRun = $script:EffectiveDryRun
    $script:CleanupReport | ConvertTo-Json -Depth 8 | Set-Content -Path $JsonReport -Encoding UTF8 -WhatIf:$false
    Write-Log "JSON report saved: $JsonReport"
}

function Write-HtmlReport {
    param(
        [string]$LicenseMode,
        [datetime]$StartTime,
        [int]$EstimatedCleanupTargets
    )

    $endTime = Get-Date
    $computerName = $env:COMPUTERNAME
    $userName = $env:USERNAME

    $html = @"
<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>BayouFinds Windows Cleanup Report</title>
<style>
body { font-family: Arial, sans-serif; margin: 32px; background: #f6f7f9; color: #222; }
.card { background: white; border-radius: 12px; padding: 24px; max-width: 900px; box-shadow: 0 2px 12px rgba(0,0,0,.08); }
h1 { margin-top: 0; }
.badge { display: inline-block; padding: 6px 10px; border-radius: 999px; background: #e8f0fe; }
table { border-collapse: collapse; width: 100%; margin-top: 16px; }
td { border-bottom: 1px solid #ddd; padding: 10px; }
.footer { margin-top: 24px; font-size: 12px; color: #666; }
</style>
</head>
<body>
<div class="card">
<h1>BayouFinds Windows Cleanup Report</h1>
<p class="badge">$LicenseMode</p>

<table>
<tr><td><strong>Tool Version</strong></td><td>$ToolVersion</td></tr>
<tr><td><strong>Session ID</strong></td><td>$SessionId</td></tr>
<tr><td><strong>Computer</strong></td><td>$computerName</td></tr>
<tr><td><strong>User</strong></td><td>$userName</td></tr>
<tr><td><strong>Started</strong></td><td>$($StartTime.ToString('yyyy-MM-dd HH:mm:ss'))</td></tr>
<tr><td><strong>Ended</strong></td><td>$($endTime.ToString('yyyy-MM-dd HH:mm:ss'))</td></tr>
<tr><td><strong>Estimated Cleanup Targets</strong></td><td>$EstimatedCleanupTargets</td></tr>
<tr><td><strong>Log File</strong></td><td>$LogFile</td></tr>
<tr><td><strong>JSON Report</strong></td><td>$JsonReport</td></tr>
<tr><td><strong>Browser Bookmark Backups</strong></td><td>$BrowserBackupDir</td></tr>
</table>

<h2>Output Location</h2>
<p>Your cleanup logs and reports are saved here:</p>
<p><strong>$LogDir</strong></p>

<h2>Notes</h2>
<p>This report confirms the tool ran and generated a cleanup session log.</p>
<p>Browser bookmark backup only copies bookmark files. Cookies, passwords, browsing history, and extensions are not touched.</p>

<div class="footer">
Generated by BayouFinds Windows Cleanup Tool<br>
https://BayouFinds.com
</div>
</div>
</body>
</html>
"@

    Set-Content -Path $HtmlReport -Value $html -Encoding UTF8 -WhatIf:$false
    Write-Log "HTML report saved: $HtmlReport"

    if ($InteractiveMode -and !$NoMenu -and (Test-Path -Path $HtmlReport)) {
        Start-Process $HtmlReport
    }
}

function Write-Summary {
    param(
        [string]$LicenseMode,
        [datetime]$StartTime,
        [int]$EstimatedCleanupTargets
    )

    $endTime = Get-Date
    if ($script:CleanupReport) {
        $script:CleanupReport.CleanupTargetsEstimated = $EstimatedCleanupTargets
    }

    Write-Log "------------------------------------------------------------"
    Write-Log "Summary"
    Write-Log "Tool version: $ToolVersion"
    Write-Log "Session ID: $SessionId"
    Write-Log "License mode: $LicenseMode"
    Write-Log "Log path: $LogFile"
    Write-Log "JSON report path: $JsonReport"
    Write-Log "Dry-run: $script:EffectiveDryRun"
    Write-Log "WhatIf: $WhatIfPreference"
    Write-Log "Started: $($StartTime.ToString('yyyy-MM-dd HH:mm:ss'))"
    Write-Log "Ended: $($endTime.ToString('yyyy-MM-dd HH:mm:ss'))"
    Write-Log "Estimated cleanup targets: $EstimatedCleanupTargets"
    Write-CleanupJsonReport
    Write-HtmlReport -LicenseMode $LicenseMode -StartTime $StartTime -EstimatedCleanupTargets $EstimatedCleanupTargets
    Write-Log "HTML report: $HtmlReport"
    Write-Log "------------------------------------------------------------"
}
#endregion Logging and reporting

#region License
function Get-LicenseCandidatePaths {
    $paths = @()

    if ($env:USERPROFILE) {
        $paths += [ordered]@{
            Path = (Join-Path -Path $env:USERPROFILE -ChildPath ".bayoufinds\license.json")
            Format = "json"
        }
    }

    if ($HOME) {
        $paths += [ordered]@{
            Path = (Join-Path -Path $HOME -ChildPath ".bayoufinds/license.json")
            Format = "json"
        }
    }

    if ($env:USERPROFILE) {
        $paths += [ordered]@{
            Path = (Join-Path -Path $env:USERPROFILE -ChildPath ".bayoufinds\license.key")
            Format = "legacy-key"
        }
    }

    if ($HOME) {
        $paths += [ordered]@{
            Path = (Join-Path -Path $HOME -ChildPath ".bayoufinds/license.key")
            Format = "legacy-key"
        }
    }

    $seen = @{}
    $uniquePaths = @()
    foreach ($candidate in $paths) {
        $key = "$($candidate.Path)|$($candidate.Format)"
        if (!$seen.ContainsKey($key)) {
            $seen[$key] = $true
            $uniquePaths += $candidate
        }
    }

    return $uniquePaths
}

function New-LicenseInfo {
    param(
        [string]$Mode,
        [string]$Source,
        [string]$Path,
        [string]$Message,
        [string]$Product = $null,
        [string]$ExpiresAt = $null
    )

    return [pscustomobject]@{
        Mode = $Mode
        Source = $Source
        Path = $Path
        Message = $Message
        Product = $Product
        ExpiresAt = $ExpiresAt
    }
}

function Test-LicenseJson {
    param([string]$Path)

    try {
        $license = Get-Content -Path $Path -Raw | ConvertFrom-Json
    }
    catch {
        return New-LicenseInfo -Mode "Invalid" -Source "license.json" -Path $Path -Message "License JSON could not be parsed."
    }

    $product = [string]$license.product
    if ($product -and $product -ne "bayoufinds-windows-cleanup") {
        return New-LicenseInfo -Mode "Invalid" -Source "license.json" -Path $Path -Message "License product does not match this tool." -Product $product
    }

    $mode = [string]$license.mode
    if (!$mode) {
        $mode = "Licensed"
    }

    $validModes = @("Licensed", "Free", "Trial")
    if ($validModes -notcontains $mode) {
        return New-LicenseInfo -Mode "Invalid" -Source "license.json" -Path $Path -Message "License mode is not recognized." -Product $product
    }

    $expiresAt = $null
    if ($license.expiresAt) {
        $expiresAt = [string]$license.expiresAt
        $expiresOn = [datetime]::MinValue
        if ([datetime]::TryParse($expiresAt, [ref]$expiresOn)) {
            if ($expiresOn -lt (Get-Date)) {
                return New-LicenseInfo -Mode "Expired" -Source "license.json" -Path $Path -Message "Local license has expired." -Product $product -ExpiresAt $expiresAt
            }
        }
        else {
            return New-LicenseInfo -Mode "Invalid" -Source "license.json" -Path $Path -Message "License expiration date is invalid." -Product $product -ExpiresAt $expiresAt
        }
    }

    return New-LicenseInfo -Mode $mode -Source "license.json" -Path $Path -Message "Local license file accepted." -Product $product -ExpiresAt $expiresAt
}

function Get-LicenseMode {
    foreach ($candidate in Get-LicenseCandidatePaths) {
        $candidatePath = $candidate.Path
        $candidateFormat = $candidate.Format

        if (!(Test-Path -Path $candidatePath -PathType Leaf)) {
            continue
        }

        if ($candidateFormat -eq "json") {
            return Test-LicenseJson -Path $candidatePath
        }

        return New-LicenseInfo -Mode "Licensed" -Source "license.key" -Path $candidatePath -Message "Legacy local license key found."
    }

    return New-LicenseInfo -Mode "Free" -Source "none" -Path $null -Message "No local license file found."
}
#endregion License

#region Platform and UI
function Test-WindowsPlatform {
    $isWindowsVariable = Get-Variable -Name IsWindows -Scope Global -ErrorAction SilentlyContinue
    if ($isWindowsVariable) {
        return [bool]$isWindowsVariable.Value
    }

    return $env:OS -eq "Windows_NT"
}

function Test-Admin {
    $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
    $principal = New-Object Security.Principal.WindowsPrincipal($identity)
    return $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
}

function Show-Splash {
    if (!$InteractiveMode -or $NoMenu) {
        return
    }

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

function Get-LastReportPath {
    if (!(Test-Path -Path $LogDir)) {
        return $null
    }

    $report = Get-ChildItem -Path $LogDir -Filter "cleanup_report_*.html" -File | Sort-Object LastWriteTime -Descending | Select-Object -First 1
    if ($report) {
        return $report.FullName
    }

    return $null
}

function Open-LastReport {
    $lastReport = Get-LastReportPath
    if ($lastReport) {
        Write-Host "Opening last report: $lastReport"
        Start-Process $lastReport
    }
    else {
        Write-Host "No previous cleanup report was found." -ForegroundColor Yellow
    }
}

function Show-MainMenu {
    param([object]$LicenseInfo)

    while ($true) {
        Clear-Host
        Write-Host "BayouFinds Windows Cleanup Tool v$ToolVersion" -ForegroundColor Cyan
        Write-Host "Session: $SessionId"
        Write-Host "License: $($LicenseInfo.Mode)"
        Write-Host ""
        Write-Host "1. Run Safe Cleanup"
        Write-Host "2. Preview Cleanup"
        Write-Host "3. Backup Browser Bookmarks"
        Write-Host "4. View Last Report"
        Write-Host "5. Exit"
        Write-Host ""

        $choice = Read-Host "Choose an option"
        switch ($choice) {
            "1" {
                return "SafeCleanup"
            }
            "2" {
                return "Preview"
            }
            "3" {
                return "BackupBookmarks"
            }
            "4" {
                Open-LastReport
                Read-Host "Press Enter to return to the menu"
            }
            "5" {
                return "Exit"
            }
            default {
                Write-Host "Please choose 1, 2, 3, 4, or 5." -ForegroundColor Yellow
                Start-Sleep -Seconds 1
            }
        }
    }
}
#endregion Platform and UI

#region Browser bookmark backup
function New-BrowserBackupResult {
    param(
        [string]$Browser,
        [string]$Profile,
        [string]$SourcePath,
        [string]$DestinationPath,
        [string]$Status,
        [string]$Message
    )

    return [ordered]@{
        Browser = $Browser
        Profile = $Profile
        SourcePath = $SourcePath
        DestinationPath = $DestinationPath
        Status = $Status
        Message = $Message
        Timestamp = (Get-Date).ToString("o")
    }
}

function Copy-BookmarkFile {
    param(
        [string]$Browser,
        [string]$Profile,
        [string]$SourcePath,
        [string]$DestinationFolder,
        [string]$DestinationFileName
    )

    if (!(Test-Path -Path $SourcePath -PathType Leaf)) {
        $result = New-BrowserBackupResult -Browser $Browser -Profile $Profile -SourcePath $SourcePath -DestinationPath $null -Status "Skipped" -Message "Bookmark file not found."
        Add-ReportBrowserBackup -BackupResult $result
        Write-Log "BOOKMARK BACKUP SKIP: $Browser $Profile bookmark file not found: $SourcePath"
        return
    }

    New-Item -ItemType Directory -Force -Path $DestinationFolder -WhatIf:$false | Out-Null
    $destinationPath = Join-Path -Path $DestinationFolder -ChildPath $DestinationFileName

    try {
        Copy-Item -Path $SourcePath -Destination $destinationPath -Force -ErrorAction Stop
        $result = New-BrowserBackupResult -Browser $Browser -Profile $Profile -SourcePath $SourcePath -DestinationPath $destinationPath -Status "BackedUp" -Message "Bookmark file backed up."
        Add-ReportBrowserBackup -BackupResult $result
        Write-Log "BOOKMARK BACKUP: $Browser $Profile saved to $destinationPath"
    }
    catch {
        $result = New-BrowserBackupResult -Browser $Browser -Profile $Profile -SourcePath $SourcePath -DestinationPath $destinationPath -Status "Failed" -Message $_.Exception.Message
        Add-ReportBrowserBackup -BackupResult $result
        Write-Log "BOOKMARK BACKUP ERROR: $Browser $Profile failed: $($_.Exception.Message)"
    }
}

function Backup-ChromiumBookmarks {
    param(
        [string]$Browser,
        [string]$UserDataPath
    )

    $browserFolder = Join-Path -Path $BrowserBackupDir -ChildPath $Browser

    if (!(Test-Path -Path $UserDataPath -PathType Container)) {
        $result = New-BrowserBackupResult -Browser $Browser -Profile $null -SourcePath $UserDataPath -DestinationPath $null -Status "Skipped" -Message "Browser profile folder not found."
        Add-ReportBrowserBackup -BackupResult $result
        Write-Log "BOOKMARK BACKUP SKIP: $Browser profile folder not found: $UserDataPath"
        return
    }

    $profiles = Get-ChildItem -Path $UserDataPath -Directory -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -eq "Default" -or $_.Name -like "Profile *"
    }

    if (!$profiles) {
        $result = New-BrowserBackupResult -Browser $Browser -Profile $null -SourcePath $UserDataPath -DestinationPath $null -Status "Skipped" -Message "No browser bookmark profiles found."
        Add-ReportBrowserBackup -BackupResult $result
        Write-Log "BOOKMARK BACKUP SKIP: $Browser no bookmark profiles found."
        return
    }

    foreach ($profile in $profiles) {
        $sourcePath = Join-Path -Path $profile.FullName -ChildPath "Bookmarks"
        $safeProfileName = $profile.Name -replace '[^\w-]', '_'
        Copy-BookmarkFile -Browser $Browser -Profile $profile.Name -SourcePath $sourcePath -DestinationFolder $browserFolder -DestinationFileName "${safeProfileName}_Bookmarks.json"
    }
}

function Backup-FirefoxBookmarks {
    if (!$env:APPDATA) {
        $result = New-BrowserBackupResult -Browser "Firefox" -Profile $null -SourcePath "%APPDATA%" -DestinationPath $null -Status "Skipped" -Message "APPDATA is not available."
        Add-ReportBrowserBackup -BackupResult $result
        Write-Log "BOOKMARK BACKUP SKIP: Firefox APPDATA is not available."
        return
    }

    $profilesRoot = Join-Path -Path $env:APPDATA -ChildPath "Mozilla\Firefox\Profiles"
    $browserFolder = Join-Path -Path $BrowserBackupDir -ChildPath "Firefox"

    if (!(Test-Path -Path $profilesRoot -PathType Container)) {
        $result = New-BrowserBackupResult -Browser "Firefox" -Profile $null -SourcePath $profilesRoot -DestinationPath $null -Status "Skipped" -Message "Firefox profile folder not found."
        Add-ReportBrowserBackup -BackupResult $result
        Write-Log "BOOKMARK BACKUP SKIP: Firefox profile folder not found: $profilesRoot"
        return
    }

    $profiles = Get-ChildItem -Path $profilesRoot -Directory -ErrorAction SilentlyContinue
    if (!$profiles) {
        $result = New-BrowserBackupResult -Browser "Firefox" -Profile $null -SourcePath $profilesRoot -DestinationPath $null -Status "Skipped" -Message "No Firefox profiles found."
        Add-ReportBrowserBackup -BackupResult $result
        Write-Log "BOOKMARK BACKUP SKIP: Firefox no profiles found."
        return
    }

    foreach ($profile in $profiles) {
        $backupFolder = Join-Path -Path $profile.FullName -ChildPath "bookmarkbackups"
        $latestBackup = Get-ChildItem -Path $backupFolder -Filter "*.jsonlz4" -File -ErrorAction SilentlyContinue | Sort-Object LastWriteTime -Descending | Select-Object -First 1

        if (!$latestBackup) {
            $result = New-BrowserBackupResult -Browser "Firefox" -Profile $profile.Name -SourcePath $backupFolder -DestinationPath $null -Status "Skipped" -Message "Firefox bookmark backup file not found."
            Add-ReportBrowserBackup -BackupResult $result
            Write-Log "BOOKMARK BACKUP SKIP: Firefox $($profile.Name) bookmark backup file not found."
            continue
        }

        $safeProfileName = $profile.Name -replace '[^\w-]', '_'
        Copy-BookmarkFile -Browser "Firefox" -Profile $profile.Name -SourcePath $latestBackup.FullName -DestinationFolder $browserFolder -DestinationFileName "${safeProfileName}_Bookmarks.jsonlz4"
    }
}

function Backup-BrowserBookmarks {
    Write-Log "Back Up Browser Bookmarks started."
    Write-Log "Browser bookmark backup folder: $BrowserBackupDir"
    Add-ReportNote -Message "Browser bookmark backup checks Chrome, Edge, and Firefox. Cookies, passwords, history, and extensions are not touched."

    if ($env:LOCALAPPDATA) {
        Backup-ChromiumBookmarks -Browser "Chrome" -UserDataPath (Join-Path -Path $env:LOCALAPPDATA -ChildPath "Google\Chrome\User Data")
        Backup-ChromiumBookmarks -Browser "Edge" -UserDataPath (Join-Path -Path $env:LOCALAPPDATA -ChildPath "Microsoft\Edge\User Data")
    }
    else {
        foreach ($browser in @("Chrome", "Edge")) {
            $result = New-BrowserBackupResult -Browser $browser -Profile $null -SourcePath "%LOCALAPPDATA%" -DestinationPath $null -Status "Skipped" -Message "LOCALAPPDATA is not available."
            Add-ReportBrowserBackup -BackupResult $result
            Write-Log "BOOKMARK BACKUP SKIP: $browser LOCALAPPDATA is not available."
        }
    }

    Backup-FirefoxBookmarks

    Write-Log "Back Up Browser Bookmarks complete."
}
#endregion Browser bookmark backup

#region Cleanup actions
function Remove-Contents {
    param(
        [string]$Path,
        [string]$Label,
        [bool]$AddToReport = $true
    )

    if (!(Test-Path $Path)) {
        Write-Log "SKIP: $Label not found: $Path"
        Add-ReportSkippedItem -Label $Label -Path $Path -Reason "Path not found"
        return
    }

    if ($AddToReport) {
        Add-ReportCategory -Label $Label
    }

    Write-Log "Cleaning: $Label - $Path"

    if ($script:EffectiveDryRun) {
        Get-ChildItem -Path $Path -Force -Recurse | Select-Object -First 20 | ForEach-Object {
            Write-Log "DRYRUN: Would remove $($_.FullName)"
        }
        return
    }

    if ($PSCmdlet.ShouldProcess($Path, "Remove cleanup contents for $Label")) {
        Get-ChildItem -Path $Path -Force -Recurse | Remove-Item -Force -Recurse
    }
}

function Test-AnyProcessRunning {
    param([string[]]$ProcessNames)

    foreach ($processName in $ProcessNames) {
        if (Get-Process -Name $processName -ErrorAction SilentlyContinue) {
            return $true
        }
    }

    return $false
}

function Confirm-RecycleBinCleanup {
    if (!$InteractiveMode -or $NoMenu -or $script:EffectiveDryRun) {
        return $false
    }

    $choice = Read-Host "Empty Recycle Bin now? This permanently removes Recycle Bin contents. Type YES to confirm"
    return $choice -eq "YES"
}

function New-CleanupCategory {
    param(
        [string]$Id,
        [string]$Label,
        [string]$Description,
        [string[]]$Paths,
        [bool]$DefaultEnabled,
        [bool]$RequiresAdmin,
        [bool]$RequiresConfirmation,
        [string[]]$SkipIfProcessRunning = @(),
        [string]$RiskLevel
    )

    return [ordered]@{
        Id = $Id
        Label = $Label
        Description = $Description
        Paths = $Paths
        DefaultEnabled = $DefaultEnabled
        RequiresAdmin = $RequiresAdmin
        RequiresConfirmation = $RequiresConfirmation
        SkipIfProcessRunning = $SkipIfProcessRunning
        RiskLevel = $RiskLevel
        EstimatedBytes = 0
        EstimatedFiles = 0
        ActualBytesRemoved = 0
        ActualFilesRemoved = 0
        Status = "Pending"
        SkippedReason = $null
        Errors = @()
        Warnings = @()
        StartedAt = $null
        EndedAt = $null
        PathsProcessed = @()
        PathsSkipped = @()
    }
}

function Get-SafeCleanupCategories {
    return @(
        New-CleanupCategory `
            -Id "user_temp" `
            -Label "Current user temp" `
            -Description "Temporary files created by the current Windows user and applications." `
            -Paths @($env:TEMP) `
            -DefaultEnabled $true `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "windows_temp" `
            -Label "Windows temp" `
            -Description "Temporary files stored in the Windows temp folder." `
            -Paths @((Join-Path -Path $env:SystemRoot -ChildPath "Temp")) `
            -DefaultEnabled $true `
            -RequiresAdmin $true `
            -RequiresConfirmation $false `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "local_app_temp" `
            -Label "Local app temp" `
            -Description "Temporary files stored under the current user's local app data." `
            -Paths @((Join-Path -Path $env:LOCALAPPDATA -ChildPath "Temp")) `
            -DefaultEnabled $true `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "internet_cache" `
            -Label "Internet cache" `
            -Description "Windows internet cache files for the current user." `
            -Paths @((Join-Path -Path $env:LOCALAPPDATA -ChildPath "Microsoft\Windows\INetCache")) `
            -DefaultEnabled $true `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "windows_web_cache" `
            -Label "Windows web cache" `
            -Description "Windows web cache files for the current user." `
            -Paths @((Join-Path -Path $env:LOCALAPPDATA -ChildPath "Microsoft\Windows\WebCache")) `
            -DefaultEnabled $true `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "edge_cache" `
            -Label "Microsoft Edge cache" `
            -Description "Microsoft Edge cache files for the default profile. Skipped while Edge is running." `
            -Paths @((Join-Path -Path $env:LOCALAPPDATA -ChildPath "Microsoft\Edge\User Data\Default\Cache")) `
            -DefaultEnabled $true `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -SkipIfProcessRunning @("msedge") `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "chrome_cache" `
            -Label "Google Chrome cache" `
            -Description "Google Chrome cache files for the default profile. Skipped while Chrome is running." `
            -Paths @((Join-Path -Path $env:LOCALAPPDATA -ChildPath "Google\Chrome\User Data\Default\Cache")) `
            -DefaultEnabled $true `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -SkipIfProcessRunning @("chrome") `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "recent_files_cache" `
            -Label "Recent files cache" `
            -Description "Windows recent-file shortcut cache for the current user." `
            -Paths @((Join-Path -Path $env:APPDATA -ChildPath "Microsoft\Windows\Recent")) `
            -DefaultEnabled $true `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "recycle_bin" `
            -Label "Recycle Bin" `
            -Description "Recycle Bin contents. Requires explicit confirmation before emptying." `
            -Paths @("Recycle Bin") `
            -DefaultEnabled $true `
            -RequiresAdmin $false `
            -RequiresConfirmation $true `
            -RiskLevel "Low-Confirmation"
    )
}

function Measure-CleanupPath {
    param([string]$Path)

    $result = [ordered]@{
        Path = $Path
        EstimatedBytes = 0
        EstimatedFiles = 0
        Exists = $false
        Error = $null
    }

    if (!(Test-Path -Path $Path)) {
        $result.Error = "Path not found"
        return $result
    }

    $result.Exists = $true

    try {
        Get-ChildItem -Path $Path -Force -Recurse -File -ErrorAction Stop | ForEach-Object {
            $result.EstimatedFiles++
            $result.EstimatedBytes += $_.Length
        }
    }
    catch {
        $result.Error = $_.Exception.Message
    }

    return $result
}

function Measure-CleanupCategory {
    param([object]$Category)

    $Category.StartedAt = (Get-Date).ToString("o")

    if (!$Category.DefaultEnabled) {
        $Category.Status = "Skipped"
        $Category.SkippedReason = "Category is not enabled by default"
        $Category.PathsSkipped += $Category.Paths
        $Category.EndedAt = (Get-Date).ToString("o")
        return $Category
    }

    if ($Category.SkipIfProcessRunning -and (Test-AnyProcessRunning -ProcessNames $Category.SkipIfProcessRunning)) {
        $Category.Status = "Skipped"
        $Category.SkippedReason = "Related process is running"
        $Category.PathsSkipped += $Category.Paths
        $Category.EndedAt = (Get-Date).ToString("o")
        return $Category
    }

    if ($Category.RequiresConfirmation) {
        $Category.Status = "RequiresConfirmation"
        $Category.SkippedReason = "Preview does not measure confirmation-required cleanup"
        $Category.Warnings += "This category requires explicit confirmation before cleanup."
        $Category.PathsSkipped += $Category.Paths
        $Category.EndedAt = (Get-Date).ToString("o")
        return $Category
    }

    foreach ($path in $Category.Paths) {
        $pathResult = Measure-CleanupPath -Path $path

        if ($pathResult.Exists) {
            $Category.PathsProcessed += $path
            $Category.EstimatedBytes += $pathResult.EstimatedBytes
            $Category.EstimatedFiles += $pathResult.EstimatedFiles
        }
        else {
            $Category.PathsSkipped += $path
        }

        if ($pathResult.Error) {
            if ($pathResult.Exists) {
                $Category.Warnings += "$path - $($pathResult.Error)"
            }
            else {
                $Category.SkippedReason = $pathResult.Error
            }
        }
    }

    if ($Category.PathsProcessed.Count -gt 0 -and $Category.Warnings.Count -gt 0) {
        $Category.Status = "Partial"
    }
    elseif ($Category.PathsProcessed.Count -gt 0) {
        $Category.Status = "Previewed"
    }
    else {
        $Category.Status = "Skipped"
        if (!$Category.SkippedReason) {
            $Category.SkippedReason = "No cleanup paths found"
        }
    }

    $Category.EndedAt = (Get-Date).ToString("o")
    return $Category
}

function Invoke-CleanupCategory {
    param([object]$Category)

    $Category.StartedAt = (Get-Date).ToString("o")

    if (!$Category.DefaultEnabled) {
        Write-Log "SKIP: $($Category.Label) is not enabled by default."
        $Category.Status = "Skipped"
        $Category.SkippedReason = "Category is not enabled by default"
        $Category.PathsSkipped += $Category.Paths
        $Category.EndedAt = (Get-Date).ToString("o")
        Add-ReportCleanupCategory -Category $Category
        Add-ReportSkippedItem -Label $Category.Label -Path ($Category.Paths -join "; ") -Reason "Category is not enabled by default"
        return
    }

    if ($Category.SkipIfProcessRunning -and (Test-AnyProcessRunning -ProcessNames $Category.SkipIfProcessRunning)) {
        Write-Log "SKIP: $($Category.Label) because a related process is running: $($Category.SkipIfProcessRunning -join ', ')."
        $Category.Status = "Skipped"
        $Category.SkippedReason = "Related process is running"
        $Category.PathsSkipped += $Category.Paths
        $Category.EndedAt = (Get-Date).ToString("o")
        Add-ReportCleanupCategory -Category $Category
        Add-ReportSkippedItem -Label $Category.Label -Path ($Category.Paths -join "; ") -Reason "Related process is running"
        return
    }

    if ($Category.RequiresConfirmation) {
        if ($Category.Id -eq "recycle_bin") {
            Write-Log "Recycle Bin cleanup requires explicit confirmation."
            if (Confirm-RecycleBinCleanup) {
                Add-ReportCategory -Label $Category.Label
                if ($PSCmdlet.ShouldProcess("Recycle Bin", "Empty")) {
                    Clear-RecycleBin -Force
                    $Category.Status = "Cleaned"
                    $Category.PathsProcessed += "Recycle Bin"
                    Write-Log "Recycle Bin emptied after explicit confirmation."
                }
            }
            else {
                Write-Log "Recycle Bin skipped."
                $Category.Status = "Skipped"
                $Category.SkippedReason = "Explicit confirmation not provided"
                $Category.PathsSkipped += "Recycle Bin"
                Add-ReportSkippedItem -Label $Category.Label -Path "Recycle Bin" -Reason "Explicit confirmation not provided"
            }
            $Category.EndedAt = (Get-Date).ToString("o")
            Add-ReportCleanupCategory -Category $Category
            return
        }

        Write-Log "SKIP: $($Category.Label) requires confirmation and has no cleanup handler yet."
        $Category.Status = "Skipped"
        $Category.SkippedReason = "Confirmation cleanup handler not implemented"
        $Category.PathsSkipped += $Category.Paths
        $Category.EndedAt = (Get-Date).ToString("o")
        Add-ReportCleanupCategory -Category $Category
        Add-ReportSkippedItem -Label $Category.Label -Path ($Category.Paths -join "; ") -Reason "Confirmation cleanup handler not implemented"
        return
    }

    Add-ReportCategory -Label $Category.Label
    foreach ($path in $Category.Paths) {
        if (Test-Path -Path $path) {
            $Category.PathsProcessed += $path
        }
        else {
            $Category.PathsSkipped += $path
        }

        Remove-Contents -Path $path -Label $Category.Label -AddToReport $false
    }

    if ($Category.PathsProcessed.Count -gt 0 -and $Category.PathsSkipped.Count -gt 0) {
        $Category.Status = "Partial"
        $Category.SkippedReason = "One or more cleanup paths were not found"
    }
    elseif ($Category.PathsProcessed.Count -gt 0) {
        $Category.Status = "Cleaned"
    }
    else {
        $Category.Status = "Skipped"
        $Category.SkippedReason = "No cleanup paths found"
    }

    $Category.EndedAt = (Get-Date).ToString("o")
    Add-ReportCleanupCategory -Category $Category
}

function Invoke-PreviewWorkflow {
    $cleanupCategories = Get-SafeCleanupCategories

    Write-Log "Preview mode measuring cleanup categories. No files will be deleted."
    Add-ReportNote -Message "Preview mode measured cleanup categories without deleting files."

    foreach ($category in $cleanupCategories) {
        $measuredCategory = Measure-CleanupCategory -Category $category
        Add-ReportCleanupCategory -Category $measuredCategory

        if ($measuredCategory.Status -eq "Skipped" -or $measuredCategory.Status -eq "RequiresConfirmation") {
            Add-ReportSkippedItem -Label $measuredCategory.Label -Path ($measuredCategory.Paths -join "; ") -Reason $measuredCategory.SkippedReason
            Write-Log "PREVIEW: $($measuredCategory.Label) skipped: $($measuredCategory.SkippedReason)"
        }
        else {
            Write-Log "PREVIEW: $($measuredCategory.Label) estimates $($measuredCategory.EstimatedFiles) files and $($measuredCategory.EstimatedBytes) bytes."
        }
    }

    return $cleanupCategories.Count
}

function Invoke-SafeCleanupWorkflow {
    $cleanupCategories = Get-SafeCleanupCategories

    Write-Log "Restore point creation skipped. Restore points are optional and are not created automatically."
    Add-ReportNote -Message "Restore point creation skipped by default."

    foreach ($category in $cleanupCategories) {
        Invoke-CleanupCategory -Category $category
    }

    Write-Log "Windows Update download cache cleanup skipped. Windows Update reset is not part of safe cleanup."
    Add-ReportNote -Message "Windows Update download cache cleanup skipped by default."

    Write-Log "Flushing DNS cache..."
    if (!$script:EffectiveDryRun) {
        if ($PSCmdlet.ShouldProcess("DNS client cache", "Flush")) {
            ipconfig.exe /flushdns | Tee-Object -FilePath $LogFile -Append | Out-Null
            Write-Log "ipconfig.exe exit code: $LASTEXITCODE"
        }
    }

    Write-Log "Running DISM component cleanup..."
    if (!$script:EffectiveDryRun) {
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
        if (!$script:EffectiveDryRun) {
            if ($PSCmdlet.ShouldProcess("System files", "Run SFC scan")) {
                sfc.exe /scannow | Tee-Object -FilePath $LogFile -Append
                Write-Log "sfc.exe exit code: $LASTEXITCODE"
            }
        }
    }

    return $cleanupCategories.Count
}
#endregion Cleanup actions

#region Orchestration
function Initialize-CleanupRun {
    param(
        [object]$LicenseInfo,
        [string]$RunMode
    )

    $script:CleanupReport = New-CleanupReportModel -LicenseInfo $LicenseInfo -RunMode $RunMode

    Write-Log "BayouFinds Windows Cleanup started."
    Write-Log "Tool version: $ToolVersion"
    Write-Log "Session ID: $SessionId"
    Write-Log "Run mode: $RunMode"
    Write-Log "Log file: $LogFile"
    Write-Log "License mode: $($LicenseInfo.Mode)"
    Write-Log "License source: $($LicenseInfo.Source)"
}

function Invoke-CleanupRun {
    param(
        [object]$LicenseInfo,
        [string]$RunMode
    )

    if ($RunMode -eq "Preview") {
        $script:EffectiveDryRun = $true
        Add-ReportNote -Message "Preview mode measures cleanup categories without deleting files."
    }

    Initialize-CleanupRun -LicenseInfo $LicenseInfo -RunMode $RunMode

    if ($RunMode -eq "LicenseCheck") {
        Write-Log "License check complete."
        Write-Log "License mode: $($LicenseInfo.Mode)"
        Write-Log "License message: $($LicenseInfo.Message)"
        Write-Summary -LicenseMode $LicenseInfo.Mode -StartTime $StartTime -EstimatedCleanupTargets 0
        return
    }

    if ($RunMode -eq "BackupBookmarks") {
        Backup-BrowserBookmarks
        Write-Summary -LicenseMode $LicenseInfo.Mode -StartTime $StartTime -EstimatedCleanupTargets 0
        return
    }

    $isWindowsPlatform = Test-WindowsPlatform
    if (!$isWindowsPlatform) {
        Write-Log "INFO: This tool is intended for Windows. Validation mode passed."
        Add-ReportNote -Message "Cleanup category measurement skipped because this validation run is not on Windows."
        Write-Summary -LicenseMode $LicenseInfo.Mode -StartTime $StartTime -EstimatedCleanupTargets 0
        return
    }

    if ($WhatIfPreference) {
        Write-Log "WhatIf validation mode detected. Administrator enforcement skipped for validation."
    }
    elseif (!(Test-Admin)) {
        Write-Log "ERROR: Please run PowerShell as Administrator."
        Write-Host "`nRight-click PowerShell and choose 'Run as Administrator'." -ForegroundColor Yellow
        Write-Summary -LicenseMode $LicenseInfo.Mode -StartTime $StartTime -EstimatedCleanupTargets 0
        if ($InteractiveMode -and !$NoMenu) {
            Read-Host "Press Enter to exit"
        }
        return
    }
    else {
        Write-Log "Admin rights confirmed."
    }

    if ($RunMode -eq "Preview") {
        $estimatedCleanupTargets = Invoke-PreviewWorkflow
    }
    else {
        $estimatedCleanupTargets = Invoke-SafeCleanupWorkflow
    }

    Write-Log "Cleanup complete."
    Write-Summary -LicenseMode $LicenseInfo.Mode -StartTime $StartTime -EstimatedCleanupTargets $estimatedCleanupTargets
    Write-Host "Cleanup complete. Check log: $LogFile"
    if ($InteractiveMode -and !$NoMenu) {
        Read-Host "Press Enter to exit"
    }
}

function Start-BayouFindsCleanupTool {
    Show-Splash

    $licenseInfo = Get-LicenseMode
    $runMode = $Mode

    if (!$runMode -and $InteractiveMode -and !$NoMenu -and !$DryRun -and !$WhatIfPreference) {
        $menuChoice = Show-MainMenu -LicenseInfo $licenseInfo
        switch ($menuChoice) {
            "SafeCleanup" {
                $runMode = "SafeCleanup"
            }
            "Preview" {
                $runMode = "Preview"
            }
            "BackupBookmarks" {
                $runMode = "BackupBookmarks"
            }
            "Exit" {
                Write-Host "Exiting BayouFinds Windows Cleanup Tool."
                return
            }
        }
    }
    elseif (!$runMode -and $DryRun) {
        $runMode = "Preview"
    }
    elseif (!$runMode) {
        $runMode = "SafeCleanup"
    }

    Invoke-CleanupRun -LicenseInfo $licenseInfo -RunMode $runMode
}
#endregion Orchestration

Start-BayouFindsCleanupTool
