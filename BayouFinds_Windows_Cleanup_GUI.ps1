<# 
BayouFinds Windows Cleanup Tool GUI
User-facing Windows Forms wrapper for BayouFinds_Windows_Cleanup.ps1.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"

Add-Type -AssemblyName System.Windows.Forms
Add-Type -AssemblyName System.Drawing

[System.Windows.Forms.Application]::EnableVisualStyles()
[System.Windows.Forms.Application]::SetCompatibleTextRenderingDefault($false)

$script:ToolVersion = "v1.2"
$script:RootDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$script:CleanupScript = Join-Path -Path $script:RootDir -ChildPath "BayouFinds_Windows_Cleanup.ps1"
$script:ReportsPath = Join-Path -Path ([Environment]::GetFolderPath("Desktop")) -ChildPath "BayouFinds_Cleanup_Logs"
$script:AgreementDir = Join-Path -Path ([Environment]::GetFolderPath("LocalApplicationData")) -ChildPath "BayouFinds\WindowsCleanupTool"
$script:AgreementPath = Join-Path -Path $script:AgreementDir -ChildPath "agreement_v1_2.accepted"
$script:RunningProcess = $null
$script:RunStartedAt = $null
$script:PendingRuns = New-Object System.Collections.Queue
$script:IsQueueRunning = $false
$script:OutputBox = $null
$script:StatusLabel = $null
$script:LicenseStatusLabel = $null
$script:AgreementStatusLabel = $null
$script:RunSelectedButton = $null
$script:MainControls = @()

function New-BfFont {
    param(
        [float]$Size,
        [System.Drawing.FontStyle]$Style = [System.Drawing.FontStyle]::Regular
    )

    return New-Object System.Drawing.Font("Segoe UI", $Size, $Style)
}

function Add-BfLogLine {
    param([string]$Message)

    if (!$script:OutputBox -or [string]::IsNullOrWhiteSpace($Message)) {
        return
    }

    $script:OutputBox.AppendText($Message + [Environment]::NewLine)
}

function Set-BfControlsEnabled {
    param([bool]$Enabled)

    foreach ($control in $script:MainControls) {
        if ($control) {
            $control.Enabled = $Enabled
        }
    }
}

function Open-ReportsFolder {
    if (!(Test-Path -Path $script:ReportsPath)) {
        New-Item -ItemType Directory -Force -Path $script:ReportsPath | Out-Null
    }

    Start-Process -FilePath $script:ReportsPath
}

function Get-LastReportPath {
    if (!(Test-Path -Path $script:ReportsPath)) {
        return $null
    }

    $report = Get-ChildItem -Path $script:ReportsPath -Filter "cleanup_report_*.html" -File |
        Sort-Object -Property LastWriteTime -Descending |
        Select-Object -First 1

    if ($report) {
        return $report.FullName
    }

    return $null
}

function Open-LastReport {
    $reportPath = Get-LastReportPath

    if (!$reportPath) {
        [System.Windows.Forms.MessageBox]::Show(
            "No HTML report was found yet. Run Preview Cleanup, Safe Cleanup, License Check, or Bookmark Backup first.",
            "BayouFinds Windows Cleanup Tool",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        ) | Out-Null
        return
    }

    Start-Process -FilePath $reportPath
}

function Show-TextWindow {
    param(
        [string]$Title,
        [string]$Text,
        [int]$Width = 620,
        [int]$Height = 460
    )

    $form = New-Object System.Windows.Forms.Form
    $form.Text = $Title
    $form.StartPosition = "CenterParent"
    $form.Size = New-Object System.Drawing.Size($Width, $Height)
    $form.MinimumSize = New-Object System.Drawing.Size(520, 360)
    $form.BackColor = [System.Drawing.Color]::FromArgb(246, 248, 250)

    $box = New-Object System.Windows.Forms.TextBox
    $box.Multiline = $true
    $box.ReadOnly = $true
    $box.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
    $box.Dock = [System.Windows.Forms.DockStyle]::Fill
    $box.Font = New-BfFont -Size 10
    $box.BackColor = [System.Drawing.Color]::White
    $box.Text = $Text

    $okButton = New-Object System.Windows.Forms.Button
    $okButton.Text = "OK"
    $okButton.Dock = [System.Windows.Forms.DockStyle]::Bottom
    $okButton.Height = 38
    $okButton.Font = New-BfFont -Size 10
    $okButton.Add_Click({ $form.Close() })

    $form.Controls.Add($box)
    $form.Controls.Add($okButton)
    $form.ShowDialog() | Out-Null
}

