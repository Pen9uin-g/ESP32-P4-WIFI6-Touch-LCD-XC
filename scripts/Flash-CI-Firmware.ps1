[CmdletBinding()]
param(
    [string]$Port = '',
    [switch]$ListOnly,
    [switch]$SelfTest
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

$Repo = 'waveshareteam/ESP32-P4-WIFI6-Touch-LCD-XC'
$DefaultStartIndex = 1
$FlashLimit = 32MB

function Resolve-Executable([string]$Name, [string[]]$Fallbacks) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command -and $command.Source) { return $command.Source }
    foreach ($candidate in $Fallbacks) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) { return $candidate }
    }
    throw "$Name was not found on PATH or in the supported fallback locations."
}

function Resolve-Git { return Resolve-Executable 'git' @((Join-Path $env:ProgramFiles 'Git\cmd\git.exe'), (Join-Path $env:ProgramFiles 'Git\bin\git.exe')) }
function Resolve-Gh { return Resolve-Executable 'gh' @((Join-Path $env:ProgramFiles 'GitHub CLI\gh.exe'), (Join-Path $env:ProgramFiles 'GitHub CLI\bin\gh.exe')) }
function Resolve-Python { return Resolve-Executable 'python' @((Join-Path $env:LocalAppData 'Programs\Python\Python313\python.exe')) }
function Resolve-PythonWithEsptool {
    $candidates = @()
    try { $candidates += Resolve-Python } catch {}
    foreach ($root in @((Join-Path $env:USERPROFILE '.espressif\python_env'))) {
        if (Test-Path -LiteralPath $root) {
            $candidates += @(Get-ChildItem -LiteralPath $root -Recurse -File -Filter python.exe -ErrorAction SilentlyContinue |
                Where-Object { $_.FullName -match '[\\/]python_env[\\/].+[\\/]Scripts[\\/]python\.exe$' } | ForEach-Object FullName)
        }
    }
    foreach ($candidate in @($candidates | Where-Object { $_ } | Select-Object -Unique)) {
        & $candidate -c 'import esptool' *> $null
        if ($LASTEXITCODE -eq 0) { return $candidate }
    }
    throw 'No Python interpreter with esptool was found.'
}

$RepoRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))
$RouterPath = Join-Path $RepoRoot '.github\scripts\ci_change_router.py'
$StateRoot = Join-Path $env:LOCALAPPDATA 'Waveshare\ESP32-P4-CI-Firmware'
$StatePath = Join-Path $StateRoot 'state-v1.json'

function Get-CiItems([string]$PythonExe) {
    if (-not (Test-Path -LiteralPath $RouterPath -PathType Leaf)) { throw 'CI router is missing.' }
    $raw = (& $PythonExe $RouterPath --all 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "CI router --all failed: $raw" }
    $route = $raw | ConvertFrom-Json
    $idf = @($route.idf_matrix.include)
    $arduino = @($route.arduino_matrix.include)
    $firmware = @($route.firmware_matrix.include)
    if ($idf.Count -ne 40 -or $arduino.Count -ne 10 -or $firmware.Count -ne 2) { throw "CI router matrix must contain 40 ESP-IDF, 10 Arduino, and 2 maintained-firmware entries; got $($idf.Count), $($arduino.Count), and $($firmware.Count)." }
    $items = @(); $index = 1
    foreach ($entry in $idf) {
        if ($entry.idf_version -notin @('v5.5.5', 'v6.0.2') -or $entry.variant_id -notin @('shared', '3_4c', '4c') -or $entry.configuration -notin @('default', 'vendor-only') -or $entry.profile_id -ne 'rev1_3' -or [string]$entry.artifact_key -notmatch 'rev1_3') { throw 'ESP-IDF router entry is outside the XC CI contract.' }
        $items += [pscustomobject]@{ Index = $index; Workflow = 'esp-idf-projects.yml'; ArtifactKey = [string]$entry.artifact_key; SourceType = 'esp-idf'; FrameworkName = 'ESP-IDF'; FrameworkVersion = [string]$entry.idf_version; Project = [string]$entry.project; Sketch = ''; Configuration = [string]$entry.configuration; VariantId = [string]$entry.variant_id; Variant = [string]$entry.variant; ProfileId = [string]$entry.profile_id; ArtifactKind = 'ci-example' }
        $index++
    }
    foreach ($entry in $arduino) {
        if ($entry.variant_id -notin @('3_4c', '4c') -or $entry.configuration -ne 'default' -or $entry.profile_id -ne 'rev1_3' -or [string]$entry.artifact_key -notmatch 'rev1_3') { throw 'Arduino router entry is outside the XC CI contract.' }
        $items += [pscustomobject]@{ Index = $index; Workflow = 'arduino-projects.yml'; ArtifactKey = [string]$entry.artifact_key; SourceType = 'arduino'; FrameworkName = 'Arduino-ESP32'; FrameworkVersion = '3.3.11'; Project = [string]$entry.sketch; Sketch = [string]$entry.sketch_name; Configuration = [string]$entry.configuration; VariantId = [string]$entry.variant_id; Variant = [string]$entry.variant; ProfileId = [string]$entry.profile_id; ArtifactKind = 'ci-example' }
        $index++
    }
    foreach ($entry in $firmware) {
        if ($entry.project -ne 'firmware/brookesia' -or $entry.profile_id -notin @('rev1_3', 'rev3_x') -or [string]$entry.artifact_key -notmatch [string]$entry.profile_id) { throw 'Maintained firmware router entry is outside the XC CI contract.' }
        $items += [pscustomobject]@{ Index = $index; Workflow = 'maintained-firmware.yml'; ArtifactKey = [string]$entry.artifact_key; SourceType = 'esp-idf'; FrameworkName = 'ESP-IDF'; FrameworkVersion = 'v5.5.5'; Project = [string]$entry.project; Sketch = ''; Configuration = 'default'; VariantId = '3_4c'; Variant = '3.4C'; ProfileId = [string]$entry.profile_id; ArtifactKind = 'maintained-firmware' }
        $index++
    }
    $keys = @($items | ForEach-Object ArtifactKey)
    $shared = @($idf | Where-Object { $_.variant_id -eq 'shared' })
    $display = @($idf | Where-Object { $_.variant_id -in @('3_4c', '4c') })
    $usb = @($idf | Where-Object { $_.project_name -eq '12_usb_extend_screen' })
    $dualScreen = @($idf | Where-Object { $_.project_name -in @('07_Displaycolorbar', '08_lvgl_demo_v9', '09_video_lcd_display', '10_mp4_player', '11_esp_brookesia_phone') })
    if ($items.Count -ne 52 -or @($keys | Sort-Object -Unique).Count -ne 52 -or @($items | Where-Object { $_.Workflow -eq 'esp-idf-projects.yml' }).Count -ne 40 -or @($items | Where-Object { $_.Workflow -eq 'arduino-projects.yml' }).Count -ne 10 -or @($items | Where-Object { $_.Workflow -eq 'maintained-firmware.yml' }).Count -ne 2 -or $shared.Count -ne 12 -or @($shared | Where-Object { $_.configuration -ne 'default' }).Count -ne 0 -or $display.Count -ne 28 -or $dualScreen.Count -ne 20 -or $usb.Count -ne 8 -or @($usb | Where-Object { $_.configuration -notin @('default', 'vendor-only') }).Count -ne 0) { throw 'CI item matrix is not the required unique 40+10+2 XC profile contract.' }
    return $items
}

