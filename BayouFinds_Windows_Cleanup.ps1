<# 
BayouFinds Windows Cleanup Tool
Cleans common temp/cache locations and performs safe Windows maintenance.
Run PowerShell as Administrator.
#>

[CmdletBinding(SupportsShouldProcess = $true)]
param(
    [switch]$DryRun,
    [switch]$SkipSFC = $true,
    [ValidateSet("Preview", "SafeCleanup", "LicenseCheck", "BackupBookmarks", "BrowserHealth", "NetworkHealth", "PrinterHealth", "FlushDns", "RenewIp", "ResetNetwork")]
    [string]$Mode,
    [switch]$NoMenu,
    [string]$OutputDir,
    [ValidateSet("Yes", "No", "Unknown")]
    [string]$GuiElevated = "Unknown",
    [string]$SessionId = ([guid]::NewGuid().ToString())
)

#region Configuration
$ErrorActionPreference = "SilentlyContinue"
$ToolVersion = "1.5.0"
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
$StatsFile = Join-Path -Path $LogDir -ChildPath "cleanup_stats.json"
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
            StatsFile = $StatsFile
            BrowserBackupDir = $BrowserBackupDir
        }
        Statistics = [ordered]@{
            RecoverableBytes = 0
            RecoveredBytes = 0
            TotalRecoveredBytes = 0
            PCHealthScore = 100
        }
        CleanupTargetsEstimated = 0
        CleanupCategoriesProcessed = @()
        CleanupCategories = @()
        BrowserHealthSummary = [ordered]@{}
        BrowserHealth = @()
        NetworkHealth = [ordered]@{}
        PrinterHealthSummary = [ordered]@{}
        PrinterHealthDetails = @()
        NetworkFirstAid = @()
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

function Set-ReportBrowserHealth {
    param(
        [object[]]$BrowserHealth,
        [object]$Summary = $null
    )

    if ($script:CleanupReport) {
        $script:CleanupReport.BrowserHealth = @($BrowserHealth)
        if ($Summary) {
            $script:CleanupReport.BrowserHealthSummary = $Summary
        }
    }
}

function Set-ReportNetworkHealth {
    param([object]$NetworkHealth)

    if ($script:CleanupReport -and $NetworkHealth) {
        $script:CleanupReport.NetworkHealth = $NetworkHealth
    }
}

function Set-ReportPrinterHealth {
    param(
        [object]$Summary,
        [object[]]$Details
    )

    if ($script:CleanupReport) {
        if ($Summary) {
            $script:CleanupReport.PrinterHealthSummary = $Summary
        }
        $script:CleanupReport.PrinterHealthDetails = @($Details)
    }
}

function Add-ReportNetworkFirstAid {
    param([object]$Result)

    if ($script:CleanupReport -and $Result) {
        $script:CleanupReport.NetworkFirstAid += $Result
    }
}

function Get-CleanupMetricTotals {
    $recoverableBytes = 0L
    $recoveredBytes = 0L

    if (!$script:CleanupReport) {
        return [ordered]@{
            RecoverableBytes = $recoverableBytes
            RecoveredBytes = $recoveredBytes
        }
    }

    foreach ($category in $script:CleanupReport.CleanupCategories) {
        if ($null -ne $category.EstimatedBytes) {
            $recoverableBytes += [int64]$category.EstimatedBytes
        }

        if ($null -ne $category.ActualBytesRemoved) {
            $recoveredBytes += [int64]$category.ActualBytesRemoved
        }
    }

    return [ordered]@{
        RecoverableBytes = $recoverableBytes
        RecoveredBytes = $recoveredBytes
    }
}

function Get-PCHealthScore {
    param([int64]$RecoverableBytes)

    $oneGb = 1024L * 1024L * 1024L
    if ($RecoverableBytes -le 0) {
        return 100
    }

    $deduction = [Math]::Min(35, [Math]::Ceiling(($RecoverableBytes / $oneGb) * 5))
    return [int](100 - $deduction)
}

function Read-CleanupStats {
    if (Test-Path -Path $StatsFile) {
        try {
            return Get-Content -Path $StatsFile -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
        }
        catch {
            Write-Log "WARN: Existing cleanup statistics could not be read. A new stats file will be created."
        }
    }

    return [pscustomobject]@{
        ToolVersion = $ToolVersion
        LastUpdatedAt = $null
        LastRunMode = $null
        LastSessionId = $null
        LastRecoverableBytes = 0
        LastRecoveredBytes = 0
        TotalRecoveredBytes = 0
        PCHealthScore = 100
    }
}