function Show-SplashScreen {
    $form = New-Object System.Windows.Forms.Form
    $form.Text = "BayouFinds Windows Cleanup Tool"
    $form.StartPosition = "CenterScreen"
    $form.Size = New-Object System.Drawing.Size(540, 260)
    $form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::FixedDialog
    $form.ControlBox = $false
    $form.TopMost = $true
    $form.BackColor = [System.Drawing.Color]::FromArgb(24, 33, 43)

    $title = New-Object System.Windows.Forms.Label
    $title.Text = "BayouFinds Windows Cleanup Tool"
    $title.AutoSize = $false
    $title.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
    $title.Location = New-Object System.Drawing.Point(24, 48)
    $title.Size = New-Object System.Drawing.Size(480, 42)
    $title.Font = New-BfFont -Size 17 -Style ([System.Drawing.FontStyle]::Bold)
    $title.ForeColor = [System.Drawing.Color]::White

    $subtitle = New-Object System.Windows.Forms.Label
    $subtitle.Text = "Safe cleanup. Clear reports. Customer-controlled."
    $subtitle.AutoSize = $false
    $subtitle.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
    $subtitle.Location = New-Object System.Drawing.Point(24, 104)
    $subtitle.Size = New-Object System.Drawing.Size(480, 30)
    $subtitle.Font = New-BfFont -Size 11
    $subtitle.ForeColor = [System.Drawing.Color]::FromArgb(218, 225, 232)

    $version = New-Object System.Windows.Forms.Label
    $version.Text = $script:ToolVersion
    $version.AutoSize = $false
    $version.TextAlign = [System.Drawing.ContentAlignment]::MiddleCenter
    $version.Location = New-Object System.Drawing.Point(24, 150)
    $version.Size = New-Object System.Drawing.Size(480, 28)
    $version.Font = New-BfFont -Size 10 -Style ([System.Drawing.FontStyle]::Bold)
    $version.ForeColor = [System.Drawing.Color]::FromArgb(166, 206, 227)

    $timer = New-Object System.Windows.Forms.Timer
    $timer.Interval = 2400
    $timer.Add_Tick({
        $timer.Stop()
        $form.Close()
    })

    $form.Add_Shown({ $timer.Start() })
    $form.Controls.AddRange(@($title, $subtitle, $version))
    $form.ShowDialog() | Out-Null
}

function Test-AgreementAccepted {
    return (Test-Path -Path $script:AgreementPath)
}

function Save-AgreementAccepted {
    if (!(Test-Path -Path $script:AgreementDir)) {
        New-Item -ItemType Directory -Force -Path $script:AgreementDir | Out-Null
    }

    "Accepted BayouFinds Windows Cleanup Tool $script:ToolVersion on $(Get-Date -Format o)" |
        Set-Content -Path $script:AgreementPath -Encoding UTF8
}