function Test-Port([string]$Value) { return $Value -match '^COM\d+$' }
function Get-NextProgress([int]$CurrentIndex, [int[]]$ConfirmedIndexes, [int]$ItemCount) {
    if ($ItemCount -lt 1 -or $CurrentIndex -lt 1 -or $CurrentIndex -gt $ItemCount) { throw 'Progress indexes must be within the item range.' }
    $confirmed = @($ConfirmedIndexes + $CurrentIndex | Where-Object { $_ -ge 1 -and $_ -le $ItemCount } | Sort-Object -Unique)
    return [pscustomobject]@{ CurrentIndex = if ($CurrentIndex -eq $ItemCount) { $CurrentIndex } else { $CurrentIndex + 1 }; ConfirmedIndexes = $confirmed; Completed = $CurrentIndex -eq $ItemCount }
}
function Get-StateForFinalSha($Saved, [string]$ExpectedSha, [string]$DefaultPort, [int]$ItemCount) {
    if (-not $Saved -or -not $Saved.PSObject.Properties['FinalSha'] -or -not $Saved.PSObject.Properties['CurrentIndex'] -or -not $Saved.PSObject.Properties['ConfirmedIndexes'] -or [string]$Saved.FinalSha -ne $ExpectedSha) { return [pscustomobject]@{ CurrentIndex = $DefaultStartIndex; ConfirmedIndexes = @(); Port = $DefaultPort } }
    $index = [int]$Saved.CurrentIndex
    if ($index -lt 1 -or $index -gt $ItemCount) { throw "Saved CurrentIndex is outside 1..$ItemCount." }
    $confirmed = @($Saved.ConfirmedIndexes | ForEach-Object { [int]$_ } | Sort-Object -Unique)
    $pendingExpected = if ($index -eq 1) { @() } else { @(1..($index - 1)) }
    $matchesPending = $confirmed.Count -eq $pendingExpected.Count -and @($confirmed | Where-Object { $_ -notin $pendingExpected }).Count -eq 0
    $matchesComplete = $false
    if ($index -eq $ItemCount) {
        $completeExpected = @(1..$ItemCount)
        $matchesComplete = $confirmed.Count -eq $completeExpected.Count -and @($confirmed | Where-Object { $_ -notin $completeExpected }).Count -eq 0
    }
    if (-not ($matchesPending -or $matchesComplete)) { throw 'Saved state violates the sequential confirmed-item invariant.' }
    return [pscustomobject]@{ CurrentIndex = $index; ConfirmedIndexes = $confirmed; Port = $DefaultPort }
}