function Write-CleanupStats {
    param([string]$RunMode)

    if (!$script:CleanupReport) {
        return
    }

    $totals = Get-CleanupMetricTotals
    $existingStats = Read-CleanupStats
    $previousTotalRecovered = 0L
    if ($null -ne $existingStats.TotalRecoveredBytes) {
        $previousTotalRecovered = [int64]$existingStats.TotalRecoveredBytes
    }

    $recoverableBytes = [int64]$totals.RecoverableBytes
    $recoveredBytes = [int64]$totals.RecoveredBytes
    $totalRecoveredBytes = $previousTotalRecovered
    if ($RunMode -eq "SafeCleanup" -and !$script:EffectiveDryRun -and !$WhatIfPreference) {
        $totalRecoveredBytes += $recoveredBytes
    }

    $healthBasisBytes = $recoverableBytes
    if ($RunMode -eq "SafeCleanup" -and !$script:EffectiveDryRun -and !$WhatIfPreference) {
        $healthBasisBytes = [Math]::Max(0, $recoverableBytes - $recoveredBytes)
    }
    $healthScore = Get-PCHealthScore -RecoverableBytes $healthBasisBytes
    $stats = [ordered]@{
        ToolVersion = $ToolVersion
        LastUpdatedAt = (Get-Date).ToString("o")
        LastRunMode = $RunMode
        LastSessionId = $SessionId
        LastRecoverableBytes = $recoverableBytes
        LastRecoveredBytes = $recoveredBytes
        TotalRecoveredBytes = $totalRecoveredBytes
        PCHealthScore = $healthScore
    }

    $script:CleanupReport.Statistics = [ordered]@{
        RecoverableBytes = $recoverableBytes
        RecoveredBytes = $recoveredBytes
        TotalRecoveredBytes = $totalRecoveredBytes
        PCHealthScore = $healthScore
    }

    $stats | ConvertTo-Json -Depth 4 | Set-Content -Path $StatsFile -Encoding UTF8 -WhatIf:$false
    Write-Log "Cleanup statistics saved: $StatsFile"
    Write-Log "Recoverable bytes: $recoverableBytes"
    Write-Log "Recovered bytes this run: $recoveredBytes"
    Write-Log "Total recovered bytes: $totalRecoveredBytes"
    Write-Log "PC health score: $healthScore"
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

function Format-ReportBytes {
    param([int64]$Bytes)

    $safeBytes = [Math]::Max(0, $Bytes)
    $units = @("B", "KB", "MB", "GB", "TB")
    $amount = [double]$safeBytes
    $unitIndex = 0

    while ($amount -ge 1024 -and $unitIndex -lt ($units.Count - 1)) {
        $amount = $amount / 1024
        $unitIndex++
    }

    if ($unitIndex -eq 0) {
        return "$([int64]$amount) $($units[$unitIndex])"
    }

    return "{0:N1} {1}" -f $amount, $units[$unitIndex]
}

function Format-ReportValue {
    param([object]$Value)

    if ($null -eq $Value -or [string]::IsNullOrWhiteSpace([string]$Value)) {
        return "Unknown"
    }

    return [string]$Value
}

function Format-ReportList {
    param([object]$Value)

    if ($null -eq $Value) {
        return "Unknown"
    }

    if ($Value -is [array]) {
        $items = @($Value | Where-Object { ![string]::IsNullOrWhiteSpace([string]$_) })
        if ($items.Count -eq 0) {
            return "Unknown"
        }
        return ($items -join ", ")
    }

    return Format-ReportValue -Value $Value
}

function ConvertTo-ReportHtml {
    param([object]$Value)

    return [System.Net.WebUtility]::HtmlEncode((Format-ReportValue -Value $Value))
}

function Get-ReportFilesIdentified {
    if (!$script:CleanupReport -or !$script:CleanupReport.CleanupCategories) {
        return 0L
    }

    $files = 0L
    foreach ($category in $script:CleanupReport.CleanupCategories) {
        if ($null -ne $category.EstimatedFiles) {
            $files += [int64]$category.EstimatedFiles
        }
    }

    return $files
}

function Get-ReportCleanupStatus {
    param([string]$RunMode)

    if ($RunMode -eq "SafeCleanup" -and !$script:EffectiveDryRun -and !$WhatIfPreference) {
        return "Cleanup completed"
    }

    if ($RunMode -eq "Preview") {
        return "Assessment complete - cleanup actions unlock after activation"
    }

    if ($RunMode -eq "LicenseCheck") {
        return "Activation status checked"
    }

    if ($RunMode -eq "BackupBookmarks") {
        return "Bookmark backup completed"
    }

    if ($RunMode -eq "BrowserHealth") {
        return "Browser Health complete"
    }

    if ($RunMode -eq "NetworkHealth") {
        return "Network Health complete"
    }

    if ($RunMode -eq "PrinterHealth") {
        return "Printer Health complete"
    }

    if (@("FlushDns", "RenewIp", "ResetNetwork") -contains $RunMode) {
        return "Network First Aid complete"
    }

    return "Report generated"
}

function New-BrowserHealthHtml {
    if (!$script:CleanupReport -or !$script:CleanupReport.BrowserHealth -or $script:CleanupReport.BrowserHealth.Count -eq 0) {
        return "<h2>Browser Health</h2><p>No Browser Health scan results were recorded for this run.</p>"
    }

    $summary = $script:CleanupReport.BrowserHealthSummary
    $defaultBrowser = if ($summary -and $summary.DefaultBrowser) { $summary.DefaultBrowser } else { "Unknown" }
    $totalProfiles = if ($summary -and $null -ne $summary.TotalProfiles) { $summary.TotalProfiles } else { "Unknown" }
    $totalExtensions = if ($summary -and $null -ne $summary.TotalExtensions) { $summary.TotalExtensions } else { "Unknown" }
    $totalCache = if ($summary -and $summary.TotalCacheSize) { $summary.TotalCacheSize } else { "Unknown" }
    $runningBrowsers = if ($summary -and $summary.RunningBrowsers -and $summary.RunningBrowsers.Count -gt 0) {
        (@($summary.RunningBrowsers) | ForEach-Object { "$($_.Name) ($($_.ProcessCount))" }) -join ", "
    }
    else {
        "None detected"
    }

    $rows = ""
    foreach ($browser in @($script:CleanupReport.BrowserHealth)) {
        $rows += "<tr><td>$(ConvertTo-ReportHtml $browser.Name)</td><td>$(ConvertTo-ReportHtml $browser.InstalledText)</td><td>$(ConvertTo-ReportHtml $browser.Version)</td><td>$(ConvertTo-ReportHtml $browser.RunningText)</td><td>$(ConvertTo-ReportHtml $browser.ProcessCount)</td><td>$(ConvertTo-ReportHtml $browser.ProfileCount)</td><td>$(ConvertTo-ReportHtml $browser.ExtensionCount)</td><td>$(ConvertTo-ReportHtml $browser.CacheSize)</td><td>$(ConvertTo-ReportHtml $browser.DefaultBrowser)</td><td>$(ConvertTo-ReportHtml $browser.DetectionSource)</td><td>$(ConvertTo-ReportHtml $browser.UpdateStatus)</td></tr>`n"
    }

    return @"
<h2>Browser Health</h2>
<p>Browser Health checks Chrome, Edge, and Firefox install status, versions, profiles, extensions, cache estimates, default browser status, and running browser processes. It does not collect passwords, cookies, browsing history, autofill, or private browser data.</p>
<table>
<tr><td><strong>Default Browser</strong></td><td>$(ConvertTo-ReportHtml $defaultBrowser)</td></tr>
<tr><td><strong>Total Profiles</strong></td><td>$(ConvertTo-ReportHtml $totalProfiles)</td></tr>
<tr><td><strong>Total Extensions</strong></td><td>$(ConvertTo-ReportHtml $totalExtensions)</td></tr>
<tr><td><strong>Total Browser Cache Estimate</strong></td><td>$(ConvertTo-ReportHtml $totalCache)</td></tr>
<tr><td><strong>Browser Processes Running</strong></td><td>$(ConvertTo-ReportHtml $runningBrowsers)</td></tr>
<tr><td><strong>Cleanup Metrics</strong></td><td>Not applicable - Browser Health is a health report, not a cleanup scan.</td></tr>
</table>
<h3>Browser Details</h3>
<table>
<tr><td><strong>Browser</strong></td><td><strong>Installed</strong></td><td><strong>Version</strong></td><td><strong>Running</strong></td><td><strong>Process Count</strong></td><td><strong>Profiles</strong></td><td><strong>Extensions</strong></td><td><strong>Cache</strong></td><td><strong>Default</strong></td><td><strong>Detection Source</strong></td><td><strong>Update Status</strong></td></tr>
$rows
</table>
"@
}

function New-PrinterHealthHtml {
    if (!$script:CleanupReport -or !$script:CleanupReport.PrinterHealthSummary -or $script:CleanupReport.PrinterHealthSummary.Count -eq 0) {
        return "<h2>Printer Health Report</h2><p>No Printer Health scan results were recorded for this run.</p>"
    }

    $summary = $script:CleanupReport.PrinterHealthSummary
    $recommendationRows = ""
    foreach ($recommendation in @($summary.Recommendations)) {
        $recommendationRows += "<li>$(ConvertTo-ReportHtml $recommendation)</li>`n"
    }
    if (!$recommendationRows) {
        $recommendationRows = "<li>No printer problems were detected.</li>"
    }

    $printerRows = ""
    foreach ($printer in @($script:CleanupReport.PrinterHealthDetails)) {
        $printerRows += "<tr><td>$(ConvertTo-ReportHtml $printer.Name)</td><td>$(ConvertTo-ReportHtml $printer.DefaultPrinter)</td><td>$(ConvertTo-ReportHtml $printer.Status)</td><td>$(ConvertTo-ReportHtml $printer.Shared)</td><td>$(ConvertTo-ReportHtml $printer.QueueJobCount)</td><td>$(ConvertTo-ReportHtml $printer.DriverName)</td><td>$(ConvertTo-ReportHtml $printer.DriverVersion)</td></tr>`n"
    }
    if (!$printerRows) {
        $printerRows = "<tr><td>No printers detected</td><td>No</td><td>Unknown</td><td>No</td><td>0</td><td>Unknown</td><td>Unknown</td></tr>"
    }

    return @"
<h2>Printer Health Report</h2>
<p>Printer Health is read-only. It checks printer status, queues, drivers, and the Windows print spooler without clearing queues, restarting services, removing printers, or removing drivers.</p>
<h3>Printer Health Summary</h3>
<table>
<tr><td><strong>Default Printer</strong></td><td>$(ConvertTo-ReportHtml $summary.DefaultPrinter)</td></tr>
<tr><td><strong>Installed Printers</strong></td><td>$(ConvertTo-ReportHtml $summary.InstalledPrinters)</td></tr>
<tr><td><strong>Online</strong></td><td>$(ConvertTo-ReportHtml $summary.OnlinePrinters)</td></tr>
<tr><td><strong>Offline</strong></td><td>$(ConvertTo-ReportHtml $summary.OfflinePrinters)</td></tr>
<tr><td><strong>Queued Jobs</strong></td><td>$(ConvertTo-ReportHtml $summary.TotalQueuedJobs)</td></tr>
<tr><td><strong>Stuck Jobs Estimate</strong></td><td>$(ConvertTo-ReportHtml $summary.StuckPrintJobsEstimate)</td></tr>
<tr><td><strong>Oldest Queued Job</strong></td><td>$(ConvertTo-ReportHtml $summary.OldestQueuedJobAge)</td></tr>
<tr><td><strong>Spooler Service</strong></td><td>$(ConvertTo-ReportHtml $summary.SpoolerServiceStatus)</td></tr>
<tr><td><strong>Printer Drivers</strong></td><td>$(ConvertTo-ReportHtml $summary.PrinterDriverCount)</td></tr>
<tr><td><strong>Microsoft Print to PDF</strong></td><td>$(ConvertTo-ReportHtml $summary.MicrosoftPrintToPDFPresent)</td></tr>
<tr><td><strong>Printer Health Score</strong></td><td>$(ConvertTo-ReportHtml $summary.PrinterHealthScore)</td></tr>
</table>
<h3>Per-Printer Details</h3>
<table>
<tr><td><strong>Printer</strong></td><td><strong>Default</strong></td><td><strong>Status</strong></td><td><strong>Shared</strong></td><td><strong>Queue Jobs</strong></td><td><strong>Driver</strong></td><td><strong>Driver Version</strong></td></tr>
$printerRows
</table>
<h3>Recommendations</h3>
<ul>
$recommendationRows
</ul>
"@
}

function New-NetworkHealthHtml {
    if (!$script:CleanupReport -or !$script:CleanupReport.NetworkHealth -or $script:CleanupReport.NetworkHealth.Count -eq 0) {
        return "<h2>Network Health</h2><p>No Network Health scan results were recorded for this run.</p>"
    }

    $network = $script:CleanupReport.NetworkHealth
    $addressRows = ""
    foreach ($address in @($network.ActiveIPv4Addresses)) {
        $primary = if ($address.IsPrimary) { "Primary" } else { "" }
        $addressRows += "<tr><td>$(ConvertTo-ReportHtml $address.Address)</td><td>$(ConvertTo-ReportHtml $primary)</td><td>$(ConvertTo-ReportHtml $address.ConnectionType)</td><td>$(ConvertTo-ReportHtml $address.InterfaceAlias)</td></tr>`n"
    }
    if (!$addressRows) {
        $addressRows = "<tr><td>Unknown</td><td></td><td>Unknown</td><td>Unknown</td></tr>"
    }

    $vpnText = if ($network.VPNAdaptersDetected -and $network.VPNAdaptersDetected.Count -gt 0) {
        (@($network.VPNAdaptersDetected) | ForEach-Object { "$($_.Name) ($($_.Status))" }) -join ", "
    }
    else {
        "None obvious"
    }

    return @"
<h2>Network Health</h2>
<table>
<tr><td><strong>Your IP Address</strong></td><td>$(ConvertTo-ReportHtml $network.YourIPAddress)</td></tr>
<tr><td><strong>Gateway</strong></td><td>$(ConvertTo-ReportHtml (Format-ReportList $network.Gateway))</td></tr>
<tr><td><strong>DNS Servers</strong></td><td>$(ConvertTo-ReportHtml (Format-ReportList $network.DNSServers))</td></tr>
<tr><td><strong>Connection Type</strong></td><td>$(ConvertTo-ReportHtml $network.ConnectionType)</td></tr>
<tr><td><strong>Wi-Fi and Ethernet Connected Together</strong></td><td>$(ConvertTo-ReportHtml $network.WifiAndEthernetConnected)</td></tr>
<tr><td><strong>VPN Adapters Detected</strong></td><td>$(ConvertTo-ReportHtml $vpnText)</td></tr>
<tr><td><strong>Internet Reachable</strong></td><td>$(ConvertTo-ReportHtml $network.InternetReachable)</td></tr>
<tr><td><strong>Gateway Reachable</strong></td><td>$(ConvertTo-ReportHtml $network.GatewayReachable)</td></tr>
</table>
<h3>Active IPv4 Addresses</h3>
<table>
<tr><td><strong>Address</strong></td><td><strong>Primary</strong></td><td><strong>Type</strong></td><td><strong>Adapter</strong></td></tr>
$addressRows
</table>
"@
}

function New-NetworkFirstAidHtml {
    if (!$script:CleanupReport -or !$script:CleanupReport.NetworkFirstAid -or $script:CleanupReport.NetworkFirstAid.Count -eq 0) {
        return "<h2>Network First Aid</h2><p>No Network First Aid actions were run during this session.</p>"
    }

    $rows = ""
    foreach ($result in @($script:CleanupReport.NetworkFirstAid)) {
        $rows += "<tr><td>$(ConvertTo-ReportHtml $result.Action)</td><td>$(ConvertTo-ReportHtml $result.Status)</td><td>$(ConvertTo-ReportHtml $result.Message)</td><td>$(ConvertTo-ReportHtml $result.PreviousIPv4)</td><td>$(ConvertTo-ReportHtml $result.CurrentIPv4)</td><td>$(ConvertTo-ReportHtml (Format-ReportList $result.Gateway))</td><td>$(ConvertTo-ReportHtml (Format-ReportList $result.DNSServers))</td></tr>`n"
    }

    return @"
<h2>Network First Aid</h2>
<p>These repair actions run only when selected by the user.</p>
<table>
<tr><td><strong>Action</strong></td><td><strong>Status</strong></td><td><strong>Message</strong></td><td><strong>Previous IP</strong></td><td><strong>Current IP</strong></td><td><strong>Gateway</strong></td><td><strong>DNS Servers</strong></td></tr>
$rows
</table>
"@
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
    $statistics = if ($script:CleanupReport) { $script:CleanupReport.Statistics } else { $null }
    $recoverableBytes = if ($statistics) { $statistics.RecoverableBytes } else { 0 }
    $recoveredBytes = if ($statistics) { $statistics.RecoveredBytes } else { 0 }
    $totalRecoveredBytes = if ($statistics) { $statistics.TotalRecoveredBytes } else { 0 }
    $pcHealthScore = if ($statistics) { $statistics.PCHealthScore } else { 100 }
    $filesIdentified = Get-ReportFilesIdentified
    $categoriesScanned = if ($script:CleanupReport -and $script:CleanupReport.CleanupCategories) { $script:CleanupReport.CleanupCategories.Count } else { $EstimatedCleanupTargets }
    $reportRunMode = if ($script:CleanupReport) { $script:CleanupReport.RunMode } else { $null }
    $cleanupStatus = Get-ReportCleanupStatus -RunMode $reportRunMode
    $potentialRecovery = Format-ReportBytes -Bytes $recoverableBytes
    $summaryItemsHtml = $null
    if ($reportRunMode -eq "BrowserHealth") {
        $browserSummary = if ($script:CleanupReport) { $script:CleanupReport.BrowserHealthSummary } else { $null }
        $browsersChecked = if ($browserSummary -and $null -ne $browserSummary.BrowsersChecked) { $browserSummary.BrowsersChecked } else { 0 }
        $installedBrowsers = if ($browserSummary -and $null -ne $browserSummary.InstalledBrowsers) { $browserSummary.InstalledBrowsers } else { 0 }
        $runningCount = if ($browserSummary -and $browserSummary.RunningBrowsers) { @($browserSummary.RunningBrowsers).Count } else { 0 }
        $summaryItemsHtml = @"
<div class="summary-item"><div class="summary-label">Browsers Checked</div><div class="summary-value">$browsersChecked</div></div>
<div class="summary-item"><div class="summary-label">Installed Browsers</div><div class="summary-value">$installedBrowsers</div></div>
<div class="summary-item"><div class="summary-label">Browser Processes</div><div class="summary-value">$runningCount running</div></div>
<div class="summary-item"><div class="summary-label">Cleanup Metrics</div><div class="summary-value">Not applicable</div></div>
"@
    }
    elseif ($reportRunMode -eq "PrinterHealth") {
        $printerSummary = if ($script:CleanupReport) { $script:CleanupReport.PrinterHealthSummary } else { $null }
        $printerScore = if ($printerSummary -and $null -ne $printerSummary.PrinterHealthScore) { $printerSummary.PrinterHealthScore } else { "Unknown" }
        $installedPrinters = if ($printerSummary -and $null -ne $printerSummary.InstalledPrinters) { $printerSummary.InstalledPrinters } else { 0 }
        $offlinePrinters = if ($printerSummary -and $null -ne $printerSummary.OfflinePrinters) { $printerSummary.OfflinePrinters } else { 0 }
        $queuedJobs = if ($printerSummary -and $null -ne $printerSummary.TotalQueuedJobs) { $printerSummary.TotalQueuedJobs } else { 0 }
        $summaryItemsHtml = @"
<div class="summary-item"><div class="summary-label">Printer Health Score</div><div class="summary-value">$printerScore</div></div>
<div class="summary-item"><div class="summary-label">Installed Printers</div><div class="summary-value">$installedPrinters</div></div>
<div class="summary-item"><div class="summary-label">Offline Printers</div><div class="summary-value">$offlinePrinters</div></div>
<div class="summary-item"><div class="summary-label">Queued Jobs</div><div class="summary-value">$queuedJobs</div></div>
"@
    }
    else {
        $summaryItemsHtml = @"
<div class="summary-item"><div class="summary-label">Potential Recovery</div><div class="summary-value">$potentialRecovery</div></div>
<div class="summary-item"><div class="summary-label">Files Identified</div><div class="summary-value">$filesIdentified</div></div>
<div class="summary-item"><div class="summary-label">Categories Scanned</div><div class="summary-value">$categoriesScanned</div></div>
<div class="summary-item"><div class="summary-label">Cleanup Status</div><div class="summary-value">$cleanupStatus</div></div>
"@
    }
    $browserHealthHtml = New-BrowserHealthHtml
    $printerHealthHtml = New-PrinterHealthHtml
    $networkHealthHtml = New-NetworkHealthHtml
    $networkFirstAidHtml = New-NetworkFirstAidHtml

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
.summary { display: grid; grid-template-columns: repeat(2, minmax(0, 1fr)); gap: 12px; margin: 20px 0; }
.summary-item { background: #f2f4f5; border-left: 4px solid #5d8892; border-radius: 8px; padding: 14px; }
.summary-label { color: #555; font-size: 12px; font-weight: bold; text-transform: uppercase; }
.summary-value { color: #15181c; font-size: 18px; font-weight: bold; margin-top: 4px; }
table { border-collapse: collapse; width: 100%; margin-top: 16px; }
td { border-bottom: 1px solid #ddd; padding: 10px; }
.footer { margin-top: 24px; font-size: 12px; color: #666; }
</style>
</head>
<body>
<div class="card">
<h1>BayouFinds Windows Cleanup Report</h1>
<p class="badge">$LicenseMode</p>

<div class="summary">
$summaryItemsHtml
</div>

<table>
<tr><td><strong>Tool Version</strong></td><td>$ToolVersion</td></tr>
<tr><td><strong>Session ID</strong></td><td>$SessionId</td></tr>
<tr><td><strong>Computer</strong></td><td>$computerName</td></tr>
<tr><td><strong>User</strong></td><td>$userName</td></tr>
<tr><td><strong>Started</strong></td><td>$($StartTime.ToString('yyyy-MM-dd HH:mm:ss'))</td></tr>
<tr><td><strong>Ended</strong></td><td>$($endTime.ToString('yyyy-MM-dd HH:mm:ss'))</td></tr>
<tr><td><strong>Estimated Cleanup Targets</strong></td><td>$(if (@("BrowserHealth", "PrinterHealth") -contains $reportRunMode) { "Not applicable" } else { $EstimatedCleanupTargets })</td></tr>
<tr><td><strong>Potential Recovery</strong></td><td>$(if (@("BrowserHealth", "PrinterHealth") -contains $reportRunMode) { "Not applicable" } else { "$recoverableBytes bytes" })</td></tr>
<tr><td><strong>Recovered This Run</strong></td><td>$(if (@("BrowserHealth", "PrinterHealth") -contains $reportRunMode) { "Not applicable" } else { "$recoveredBytes bytes" })</td></tr>
<tr><td><strong>Total Recovered</strong></td><td>$totalRecoveredBytes bytes</td></tr>
<tr><td><strong>PC Health Score</strong></td><td>$pcHealthScore / 100</td></tr>
<tr><td><strong>Log File</strong></td><td>$LogFile</td></tr>
<tr><td><strong>JSON Report</strong></td><td>$JsonReport</td></tr>
<tr><td><strong>Statistics File</strong></td><td>$StatsFile</td></tr>
<tr><td><strong>Browser Bookmark Backups</strong></td><td>$BrowserBackupDir</td></tr>
</table>

<h2>Output Location</h2>
<p>Your cleanup logs and reports are saved here:</p>
<p><strong>$LogDir</strong></p>

$browserHealthHtml

$printerHealthHtml

$networkHealthHtml

$networkFirstAidHtml

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
    if ($script:CleanupReport) {
        Write-CleanupStats -RunMode $script:CleanupReport.RunMode
    }
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
    if (!(Test-WindowsPlatform)) {
        return $false
    }

    try {
        $identity = [Security.Principal.WindowsIdentity]::GetCurrent()
        $principal = New-Object Security.Principal.WindowsPrincipal($identity)
        return [bool]$principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    }
    catch {
        Write-Log "WARN: Engine elevation check failed: $($_.Exception.Message)"
        return $false
    }
}

function Test-RunModeRequiresAdmin {
    param([string]$RunMode)

    return @("ResetNetwork") -contains $RunMode
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
        Write-Host "3. Browser Health"
        Write-Host "4. Network Health"
        Write-Host "5. Printer Health"
        Write-Host "6. Backup Browser Bookmarks"
        Write-Host "7. Refresh Website Addresses"
        Write-Host "8. Get New Network Address"
        Write-Host "9. Repair Windows Networking"
        Write-Host "10. View Last Report"
        Write-Host "11. Exit"
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
                return "BrowserHealth"
            }
            "4" {
                return "NetworkHealth"
            }
            "5" {
                return "PrinterHealth"
            }
            "6" {
                return "BackupBookmarks"
            }
            "7" {
                Write-Host "Refresh Website Addresses clears Windows saved website lookup results. It can help when websites do not open after a router, modem, or DNS change." -ForegroundColor Yellow
                $confirm = Read-Host "Type YES to run Refresh Website Addresses"
                if ($confirm -eq "YES") { return "FlushDns" }
            }
            "8" {
                Write-Host "Get New Network Address asks your router for a network address again. Your router may assign the same address again, which is normal." -ForegroundColor Yellow
                $confirm = Read-Host "Type YES to run Get New Network Address"
                if ($confirm -eq "YES") { return "RenewIp" }
            }
            "9" {
                Write-Host "Repair Windows Networking resets Winsock and the Windows IP network stack. A restart may be needed after this repair." -ForegroundColor Yellow
                $confirm = Read-Host "Type YES to run Repair Windows Networking"
                if ($confirm -eq "YES") { return "ResetNetwork" }
            }
            "10" {
                Open-LastReport
                Read-Host "Press Enter to return to the menu"
            }
            "11" {
                return "Exit"
            }
            default {
                Write-Host "Please choose a menu option." -ForegroundColor Yellow
                Start-Sleep -Seconds 1
            }
        }
    }
}
#endregion Platform and UI

#region Browser and network health
function Get-FolderSizeEstimate {
    param([string[]]$Paths)

    $bytes = 0L
    foreach ($path in @($Paths)) {
        if ([string]::IsNullOrWhiteSpace($path) -or !(Test-Path -Path $path -PathType Container)) {
            continue
        }

        try {
            Get-ChildItem -Path $path -Force -Recurse -File -ErrorAction SilentlyContinue | ForEach-Object {
                $bytes += [int64]$_.Length
            }
        }
        catch {
            Write-Log "WARN: Could not estimate folder size for $path. $($_.Exception.Message)"
        }
    }

    return $bytes
}

function Get-FileVersionValue {
    param([string]$Path)

    if ([string]::IsNullOrWhiteSpace($Path) -or !(Test-Path -Path $Path -PathType Leaf)) {
        return $null
    }

    try {
        $version = (Get-Item -Path $Path -ErrorAction Stop).VersionInfo.ProductVersion
        if (!$version) {
            $version = (Get-Item -Path $Path -ErrorAction Stop).VersionInfo.FileVersion
        }
        return $version
    }
    catch {
        return $null
    }
}

function Get-DefaultBrowserProgId {
    $userChoicePath = "HKCU:\Software\Microsoft\Windows\Shell\Associations\UrlAssociations\http\UserChoice"
    try {
        return (Get-ItemProperty -Path $userChoicePath -Name ProgId -ErrorAction Stop).ProgId
    }
    catch {
        return $null
    }
}

function Get-BrowserNameFromProgId {
    param([string]$ProgId)

    if (!$ProgId) {
        return "Unknown"
    }

    $normalized = $ProgId.ToLowerInvariant()
    if ($normalized -like "*chrome*") {
        return "Google Chrome"
    }
    if ($normalized -like "*edge*" -or $normalized -like "*mse*") {
        return "Microsoft Edge"
    }
    if ($normalized -like "*firefox*") {
        return "Mozilla Firefox"
    }

    return "Unknown ($ProgId)"
}

function Get-BrowserDefaultStatus {
    param(
        [string]$Browser,
        [string]$ProgId
    )

    if (!$ProgId) {
        return "Unknown"
    }

    $normalized = $ProgId.ToLowerInvariant()
    if ($Browser -eq "Google Chrome" -and $normalized -like "*chrome*") {
        return "Yes"
    }
    if ($Browser -eq "Microsoft Edge" -and ($normalized -like "*edge*" -or $normalized -like "*mse*")) {
        return "Yes"
    }
    if ($Browser -eq "Mozilla Firefox" -and $normalized -like "*firefox*") {
        return "Yes"
    }

    return "No"
}

function Get-FirstExistingPath {
    param([object[]]$Paths)

    foreach ($path in @($Paths)) {
        if ([string]::IsNullOrWhiteSpace([string]$path)) {
            continue
        }

        if (Test-Path -Path ([string]$path) -PathType Leaf) {
            return [string]$path
        }
    }

    return $null
}

function Join-OptionalPath {
    param(
        [string]$BasePath,
        [string]$ChildPath
    )

    if ([string]::IsNullOrWhiteSpace($BasePath)) {
        return $null
    }

    return Join-Path -Path $BasePath -ChildPath $ChildPath
}

function Get-BrowserRegistryInstall {
    param([string]$Browser)

    if (!(Test-WindowsPlatform)) {
        return $null
    }

    $uninstallPaths = @(
        "HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*",
        "HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*"
    )

    foreach ($uninstallPath in $uninstallPaths) {
        $matches = @(Get-ItemProperty -Path $uninstallPath -ErrorAction SilentlyContinue | Where-Object {
            $displayName = [string]$_.DisplayName
            if ([string]::IsNullOrWhiteSpace($displayName)) {
                return $false
            }

            if ($Browser -eq "Google Chrome") {
                return $displayName -like "Google Chrome*"
            }
            if ($Browser -eq "Microsoft Edge") {
                return $displayName -match "^Microsoft Edge( Beta| Dev| Canary)?$"
            }
            if ($Browser -eq "Mozilla Firefox") {
                return $displayName -like "Mozilla Firefox*"
            }

            return $false
        })

        if ($matches.Count -gt 0) {
            $match = $matches | Sort-Object DisplayName | Select-Object -First 1
            return [ordered]@{
                DisplayName = [string]$match.DisplayName
                DisplayVersion = [string]$match.DisplayVersion
                InstallLocation = [string]$match.InstallLocation
                Publisher = [string]$match.Publisher
            }
        }
    }

    return $null
}

function Resolve-BrowserInstall {
    param(
        [string]$Name,
        [object]$RegistryInfo,
        [object[]]$ExecutableCandidates,
        [bool]$ProfileFound
    )

    $exePath = Get-FirstExistingPath -Paths $ExecutableCandidates
    $installLocation = if ($RegistryInfo -and $RegistryInfo.InstallLocation) { [string]$RegistryInfo.InstallLocation } else { $null }
    if (!$installLocation -and $exePath) {
        $installLocation = Split-Path -Path $exePath -Parent
    }

    $version = if ($RegistryInfo -and $RegistryInfo.DisplayVersion) { [string]$RegistryInfo.DisplayVersion } else { $null }
    if (!$version -and $exePath) {
        $version = Get-FileVersionValue -Path $exePath
    }

    $detectionSource = "NotFound"
    if ($RegistryInfo) {
        $detectionSource = "Registry"
    }
    elseif ($exePath) {
        $detectionSource = "ExecutablePath"
    }
    elseif ($ProfileFound) {
        $detectionSource = "ProfileOnly"
    }

    return [ordered]@{
        Name = $Name
        Installed = $detectionSource -ne "NotFound"
        Version = $version
        ExecutablePath = $exePath
        InstallLocation = $installLocation
        Publisher = if ($RegistryInfo -and $RegistryInfo.Publisher) { [string]$RegistryInfo.Publisher } else { $null }
        DetectionSource = $detectionSource
    }
}

function Get-BrowserProcessCount {
    param([string[]]$ProcessNames)

    $count = 0
    foreach ($processName in @($ProcessNames)) {
        if ([string]::IsNullOrWhiteSpace($processName)) {
            continue
        }

        $count += @(Get-Process -Name $processName -ErrorAction SilentlyContinue).Count
    }

    return $count
}

function Get-ChromiumProfiles {
    param([string]$UserDataPath)

    if ([string]::IsNullOrWhiteSpace($UserDataPath) -or !(Test-Path -Path $UserDataPath -PathType Container)) {
        return @()
    }

    return @(Get-ChildItem -Path $UserDataPath -Directory -ErrorAction SilentlyContinue | Where-Object {
        $_.Name -eq "Default" -or $_.Name -like "Profile *"
    })
}

function Get-ChromiumExtensionCount {
    param([object[]]$Profiles)

    $count = 0
    foreach ($profile in @($Profiles)) {
        $extensionsPath = Join-Path -Path $profile.FullName -ChildPath "Extensions"
        if (Test-Path -Path $extensionsPath -PathType Container) {
            $count += @(Get-ChildItem -Path $extensionsPath -Directory -ErrorAction SilentlyContinue).Count
        }
    }

    return $count
}

function Get-ChromiumCachePaths {
    param([object[]]$Profiles)

    $paths = @()
    foreach ($profile in @($Profiles)) {
        $paths += Join-Path -Path $profile.FullName -ChildPath "Cache"
        $paths += Join-Path -Path $profile.FullName -ChildPath "Code Cache"
        $paths += Join-Path -Path $profile.FullName -ChildPath "GPUCache"
    }

    return $paths
}

function Get-FirefoxProfiles {
    if (!$env:APPDATA) {
        return @()
    }

    $profilesRoot = Join-Path -Path $env:APPDATA -ChildPath "Mozilla\Firefox\Profiles"
    if (!(Test-Path -Path $profilesRoot -PathType Container)) {
        return @()
    }

    return @(Get-ChildItem -Path $profilesRoot -Directory -ErrorAction SilentlyContinue)
}

function Get-FirefoxExtensionCount {
    param([object[]]$Profiles)

    $count = 0
    foreach ($profile in @($Profiles)) {
        $extensionsPath = Join-Path -Path $profile.FullName -ChildPath "extensions"
        if (Test-Path -Path $extensionsPath -PathType Container) {
            $count += @(Get-ChildItem -Path $extensionsPath -File -ErrorAction SilentlyContinue).Count
            $count += @(Get-ChildItem -Path $extensionsPath -Directory -ErrorAction SilentlyContinue).Count
        }
    }

    return $count
}

function Get-FirefoxCachePaths {
    param([object[]]$Profiles)

    $paths = @()
    if (!$env:LOCALAPPDATA) {
        return $paths
    }

    foreach ($profile in @($Profiles)) {
        $paths += Join-Path -Path $env:LOCALAPPDATA -ChildPath "Mozilla\Firefox\Profiles\$($profile.Name)\cache2"
        $paths += Join-Path -Path $env:LOCALAPPDATA -ChildPath "Mozilla\Firefox\Profiles\$($profile.Name)\startupCache"
    }

    return $paths
}

function New-BrowserHealthResult {
    param(
        [string]$Name,
        [string]$ExecutablePath,
        [bool]$Installed,
        [string]$Version,
        [string]$DefaultBrowserStatus,
        [nullable[int]]$ProfileCount,
        [nullable[int64]]$CacheBytes,
        [nullable[int]]$ExtensionCount,
        [int]$ProcessCount,
        [string]$UpdateStatus,
        [string]$DetectionSource,
        [string]$InstallLocation,
        [string]$Publisher
    )

    return [ordered]@{
        Name = $Name
        Installed = $Installed
        InstalledText = if ($Installed) { "Yes" } else { "No" }
        Status = if ($Installed) { "Installed" } else { "Not found" }
        Version = if ($Installed) { Format-ReportValue -Value $Version } else { "Not found" }
        DefaultBrowser = Format-ReportValue -Value $DefaultBrowserStatus
        ProfileCount = if ($null -ne $ProfileCount) { [int]$ProfileCount } else { 0 }
        CacheBytes = $CacheBytes
        CacheSize = if ($null -ne $CacheBytes) { Format-ReportBytes -Bytes $CacheBytes } else { "0 B" }
        ExtensionCount = if ($null -ne $ExtensionCount) { [int]$ExtensionCount } else { 0 }
        ProcessCount = $ProcessCount
        BrowserProcessesRunning = $ProcessCount -gt 0
        Running = $ProcessCount -gt 0
        RunningText = if ($ProcessCount -gt 0) { "Yes" } else { "No" }
        ProcessStatus = if ($ProcessCount -gt 0) { "Running ($ProcessCount)" } else { "Not running" }
        UpdateStatus = if ($UpdateStatus) { $UpdateStatus } else { "Unknown" }
        DetectionSource = if ($DetectionSource) { $DetectionSource } else { "Unknown" }
        ExecutablePath = $ExecutablePath
        ExePath = $ExecutablePath
        InstallLocation = Format-ReportValue -Value $InstallLocation
        Publisher = Format-ReportValue -Value $Publisher
    }
}

function Get-BrowserHealth {
    Write-Log "Browser Health scan started. Passwords, cookies, browsing history, and private browser data are not collected."

    $defaultProgId = Get-DefaultBrowserProgId
    $results = @()

    $chromeUserData = if ($env:LOCALAPPDATA) { Join-Path -Path $env:LOCALAPPDATA -ChildPath "Google\Chrome\User Data" } else { $null }
    $chromeProfiles = Get-ChromiumProfiles -UserDataPath $chromeUserData
    $chromeRegistry = Get-BrowserRegistryInstall -Browser "Google Chrome"
    $chromeInstall = Resolve-BrowserInstall -Name "Google Chrome" -RegistryInfo $chromeRegistry -ExecutableCandidates @(
        (Join-OptionalPath -BasePath $chromeRegistry.InstallLocation -ChildPath "chrome.exe"),
        (Join-OptionalPath -BasePath $chromeRegistry.InstallLocation -ChildPath "Application\chrome.exe"),
        (Join-OptionalPath -BasePath ${env:ProgramFiles} -ChildPath "Google\Chrome\Application\chrome.exe"),
        (Join-OptionalPath -BasePath ${env:ProgramFiles(x86)} -ChildPath "Google\Chrome\Application\chrome.exe"),
        (Join-OptionalPath -BasePath $env:LOCALAPPDATA -ChildPath "Google\Chrome\Application\chrome.exe")
    ) -ProfileFound ($chromeProfiles.Count -gt 0)
    $chromeCacheBytes = if ($chromeProfiles.Count -gt 0) { Get-FolderSizeEstimate -Paths (Get-ChromiumCachePaths -Profiles $chromeProfiles) } else { $null }
    $chromeExtensionCount = if ($chromeProfiles.Count -gt 0) { Get-ChromiumExtensionCount -Profiles $chromeProfiles } else { $null }
    $chromeProcessCount = Get-BrowserProcessCount -ProcessNames @("chrome")
    $results += New-BrowserHealthResult -Name "Google Chrome" -ExecutablePath $chromeInstall.ExecutablePath -Installed $chromeInstall.Installed -Version $chromeInstall.Version -DefaultBrowserStatus (Get-BrowserDefaultStatus -Browser "Google Chrome" -ProgId $defaultProgId) -ProfileCount $chromeProfiles.Count -CacheBytes $chromeCacheBytes -ExtensionCount $chromeExtensionCount -ProcessCount $chromeProcessCount -UpdateStatus "Unknown" -DetectionSource $chromeInstall.DetectionSource -InstallLocation $chromeInstall.InstallLocation -Publisher $chromeInstall.Publisher

    $edgeUserData = if ($env:LOCALAPPDATA) { Join-Path -Path $env:LOCALAPPDATA -ChildPath "Microsoft\Edge\User Data" } else { $null }
    $edgeProfiles = Get-ChromiumProfiles -UserDataPath $edgeUserData
    $edgeRegistry = Get-BrowserRegistryInstall -Browser "Microsoft Edge"
    $edgeInstall = Resolve-BrowserInstall -Name "Microsoft Edge" -RegistryInfo $edgeRegistry -ExecutableCandidates @(
        (Join-OptionalPath -BasePath $edgeRegistry.InstallLocation -ChildPath "msedge.exe"),
        (Join-OptionalPath -BasePath $edgeRegistry.InstallLocation -ChildPath "Application\msedge.exe"),
        (Join-OptionalPath -BasePath ${env:ProgramFiles(x86)} -ChildPath "Microsoft\Edge\Application\msedge.exe"),
        (Join-OptionalPath -BasePath ${env:ProgramFiles} -ChildPath "Microsoft\Edge\Application\msedge.exe")
    ) -ProfileFound ($edgeProfiles.Count -gt 0)
    $edgeCacheBytes = if ($edgeProfiles.Count -gt 0) { Get-FolderSizeEstimate -Paths (Get-ChromiumCachePaths -Profiles $edgeProfiles) } else { $null }
    $edgeExtensionCount = if ($edgeProfiles.Count -gt 0) { Get-ChromiumExtensionCount -Profiles $edgeProfiles } else { $null }
    $edgeProcessCount = Get-BrowserProcessCount -ProcessNames @("msedge")
    $results += New-BrowserHealthResult -Name "Microsoft Edge" -ExecutablePath $edgeInstall.ExecutablePath -Installed $edgeInstall.Installed -Version $edgeInstall.Version -DefaultBrowserStatus (Get-BrowserDefaultStatus -Browser "Microsoft Edge" -ProgId $defaultProgId) -ProfileCount $edgeProfiles.Count -CacheBytes $edgeCacheBytes -ExtensionCount $edgeExtensionCount -ProcessCount $edgeProcessCount -UpdateStatus "Unknown" -DetectionSource $edgeInstall.DetectionSource -InstallLocation $edgeInstall.InstallLocation -Publisher $edgeInstall.Publisher

    $firefoxProfiles = Get-FirefoxProfiles
    $firefoxRegistry = Get-BrowserRegistryInstall -Browser "Mozilla Firefox"
    $firefoxInstall = Resolve-BrowserInstall -Name "Mozilla Firefox" -RegistryInfo $firefoxRegistry -ExecutableCandidates @(
        (Join-OptionalPath -BasePath $firefoxRegistry.InstallLocation -ChildPath "firefox.exe"),
        (Join-OptionalPath -BasePath ${env:ProgramFiles} -ChildPath "Mozilla Firefox\firefox.exe"),
        (Join-OptionalPath -BasePath ${env:ProgramFiles(x86)} -ChildPath "Mozilla Firefox\firefox.exe")
    ) -ProfileFound ($firefoxProfiles.Count -gt 0)
    $firefoxCacheBytes = if ($firefoxProfiles.Count -gt 0) { Get-FolderSizeEstimate -Paths (Get-FirefoxCachePaths -Profiles $firefoxProfiles) } else { $null }
    $firefoxExtensionCount = if ($firefoxProfiles.Count -gt 0) { Get-FirefoxExtensionCount -Profiles $firefoxProfiles } else { $null }
    $firefoxProcessCount = Get-BrowserProcessCount -ProcessNames @("firefox")
    $results += New-BrowserHealthResult -Name "Mozilla Firefox" -ExecutablePath $firefoxInstall.ExecutablePath -Installed $firefoxInstall.Installed -Version $firefoxInstall.Version -DefaultBrowserStatus (Get-BrowserDefaultStatus -Browser "Mozilla Firefox" -ProgId $defaultProgId) -ProfileCount $firefoxProfiles.Count -CacheBytes $firefoxCacheBytes -ExtensionCount $firefoxExtensionCount -ProcessCount $firefoxProcessCount -UpdateStatus "Unknown" -DetectionSource $firefoxInstall.DetectionSource -InstallLocation $firefoxInstall.InstallLocation -Publisher $firefoxInstall.Publisher

    $totalCacheBytes = 0L
    $totalProfiles = 0
    $totalExtensions = 0
    $runningBrowsers = @()
    foreach ($browser in @($results)) {
        if ($null -ne $browser.CacheBytes) {
            $totalCacheBytes += [int64]$browser.CacheBytes
        }
        if ($null -ne $browser.ProfileCount) {
            $totalProfiles += [int]$browser.ProfileCount
        }
        if ($null -ne $browser.ExtensionCount) {
            $totalExtensions += [int]$browser.ExtensionCount
        }
        if ($browser.ProcessCount -gt 0) {
            $runningBrowsers += [ordered]@{
                Name = $browser.Name
                ProcessCount = $browser.ProcessCount
            }
        }
    }

    $summary = [ordered]@{
        DefaultBrowser = Get-BrowserNameFromProgId -ProgId $defaultProgId
        DefaultBrowserProgId = Format-ReportValue -Value $defaultProgId
        BrowsersChecked = $results.Count
        InstalledBrowsers = @($results | Where-Object { $_.Installed }).Count
        TotalProfiles = $totalProfiles
        TotalExtensions = $totalExtensions
        TotalCacheBytes = $totalCacheBytes
        TotalCacheSize = Format-ReportBytes -Bytes $totalCacheBytes
        RunningBrowsers = @($runningBrowsers)
        PrivacyNote = "Browser Health does not collect passwords, cookies, browsing history, autofill, or private browser data."
    }

    Set-ReportBrowserHealth -BrowserHealth $results -Summary $summary
    Add-ReportNote -Message "Browser Health reports browser install, version, default browser, profile count, extension count, cache estimate, and process count only. Passwords, cookies, browsing history, autofill, and private browser data are not collected."
    Write-Log "Browser Health scan complete."
    return $results
}

function ConvertTo-YesNo {
    param([bool]$Value)

    if ($Value) {
        return "Yes"
    }

    return "No"
}

function Format-JobAge {
    param([nullable[timespan]]$Age)

    if ($null -eq $Age) {
        return "Unknown"
    }

    if ($Age.Value.TotalDays -ge 1) {
        return "{0:N0} days" -f [Math]::Floor($Age.Value.TotalDays)
    }
    if ($Age.Value.TotalHours -ge 1) {
        return "{0:N0} hours" -f [Math]::Floor($Age.Value.TotalHours)
    }
    if ($Age.Value.TotalMinutes -ge 1) {
        return "{0:N0} minutes" -f [Math]::Floor($Age.Value.TotalMinutes)
    }

    return "Less than 1 minute"
}

function Get-PrinterDriverVersion {
    param([object]$Driver)

    if (!$Driver) {
        return "Unknown"
    }

    foreach ($propertyName in @("DriverVersion", "Version", "MajorVersion")) {
        if ($Driver.PSObject.Properties.Name -contains $propertyName -and $null -ne $Driver.$propertyName) {
            return [string]$Driver.$propertyName
        }
    }

    return "Unknown"
}

function Get-PrinterRecommendations {
    param([object]$Summary)

    $recommendations = @()

    if ($Summary.SpoolerServiceStatus -ne "Running") {
        $recommendations += "The Windows print spooler is not running."
    }
    if ([int]$Summary.OfflinePrinters -gt 0) {
        $recommendations += "$($Summary.OfflinePrinters) printer(s) appear offline."
    }
    if ([int]$Summary.TotalQueuedJobs -gt 0) {
        $recommendations += "$($Summary.TotalQueuedJobs) print job(s) are waiting in queue."
    }
    if ([int]$Summary.StuckPrintJobsEstimate -gt 0) {
        $recommendations += "$($Summary.StuckPrintJobsEstimate) print job(s) may be stuck."
    }
    if ($Summary.DefaultPrinter -eq "Unknown" -or $Summary.DefaultPrinter -eq "None detected") {
        $recommendations += "No default printer was detected."
    }

    if ($recommendations.Count -eq 0) {
        $recommendations += "No printer problems were detected."
    }

    return @($recommendations)
}

function Get-PrinterHealthScore {
    param([object]$Summary)

    $score = 100
    if ($Summary.SpoolerServiceStatus -ne "Running") {
        $score -= 35
    }
    $score -= [Math]::Min(25, ([int]$Summary.OfflinePrinters * 10))
    $score -= [Math]::Min(20, ([int]$Summary.StuckPrintJobsEstimate * 8))
    $score -= [Math]::Min(10, ([int]$Summary.TotalQueuedJobs * 2))
    if ($Summary.DefaultPrinter -eq "Unknown" -or $Summary.DefaultPrinter -eq "None detected") {
        $score -= 10
    }

    return [Math]::Max(0, [Math]::Min(100, $score))
}

function Get-PrinterHealth {
    Write-Log "Printer Health scan started. This check is read-only and does not clear queues, restart services, remove printers, or remove drivers."

    if (!(Test-WindowsPlatform)) {
        $summary = [ordered]@{
            DefaultPrinter = "Unknown"
            InstalledPrinters = 0
            OnlinePrinters = 0
            OfflinePrinters = 0
            SpoolerServiceStatus = "Unavailable"
            TotalQueuedJobs = 0
            StuckPrintJobsEstimate = 0
            OldestQueuedJobAge = "Unknown"
            OldestQueuedJobAgeMinutes = $null
            PrinterDriverCount = 0
            MicrosoftPrintToPDFPresent = "Unknown"
            PrinterHealthScore = 100
            Recommendations = @("Printer Health requires Windows printer APIs. No printer checks were run in this environment.")
            SafetyNote = "Printer Health is read-only. No queues, services, printers, or drivers are changed."
        }
        Set-ReportPrinterHealth -Summary $summary -Details @()
        Add-ReportNote -Message "Printer Health skipped Windows printer APIs because this validation run is not on Windows."
        Write-Log "Printer Health scan complete."
        return $summary
    }

    $printers = @(Get-Printer -ErrorAction SilentlyContinue)
    $cimPrinters = @(Get-CimInstance -ClassName Win32_Printer -ErrorAction SilentlyContinue)
    $drivers = @(Get-PrinterDriver -ErrorAction SilentlyContinue)
    $spooler = Get-Service -Name Spooler -ErrorAction SilentlyContinue
    $defaultPrinter = $cimPrinters | Where-Object { $_.Default } | Select-Object -First 1
    $defaultPrinterName = if ($defaultPrinter) { [string]$defaultPrinter.Name } else { "None detected" }

    $driverLookup = @{}
    foreach ($driver in @($drivers)) {
        if ($driver.Name -and !$driverLookup.ContainsKey($driver.Name)) {
            $driverLookup[$driver.Name] = $driver
        }
    }

    $details = @()
    $totalQueuedJobs = 0
    $stuckJobs = 0
    $oldestAge = $null
    $now = Get-Date

    foreach ($printer in @($printers)) {
        $printerName = [string]$printer.Name
        $queueJobs = @(Get-PrintJob -PrinterName $printerName -ErrorAction SilentlyContinue)
        $queueCount = $queueJobs.Count
        $totalQueuedJobs += $queueCount

        foreach ($job in @($queueJobs)) {
            $submitted = $null
            if ($job.PSObject.Properties.Name -contains "SubmittedTime" -and $job.SubmittedTime) {
                $submitted = [datetime]$job.SubmittedTime
            }
            elseif ($job.PSObject.Properties.Name -contains "TimeSubmitted" -and $job.TimeSubmitted) {
                $submitted = [datetime]$job.TimeSubmitted
            }

            if ($submitted) {
                $age = $now - $submitted
                if ($null -eq $oldestAge -or $age -gt $oldestAge) {
                    $oldestAge = $age
                }
                if ($age.TotalMinutes -ge 15) {
                    $stuckJobs++
                }
            }
        }

        $isOffline = [bool]$printer.WorkOffline -or ([string]$printer.PrinterStatus -match "Offline|Error")
        $driverName = Format-ReportValue -Value $printer.DriverName
        $driver = if ($driverLookup.ContainsKey($printer.DriverName)) { $driverLookup[$printer.DriverName] } else { $null }

        $details += [ordered]@{
            Name = $printerName
            DefaultPrinter = ConvertTo-YesNo -Value ($printerName -eq $defaultPrinterName)
            Online = -not $isOffline
            Status = if ($isOffline) { "Offline" } else { "Online" }
            Shared = ConvertTo-YesNo -Value ([bool]$printer.Shared)
            QueueJobCount = $queueCount
            DriverName = $driverName
            DriverVersion = Get-PrinterDriverVersion -Driver $driver
        }
    }

    $offlineCount = @($details | Where-Object { $_.Status -eq "Offline" }).Count
    $onlineCount = @($details | Where-Object { $_.Status -eq "Online" }).Count
    $microsoftPrintToPdf = @($printers | Where-Object { $_.Name -eq "Microsoft Print to PDF" }).Count -gt 0

    $summary = [ordered]@{
        DefaultPrinter = $defaultPrinterName
        InstalledPrinters = $printers.Count
        OnlinePrinters = $onlineCount
        OfflinePrinters = $offlineCount
        SpoolerServiceStatus = if ($spooler) { [string]$spooler.Status } else { "Unknown" }
        TotalQueuedJobs = $totalQueuedJobs
        StuckPrintJobsEstimate = $stuckJobs
        OldestQueuedJobAge = Format-JobAge -Age $oldestAge
        OldestQueuedJobAgeMinutes = if ($null -ne $oldestAge) { [Math]::Round($oldestAge.TotalMinutes, 1) } else { $null }
        PrinterDriverCount = $drivers.Count
        MicrosoftPrintToPDFPresent = ConvertTo-YesNo -Value $microsoftPrintToPdf
        PrinterHealthScore = 100
        Recommendations = @()
        SafetyNote = "Printer Health is read-only. No queues, services, printers, or drivers are changed."
    }
    $summary.PrinterHealthScore = Get-PrinterHealthScore -Summary $summary
    $summary.Recommendations = Get-PrinterRecommendations -Summary $summary

    Set-ReportPrinterHealth -Summary $summary -Details $details
    Add-ReportNote -Message "Printer Health is read-only. It does not clear queues, restart the spooler, remove printers, or remove drivers."
    Write-Log "Printer Health scan complete."
    return $summary
}

function Get-NetworkAdapterKind {
    param([object]$Adapter)

    $text = "$($Adapter.Name) $($Adapter.InterfaceDescription)".ToLowerInvariant()
    if ($text -match "wi-fi|wifi|wireless|wlan|802\.11") {
        return "Wi-Fi"
    }
    if ($text -match "ethernet|gbe|lan|realtek|intel\(r\)") {
        return "Ethernet"
    }
    return "Other"
}

function Test-VpnAdapterName {
    param([object]$Adapter)

    $text = "$($Adapter.Name) $($Adapter.InterfaceDescription)".ToLowerInvariant()
    return $text -match "vpn|wireguard|openvpn|tap-|tap |tun |tunnel|tailscale|zerotier|zscaler|globalprotect|anyconnect|cisco|fortinet|nord|expressvpn|protonvpn|surfshark"
}

function Get-PrimaryIPv4Address {
    $route = Get-NetRoute -DestinationPrefix "0.0.0.0/0" -ErrorAction SilentlyContinue |
        Sort-Object RouteMetric, InterfaceMetric |
        Select-Object -First 1

    if (!$route) {
        return $null
    }

    $address = Get-NetIPAddress -AddressFamily IPv4 -InterfaceIndex $route.InterfaceIndex -ErrorAction SilentlyContinue |
        Where-Object { $_.IPAddress -and $_.IPAddress -notlike "169.254.*" } |
        Select-Object -First 1

    if (!$address) {
        return $null
    }

    return $address.IPAddress
}

function Test-HostReachable {
    param([string]$Target)

    if ([string]::IsNullOrWhiteSpace($Target)) {
        return "Unknown"
    }

    try {
        if (Test-Connection -ComputerName $Target -Count 1 -Quiet -ErrorAction Stop) {
            return "Yes"
        }
        return "No"
    }
    catch {
        return "Unknown"
    }
}

function Get-NetworkHealth {
    Write-Log "Network Health scan started."

    $primaryIpv4 = Get-PrimaryIPv4Address
    $ipConfigurations = @(Get-NetIPConfiguration -ErrorAction SilentlyContinue)
    $connectedAdapters = @(Get-NetAdapter -Physical -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq "Up" })
    if ($connectedAdapters.Count -eq 0) {
        $connectedAdapters = @(Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq "Up" })
    }

    $addresses = @()
    $gateways = @()
    $dnsServers = @()
    foreach ($config in $ipConfigurations) {
        $adapter = Get-NetAdapter -InterfaceIndex $config.InterfaceIndex -ErrorAction SilentlyContinue
        $kind = if ($adapter) { Get-NetworkAdapterKind -Adapter $adapter } else { "Other" }

        foreach ($ip in @($config.IPv4Address)) {
            if (!$ip.IPAddress) {
                continue
            }

            $addresses += [ordered]@{
                Address = $ip.IPAddress
                InterfaceAlias = $config.InterfaceAlias
                ConnectionType = $kind
                IsPrimary = ($ip.IPAddress -eq $primaryIpv4)
            }
        }

        foreach ($gateway in @($config.IPv4DefaultGateway)) {
            if ($gateway.NextHop -and $gateways -notcontains $gateway.NextHop) {
                $gateways += $gateway.NextHop
            }
        }

        foreach ($server in @($config.DNSServer.ServerAddresses)) {
            if ($server -and $server -match "^\d{1,3}(\.\d{1,3}){3}$" -and $dnsServers -notcontains $server) {
                $dnsServers += $server
            }
        }
    }

    $hasWifi = $false
    $hasEthernet = $false
    foreach ($adapter in $connectedAdapters) {
        $kind = Get-NetworkAdapterKind -Adapter $adapter
        if ($kind -eq "Wi-Fi") {
            $hasWifi = $true
        }
        elseif ($kind -eq "Ethernet") {
            $hasEthernet = $true
        }
    }

    $vpnAdapters = @()
    foreach ($adapter in @(Get-NetAdapter -ErrorAction SilentlyContinue | Where-Object { $_.Status -eq "Up" })) {
        if (Test-VpnAdapterName -Adapter $adapter) {
            $vpnAdapters += [ordered]@{
                Name = $adapter.Name
                Description = $adapter.InterfaceDescription
                Status = $adapter.Status
            }
        }
    }

    $connectionType = if ($hasWifi -and $hasEthernet) {
        "both"
    }
    elseif ($hasWifi) {
        "Wi-Fi"
    }
    elseif ($hasEthernet) {
        "Ethernet"
    }
    else {
        "Unknown"
    }

    $gatewayReachable = if ($gateways.Count -gt 0) { Test-HostReachable -Target $gateways[0] } else { "Unknown" }
    $internetReachable = Test-HostReachable -Target "1.1.1.1"

    $result = [ordered]@{
        YourIPAddress = Format-ReportValue -Value $primaryIpv4
        ActiveIPv4Addresses = @($addresses)
        Gateway = @($gateways)
        DNSServers = @($dnsServers)
        ConnectionType = $connectionType
        WifiAndEthernetConnected = [bool]($hasWifi -and $hasEthernet)
        VPNAdaptersDetected = @($vpnAdapters)
        InternetReachable = $internetReachable
        GatewayReachable = $gatewayReachable
        CheckedAt = (Get-Date).ToString("o")
    }

    Set-ReportNetworkHealth -NetworkHealth $result
    Write-Log "Network Health scan complete. Primary IPv4: $($result.YourIPAddress)"
    return $result
}

function New-NetworkFirstAidResult {
    param(
        [string]$Action,
        [string]$Description,
        [string]$Status,
        [int]$ExitCode,
        [string]$Message,
        [string]$PreviousIPv4 = $null,
        [string]$CurrentIPv4 = $null,
        [object]$NetworkHealth = $null
    )

    return [ordered]@{
        Action = $Action
        Description = $Description
        Status = $Status
        ExitCode = $ExitCode
        Message = $Message
        PreviousIPv4 = Format-ReportValue -Value $PreviousIPv4
        CurrentIPv4 = Format-ReportValue -Value $CurrentIPv4
        Gateway = if ($NetworkHealth) { @($NetworkHealth.Gateway) } else { @() }
        DNSServers = if ($NetworkHealth) { @($NetworkHealth.DNSServers) } else { @() }
        RanAt = (Get-Date).ToString("o")
    }
}

function Invoke-FlushDnsFirstAid {
    $description = "Refresh Website Addresses clears Windows saved website lookup results. It can help when websites do not open after a router, modem, or DNS change."
    Write-Log "Network First Aid: Refresh Website Addresses started."
    ipconfig.exe /flushdns | Tee-Object -FilePath $LogFile -Append | Out-Null
    $exitCode = $LASTEXITCODE
    $status = if ($exitCode -eq 0) { "Completed" } else { "Failed" }
    $result = New-NetworkFirstAidResult -Action "Refresh Website Addresses" -Description $description -Status $status -ExitCode $exitCode -Message "DNS refresh finished."
    Add-ReportNetworkFirstAid -Result $result
    return $result
}

function Invoke-RenewIpFirstAid {
    $description = "Get New Network Address asks your router for a network address again. Your router may assign the same address again, which is normal."
    Write-Log "Network First Aid: Get New Network Address started."
    $previousIpv4 = Get-PrimaryIPv4Address
    ipconfig.exe /renew | Tee-Object -FilePath $LogFile -Append | Out-Null
    $exitCode = $LASTEXITCODE
    Start-Sleep -Seconds 2
    $networkHealth = Get-NetworkHealth
    $currentIpv4 = Get-PrimaryIPv4Address
    $message = if ($previousIpv4 -and $currentIpv4 -and $previousIpv4 -eq $currentIpv4) {
        "Your router assigned the same address again. This is normal."
    }
    else {
        "Network address renewal finished."
    }
    $status = if ($exitCode -eq 0) { "Completed" } else { "Failed" }
    $result = New-NetworkFirstAidResult -Action "Get New Network Address" -Description $description -Status $status -ExitCode $exitCode -Message $message -PreviousIPv4 $previousIpv4 -CurrentIPv4 $currentIpv4 -NetworkHealth $networkHealth
    Add-ReportNetworkFirstAid -Result $result
    return $result
}

function Invoke-ResetNetworkFirstAid {
    $description = "Repair Windows Networking resets Winsock and the Windows IP network stack. A restart may be needed after this repair."
    Write-Log "Network First Aid: Repair Windows Networking started."
    netsh.exe winsock reset | Tee-Object -FilePath $LogFile -Append | Out-Null
    $winsockExitCode = $LASTEXITCODE
    netsh.exe int ip reset | Tee-Object -FilePath $LogFile -Append | Out-Null
    $ipResetExitCode = $LASTEXITCODE
    $exitCode = if ($winsockExitCode -eq 0 -and $ipResetExitCode -eq 0) { 0 } else { 1 }
    $status = if ($exitCode -eq 0) { "Completed" } else { "Failed" }
    $networkHealth = Get-NetworkHealth
    $result = New-NetworkFirstAidResult -Action "Repair Windows Networking" -Description $description -Status $status -ExitCode $exitCode -Message "Windows networking repair finished. Restart Windows if connection problems continue." -CurrentIPv4 (Get-PrimaryIPv4Address) -NetworkHealth $networkHealth
    Add-ReportNetworkFirstAid -Result $result
    return $result
}


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
        return [ordered]@{
            FilesRemoved = 0
            BytesRemoved = 0
        }
    }

    if ($AddToReport) {
        Add-ReportCategory -Label $Label
    }

    Write-Log "Cleaning: $Label - $Path"
    $before = Measure-CleanupPath -Path $Path

    if ($script:EffectiveDryRun) {
        Get-ChildItem -Path $Path -Force -Recurse | Select-Object -First 20 | ForEach-Object {
            Write-Log "DRYRUN: Would remove $($_.FullName)"
        }
        return [ordered]@{
            FilesRemoved = 0
            BytesRemoved = 0
        }
    }

    if ($PSCmdlet.ShouldProcess($Path, "Remove cleanup contents for $Label")) {
        Get-ChildItem -Path $Path -Force -Recurse | Remove-Item -Force -Recurse
    }

    $after = Measure-CleanupPath -Path $Path
    $filesRemoved = [Math]::Max(0, [int64]$before.EstimatedFiles - [int64]$after.EstimatedFiles)
    $bytesRemoved = [Math]::Max(0, [int64]$before.EstimatedBytes - [int64]$after.EstimatedBytes)

    return [ordered]@{
        FilesRemoved = $filesRemoved
        BytesRemoved = $bytesRemoved
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
            -DefaultEnabled $false `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "windows_web_cache" `
            -Label "Windows web cache" `
            -Description "Windows web cache files for the current user." `
            -Paths @((Join-Path -Path $env:LOCALAPPDATA -ChildPath "Microsoft\Windows\WebCache")) `
            -DefaultEnabled $false `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "edge_cache" `
            -Label "Microsoft Edge cache" `
            -Description "Microsoft Edge cache files for the default profile. Skipped while Edge is running." `
            -Paths @((Join-Path -Path $env:LOCALAPPDATA -ChildPath "Microsoft\Edge\User Data\Default\Cache")) `
            -DefaultEnabled $false `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -SkipIfProcessRunning @("msedge") `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "chrome_cache" `
            -Label "Google Chrome cache" `
            -Description "Google Chrome cache files for the default profile. Skipped while Chrome is running." `
            -Paths @((Join-Path -Path $env:LOCALAPPDATA -ChildPath "Google\Chrome\User Data\Default\Cache")) `
            -DefaultEnabled $false `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -SkipIfProcessRunning @("chrome") `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "discord_cache" `
            -Label "Discord cache" `
            -Description "Discord cache, temporary log, and crash-report files. Skipped while Discord is running." `
            -Paths @(
                (Join-Path -Path $env:APPDATA -ChildPath "discord\Cache"),
                (Join-Path -Path $env:APPDATA -ChildPath "discord\Code Cache"),
                (Join-Path -Path $env:APPDATA -ChildPath "discord\GPUCache"),
                (Join-Path -Path $env:APPDATA -ChildPath "discord\logs"),
                (Join-Path -Path $env:APPDATA -ChildPath "discord\Crashpad\reports")
            ) `
            -DefaultEnabled $true `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -SkipIfProcessRunning @("Discord") `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "discord_ptb_cache" `
            -Label "Discord PTB cache" `
            -Description "Discord PTB cache, temporary log, and crash-report files. Skipped while Discord PTB is running." `
            -Paths @(
                (Join-Path -Path $env:APPDATA -ChildPath "discordptb\Cache"),
                (Join-Path -Path $env:APPDATA -ChildPath "discordptb\Code Cache"),
                (Join-Path -Path $env:APPDATA -ChildPath "discordptb\GPUCache"),
                (Join-Path -Path $env:APPDATA -ChildPath "discordptb\logs"),
                (Join-Path -Path $env:APPDATA -ChildPath "discordptb\Crashpad\reports")
            ) `
            -DefaultEnabled $true `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -SkipIfProcessRunning @("DiscordPTB") `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "discord_canary_cache" `
            -Label "Discord Canary cache" `
            -Description "Discord Canary cache, temporary log, and crash-report files. Skipped while Discord Canary is running." `
            -Paths @(
                (Join-Path -Path $env:APPDATA -ChildPath "discordcanary\Cache"),
                (Join-Path -Path $env:APPDATA -ChildPath "discordcanary\Code Cache"),
                (Join-Path -Path $env:APPDATA -ChildPath "discordcanary\GPUCache"),
                (Join-Path -Path $env:APPDATA -ChildPath "discordcanary\logs"),
                (Join-Path -Path $env:APPDATA -ChildPath "discordcanary\Crashpad\reports")
            ) `
            -DefaultEnabled $true `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -SkipIfProcessRunning @("DiscordCanary") `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "teams_cache" `
            -Label "Microsoft Teams cache" `
            -Description "Microsoft Teams cache, temporary log, and crash-report files. Skipped while Teams is running." `
            -Paths @(
                (Join-Path -Path $env:APPDATA -ChildPath "Microsoft\Teams\Cache"),
                (Join-Path -Path $env:APPDATA -ChildPath "Microsoft\Teams\Code Cache"),
                (Join-Path -Path $env:APPDATA -ChildPath "Microsoft\Teams\GPUCache"),
                (Join-Path -Path $env:APPDATA -ChildPath "Microsoft\Teams\logs"),
                (Join-Path -Path $env:APPDATA -ChildPath "Microsoft\Teams\Crashpad\reports"),
                (Join-Path -Path $env:LOCALAPPDATA -ChildPath "Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\Cache"),
                (Join-Path -Path $env:LOCALAPPDATA -ChildPath "Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\Code Cache"),
                (Join-Path -Path $env:LOCALAPPDATA -ChildPath "Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\GPUCache"),
                (Join-Path -Path $env:LOCALAPPDATA -ChildPath "Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\Logs"),
                (Join-Path -Path $env:LOCALAPPDATA -ChildPath "Packages\MSTeams_8wekyb3d8bbwe\LocalCache\Microsoft\MSTeams\Crashpad\reports")
            ) `
            -DefaultEnabled $true `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -SkipIfProcessRunning @("Teams", "ms-teams", "msteams") `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "slack_cache" `
            -Label "Slack cache" `
            -Description "Slack cache, temporary log, and crash-report files. Skipped while Slack is running." `
            -Paths @(
                (Join-Path -Path $env:APPDATA -ChildPath "Slack\Cache"),
                (Join-Path -Path $env:APPDATA -ChildPath "Slack\Code Cache"),
                (Join-Path -Path $env:APPDATA -ChildPath "Slack\GPUCache"),
                (Join-Path -Path $env:APPDATA -ChildPath "Slack\logs"),
                (Join-Path -Path $env:APPDATA -ChildPath "Slack\Crashpad\reports")
            ) `
            -DefaultEnabled $true `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -SkipIfProcessRunning @("slack") `
            -RiskLevel "Low"

        New-CleanupCategory `
            -Id "zoom_cache" `
            -Label "Zoom cache" `
            -Description "Zoom cache, temporary log, and crash-report files. Skipped while Zoom is running." `
            -Paths @(
                (Join-Path -Path $env:APPDATA -ChildPath "Zoom\data\Cache"),
                (Join-Path -Path $env:APPDATA -ChildPath "Zoom\data\Code Cache"),
                (Join-Path -Path $env:APPDATA -ChildPath "Zoom\data\GPUCache"),
                (Join-Path -Path $env:APPDATA -ChildPath "Zoom\data\logs"),
                (Join-Path -Path $env:APPDATA -ChildPath "Zoom\data\Crashpad\reports"),
                (Join-Path -Path $env:APPDATA -ChildPath "Zoom\logs")
            ) `
            -DefaultEnabled $true `
            -RequiresAdmin $false `
            -RequiresConfirmation $false `
            -SkipIfProcessRunning @("Zoom") `
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

    if ($Category.RequiresAdmin -and !(Test-Admin)) {
        Write-Log "SKIP: $($Category.Label) requires Administrator access."
        $Category.Status = "Skipped"
        $Category.SkippedReason = "Administrator access required"
        $Category.PathsSkipped += $Category.Paths
        $Category.EndedAt = (Get-Date).ToString("o")
        Add-ReportCleanupCategory -Category $Category
        Add-ReportSkippedItem -Label $Category.Label -Path ($Category.Paths -join "; ") -Reason "Administrator access required"
        return
    }

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
            $pathEstimate = Measure-CleanupPath -Path $path
            $Category.EstimatedBytes += [int64]$pathEstimate.EstimatedBytes
            $Category.EstimatedFiles += [int64]$pathEstimate.EstimatedFiles
        }
        else {
            $Category.PathsSkipped += $path
        }

        $cleanupResult = Remove-Contents -Path $path -Label $Category.Label -AddToReport $false
        $Category.ActualBytesRemoved += [int64]$cleanupResult.BytesRemoved
        $Category.ActualFilesRemoved += [int64]$cleanupResult.FilesRemoved
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
    Get-BrowserHealth | Out-Null
    Get-NetworkHealth | Out-Null

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
    Add-ReportNote -Message "Browser cache and browser data cleanup are not run automatically."

    foreach ($category in $cleanupCategories) {
        Invoke-CleanupCategory -Category $category
    }

    Write-Log "Windows Update download cache cleanup skipped. Windows Update reset is not part of safe cleanup."
    Add-ReportNote -Message "Windows Update download cache cleanup skipped by default."

    Write-Log "DNS refresh skipped. Use Network First Aid > Refresh Website Addresses to run it explicitly."
    Add-ReportNote -Message "DNS refresh is not run automatically. Use Network First Aid > Refresh Website Addresses if needed."

    if (!(Test-Admin)) {
        Write-Log "Skipping DISM component cleanup because Administrator access is required."
        Add-ReportNote -Message "DISM component cleanup skipped because Administrator access is required."
    }
    else {
        Write-Log "Running DISM component cleanup..."
    }
    if (!$script:EffectiveDryRun -and (Test-Admin)) {
        if ($PSCmdlet.ShouldProcess("Windows component store", "Run DISM component cleanup")) {
            DISM.exe /Online /Cleanup-Image /StartComponentCleanup | Tee-Object -FilePath $LogFile -Append
            Write-Log "DISM.exe exit code: $LASTEXITCODE"
        }
    }

    if ($SkipSFC) {
        Write-Log "Skipping system file integrity scan. Use -SkipSFC:`$false to run SFC."
    }
    elseif (!(Test-Admin)) {
        Write-Log "Skipping system file integrity scan because Administrator access is required."
        Add-ReportNote -Message "SFC system file scan skipped because Administrator access is required."
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
    Write-Log "GUI process elevated: $GuiElevated"
    Write-Log "PowerShell/engine process elevated: $(if (Test-Admin) { 'Yes' } else { 'No' })"
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

    if ($RunMode -eq "SafeCleanup" -and $LicenseInfo.Mode -ne "Licensed") {
        Write-Log "LICENSE REQUIRED: Scan and reports are available in trial mode. Activate to clean and recover space."
        Add-ReportNote -Message "License required for Safe Cleanup. Preview reports remain available."
        Write-Summary -LicenseMode $LicenseInfo.Mode -StartTime $StartTime -EstimatedCleanupTargets 0
        return
    }

    if ($RunMode -eq "BrowserHealth") {
        Get-BrowserHealth | Out-Null
        Write-Summary -LicenseMode $LicenseInfo.Mode -StartTime $StartTime -EstimatedCleanupTargets 0
        return
    }

    if ($RunMode -eq "PrinterHealth") {
        Get-PrinterHealth | Out-Null
        Write-Summary -LicenseMode $LicenseInfo.Mode -StartTime $StartTime -EstimatedCleanupTargets 0
        return
    }

    $isWindowsPlatform = Test-WindowsPlatform
    if (!$isWindowsPlatform) {
        Write-Log "INFO: This tool is intended for Windows. Validation mode passed."
        Add-ReportNote -Message "Windows-only checks were skipped because this validation run is not on Windows."
        Write-Summary -LicenseMode $LicenseInfo.Mode -StartTime $StartTime -EstimatedCleanupTargets 0
        return
    }

    if ($RunMode -eq "NetworkHealth") {
        Get-NetworkHealth | Out-Null
        Write-Summary -LicenseMode $LicenseInfo.Mode -StartTime $StartTime -EstimatedCleanupTargets 0
        return
    }

    if ($WhatIfPreference) {
        Write-Log "WhatIf validation mode detected."
    }
    elseif ((Test-RunModeRequiresAdmin -RunMode $RunMode) -and !(Test-Admin)) {
        Write-Log "ERROR: Administrator access is required for $RunMode."
        Add-ReportNote -Message "Administrator access is required for this action."
        Write-Host "`nAdministrator Required: This action requires Administrator access." -ForegroundColor Yellow
        Write-Summary -LicenseMode $LicenseInfo.Mode -StartTime $StartTime -EstimatedCleanupTargets 0
        if ($InteractiveMode -and !$NoMenu) {
            Read-Host "Press Enter to exit"
        }
        return
    }
    else {
        Write-Log "Admin requirement check passed for $RunMode."
    }

    if ($RunMode -eq "FlushDns") {
        Invoke-FlushDnsFirstAid | Out-Null
        Write-Summary -LicenseMode $LicenseInfo.Mode -StartTime $StartTime -EstimatedCleanupTargets 0
        return
    }

    if ($RunMode -eq "RenewIp") {
        Invoke-RenewIpFirstAid | Out-Null
        Write-Summary -LicenseMode $LicenseInfo.Mode -StartTime $StartTime -EstimatedCleanupTargets 0
        return
    }

    if ($RunMode -eq "ResetNetwork") {
        Invoke-ResetNetworkFirstAid | Out-Null
        Write-Summary -LicenseMode $LicenseInfo.Mode -StartTime $StartTime -EstimatedCleanupTargets 0
        return
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
            "BrowserHealth" {
                $runMode = "BrowserHealth"
            }
            "NetworkHealth" {
                $runMode = "NetworkHealth"
            }
            "PrinterHealth" {
                $runMode = "PrinterHealth"
            }
            "FlushDns" {
                $runMode = "FlushDns"
            }
            "RenewIp" {
                $runMode = "RenewIp"
            }
            "ResetNetwork" {
                $runMode = "ResetNetwork"
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