function Show-UserAgreement {
    $form = New-Object System.Windows.Forms.Form
    $form.Text = "BayouFinds Windows Cleanup Tool - User Agreement"
    $form.StartPosition = "CenterScreen"
    $form.Size = New-Object System.Drawing.Size(720, 560)
    $form.MinimumSize = New-Object System.Drawing.Size(640, 500)
    $form.FormBorderStyle = [System.Windows.Forms.FormBorderStyle]::Sizable
    $form.MaximizeBox = $false
    $form.BackColor = [System.Drawing.Color]::FromArgb(246, 248, 250)

    $title = New-Object System.Windows.Forms.Label
    $title.Text = "BayouFinds Windows Cleanup Tool - User Agreement"
    $title.AutoSize = $false
    $title.Location = New-Object System.Drawing.Point(20, 18)
    $title.Size = New-Object System.Drawing.Size(660, 32)
    $title.Font = New-BfFont -Size 13 -Style ([System.Drawing.FontStyle]::Bold)
    $title.ForeColor = [System.Drawing.Color]::FromArgb(24, 33, 43)

    $agreement = New-Object System.Windows.Forms.TextBox
    $agreement.Multiline = $true
    $agreement.ReadOnly = $true
    $agreement.ScrollBars = [System.Windows.Forms.ScrollBars]::Vertical
    $agreement.Location = New-Object System.Drawing.Point(20, 62)
    $agreement.Size = New-Object System.Drawing.Size(662, 340)
    $agreement.Anchor = "Top,Left,Right,Bottom"
    $agreement.Font = New-BfFont -Size 10
    $agreement.BackColor = [System.Drawing.Color]::White
    $agreement.Text = @"
BayouFinds Windows Cleanup Tool v1.2

Please read this User Agreement before continuing.

This software is provided as-is, without warranties or guarantees of any kind. By using this tool, you understand that all cleanup, preview, maintenance, and backup actions are run at your own risk.

You are responsible for choosing which actions to run and for reviewing the results of those actions. BayouFinds is not responsible for misuse, user error, data loss, system changes, software conflicts, service interruptions, or damage caused by improper use of this tool.

Preview Cleanup is recommended before Safe Cleanup. Preview Cleanup is designed to show what the tool can inspect before you choose to run cleanup actions.

Personal folders are designed to be protected. The tool is intended to avoid personal folders such as Desktop, Documents, Pictures, Music, Videos, and Downloads. You should still keep your own backups of important files before running any maintenance utility.

Browser bookmark backup only copies bookmark files. It does not back up cookies, passwords, browsing history, extensions, or full browser profiles.

Safe Cleanup is intended for common temporary files, cache locations, and safe maintenance tasks. Do not run cleanup actions unless you understand what they do and accept responsibility for the result.

If you do not agree to these terms, select Cancel. The tool will close without running any actions.
"@

    $checkbox = New-Object System.Windows.Forms.CheckBox
    $checkbox.Text = "I understand and agree to use this software at my own risk."
    $checkbox.AutoSize = $false
    $checkbox.Location = New-Object System.Drawing.Point(20, 418)
    $checkbox.Size = New-Object System.Drawing.Size(662, 28)
    $checkbox.Anchor = "Left,Right,Bottom"
    $checkbox.Font = New-BfFont -Size 10
    $checkbox.ForeColor = [System.Drawing.Color]::FromArgb(24, 33, 43)

    $agreeButton = New-Object System.Windows.Forms.Button
    $agreeButton.Text = "I Agree"
    $agreeButton.Location = New-Object System.Drawing.Point(462, 462)
    $agreeButton.Size = New-Object System.Drawing.Size(104, 34)
    $agreeButton.Anchor = "Right,Bottom"
    $agreeButton.Enabled = $false
    $agreeButton.Font = New-BfFont -Size 10 -Style ([System.Drawing.FontStyle]::Bold)

    $cancelButton = New-Object System.Windows.Forms.Button
    $cancelButton.Text = "Cancel"
    $cancelButton.Location = New-Object System.Drawing.Point(578, 462)
    $cancelButton.Size = New-Object System.Drawing.Size(104, 34)
    $cancelButton.Anchor = "Right,Bottom"
    $cancelButton.Font = New-BfFont -Size 10

    $checkbox.Add_CheckedChanged({ $agreeButton.Enabled = $checkbox.Checked })
    $agreeButton.Add_Click({
        if ($checkbox.Checked) {
            Save-AgreementAccepted
            $form.DialogResult = [System.Windows.Forms.DialogResult]::OK
            $form.Close()
        }
    })
    $cancelButton.Add_Click({
        $form.DialogResult = [System.Windows.Forms.DialogResult]::Cancel
        $form.Close()
    })

    $form.AcceptButton = $agreeButton
    $form.CancelButton = $cancelButton
    $form.Controls.AddRange(@($title, $agreement, $checkbox, $agreeButton, $cancelButton))

    return ($form.ShowDialog() -eq [System.Windows.Forms.DialogResult]::OK)
}

function Show-HelpGuide {
    Show-TextWindow -Title "BayouFinds Windows Cleanup Tool - Help Guide" -Text @"
Help Guide

Preview Cleanup
Preview Cleanup checks safe cleanup targets and writes reports without deleting files. Run this first to understand what the tool can inspect.

Safe Cleanup
Safe Cleanup runs the approved cleanup actions for common temporary files, cache locations, and safe Windows maintenance. It is recommended only after Preview Cleanup.

Bookmark Backup
Bookmark Backup copies supported browser bookmark files into the BayouFinds reports folder. It does not copy passwords, cookies, history, extensions, or full browser profiles.

Report Location
Reports are saved here:
$script:ReportsPath

The folder can include LOG, HTML, and JSON report files, plus browser bookmark backup folders.

Admin Rights
Windows may request administrator rights when cleanup or maintenance actions need access to protected system locations. If admin rights are not granted, some actions may be skipped or report limited access.
"@
}