function Test-SafeRelativePackagePath([string]$PackageRoot, [string]$RelativePath) {
    if ([string]::IsNullOrWhiteSpace($RelativePath) -or [System.IO.Path]::IsPathRooted($RelativePath) -or $RelativePath -match '^[A-Za-z]:' -or $RelativePath -match '^[\\/]{2}' -or $RelativePath -match '(^|[\\/])\.\.([\\/]|$)') { return $false }
    $root = [System.IO.Path]::GetFullPath($PackageRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    $candidate = [System.IO.Path]::GetFullPath((Join-Path $PackageRoot $RelativePath))
    return $candidate.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)
}
function Get-FileSha256([string]$Path) {
    $stream = $null; $algorithm = $null
    try { $stream = [System.IO.File]::OpenRead($Path); $algorithm = [System.Security.Cryptography.SHA256]::Create(); return [System.BitConverter]::ToString($algorithm.ComputeHash($stream)).Replace('-', '').ToLowerInvariant() }
    finally { if ($stream) { $stream.Dispose() }; if ($algorithm) { $algorithm.Dispose() } }
}
function Test-LeafNotLink([string]$Path) {
    $item = Get-Item -LiteralPath $Path -Force
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0 -or $item.LinkType) { throw "Refusing a linked package file: $Path" }
}
function Get-FlashOptions($FlashSettings) {
    $allowed = @{ '--flash_mode' = '^(qio|qout|dio|dout)$'; '--flash_freq' = '^(20m|26m|40m|80m)$'; '--flash_size' = '^(detect|1MB|2MB|4MB|8MB|16MB|32MB)$' }
    $aliases = @{ '--flash_mode' = '--flash_mode'; '--flash-mode' = '--flash_mode'; '--flash_freq' = '--flash_freq'; '--flash-freq' = '--flash_freq'; '--flash_size' = '--flash_size'; '--flash-size' = '--flash_size' }
    $pairs = @()
    if ($FlashSettings -and $FlashSettings.PSObject.Properties['esptool_options']) {
        $options = @($FlashSettings.esptool_options)
        if ($options.Count % 2 -ne 0) { throw 'Manifest esptool_options must be option/value pairs.' }
        for ($i = 0; $i -lt $options.Count; $i += 2) { $pairs += ,@([string]$options[$i], [string]$options[$i + 1]) }
    } elseif ($FlashSettings) {
        foreach ($key in @('flash_mode', 'flash_freq', 'flash_size')) { if ($FlashSettings.PSObject.Properties[$key] -and [string]$FlashSettings.$key) { $pairs += ,@('--' + $key, [string]$FlashSettings.$key) } }
    }
    $seen = @{}; $result = @()
    foreach ($pair in $pairs) {
        $option, $value = $pair[0], $pair[1]
        if (-not $aliases.ContainsKey($option)) { throw 'Manifest has unsafe esptool flash settings.' }
        $canonical = $aliases[$option]
        if ($seen.ContainsKey($canonical) -or $value -notmatch $allowed[$canonical]) { throw 'Manifest has unsafe esptool flash settings.' }
        $seen[$canonical] = $true; $result += $canonical; $result += $value
    }
    return $result
}

function ConvertFrom-ESP32P4ChipIdOutput([string]$Output) {
    if ($Output -notmatch '(?i)ESP32-P4') { throw 'Chip probe did not identify ESP32-P4.' }
    $match = [regex]::Match($Output, '(?im)\brevision\s*(?:v(?:ersion)?)?\s*([0-9]+(?:\.[0-9]+){0,2})\b')
    if (-not $match.Success) { throw "ESP32-P4 chip revision probe did not report a parseable revision: $Output" }
    try { $major = [int]($match.Groups[1].Value.Split('.')[0]) } catch { throw "ESP32-P4 chip revision is invalid: $($match.Groups[1].Value)" }
    $profile = if ($major -lt 3) { 'rev1_3' } else { 'rev3_x' }
    return [pscustomobject]@{ Revision = $match.Groups[1].Value; Major = $major; ProfileId = $profile; Output = $Output }
}
function Get-ESP32P4SiliconProfile([string]$PythonExe, [string]$SelectedPort) {
    # chip_id only reads the ROM identity.  It runs before any artifact download
    # so an incompatible profile cannot be selected for this connected chip.
    $output = (& $PythonExe -m esptool --chip esp32p4 --port $SelectedPort chip-id 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) {
        $output = (& $PythonExe -m esptool --chip esp32p4 --port $SelectedPort chip_id 2>&1 | Out-String)
    }
    if ($LASTEXITCODE -ne 0) { throw "Read-only ESP32-P4 chip revision probe failed: $output" }
    return ConvertFrom-ESP32P4ChipIdOutput $output
}

function Select-CompatibleItems($Items, [string]$ProfileId) {
    $selected = @($Items | Where-Object { $_.ProfileId -eq $ProfileId })
    if ($ProfileId -eq 'rev1_3') {
        if ($selected.Count -ne 51 -or @($selected | Where-Object { $_.ProfileId -ne 'rev1_3' }).Count -ne 0) { throw 'Pre-v3 ESP32-P4 must select exactly the 50 example artifacts plus rev1_3 maintained firmware.' }
    } elseif ($ProfileId -eq 'rev3_x') {
        if ($selected.Count -ne 1 -or $selected[0].ArtifactKind -ne 'maintained-firmware') { throw 'ESP32-P4 revision >= 3.0 must select only the rev3_x maintained-firmware artifact.' }
    } else { throw "Unsupported ESP32-P4 profile: $ProfileId" }
    $index = 1
    foreach ($item in $selected) { $item.Index = $index; $index++ }
    return $selected
}