function Show-SafetyNotes {
    Show-TextWindow -Title "BayouFinds Windows Cleanup Tool - Safety Notes" -Text @"
Safety Notes

Preview Cleanup is recommended before Safe Cleanup.

Personal folders are designed to be protected, including Desktop, Documents, Downloads, Pictures, Music, and Videos.

You remain responsible for choosing which actions to run. Keep your own backups of important files before running any cleanup or maintenance utility.

Safe Cleanup is intended for common temporary files, cache locations, and safe maintenance tasks. Do not use it unless you understand and accept the result.
"@
}

function Show-AboutWindow {
    Show-TextWindow -Title "About BayouFinds Windows Cleanup Tool" -Text @"
About BayouFinds Windows Cleanup Tool

Product name:
BayouFinds Windows Cleanup Tool

Version:
v1.2

Built by:
BayouFinds

Website:
https://bayoufinds.com

Purpose:
A customer-controlled Windows cleanup and reporting utility.
"@ -Width 560 -Height 360
}

function Show-SupportWindow {
    Show-TextWindow -Title "BayouFinds Windows Cleanup Tool - Support" -Text @"
Support

Support:
BayouFinds.com

Report folder location:
$script:ReportsPath

When requesting help, send the latest HTML report and LOG file from the report folder. These files help identify what action was run, what was skipped, and where the tool saved its output.
"@ -Width 600 -Height 360
}

function Start-QueuedRuns {
    param([object[]]$Runs)

    if ($script:RunningProcess -and !$script:RunningProcess.HasExited) {
        [System.Windows.Forms.MessageBox]::Show(
            "A cleanup action is already running. Wait for it to finish before starting another action.",
            "BayouFinds Windows Cleanup Tool",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        ) | Out-Null
        return
    }

    if (!(Test-Path -Path $script:CleanupScript)) {
        [System.Windows.Forms.MessageBox]::Show(
            "The cleanup script was not found:`n$script:CleanupScript",
            "BayouFinds Windows Cleanup Tool",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Error
        ) | Out-Null
        return
    }

    if (!$Runs -or $Runs.Count -eq 0) {
        [System.Windows.Forms.MessageBox]::Show(
            "Select at least one action before clicking Run Selected.",
            "BayouFinds Windows Cleanup Tool",
            [System.Windows.Forms.MessageBoxButtons]::OK,
            [System.Windows.Forms.MessageBoxIcon]::Information
        ) | Out-Null
        return
    }

    $hasSafeCleanup = @($Runs | Where-Object { $_.Mode -eq "SafeCleanup" }).Count -gt 0
    if ($hasSafeCleanup) {
        $confirm = [System.Windows.Forms.MessageBox]::Show(
            "Safe Cleanup should be run only after Preview Cleanup. Personal folders are designed to be protected, but you are responsible for choosing this action.`n`nContinue?",
            "Confirm Safe Cleanup",
            [System.Windows.Forms.MessageBoxButtons]::YesNo,
            [System.Windows.Forms.MessageBoxIcon]::Warning
        )

        if ($confirm -ne [System.Windows.Forms.DialogResult]::Yes) {
            return
        }
    }

    $script:PendingRuns.Clear()
    foreach ($run in $Runs) {
        $script:PendingRuns.Enqueue($run)
    }

    $script:OutputBox.Clear()
    Add-BfLogLine -Message "Reports will be saved to: $script:ReportsPath"
    Add-BfLogLine -Message ""
    $script:IsQueueRunning = $true
    Set-BfControlsEnabled -Enabled $false
    Start-NextQueuedRun
}

function Start-NextQueuedRun {
    if ($script:PendingRuns.Count -eq 0) {
        $script:IsQueueRunning = $false
        $script:RunningProcess = $null
        $script:StatusLabel.Text = "Ready"
        Set-BfControlsEnabled -Enabled $true
        Add-BfLogLine -Message ""
        Add-BfLogLine -Message "All selected actions finished."
        Add-BfLogLine -Message "Reports saved to: $script:ReportsPath"
        return
    }

    $run = $script:PendingRuns.Dequeue()
    Start-CleanupMode -Mode $run.Mode -DisplayName $run.DisplayName
}

function Start-CleanupMode {
    param(
        [string]$Mode,
        [string]$DisplayName
    )

    Add-BfLogLine -Message "Starting $DisplayName..."
    $script:StatusLabel.Text = "Running $DisplayName..."
    $script:RunStartedAt = Get-Date

    $process = New-Object System.Diagnostics.Process
    $process.StartInfo.FileName = "powershell.exe"
    $process.StartInfo.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$script:CleanupScript`" -NoMenu -Mode $Mode"
    $process.StartInfo.UseShellExecute = $false
    $process.StartInfo.RedirectStandardOutput = $true
    $process.StartInfo.RedirectStandardError = $true
    $process.StartInfo.CreateNoWindow = $true
    $process.EnableRaisingEvents = $true

    $outputHandler = [System.Diagnostics.DataReceivedEventHandler]{
        param($sender, $eventArgs)

        if ($eventArgs.Data -and $script:OutputBox) {
            $script:OutputBox.BeginInvoke([Action[string]]{
                param($line)
                Add-BfLogLine -Message $line
            }, $eventArgs.Data) | Out-Null
        }
    }

    $errorHandler = [System.Diagnostics.DataReceivedEventHandler]{
        param($sender, $eventArgs)

        if ($eventArgs.Data -and $script:OutputBox) {
            $script:OutputBox.BeginInvoke([Action[string]]{
                param($line)
                Add-BfLogLine -Message ("ERROR: " + $line)
            }, $eventArgs.Data) | Out-Null
        }
    }

    $exitHandler = {
        if ($script:OutputBox) {
            $script:OutputBox.BeginInvoke([Action]{
                $elapsed = ""
                if ($script:RunStartedAt) {
                    $elapsed = " Duration: {0:n0} seconds." -f ((Get-Date) - $script:RunStartedAt).TotalSeconds
                }

                $exitCode = 0
                if ($script:RunningProcess) {
                    $exitCode = $script:RunningProcess.ExitCode
                }

                Add-BfLogLine -Message ""
                Add-BfLogLine -Message ("Finished with exit code {0}.{1}" -f $exitCode, $elapsed)
                Add-BfLogLine -Message ""

                if ($Mode -eq "LicenseCheck" -and $script:LicenseStatusLabel) {
                    $script:LicenseStatusLabel.Text = "License status: check completed"
                }

                Start-NextQueuedRun
            }) | Out-Null
        }
    }

    $process.add_OutputDataReceived($outputHandler)
    $process.add_ErrorDataReceived($errorHandler)
    $process.add_Exited($exitHandler)

    $script:RunningProcess = $process
    [void]$process.Start()
    $process.BeginOutputReadLine()
    $process.BeginErrorReadLine()
}

function New-RunItem {
    param(
        [string]$Mode,
        [string]$DisplayName
    )

    return [pscustomobject]@{
        Mode = $Mode
        DisplayName = $DisplayName
    }
}

function Show-MainWindow {
    $form = New-Object System.Windows.Forms.Form
    $form.Text = "BayouFinds Windows Cleanup Tool v1.2"
    $form.StartPosition = "CenterScreen"
    $form.Size = New-Object System.Drawing.Size(960, 690)
    $form.MinimumSize = New-Object System.Drawing.Size(860, 620)
    $form.BackColor = [System.Drawing.Color]::FromArgb(244, 246, 248)

    $menu = New-Object System.Windows.Forms.MenuStrip
    $fileMenu = New-Object System.Windows.Forms.ToolStripMenuItem("File")
    $toolsMenu = New-Object System.Windows.Forms.ToolStripMenuItem("Tools")
    $helpMenu = New-Object System.Windows.Forms.ToolStripMenuItem("Help")

    $openReportsMenu = New-Object System.Windows.Forms.ToolStripMenuItem("Open Report Folder")
    $exitMenu = New-Object System.Windows.Forms.ToolStripMenuItem("Exit")
    $licenseMenu = New-Object System.Windows.Forms.ToolStripMenuItem("Check License")
    $previewMenu = New-Object System.Windows.Forms.ToolStripMenuItem("Preview Cleanup")
    $bookmarkMenu = New-Object System.Windows.Forms.ToolStripMenuItem("Back Up Browser Bookmarks")
    $safeMenu = New-Object System.Windows.Forms.ToolStripMenuItem("Safe Cleanup")
    $helpGuideMenu = New-Object System.Windows.Forms.ToolStripMenuItem("Help Guide")
    $safetyNotesMenu = New-Object System.Windows.Forms.ToolStripMenuItem("Safety Notes")
    $aboutMenu = New-Object System.Windows.Forms.ToolStripMenuItem("About BayouFinds")
    $supportMenu = New-Object System.Windows.Forms.ToolStripMenuItem("Contact Support")

    $fileMenu.DropDownItems.AddRange(@($openReportsMenu, $exitMenu))
    $toolsMenu.DropDownItems.AddRange(@($licenseMenu, $previewMenu, $bookmarkMenu, $safeMenu))
    $helpMenu.DropDownItems.AddRange(@($helpGuideMenu, $safetyNotesMenu, $aboutMenu, $supportMenu))
    $menu.Items.AddRange(@($fileMenu, $toolsMenu, $helpMenu))

    $header = New-Object System.Windows.Forms.Panel
    $header.Dock = [System.Windows.Forms.DockStyle]::Top
    $header.Height = 98
    $header.BackColor = [System.Drawing.Color]::FromArgb(24, 33, 43)

    $title = New-Object System.Windows.Forms.Label
    $title.Text = "BayouFinds Windows Cleanup Tool"
    $title.AutoSize = $false
    $title.Location = New-Object System.Drawing.Point(22, 14)
    $title.Size = New-Object System.Drawing.Size(620, 30)
    $title.Font = New-BfFont -Size 16 -Style ([System.Drawing.FontStyle]::Bold)
    $title.ForeColor = [System.Drawing.Color]::White

    $subtitle = New-Object System.Windows.Forms.Label
    $subtitle.Text = "Safe cleanup. Clear reports. Customer-controlled."
    $subtitle.AutoSize = $false
    $subtitle.Location = New-Object System.Drawing.Point(24, 48)
    $subtitle.Size = New-Object System.Drawing.Size(520, 24)
    $subtitle.Font = New-BfFont -Size 10
    $subtitle.ForeColor = [System.Drawing.Color]::FromArgb(218, 225, 232)

    $version = New-Object System.Windows.Forms.Label
    $version.Text = $script:ToolVersion
    $version.AutoSize = $false
    $version.TextAlign = [System.Drawing.ContentAlignment]::MiddleRight
    $version.Location = New-Object System.Drawing.Point(760, 28)
    $version.Size = New-Object System.Drawing.Size(150, 28)
    $version.Anchor = "Top,Right"
    $version.Font = New-BfFont -Size 11 -Style ([System.Drawing.FontStyle]::Bold)
    $version.ForeColor = [System.Drawing.Color]::FromArgb(166, 206, 227)

    $header.Controls.AddRange(@($title, $subtitle, $version))

    $content = New-Object System.Windows.Forms.TableLayoutPanel
    $content.Dock = [System.Windows.Forms.DockStyle]::Fill
    $content.ColumnCount = 2
    $content.RowCount = 1
    $content.Padding = New-Object System.Windows.Forms.Padding(16)
    $content.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Absolute, 300))) | Out-Null
    $content.ColumnStyles.Add((New-Object System.Windows.Forms.ColumnStyle([System.Windows.Forms.SizeType]::Percent, 100))) | Out-Null

    $actions = New-Object System.Windows.Forms.Panel
    $actions.Dock = [System.Windows.Forms.DockStyle]::Fill
    $actions.BackColor = [System.Drawing.Color]::White
    $actions.Padding = New-Object System.Windows.Forms.Padding(14)

    $actionsTitle = New-Object System.Windows.Forms.Label
    $actionsTitle.Text = "Select Actions"
    $actionsTitle.Location = New-Object System.Drawing.Point(14, 14)
    $actionsTitle.Size = New-Object System.Drawing.Size(250, 24)
    $actionsTitle.Font = New-BfFont -Size 11 -Style ([System.Drawing.FontStyle]::Bold)

    $script:LicenseStatusLabel = New-Object System.Windows.Forms.Label
    $script:LicenseStatusLabel.Text = "License status: not checked"
    $script:LicenseStatusLabel.Location = New-Object System.Drawing.Point(14, 48)
    $script:LicenseStatusLabel.Size = New-Object System.Drawing.Size(260, 24)
    $script:LicenseStatusLabel.Font = New-BfFont -Size 9

    $script:AgreementStatusLabel = New-Object System.Windows.Forms.Label
    $script:AgreementStatusLabel.Text = "Agreement status: accepted"
    $script:AgreementStatusLabel.Location = New-Object System.Drawing.Point(14, 74)
    $script:AgreementStatusLabel.Size = New-Object System.Drawing.Size(260, 24)
    $script:AgreementStatusLabel.Font = New-BfFont -Size 9

    $licenseCheck = New-Object System.Windows.Forms.CheckBox
    $licenseCheck.Text = "Check License"
    $licenseCheck.Location = New-Object System.Drawing.Point(18, 120)
    $licenseCheck.Size = New-Object System.Drawing.Size(252, 26)
    $licenseCheck.Font = New-BfFont -Size 10

    $previewCheck = New-Object System.Windows.Forms.CheckBox
    $previewCheck.Text = "Preview Cleanup"
    $previewCheck.Location = New-Object System.Drawing.Point(18, 152)
    $previewCheck.Size = New-Object System.Drawing.Size(252, 26)
    $previewCheck.Font = New-BfFont -Size 10
    $previewCheck.Checked = $true

    $bookmarkCheck = New-Object System.Windows.Forms.CheckBox
    $bookmarkCheck.Text = "Back Up Browser Bookmarks"
    $bookmarkCheck.Location = New-Object System.Drawing.Point(18, 184)
    $bookmarkCheck.Size = New-Object System.Drawing.Size(252, 26)
    $bookmarkCheck.Font = New-BfFont -Size 10

    $safeCheck = New-Object System.Windows.Forms.CheckBox
    $safeCheck.Text = "Safe Cleanup"
    $safeCheck.Location = New-Object System.Drawing.Point(18, 216)
    $safeCheck.Size = New-Object System.Drawing.Size(252, 26)
    $safeCheck.Font = New-BfFont -Size 10

    $script:RunSelectedButton = New-Object System.Windows.Forms.Button
    $script:RunSelectedButton.Text = "Run Selected"
    $script:RunSelectedButton.Location = New-Object System.Drawing.Point(14, 264)
    $script:RunSelectedButton.Size = New-Object System.Drawing.Size(256, 40)
    $script:RunSelectedButton.Font = New-BfFont -Size 10 -Style ([System.Drawing.FontStyle]::Bold)

    $openReportsButton = New-Object System.Windows.Forms.Button
    $openReportsButton.Text = "Open Report Folder"
    $openReportsButton.Location = New-Object System.Drawing.Point(14, 316)
    $openReportsButton.Size = New-Object System.Drawing.Size(256, 36)
    $openReportsButton.Font = New-BfFont -Size 9.5

    $viewLastReportButton = New-Object System.Windows.Forms.Button
    $viewLastReportButton.Text = "View Last Report"
    $viewLastReportButton.Location = New-Object System.Drawing.Point(14, 362)
    $viewLastReportButton.Size = New-Object System.Drawing.Size(256, 36)
    $viewLastReportButton.Font = New-BfFont -Size 9.5

    $helpButton = New-Object System.Windows.Forms.Button
    $helpButton.Text = "Help"
    $helpButton.Location = New-Object System.Drawing.Point(14, 408)
    $helpButton.Size = New-Object System.Drawing.Size(124, 36)
    $helpButton.Font = New-BfFont -Size 9.5

    $exitButton = New-Object System.Windows.Forms.Button
    $exitButton.Text = "Exit"
    $exitButton.Location = New-Object System.Drawing.Point(146, 408)
    $exitButton.Size = New-Object System.Drawing.Size(124, 36)
    $exitButton.Font = New-BfFont -Size 9.5

    $script:StatusLabel = New-Object System.Windows.Forms.Label
    $script:StatusLabel.Text = "Ready"
    $script:StatusLabel.Location = New-Object System.Drawing.Point(14, 466)
    $script:StatusLabel.Size = New-Object System.Drawing.Size(256, 48)
    $script:StatusLabel.Font = New-BfFont -Size 9
    $script:StatusLabel.ForeColor = [System.Drawing.Color]::FromArgb(72, 84, 96)

    $actions.Controls.AddRange(@(
        $actionsTitle,
        $script:LicenseStatusLabel,
        $script:AgreementStatusLabel,
        $licenseCheck,
        $previewCheck,
        $bookmarkCheck,
        $safeCheck,
        $script:RunSelectedButton,
        $openReportsButton,
        $viewLastReportButton,
        $helpButton,
        $exitButton,
        $script:StatusLabel
    ))

    $outputPanel = New-Object System.Windows.Forms.Panel
    $outputPanel.Dock = [System.Windows.Forms.DockStyle]::Fill
    $outputPanel.BackColor = [System.Drawing.Color]::White
    $outputPanel.Padding = New-Object System.Windows.Forms.Padding(14)

    $outputTitle = New-Object System.Windows.Forms.Label
    $outputTitle.Text = "Output / Status"
    $outputTitle.Dock = [System.Windows.Forms.DockStyle]::Top
    $outputTitle.Height = 28
    $outputTitle.Font = New-BfFont -Size 11 -Style ([System.Drawing.FontStyle]::Bold)

    $script:OutputBox = New-Object System.Windows.Forms.TextBox
    $script:OutputBox.Multiline = $true
    $script:OutputBox.ReadOnly = $true
    $script:OutputBox.ScrollBars = [System.Windows.Forms.ScrollBars]::Both
    $script:OutputBox.WordWrap = $false
    $script:OutputBox.Dock = [System.Windows.Forms.DockStyle]::Fill
    $script:OutputBox.Font = New-Object System.Drawing.Font("Consolas", 9)
    $script:OutputBox.BackColor = [System.Drawing.Color]::FromArgb(12, 16, 22)
    $script:OutputBox.ForeColor = [System.Drawing.Color]::FromArgb(226, 232, 240)
    $script:OutputBox.Text = "Select one or more actions, then click Run Selected. Preview Cleanup is recommended before Safe Cleanup."

    $outputPanel.Controls.Add($script:OutputBox)
    $outputPanel.Controls.Add($outputTitle)

    $content.Controls.Add($actions, 0, 0)
    $content.Controls.Add($outputPanel, 1, 0)

    $script:MainControls = @(
        $licenseCheck,
        $previewCheck,
        $bookmarkCheck,
        $safeCheck,
        $script:RunSelectedButton,
        $openReportsButton,
        $viewLastReportButton,
        $helpButton,
        $exitButton,
        $openReportsMenu,
        $exitMenu,
        $licenseMenu,
        $previewMenu,
        $bookmarkMenu,
        $safeMenu
    )

    $runSelected = {
        $runs = @()
        if ($licenseCheck.Checked) { $runs += New-RunItem -Mode "LicenseCheck" -DisplayName "License Check" }
        if ($previewCheck.Checked) { $runs += New-RunItem -Mode "Preview" -DisplayName "Preview Cleanup" }
        if ($bookmarkCheck.Checked) { $runs += New-RunItem -Mode "BackupBookmarks" -DisplayName "Browser Bookmark Backup" }
        if ($safeCheck.Checked) { $runs += New-RunItem -Mode "SafeCleanup" -DisplayName "Safe Cleanup" }
        Start-QueuedRuns -Runs $runs
    }

    $script:RunSelectedButton.Add_Click($runSelected)
    $openReportsButton.Add_Click({ Open-ReportsFolder })
    $viewLastReportButton.Add_Click({ Open-LastReport })
    $helpButton.Add_Click({ Show-HelpGuide })
    $exitButton.Add_Click({ $form.Close() })

    $openReportsMenu.Add_Click({ Open-ReportsFolder })
    $exitMenu.Add_Click({ $form.Close() })
    $licenseMenu.Add_Click({ Start-QueuedRuns -Runs @(New-RunItem -Mode "LicenseCheck" -DisplayName "License Check") })
    $previewMenu.Add_Click({ Start-QueuedRuns -Runs @(New-RunItem -Mode "Preview" -DisplayName "Preview Cleanup") })
    $bookmarkMenu.Add_Click({ Start-QueuedRuns -Runs @(New-RunItem -Mode "BackupBookmarks" -DisplayName "Browser Bookmark Backup") })
    $safeMenu.Add_Click({ Start-QueuedRuns -Runs @(New-RunItem -Mode "SafeCleanup" -DisplayName "Safe Cleanup") })
    $helpGuideMenu.Add_Click({ Show-HelpGuide })
    $safetyNotesMenu.Add_Click({ Show-SafetyNotes })
    $aboutMenu.Add_Click({ Show-AboutWindow })
    $supportMenu.Add_Click({ Show-SupportWindow })

    $form.Add_FormClosing({
        if ($script:RunningProcess -and !$script:RunningProcess.HasExited) {
            $confirm = [System.Windows.Forms.MessageBox]::Show(
                "A cleanup action is still running. Closing now will stop the action.`n`nClose anyway?",
                "BayouFinds Windows Cleanup Tool",
                [System.Windows.Forms.MessageBoxButtons]::YesNo,
                [System.Windows.Forms.MessageBoxIcon]::Warning
            )

            if ($confirm -ne [System.Windows.Forms.DialogResult]::Yes) {
                $_.Cancel = $true
                return
            }

            try {
                $script:RunningProcess.Kill()
            }
            catch {
            }
        }
    })

    $form.MainMenuStrip = $menu
    $form.Controls.Add($content)
    $form.Controls.Add($header)
    $form.Controls.Add($menu)

    [System.Windows.Forms.Application]::Run($form)
}

Show-SplashScreen

if ((Test-AgreementAccepted) -or (Show-UserAgreement)) {
    Show-MainWindow
}