function Resolve-FinalSha([string]$GitExe) {
    $sha = (& $GitExe -C $RepoRoot rev-parse HEAD 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or $sha -notmatch '^[0-9a-fA-F]{40}$') { throw 'Unable to resolve a full local git HEAD SHA.' }
    return $sha.ToLowerInvariant()
}
function Assert-CleanWorktree([string]$GitExe) {
    $status = (& $GitExe -C $RepoRoot status --porcelain=v1 --untracked-files=all 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0 -or -not [string]::IsNullOrWhiteSpace($status)) { throw 'Refusing to continue: the working tree must be clean.' }
}
function Resolve-CurrentBranch([string]$GitExe) {
    $branch = (& $GitExe -C $RepoRoot symbolic-ref --quiet --short HEAD 2>&1 | Out-String).Trim()
    if ($LASTEXITCODE -ne 0 -or [string]::IsNullOrWhiteSpace($branch)) { throw 'Refusing to continue: check out a non-detached branch first.' }
    return $branch
}
function Assert-ReadyPullRequest([string]$GhExe, [string]$Branch, [string]$FinalSha) {
    $raw = (& $GhExe pr list --repo $Repo --head $Branch --state open --limit 2 --json number,state,isDraft,headRefName,headRefOid 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw 'Unable to query the open pull request for the current branch.' }
    $prs = @($raw | ConvertFrom-Json)
    if ($prs.Count -ne 1 -or [string]$prs[0].state -ine 'OPEN' -or [bool]$prs[0].isDraft -or [string]$prs[0].headRefName -ne $Branch -or -not [string]::Equals([string]$prs[0].headRefOid, $FinalSha, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Refusing to continue: exactly one ready PR must match this branch and complete local HEAD SHA.' }
    return [pscustomobject]@{ Number = [int]$prs[0].number; Branch = $Branch; HeadSha = $FinalSha }
}
function Test-ExactArtifactSet($Artifacts, [string[]]$ExpectedNames) {
    $expected = @($ExpectedNames | Sort-Object -Unique)
    $actual = @($Artifacts)
    if ($expected.Count -eq 0 -or $expected.Count -ne $ExpectedNames.Count -or $actual.Count -ne $expected.Count) { return $false }
    foreach ($artifact in $actual) {
        if (-not $artifact -or -not $artifact.PSObject.Properties['name'] -or -not $artifact.PSObject.Properties['expired'] -or [bool]$artifact.expired) { return $false }
    }
    $names = @($actual | ForEach-Object { [string]$_.name } | Sort-Object)
    if (@($names | Sort-Object -Unique).Count -ne $names.Count) { return $false }
    return @($names | Where-Object { $_ -notin $expected }).Count -eq 0
}
function Resolve-ArtifactRuns([string]$GhExe, [string]$FinalSha, [string]$Branch, $Items) {
    foreach ($item in $Items) { $item | Add-Member -NotePropertyName Artifact -NotePropertyValue ($item.ArtifactKey + '-' + $FinalSha.Substring(0, 12)) -Force }
    $runs = @{}
    foreach ($workflow in @($Items.Workflow | Sort-Object -Unique)) {
        $raw = (& $GhExe run list --repo $Repo --workflow $workflow --commit $FinalSha --status success --limit 20 --json databaseId,headSha,headBranch,event,createdAt 2>&1 | Out-String)
        if ($LASTEXITCODE -ne 0) { throw "Unable to list successful $workflow runs: $raw" }
        $expected = @($Items | Where-Object { $_.Workflow -eq $workflow } | ForEach-Object Artifact)
        $candidates = @($raw | ConvertFrom-Json | Where-Object { [string]$_.headSha -eq $FinalSha -and [string]$_.headBranch -eq $Branch -and [string]$_.event -in @('pull_request', 'workflow_dispatch') } | Sort-Object createdAt -Descending)
        $selected = $null
        foreach ($candidate in $candidates) {
            $artifactRaw = (& $GhExe api "repos/$Repo/actions/runs/$($candidate.databaseId)/artifacts?per_page=100" 2>&1 | Out-String)
            if ($LASTEXITCODE -ne 0) { throw "Unable to inspect artifacts for $workflow run $($candidate.databaseId): $artifactRaw" }
            try { $artifactResult = $artifactRaw | ConvertFrom-Json } catch { throw "Artifact API response for $workflow run $($candidate.databaseId) was invalid." }
            if (-not $artifactResult.PSObject.Properties['artifacts'] -or -not $artifactResult.PSObject.Properties['total_count'] -or [int]$artifactResult.total_count -ne @($artifactResult.artifacts).Count) { throw "Artifact API response for $workflow run $($candidate.databaseId) was incomplete." }
            if (Test-ExactArtifactSet @($artifactResult.artifacts) $expected) { $selected = $candidate; break }
        }
        if (-not $selected) { throw "No complete unexpired $workflow artifact set exists for exact local HEAD and branch." }
        $runs[$workflow] = [string]$selected.databaseId
    }
    foreach ($item in $Items) { $item | Add-Member -NotePropertyName Run -NotePropertyValue $runs[$item.Workflow] -Force }
}

function Ensure-StateRoot { if (-not (Test-Path -LiteralPath $StateRoot)) { New-Item -ItemType Directory -Path $StateRoot | Out-Null } }
function Read-State([string]$FinalSha, [int]$ItemCount) { $saved = if (Test-Path -LiteralPath $StatePath) { Get-Content -LiteralPath $StatePath -Raw | ConvertFrom-Json } else { $null }; return Get-StateForFinalSha $saved $FinalSha $Port $ItemCount }
function Save-State([int]$CurrentIndex, [int[]]$ConfirmedIndexes, [string]$SavedPort, [string]$FinalSha) { Ensure-StateRoot; [pscustomobject]@{ CurrentIndex = $CurrentIndex; ConfirmedIndexes = @($ConfirmedIndexes | Sort-Object -Unique); Port = $SavedPort; UpdatedAt = (Get-Date).ToString('o'); Repository = $Repo; FinalSha = $FinalSha } | ConvertTo-Json | Set-Content -LiteralPath $StatePath -Encoding utf8 }
function New-RunPaths { Ensure-StateRoot; $stamp = Get-Date -Format 'yyyyMMdd-HHmmss-fff'; $downloadRoot = Join-Path $StateRoot 'downloads'; $logRoot = Join-Path $StateRoot 'logs'; foreach ($dir in @($downloadRoot, $logRoot)) { if (-not (Test-Path -LiteralPath $dir)) { New-Item -ItemType Directory -Path $dir | Out-Null } }; $download = Join-Path $downloadRoot $stamp; $log = Join-Path $logRoot ($stamp + '.log'); New-Item -ItemType Directory -Path $download | Out-Null; New-Item -ItemType File -Path $log | Out-Null; return [pscustomobject]@{ DownloadDir = $download; LogPath = $log } }
function Add-RunLog([string]$Path, [string]$Text) { Add-Content -LiteralPath $Path -Value $Text -Encoding utf8 }
function Find-PackageDirectory([string]$DownloadDir) {
    foreach ($zip in @(Get-ChildItem -LiteralPath $DownloadDir -Recurse -File -Filter '*.zip')) { $destination = Join-Path $zip.DirectoryName ($zip.BaseName + '-unzipped'); if (Test-Path -LiteralPath $destination) { throw "Refusing to overwrite extraction directory: $destination" }; Expand-Archive -LiteralPath $zip.FullName -DestinationPath $destination -ErrorAction Stop }
    $manifests = @(Get-ChildItem -LiteralPath $DownloadDir -Recurse -File -Filter 'manifest.json')
    if ($manifests.Count -ne 1) { throw 'Expected exactly one manifest.json in the downloaded artifact.' }
    Test-LeafNotLink $manifests[0].FullName; return $manifests[0].DirectoryName
}
function Test-PackageManifest([string]$PackageDir, $Item, [string]$FinalSha) {
    $manifestPath = Join-Path $PackageDir 'manifest.json'; Test-LeafNotLink $manifestPath
    $manifest = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($manifest.schema -ne 2 -or [string]$manifest.target -ne 'esp32p4' -or [string]$manifest.artifact_kind -ne $Item.ArtifactKind -or [string]$manifest.profile_id -ne $Item.ProfileId -or -not [string]::Equals([string]$manifest.git_sha, $FinalSha, [System.StringComparison]::OrdinalIgnoreCase) -or [string]$manifest.source_type -ne $Item.SourceType -or [string]$manifest.framework.name -ne $Item.FrameworkName -or [string]$manifest.framework.version -ne $Item.FrameworkVersion -or [string]$manifest.project -ne $Item.Project -or [string]$manifest.sketch -ne $Item.Sketch -or [string]$manifest.configuration -ne $Item.Configuration -or [string]$manifest.product_variant_id -ne $Item.VariantId) { throw 'Package manifest identity, target, or profile does not match the selected XC CI item and local HEAD.' }
    if ([int64]$manifest.flash_capacity_bytes -ne $FlashLimit -or [int64]$manifest.baud -le 0 -or @($manifest.files).Count -lt 1) { throw 'Package manifest flash metadata is incomplete or not bounded to 32 MiB.' }
    if ([string]$manifest.portable_flash_command -notmatch '(?i)--chip\s+esp32p4\b.*\bwrite[_-]flash\b' -or [string]$manifest.portable_flash_command -match '(?i)erase(?:[_-](?:flash|region))?|esp32c6') { throw 'Package manifest portable command is not a P4-only non-erase write.' }
    $originalArgsJson = $manifest.original_flash_args | ConvertTo-Json -Compress -Depth 20
    if ($originalArgsJson -match '(?i)erase(?:[_-](?:flash|region))?|esp32c6') { throw 'Package manifest original flash plan contains C6 or erase instructions.' }
    $plan = @(); $offsets = @{}
    foreach ($file in @($manifest.files)) {
        $relative = [string]$file.path
        if ($relative -match '(?i)(^|[\\/_.-])(?:esp32)?c6([\\/_.-]|$)' -or $relative -match '(?i)erase(?:[_-](?:flash|region))?') { throw "Manifest file path contains a forbidden C6 or erase token: $relative" }
        if (-not (Test-SafeRelativePackagePath $PackageDir $relative) -or [string]$file.sha256 -notmatch '^[0-9a-fA-F]{64}$' -or [int64]$file.size -le 0) { throw "Manifest file metadata is unsafe: $relative" }
        $full = Join-Path $PackageDir $relative
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { throw "Manifest file is missing: $relative" }
        Test-LeafNotLink $full
        if ((Get-FileSha256 $full) -ne [string]$file.sha256 -or [int64](Get-Item -LiteralPath $full).Length -ne [int64]$file.size) { throw "Manifest checksum or size verification failed: $relative" }
        if ($null -ne $file.offset -and [string]$file.offset -ne '') {
            $rawOffset = [string]$file.offset
            try {
                if ($rawOffset -match '^0[xX][0-9a-fA-F]+$') { $offset = [Convert]::ToInt64($rawOffset.Substring(2), 16) }
                elseif ($rawOffset -match '^\d+$') { $offset = [Convert]::ToInt64($rawOffset, 10) }
                else { throw 'not an integer offset' }
            } catch { throw "Manifest flash offset is invalid: $relative" }
            if ($offset -lt 0 -or $offsets.ContainsKey($offset) -or $offset -gt ($FlashLimit - [int64]$file.size)) { throw "Manifest flash range is unsafe: $relative" }
            $offsets[$offset] = $true; $plan += [pscustomobject]@{ Offset = $offset; Size = [int64]$file.size; Path = $full }
        }
    }
    if ($plan.Count -lt 1) { throw 'Package manifest contains no flashable files.' }
    $ordered = @($plan | Sort-Object Offset)
    for ($i = 1; $i -lt $ordered.Count; $i++) { if ($ordered[$i - 1].Offset + $ordered[$i - 1].Size -gt $ordered[$i].Offset) { throw 'Package manifest contains overlapping flash ranges.' } }
    return [pscustomobject]@{ Plan = $ordered; Baud = [int]$manifest.baud; Options = @(Get-FlashOptions $manifest.flash_settings) }
}
function Invoke-CurrentFlash($Item, [string]$SelectedPort, [string]$GhExe, [string]$PythonExe, [string]$FinalSha) {
    $paths = New-RunPaths; Add-RunLog $paths.LogPath "finalSHA=$FinalSha index=$($Item.Index) artifact=$($Item.Artifact) run=$($Item.Run) port=$SelectedPort"
    $download = (& $GhExe run download $Item.Run --repo $Repo --name $Item.Artifact --dir $paths.DownloadDir 2>&1 | Out-String); $downloadExit = $LASTEXITCODE; Add-RunLog $paths.LogPath $download
    if ($downloadExit -ne 0) { throw "Artifact download failed with exit code $downloadExit. Log: $($paths.LogPath)" }
    $flash = Test-PackageManifest (Find-PackageDirectory $paths.DownloadDir) $Item $FinalSha
    $flashArguments = @('-m', 'esptool', '--chip', 'esp32p4', '--port', $SelectedPort, '--baud', [string]$flash.Baud, 'write_flash') + @($flash.Options)
    foreach ($entry in $flash.Plan) { $flashArguments += ('0x{0:X}' -f $entry.Offset); $flashArguments += $entry.Path }
    $output = (& $PythonExe @flashArguments 2>&1 | Out-String); $exit = $LASTEXITCODE; Add-RunLog $paths.LogPath $output
    return [pscustomobject]@{ Success = ($exit -eq 0 -and $output.Contains('Hash of data verified')); Output = $output; LogPath = $paths.LogPath; Detail = if ($exit -eq 0 -and $output.Contains('Hash of data verified')) { 'Flash write was verified. Check the hardware before marking PASS.' } else { 'Flash did not meet the required exit-code and hash-verification condition.' } }
}

if ($SelfTest -or $ListOnly) {
    $PythonExe = Resolve-Python; $Items = Get-CiItems $PythonExe
    if ($SelfTest) {
        $current = $DefaultStartIndex; $confirmed = @(); while ($current -lt $Items.Count) { $next = Get-NextProgress $current $confirmed $Items.Count; $current = $next.CurrentIndex; $confirmed = @($next.ConfirmedIndexes) }
        $last = Get-NextProgress $current $confirmed $Items.Count
        $testRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'ci-package'
        $absoluteTestPath = Join-Path ([System.IO.Path]::GetTempPath()) 'escape.bin'
        if (-not $last.Completed -or @($last.ConfirmedIndexes).Count -ne 52 -or (Test-SafeRelativePackagePath $testRoot '..\escape.bin') -or (Test-SafeRelativePackagePath $testRoot $absoluteTestPath) -or -not (Test-SafeRelativePackagePath $testRoot 'bin\app.bin')) { throw 'SelfTest safety or progress check failed.' }
        $arduinoOptions = @(Get-FlashOptions ([pscustomobject]@{ esptool_options = @('--flash-mode', 'dio', '--flash-freq', '80m', '--flash-size', '32MB') }))
        if (($arduinoOptions -join ' ') -ne '--flash_mode dio --flash_freq 80m --flash_size 32MB') { throw 'SelfTest did not normalize Arduino hyphen flash options.' }
        try { Get-FlashOptions ([pscustomobject]@{ esptool_options = @('--before', 'default-reset') }) | Out-Null; throw 'SelfTest accepted unsafe options.' } catch { if ($_.Exception.Message -eq 'SelfTest accepted unsafe options.') { throw } }
        try { Get-FlashOptions ([pscustomobject]@{ esptool_options = @('--flash-mode', 'dio', '--flash_mode', 'qio') }) | Out-Null; throw 'SelfTest accepted duplicate flash-option aliases.' } catch { if ($_.Exception.Message -eq 'SelfTest accepted duplicate flash-option aliases.') { throw } }
        $pendingLast = Get-StateForFinalSha ([pscustomobject]@{ FinalSha = 'expected'; CurrentIndex = 52; ConfirmedIndexes = @(1..51) }) 'expected' '' 52
        $completedLast = Get-StateForFinalSha ([pscustomobject]@{ FinalSha = 'expected'; CurrentIndex = 52; ConfirmedIndexes = @(1..52) }) 'expected' '' 52
        if (@($pendingLast.ConfirmedIndexes).Count -ne 51 -or @($completedLast.ConfirmedIndexes).Count -ne 52) { throw 'SelfTest rejected a valid final-item state.' }
        try { Get-StateForFinalSha ([pscustomobject]@{ FinalSha = 'expected'; CurrentIndex = 52; ConfirmedIndexes = @(52) }) 'expected' '' 52 | Out-Null; throw 'SelfTest accepted an invalid saved state.' } catch { if ($_.Exception.Message -eq 'SelfTest accepted an invalid saved state.') { throw } }
        if (@(Select-CompatibleItems $Items 'rev1_3').Count -ne 51 -or @(Select-CompatibleItems $Items 'rev3_x').Count -ne 1) { throw 'SelfTest profile selection contract failed.' }
        $parsedPreV3 = ConvertFrom-ESP32P4ChipIdOutput 'Chip is ESP32-P4 (revision v1.3)'
        $parsedV3 = ConvertFrom-ESP32P4ChipIdOutput 'Chip is ESP32-P4 (revision v3.2)'
        if ($parsedPreV3.ProfileId -ne 'rev1_3' -or $parsedV3.ProfileId -ne 'rev3_x') { throw 'SelfTest chip revision parser contract failed.' }
        try { ConvertFrom-ESP32P4ChipIdOutput 'Chip is ESP32-C6 (revision v1.0)' | Out-Null; throw 'SelfTest accepted a non-P4 chip.' } catch { if ($_.Exception.Message -eq 'SelfTest accepted a non-P4 chip.') { throw } }
        $syntheticSha = '0123456789abcdef0123456789abcdef01234567'
        $idfNames = @($Items | Where-Object { $_.Workflow -eq 'esp-idf-projects.yml' } | ForEach-Object { $_.ArtifactKey + '-' + $syntheticSha.Substring(0, 12) })
        $arduinoNames = @($Items | Where-Object { $_.Workflow -eq 'arduino-projects.yml' } | ForEach-Object { $_.ArtifactKey + '-' + $syntheticSha.Substring(0, 12) })
        $firmwareNames = @($Items | Where-Object { $_.Workflow -eq 'maintained-firmware.yml' } | ForEach-Object { $_.ArtifactKey + '-' + $syntheticSha.Substring(0, 12) })
        $idfArtifacts = @($idfNames | ForEach-Object { [pscustomobject]@{ name = $_; expired = $false } })
        $arduinoArtifacts = @($arduinoNames | ForEach-Object { [pscustomobject]@{ name = $_; expired = $false } })
        $firmwareArtifacts = @($firmwareNames | ForEach-Object { [pscustomobject]@{ name = $_; expired = $false } })
        if (-not (Test-ExactArtifactSet $idfArtifacts $idfNames) -or -not (Test-ExactArtifactSet $arduinoArtifacts $arduinoNames) -or -not (Test-ExactArtifactSet $firmwareArtifacts $firmwareNames) -or (Test-ExactArtifactSet @($idfArtifacts | Select-Object -Skip 1) $idfNames) -or (Test-ExactArtifactSet @($arduinoArtifacts + [pscustomobject]@{ name = $arduinoNames[0]; expired = $false }) $arduinoNames) -or (Test-ExactArtifactSet @($firmwareArtifacts | Select-Object -Skip 1) $firmwareNames) -or (Test-ExactArtifactSet @($idfArtifacts | ForEach-Object { [pscustomobject]@{ name = $_.name; expired = ($_.name -eq $idfNames[0]) } }) $idfNames)) { throw 'SelfTest artifact-set validation failed.' }
        Write-Output 'SELF_TEST_OK items=52 esp_idf=40 arduino=10 maintained_firmware=2 no_network_no_serial_no_flash'
        return
    }
    Write-Output 'LIST_ONLY items=52 esp_idf=40 arduino=10 maintained_firmware=2 no_network_no_serial_no_flash'
    foreach ($item in $Items) { Write-Output ('{0}: workflow={1} artifact_key={2} artifact_suffix=HEAD12 source_type={3} project={4} configuration={5} variant={6} profile={7}' -f $item.Index, $item.Workflow, $item.ArtifactKey, $item.SourceType, $item.Project, $item.Configuration, $item.VariantId, $item.ProfileId) }
    return
}

if ([string]::IsNullOrWhiteSpace($Port)) { throw 'Normal mode requires an explicit -Port COMx.' }
$Port = $Port.Trim().ToUpperInvariant(); if (-not (Test-Port $Port)) { throw 'Port must be COM followed by digits, for example COMx.' }
$GitExe = Resolve-Git; $FinalSha = Resolve-FinalSha $GitExe; Assert-CleanWorktree $GitExe; $Branch = Resolve-CurrentBranch $GitExe
$GhExe = Resolve-Gh; $pullRequest = Assert-ReadyPullRequest $GhExe $Branch $FinalSha; $PythonExe = Resolve-PythonWithEsptool; $CatalogItems = Get-CiItems $PythonExe
$silicon = Get-ESP32P4SiliconProfile $PythonExe $Port
Resolve-ArtifactRuns $GhExe $FinalSha $pullRequest.Branch $CatalogItems
$Items = @(Select-CompatibleItems $CatalogItems $silicon.ProfileId)
Add-Type -AssemblyName System.Windows.Forms; Add-Type -AssemblyName System.Drawing
$state = Read-State $FinalSha $Items.Count; $script:CurrentIndex = $state.CurrentIndex; $script:ConfirmedIndexes = @($state.ConfirmedIndexes); $script:CurrentFlashVerified = $false
$form = New-Object System.Windows.Forms.Form; $form.Text = 'CI Firmware Flasher'; $form.StartPosition = 'CenterScreen'; $form.ClientSize = New-Object System.Drawing.Size(900, 700); $form.FormBorderStyle = 'FixedDialog'; $form.MaximizeBox = $false
function Add-Label([string]$Text, [int]$X, [int]$Y, [int]$Width = 860) { $label = New-Object System.Windows.Forms.Label; $label.Text = $Text; $label.Location = New-Object System.Drawing.Point($X, $Y); $label.Size = New-Object System.Drawing.Size($Width, 20); $form.Controls.Add($label); return $label }
$null = Add-Label "Repository: $Repo" 15 15; $null = Add-Label "Exact HEAD: $FinalSha" 15 40; $null = Add-Label 'Port:' 15 70 45
$portBox = New-Object System.Windows.Forms.TextBox; $portBox.Text = $state.Port; $portBox.ReadOnly = $true; $portBox.Location = New-Object System.Drawing.Point(65, 67); $portBox.Size = New-Object System.Drawing.Size(110, 22); $form.Controls.Add($portBox)
$currentLabel = Add-Label '' 15 100; $statusLabel = Add-Label 'Status: confirm the port, flash the current artifact, then test the hardware.' 15 125
$noticeLabel = Add-Label "Silicon revision v$($silicon.Revision) selected $($silicon.ProfileId). Warning: silicon revision is not the PCB/electrical revision. CI and a verified write do not prove display, touch, audio, USB, or other hardware behavior." 15 145
$progressList = New-Object System.Windows.Forms.ListBox; $progressList.Font = New-Object System.Drawing.Font('Consolas', 9); $progressList.Location = New-Object System.Drawing.Point(15, 170); $progressList.Size = New-Object System.Drawing.Size(870, 260); $form.Controls.Add($progressList)
$outputBox = New-Object System.Windows.Forms.TextBox; $outputBox.Multiline = $true; $outputBox.ReadOnly = $true; $outputBox.ScrollBars = 'Both'; $outputBox.WordWrap = $false; $outputBox.Font = New-Object System.Drawing.Font('Consolas', 9); $outputBox.Location = New-Object System.Drawing.Point(15, 440); $outputBox.Size = New-Object System.Drawing.Size(870, 190); $form.Controls.Add($outputBox)
$flashButton = New-Object System.Windows.Forms.Button; $flashButton.Text = 'Confirm port and flash current'; $flashButton.Location = New-Object System.Drawing.Point(15, 645); $flashButton.Size = New-Object System.Drawing.Size(205, 32); $form.Controls.Add($flashButton)
$confirmButton = New-Object System.Windows.Forms.Button; $confirmButton.Text = 'Mark hardware PASS and next'; $confirmButton.Location = New-Object System.Drawing.Point(230, 645); $confirmButton.Size = New-Object System.Drawing.Size(220, 32); $confirmButton.Enabled = $false; $form.Controls.Add($confirmButton)
$exitButton = New-Object System.Windows.Forms.Button; $exitButton.Text = 'Exit'; $exitButton.Location = New-Object System.Drawing.Point(765, 645); $exitButton.Size = New-Object System.Drawing.Size(120, 32); $form.Controls.Add($exitButton)
function Update-CurrentDisplay { $item = $Items[$script:CurrentIndex - 1]; $currentLabel.Text = "Current: $($item.Index)/$($Items.Count) Artifact: $($item.Artifact) Run: $($item.Run)"; $progressList.Items.Clear(); foreach ($entry in $Items) { $prefix = if ($script:ConfirmedIndexes -contains $entry.Index) { '[PASS]' } elseif ($entry.Index -eq $script:CurrentIndex) { '[CURRENT]' } else { '[WAIT]' }; [void]$progressList.Items.Add(('{0} {1}: {2}' -f $prefix, $entry.Index, $entry.Artifact)) }; $progressList.SelectedIndex = $script:CurrentIndex - 1 }
function Set-Busy([bool]$Busy) { $complete = $script:CurrentIndex -eq $Items.Count -and $script:ConfirmedIndexes -contains $Items.Count; $flashButton.Enabled = (-not $Busy) -and (-not $complete); $confirmButton.Enabled = (-not $Busy) -and $script:CurrentFlashVerified -and (-not $complete); $exitButton.Enabled = -not $Busy; $portBox.Enabled = -not $Busy; $form.UseWaitCursor = $Busy; [System.Windows.Forms.Application]::DoEvents() }
function Flash-CurrentItem {
    $selectedPort = $portBox.Text.Trim().ToUpperInvariant(); if ($selectedPort -ne $Port -or -not (Test-Port $selectedPort)) { [System.Windows.Forms.MessageBox]::Show('The read-only port must match the explicit -Port COMx argument.', 'Invalid port') | Out-Null; return }
    if ([System.Windows.Forms.MessageBox]::Show("Flash the current CI artifact to $selectedPort? This does not erase the flash.", 'Confirm port', [System.Windows.Forms.MessageBoxButtons]::YesNo) -ne [System.Windows.Forms.DialogResult]::Yes) { return }
    $script:CurrentFlashVerified = $false; Set-Busy $true; $item = $Items[$script:CurrentIndex - 1]; $statusLabel.Text = "Status: Flashing item $($item.Index) on $selectedPort..."
    try { $result = Invoke-CurrentFlash $item $selectedPort $GhExe $PythonExe $FinalSha; $outputBox.Text = "Log: $($result.LogPath)`r`n`r`n$($result.Output)"; if ($result.Success) { Save-State $script:CurrentIndex $script:ConfirmedIndexes $selectedPort $FinalSha; $statusLabel.Text = "Status: $($result.Detail)"; $script:CurrentFlashVerified = $true } else { $statusLabel.Text = "Status: $($result.Detail) Current item was not advanced. Log: $($result.LogPath)" } }
    catch { $outputBox.Text = $_ | Out-String; $statusLabel.Text = "Status: Error. Current item was not advanced. $($_.Exception.Message)" }
    finally { Set-Busy $false }
}
$flashButton.Add_Click({ Flash-CurrentItem })
$confirmButton.Add_Click({ if (-not $script:CurrentFlashVerified) { return }; if ([System.Windows.Forms.MessageBox]::Show('Have you manually tested the hardware and confirmed PASS for this item?', 'Confirm hardware PASS', [System.Windows.Forms.MessageBoxButtons]::YesNo) -ne [System.Windows.Forms.DialogResult]::Yes) { return }; $selectedPort = $portBox.Text.Trim().ToUpperInvariant(); $next = Get-NextProgress $script:CurrentIndex $script:ConfirmedIndexes $Items.Count; $script:CurrentIndex = $next.CurrentIndex; $script:ConfirmedIndexes = @($next.ConfirmedIndexes); $script:CurrentFlashVerified = $false; Save-State $script:CurrentIndex $script:ConfirmedIndexes $selectedPort $FinalSha; Update-CurrentDisplay; if ($next.Completed) { Set-Busy $false; $statusLabel.Text = "Status: All $($Items.Count) items are confirmed." } })
$exitButton.Add_Click({ $form.Close() }); $progressList.Add_SelectedIndexChanged({ if ($progressList.SelectedIndex -ne ($script:CurrentIndex - 1)) { $progressList.SelectedIndex = $script:CurrentIndex - 1 } })
Update-CurrentDisplay; if ($script:CurrentIndex -eq $Items.Count -and $script:ConfirmedIndexes -contains $Items.Count) { Set-Busy $false; $statusLabel.Text = "Status: All $($Items.Count) items are confirmed." }; [void]$form.ShowDialog()
