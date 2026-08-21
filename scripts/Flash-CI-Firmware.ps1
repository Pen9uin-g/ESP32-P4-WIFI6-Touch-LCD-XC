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
$ManifestSchema = 3
$ArduinoWorkflowPath = Join-Path ([System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..'))) '.github\workflows\arduino-projects.yml'

function Resolve-Executable([string]$Name, [string[]]$Fallbacks) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue | Select-Object -First 1
    if ($command -and $command.Source) { return $command.Source }
    foreach ($candidate in $Fallbacks) {
        if ($candidate -and (Test-Path -LiteralPath $candidate -PathType Leaf)) { return $candidate }
    }
    throw "$Name was not found on PATH or in the supported fallback locations."
}

function Get-OptionalEnvironmentPath([string]$VariableName, [string]$ChildPath) {
    $root = [System.Environment]::GetEnvironmentVariable($VariableName)
    if ([string]::IsNullOrWhiteSpace($root)) { return '' }
    return Join-Path $root $ChildPath
}
function Resolve-Git { return Resolve-Executable 'git' @((Get-OptionalEnvironmentPath 'ProgramFiles' 'Git\cmd\git.exe'), (Get-OptionalEnvironmentPath 'ProgramFiles' 'Git\bin\git.exe')) }
function Resolve-Gh { return Resolve-Executable 'gh' @((Get-OptionalEnvironmentPath 'ProgramFiles' 'GitHub CLI\gh.exe'), (Get-OptionalEnvironmentPath 'ProgramFiles' 'GitHub CLI\bin\gh.exe')) }
function Resolve-Python { return Resolve-Executable 'python' @((Get-OptionalEnvironmentPath 'LocalAppData' 'Programs\Python\Python313\python.exe')) }
function Resolve-PythonWithEsptool {
    $candidates = @()
    try { $candidates += Resolve-Python } catch {}
    foreach ($root in @((Get-OptionalEnvironmentPath 'USERPROFILE' '.espressif\python_env'))) {
        if ([string]::IsNullOrWhiteSpace($root)) { continue }
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
$LocalApplicationData = [System.Environment]::GetEnvironmentVariable('LOCALAPPDATA')
if ([string]::IsNullOrWhiteSpace($LocalApplicationData)) { $LocalApplicationData = [System.IO.Path]::GetTempPath() }
$StateRoot = Join-Path $LocalApplicationData 'Waveshare\ESP32-P4-CI-Firmware'
$StatePath = Join-Path $StateRoot 'state-v1.json'

function Get-ExpectedArduinoIdentity {
    if (-not (Test-Path -LiteralPath $ArduinoWorkflowPath -PathType Leaf)) { throw 'Arduino workflow is missing.' }
    $required = @(
        'ARDUINO_CORE_VERSION',
        'ARDUINO_FQBN',
        'BSP_REFERENCE_VERSION',
        'BSP_REFERENCE_SOURCE_SHA',
        'BSP_REFERENCE_SOURCE_TREE',
        'BSP_REFERENCE_COMPONENT_TREE',
        'BSP_REFERENCE_RELATIONSHIP'
    )
    $values = @{}
    foreach ($line in [System.IO.File]::ReadAllLines($ArduinoWorkflowPath)) {
        $match = [regex]::Match($line, '^\s{2}([A-Z0-9_]+):\s+"([^"]+)"\s*$')
        if (-not $match.Success -or $match.Groups[1].Value -notin $required) { continue }
        $key = $match.Groups[1].Value
        if ($values.ContainsKey($key)) { throw "Arduino workflow declares duplicate $key values." }
        $values[$key] = $match.Groups[2].Value
    }
    foreach ($key in $required) { if (-not $values.ContainsKey($key)) { throw "Arduino workflow does not declare $key." } }
    foreach ($key in @('BSP_REFERENCE_SOURCE_SHA', 'BSP_REFERENCE_SOURCE_TREE', 'BSP_REFERENCE_COMPONENT_TREE')) {
        if ([string]$values[$key] -cnotmatch '^[0-9a-f]{40}$') { throw "Arduino workflow $key must be a lowercase full Git object ID." }
    }
    if ([string]$values['ARDUINO_CORE_VERSION'] -ne '3.3.11' -or [string]$values['ARDUINO_FQBN'] -notmatch '^esp32:esp32:esp32p4:ChipVariant=postv3,' -or [string]$values['BSP_REFERENCE_VERSION'] -ne '3.0.1' -or [string]$values['BSP_REFERENCE_RELATIONSHIP'] -ne 'reference-only') { throw 'Arduino workflow identity is outside the XC rev3 artifact contract.' }
    return [pscustomobject]@{
        CoreVersion = [string]$values['ARDUINO_CORE_VERSION']
        Fqbn = [string]$values['ARDUINO_FQBN']
        BspVersion = [string]$values['BSP_REFERENCE_VERSION']
        BspSourceSha = [string]$values['BSP_REFERENCE_SOURCE_SHA']
        BspSourceTree = [string]$values['BSP_REFERENCE_SOURCE_TREE']
        BspComponentTree = [string]$values['BSP_REFERENCE_COMPONENT_TREE']
        BspRelationship = [string]$values['BSP_REFERENCE_RELATIONSHIP']
    }
}

function Get-CiItems([string]$PythonExe) {
    if (-not (Test-Path -LiteralPath $RouterPath -PathType Leaf)) { throw 'CI router is missing.' }
    $raw = (& $PythonExe $RouterPath --all 2>&1 | Out-String)
    if ($LASTEXITCODE -ne 0) { throw "CI router --all failed: $raw" }
    $route = $raw | ConvertFrom-Json
    $idf = @($route.idf_matrix.include)
    $arduino = @($route.arduino_matrix.include)
    $firmware = @($route.firmware_matrix.include)
    if ($idf.Count -ne 40 -or $arduino.Count -ne 20 -or $firmware.Count -ne 2) { throw "CI router matrix must contain 40 ESP-IDF, 20 Arduino, and 2 maintained-firmware entries; got $($idf.Count), $($arduino.Count), and $($firmware.Count)." }
    $arduinoIdentity = Get-ExpectedArduinoIdentity
    $items = @(); $index = 1
    foreach ($entry in $idf) {
        if ($entry.idf_version -notin @('v5.5.5', 'v6.0.2') -or $entry.variant_id -notin @('shared', '3_4c', '4c') -or $entry.configuration -notin @('default', 'vendor-only') -or $entry.profile_id -ne 'rev3_x' -or [string]$entry.artifact_key -notmatch 'rev3_x') { throw 'ESP-IDF router entry is outside the XC rev3 CI contract.' }
        $items += [pscustomobject]@{ Index = $index; Workflow = 'esp-idf-projects.yml'; ArtifactKey = [string]$entry.artifact_key; SourceType = 'esp-idf'; FrameworkName = 'ESP-IDF'; FrameworkVersion = [string]$entry.idf_version; Project = [string]$entry.project; Sketch = ''; Configuration = [string]$entry.configuration; VariantId = [string]$entry.variant_id; Variant = [string]$entry.variant; ProfileId = [string]$entry.profile_id; ArtifactKind = 'ci-example' }
        $index++
    }
    foreach ($entry in $arduino) {
        if ($entry.variant_id -notin @('3_4c', '4c') -or $entry.configuration -ne 'default' -or $entry.profile_id -ne 'rev3_x' -or [string]$entry.artifact_key -notmatch 'rev3_x') { throw 'Arduino router entry is outside the XC rev3 CI contract.' }
        $items += [pscustomobject]@{ Index = $index; Workflow = 'arduino-projects.yml'; ArtifactKey = [string]$entry.artifact_key; SourceType = 'arduino'; FrameworkName = 'Arduino-ESP32'; FrameworkVersion = $arduinoIdentity.CoreVersion; Project = [string]$entry.sketch; Sketch = [string]$entry.sketch_name; Configuration = [string]$entry.configuration; VariantId = [string]$entry.variant_id; Variant = [string]$entry.variant; Resolution = [string]$entry.resolution; ProfileId = [string]$entry.profile_id; ArtifactKind = 'ci-example'; Fqbn = $arduinoIdentity.Fqbn; BspVersion = $arduinoIdentity.BspVersion; BspSourceSha = $arduinoIdentity.BspSourceSha; BspSourceTree = $arduinoIdentity.BspSourceTree; BspComponentTree = $arduinoIdentity.BspComponentTree; BspRelationship = $arduinoIdentity.BspRelationship }
        $index++
    }
    foreach ($entry in $firmware) {
        if ($entry.project -ne 'firmware/brookesia' -or $entry.profile_id -ne 'rev3_x' -or $entry.variant_id -notin @('3_4c', '4c') -or $entry.variant -notin @('3.4C', '4C') -or [string]$entry.artifact_key -notmatch 'rev3_x' -or [string]$entry.artifact_key -notmatch [string]$entry.variant_id -or [string]$entry.sdkconfig_defaults -notmatch 'sdkconfig\.defaults\.rev3_x' -or [string]$entry.sdkconfig_defaults -notmatch ('sdkconfig\.defaults\.' + [string]$entry.variant_id)) { throw 'Maintained firmware router entry is outside the XC rev3 dual-panel CI contract.' }
        $items += [pscustomobject]@{ Index = $index; Workflow = 'maintained-firmware.yml'; ArtifactKey = [string]$entry.artifact_key; SourceType = 'esp-idf'; FrameworkName = 'ESP-IDF'; FrameworkVersion = 'v5.5.5'; Project = [string]$entry.project; Sketch = ''; Configuration = 'default'; VariantId = [string]$entry.variant_id; Variant = [string]$entry.variant; Resolution = [string]$entry.resolution; ProfileId = [string]$entry.profile_id; ArtifactKind = 'maintained-firmware' }
        $index++
    }
    $keys = @($items | ForEach-Object ArtifactKey)
    $shared = @($idf | Where-Object { $_.variant_id -eq 'shared' })
    $display = @($idf | Where-Object { $_.variant_id -in @('3_4c', '4c') })
    $usb = @($idf | Where-Object { $_.project_name -eq '12_usb_extend_screen' })
    $dualScreen = @($idf | Where-Object { $_.project_name -in @('07_Displaycolorbar', '08_lvgl_demo_v9', '09_video_lcd_display', '10_mp4_player', '11_esp_brookesia_phone') })
    if ($items.Count -ne 62 -or @($keys | Sort-Object -Unique).Count -ne 62 -or @($items | Where-Object { $_.Workflow -eq 'esp-idf-projects.yml' }).Count -ne 40 -or @($items | Where-Object { $_.Workflow -eq 'arduino-projects.yml' }).Count -ne 20 -or @($items | Where-Object { $_.Workflow -eq 'maintained-firmware.yml' }).Count -ne 2 -or $shared.Count -ne 12 -or @($shared | Where-Object { $_.configuration -ne 'default' }).Count -ne 0 -or $display.Count -ne 28 -or $dualScreen.Count -ne 20 -or $usb.Count -ne 8 -or @($usb | Where-Object { $_.configuration -notin @('default', 'vendor-only') }).Count -ne 0) { throw 'CI item matrix is not the required unique 40+20+2 XC rev3 dual-panel contract.' }
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
function Test-PortableArtifactPath([string]$PackageRoot, [string]$RelativePath) {
    if (-not (Test-SafeRelativePackagePath $PackageRoot $RelativePath)) { return $false }
    $normalized = $RelativePath.Replace('\', '/')
    if ($normalized -ne $RelativePath -or $normalized -notmatch '^[A-Za-z0-9][A-Za-z0-9._/-]*$' -or $normalized.Contains('//')) { return $false }
    foreach ($part in $normalized.Split('/')) { if ([string]::IsNullOrWhiteSpace($part) -or $part -in @('.', '..')) { return $false } }
    return $true
}
function Get-PackageRelativePath([string]$PackageRoot, [string]$Path) {
    $root = [System.IO.Path]::GetFullPath($PackageRoot).TrimEnd([System.IO.Path]::DirectorySeparatorChar, [System.IO.Path]::AltDirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar
    $full = [System.IO.Path]::GetFullPath($Path)
    if (-not $full.StartsWith($root, [System.StringComparison]::OrdinalIgnoreCase)) { throw "Package file escapes its root: $Path" }
    return $full.Substring($root.Length).Replace('\', '/')
}
function Test-ForbiddenPublishedImage([string]$RelativePath) {
    $leaf = [System.IO.Path]::GetFileName($RelativePath.Replace('/', [System.IO.Path]::DirectorySeparatorChar)).ToLowerInvariant()
    return $leaf -eq 'merged.bin' -or $leaf.EndsWith('.merged.bin') -or $leaf -in @('whole-flash.bin', 'whole_flash.bin', 'wholeflash.bin')
}
function Get-RequiredProperty($Object, [string]$Name) {
    if ($null -eq $Object -or -not $Object.PSObject.Properties[$Name]) { throw "Package metadata is missing required property: $Name" }
    return $Object.PSObject.Properties[$Name].Value
}
function Assert-ExactPropertySet($Object, [string[]]$Expected, [string]$Label) {
    if ($null -eq $Object) { throw "$Label must be an object." }
    $actual = @($Object.PSObject.Properties | ForEach-Object Name)
    if ($actual.Count -ne $Expected.Count -or @($actual | Where-Object { $_ -notin $Expected }).Count -ne 0 -or @($Expected | Where-Object { $_ -notin $actual }).Count -ne 0) { throw "$Label has missing or unexpected properties." }
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
function Get-StrictUtf8Text([string]$Path) {
    try {
        $encoding = New-Object System.Text.UTF8Encoding($false, $true)
        return [System.IO.File]::ReadAllText($Path, $encoding)
    } catch { throw "Package public text is not valid UTF-8: $Path" }
}
function Test-PackageTextPrivacy([string]$PackageDir, [string]$SourceType) {
    $publicNames = @('manifest.json', 'flash_args', 'flasher_args.json', 'SHA256SUMS', 'flash.sh', 'flash.bat')
    $publicExtensions = @('.json', '.txt', '.md', '.sh', '.bat', '.cmd', '.ps1', '.yml', '.yaml', '.csv', '.html', '.htm', '.xml', '.map')
    foreach ($file in @(Get-ChildItem -LiteralPath $PackageDir -Recurse -File -Force)) {
        Test-LeafNotLink $file.FullName
        $relative = Get-PackageRelativePath $PackageDir $file.FullName
        if (-not (Test-PortableArtifactPath $PackageDir $relative)) { throw "Package contains a non-portable path: $relative" }
        if ($file.Name -ieq 'build.options.json') { throw 'Arduino build.options.json must never be published in a package.' }
        $mustScan = $file.Name -ieq 'manifest.json'
        if ($SourceType -eq 'arduino' -and ($file.Name -iin $publicNames -or $file.Extension.ToLowerInvariant() -in $publicExtensions -or $file.Name -match '(?i)^index(?:[._-]|$)')) { $mustScan = $true }
        if (-not $mustScan) { continue }
        $text = Get-StrictUtf8Text $file.FullName
        if ($text.Contains([char]0) -or $text -match '(?i)(?:[A-Z]:[\\/]|\\\\[^\\\r\n]+[\\/]|/(?:home|tmp|Users|private/tmp|var/folders|workspace|workspaces|__w|github/workspace)(?:[\\/]|$)|(?:^|[\\/])(?:AppData|\.cache|arduino15|_work)(?:[\\/]|$))') { throw "Package public text exposes a host, user, cache, or work-directory path: $relative" }
        if ($SourceType -eq 'arduino' -and $text -match '(?i)"(?:hardwareFolders|build\.path|build\.source\.path|runtime\.platform\.path|runtime\.tools\.[^"]+)"\s*:') { throw "Arduino package exposes expanded build.options properties: $relative" }
    }
}
function Test-PackageChecksums([string]$PackageDir) {
    $sumsPath = Join-Path $PackageDir 'SHA256SUMS'
    if (-not (Test-Path -LiteralPath $sumsPath -PathType Leaf)) { throw 'Package is missing SHA256SUMS.' }
    Test-LeafNotLink $sumsPath
    $entries = @{}
    $lines = (Get-StrictUtf8Text $sumsPath) -split "`r?`n"
    for ($index = 0; $index -lt $lines.Count; $index++) {
        $line = $lines[$index]
        if ($index -eq $lines.Count - 1 -and $line -eq '') { continue }
        $match = [regex]::Match($line, '^([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._/-]*)$')
        if (-not $match.Success) { throw 'SHA256SUMS contains a malformed or unsafe entry.' }
        $relative = $match.Groups[2].Value
        $key = $relative.ToLowerInvariant()
        if (-not (Test-PortableArtifactPath $PackageDir $relative) -or $relative -ieq 'SHA256SUMS' -or $entries.ContainsKey($key)) { throw 'SHA256SUMS contains an unsafe, self-referential, or duplicate entry.' }
        $entries[$key] = [pscustomobject]@{ Path = $relative; Sha256 = $match.Groups[1].Value }
    }
    $actual = @{}
    foreach ($file in @(Get-ChildItem -LiteralPath $PackageDir -Recurse -File -Force)) {
        Test-LeafNotLink $file.FullName
        $relative = Get-PackageRelativePath $PackageDir $file.FullName
        if ($relative -ieq 'SHA256SUMS') { continue }
        $key = $relative.ToLowerInvariant()
        if (-not (Test-PortableArtifactPath $PackageDir $relative) -or $actual.ContainsKey($key)) { throw 'Package contains an unsafe or case-colliding file path.' }
        $actual[$key] = $relative
    }
    if ($entries.Count -eq 0 -or $entries.Count -ne $actual.Count) { throw 'SHA256SUMS does not cover the exact package file set.' }
    foreach ($key in $actual.Keys) {
        if (-not $entries.ContainsKey($key)) { throw 'SHA256SUMS does not cover the exact package file set.' }
        $full = Join-Path $PackageDir $actual[$key]
        if ((Get-FileSha256 $full) -cne [string]$entries[$key].Sha256) { throw "SHA256SUMS verification failed: $($actual[$key])" }
    }
    return $entries
}
function Expand-SafePackageZip([string]$ZipPath, [string]$Destination) {
    Test-LeafNotLink $ZipPath
    if (Test-Path -LiteralPath $Destination) { throw "Refusing to overwrite extraction directory: $Destination" }
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = $null
    try {
        $archive = [System.IO.Compression.ZipFile]::OpenRead($ZipPath)
        $entries = @($archive.Entries)
        if ($entries.Count -lt 1 -or $entries.Count -gt 128) { throw 'Package ZIP has an invalid entry count.' }
        $seen = @{}; [int64]$total = 0
        foreach ($entry in $entries) {
            $relative = [string]$entry.FullName
            if ([string]::IsNullOrWhiteSpace([string]$entry.Name) -or -not (Test-PortableArtifactPath $Destination $relative)) { throw 'Package ZIP contains an unsafe path or directory entry.' }
            $key = $relative.ToLowerInvariant()
            if ($seen.ContainsKey($key)) { throw 'Package ZIP contains duplicate or case-colliding paths.' }
            foreach ($existing in @($seen.Keys)) { if ($existing.StartsWith($key + '/', [System.StringComparison]::OrdinalIgnoreCase) -or $key.StartsWith($existing + '/', [System.StringComparison]::OrdinalIgnoreCase)) { throw 'Package ZIP contains a file/directory path collision.' } }
            $unixType = ([int64]$entry.ExternalAttributes -shr 16) -band 0xF000
            if ($unixType -ne 0 -and $unixType -ne 0x8000) { throw 'Package ZIP contains a link or non-regular entry.' }
            if ([int64]$entry.Length -le 0 -or [int64]$entry.Length -gt ($FlashLimit * 2)) { throw 'Package ZIP contains an empty or oversized entry.' }
            $total += [int64]$entry.Length
            if ($total -gt ($FlashLimit * 2)) { throw 'Package ZIP expands beyond the allowed size.' }
            $seen[$key] = $true
        }
        New-Item -ItemType Directory -Path $Destination | Out-Null
        foreach ($entry in $entries) {
            $target = Join-Path $Destination ([string]$entry.FullName)
            $parent = Split-Path -Parent $target
            if (-not (Test-Path -LiteralPath $parent)) { New-Item -ItemType Directory -Path $parent -Force | Out-Null }
            $input = $null; $output = $null
            try {
                $input = $entry.Open()
                $output = [System.IO.File]::Open($target, [System.IO.FileMode]::CreateNew, [System.IO.FileAccess]::Write, [System.IO.FileShare]::None)
                $input.CopyTo($output)
            } finally { if ($output) { $output.Dispose() }; if ($input) { $input.Dispose() } }
        }
    } finally { if ($archive) { $archive.Dispose() } }
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
        throw 'This XC CI catalog is rev3.x-only; pre-v3 ESP32-P4 silicon is not supported.'
    } elseif ($ProfileId -eq 'rev3_x') {
        if ($selected.Count -ne 62 -or @($selected | Where-Object { $_.ArtifactKind -eq 'ci-example' }).Count -ne 60 -or @($selected | Where-Object { $_.ArtifactKind -eq 'maintained-firmware' }).Count -ne 2) { throw 'ESP32-P4 revision >= 3.0 must select the 60 rev3_x example artifacts plus both rev3_x maintained-firmware panel variants.' }
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
function Find-PackageDirectory([string]$DownloadDir, $Item) {
    $downloadedFiles = @(Get-ChildItem -LiteralPath $DownloadDir -Recurse -File -Force)
    foreach ($file in $downloadedFiles) { Test-LeafNotLink $file.FullName }
    $zips = @($downloadedFiles | Where-Object { $_.Extension -ieq '.zip' })
    if ($Item.SourceType -eq 'arduino') {
        if ($downloadedFiles.Count -ne 1 -or $zips.Count -ne 1) { throw 'Arduino Actions artifact must contain exactly one segmented-package ZIP.' }
        $destination = Join-Path $zips[0].DirectoryName ($zips[0].BaseName + '-unzipped')
        Expand-SafePackageZip $zips[0].FullName $destination
        if (@(Get-ChildItem -LiteralPath $destination -Recurse -File -Filter '*.zip').Count -ne 0 -or -not (Test-Path -LiteralPath (Join-Path $destination 'manifest.json') -PathType Leaf)) { throw 'Arduino package ZIP must contain one flat package root and no nested ZIP.' }
        return $destination
    }
    if ($zips.Count -ne 0) { throw 'ESP-IDF Actions artifacts must not contain nested package ZIPs.' }
    $manifests = @($downloadedFiles | Where-Object { $_.Name -ieq 'manifest.json' })
    if ($manifests.Count -ne 1) { throw 'Expected exactly one manifest.json in the downloaded artifact.' }
    Test-LeafNotLink $manifests[0].FullName
    return $manifests[0].DirectoryName
}
function Test-PackageManifest([string]$PackageDir, $Item, [string]$FinalSha) {
    $manifestPath = Join-Path $PackageDir 'manifest.json'
    if (-not (Test-Path -LiteralPath $manifestPath -PathType Leaf)) { throw 'Package is missing manifest.json.' }
    Test-LeafNotLink $manifestPath
    Test-PackageTextPrivacy $PackageDir $Item.SourceType
    $checksums = Test-PackageChecksums $PackageDir
    $manifestText = Get-StrictUtf8Text $manifestPath
    try { $manifest = $manifestText | ConvertFrom-Json } catch { throw 'Package manifest is not valid JSON.' }
    if ([int]$manifest.schema -ne $ManifestSchema -or [string]$manifest.target -ne 'esp32p4' -or [string]$manifest.artifact_kind -ne $Item.ArtifactKind -or [string]$manifest.profile_id -ne $Item.ProfileId -or [string]$manifest.git_sha -cnotmatch '^[0-9a-f]{40}$' -or [string]$manifest.product_git_sha -cnotmatch '^[0-9a-f]{40}$' -or [string]$manifest.git_sha -cne $FinalSha -or [string]$manifest.product_git_sha -cne $FinalSha -or [string]$manifest.source_type -ne $Item.SourceType -or [string]$manifest.framework.name -ne $Item.FrameworkName -or [string]$manifest.framework.version -ne $Item.FrameworkVersion -or [string]$manifest.project -ne $Item.Project -or [string]$manifest.configuration -ne $Item.Configuration -or [string]$manifest.product_variant_id -ne $Item.VariantId -or [string]$manifest.product_variant -ne $Item.Variant) { throw 'Package manifest identity, target, or profile does not match the selected XC CI item and exact local HEAD.' }
    if ([int64]$manifest.flash_capacity_bytes -ne $FlashLimit -or [int64]$manifest.flash_size_bytes -ne $FlashLimit -or [string]$manifest.flash_size -ne '32MiB' -or [int64]$manifest.baud -le 0 -or @($manifest.files).Count -lt 1) { throw 'Package manifest flash metadata is incomplete or not bounded to 32 MiB.' }
    if ([string]$manifest.portable_flash_command -notmatch '(?i)^python\s+-m\s+esptool\s+--chip\s+esp32p4\b.*\bwrite[_-]flash\b' -or [string]$manifest.portable_flash_command -match '(?i)erase(?:[_-](?:flash|region))?|esp32c6') { throw 'Package manifest portable command is not a P4-only non-erase write.' }

    $argsMetadata = Get-RequiredProperty $manifest 'flash_args'
    Assert-ExactPropertySet $argsMetadata @('path', 'size', 'sha256') 'manifest.flash_args'
    $expectedArgsName = if ($Item.SourceType -eq 'arduino') { 'flash_args' } else { 'flasher_args.json' }
    if ([string]$argsMetadata.path -ne $expectedArgsName -or [string]$argsMetadata.sha256 -cnotmatch '^[0-9a-f]{64}$' -or [int64]$argsMetadata.size -le 0) { throw 'Package flash_args metadata is invalid.' }
    $argsPath = Join-Path $PackageDir $expectedArgsName
    if (-not (Test-Path -LiteralPath $argsPath -PathType Leaf)) { throw 'Package flash_args metadata names a missing file.' }
    Test-LeafNotLink $argsPath
    if ([int64](Get-Item -LiteralPath $argsPath).Length -ne [int64]$argsMetadata.size -or (Get-FileSha256 $argsPath) -cne [string]$argsMetadata.sha256) { throw 'Package flash_args metadata hash or size is inconsistent.' }

    $plan = @(); $offsets = @{}; $declaredPaths = @{}; [int64]$payloadTotal = 0; [int64]$previousOffset = -1
    foreach ($file in @($manifest.files)) {
        if ($Item.SourceType -eq 'arduino') { Assert-ExactPropertySet $file @('path', 'size', 'sha256', 'offset', 'target', 'fqbn', 'product_git_sha', 'bsp_git_sha', 'bsp_source_tree', 'bsp_component_tree', 'bsp_version', 'bsp_linked') 'Arduino segment metadata' }
        $relative = [string](Get-RequiredProperty $file 'path')
        if (-not (Test-PortableArtifactPath $PackageDir $relative) -or -not $relative.StartsWith('bin/', [System.StringComparison]::Ordinal) -or $relative -match '(?i)(^|[\/_.-])(?:esp32)?c6([\/_.-]|$)' -or $relative -match '(?i)erase(?:[_-](?:flash|region))?' -or ($Item.SourceType -eq 'arduino' -and (Test-ForbiddenPublishedImage $relative))) { throw "Manifest file path is unsafe: $relative" }
        $pathKey = $relative.ToLowerInvariant()
        if ($declaredPaths.ContainsKey($pathKey) -or [string]$file.sha256 -cnotmatch '^[0-9a-f]{64}$' -or [int64]$file.size -le 0) { throw "Manifest file metadata is unsafe: $relative" }
        $full = Join-Path $PackageDir $relative
        if (-not (Test-Path -LiteralPath $full -PathType Leaf)) { throw "Manifest file is missing: $relative" }
        Test-LeafNotLink $full
        if ((Get-FileSha256 $full) -cne [string]$file.sha256 -or [int64](Get-Item -LiteralPath $full).Length -ne [int64]$file.size) { throw "Manifest checksum or size verification failed: $relative" }
        try { [int64]$offset = $file.offset } catch { throw "Manifest flash offset is invalid: $relative" }
        if ([string]$file.offset -notmatch '^\d+$' -or $offset -lt 0 -or $offset -le $previousOffset -or $offsets.ContainsKey($offset) -or $offset -gt ($FlashLimit - [int64]$file.size)) { throw "Manifest flash range is unsafe or not strictly ordered: $relative" }
        if ([string]$file.target -ne 'esp32p4' -or [string]$file.product_git_sha -cne $FinalSha) { throw "Manifest segment product binding is inconsistent: $relative" }
        if ($Item.SourceType -eq 'arduino' -and ([string]$file.fqbn -ne $Item.Fqbn -or [string]$file.bsp_git_sha -cne $Item.BspSourceSha -or [string]$file.bsp_source_tree -cne $Item.BspSourceTree -or [string]$file.bsp_component_tree -cne $Item.BspComponentTree -or [string]$file.bsp_version -ne $Item.BspVersion -or $file.bsp_linked -isnot [bool] -or [bool]$file.bsp_linked)) { throw "Manifest Arduino segment provenance is inconsistent: $relative" }
        $offsets[$offset] = $true; $declaredPaths[$pathKey] = $true; $payloadTotal += [int64]$file.size; $previousOffset = $offset
        $plan += [pscustomobject]@{ Offset = $offset; Size = [int64]$file.size; Sha256 = [string]$file.sha256; Path = $full; Relative = $relative; Source = $relative.Substring(4) }
    }
    for ($i = 1; $i -lt $plan.Count; $i++) { if ($plan[$i - 1].Offset + $plan[$i - 1].Size -gt $plan[$i].Offset) { throw 'Package manifest contains overlapping flash ranges.' } }
    if ([int]$manifest.segment_count -ne $plan.Count -or [int64]$manifest.total_segment_bytes -ne $payloadTotal -or [int64]$manifest.segmented_payload_total -ne $payloadTotal) { throw 'Package manifest segment count or payload total is inconsistent.' }

    $options = @(Get-FlashOptions $manifest.flash_settings)
    if ($Item.SourceType -eq 'arduino') {
        $arduinoProperties = @('schema', 'artifact_kind', 'source_type', 'product_variant', 'product_variant_id', 'product_label', 'resolution', 'scope', 'framework', 'target', 'project', 'sketch', 'configuration', 'profile_id', 'profile_compatibility', 'flash_capacity_bytes', 'flash_size', 'flash_size_bytes', 'segment_count', 'total_segment_bytes', 'segmented_payload_total', 'git_sha', 'product_git_sha', 'bsp_git_sha', 'bsp_source_tree', 'bsp_component_tree', 'bsp_version', 'bsp_linked', 'bsp_relationship', 'bsp', 'baud', 'fqbn', 'flash_settings', 'flash_args', 'files', 'debug_files', 'portable_flash_command', 'build_inputs', 'build_identity')
        Assert-ExactPropertySet $manifest $arduinoProperties 'Arduino manifest'
        Assert-ExactPropertySet $manifest.framework @('name', 'version') 'Arduino framework metadata'
        Assert-ExactPropertySet $manifest.bsp @('source_sha', 'source_tree', 'component_tree', 'version', 'linked', 'relationship') 'Arduino BSP metadata'
        Assert-ExactPropertySet $manifest.flash_settings @('esptool_options') 'Arduino flash settings'
        if ([string]$manifest.product_label -ne 'ESP32-P4-WIFI6-Touch-LCD-XC' -or [string]$manifest.resolution -ne $Item.Resolution -or [string]$manifest.scope -ne 'first-party example' -or [string]$manifest.sketch -ne $Item.Sketch -or [string]$manifest.profile_compatibility -ne 'ESP32-P4 silicon revision >= 3.0') { throw 'Arduino manifest product metadata is outside the XC rev3 contract.' }
        if ([string]$manifest.fqbn -ne $Item.Fqbn -or [string]$manifest.bsp_git_sha -cne $Item.BspSourceSha -or [string]$manifest.bsp_source_tree -cne $Item.BspSourceTree -or [string]$manifest.bsp_component_tree -cne $Item.BspComponentTree -or [string]$manifest.bsp_version -ne $Item.BspVersion -or $manifest.bsp_linked -isnot [bool] -or [bool]$manifest.bsp_linked -or [string]$manifest.bsp_relationship -ne $Item.BspRelationship) { throw 'Arduino manifest direct BSP or FQBN binding is inconsistent.' }
        if ([string]$manifest.bsp.source_sha -cne $Item.BspSourceSha -or [string]$manifest.bsp.source_tree -cne $Item.BspSourceTree -or [string]$manifest.bsp.component_tree -cne $Item.BspComponentTree -or [string]$manifest.bsp.version -ne $Item.BspVersion -or $manifest.bsp.linked -isnot [bool] -or [bool]$manifest.bsp.linked -or [string]$manifest.bsp.relationship -ne $Item.BspRelationship) { throw 'Arduino manifest nested BSP binding is inconsistent.' }
        if ($manifest.PSObject.Properties['merged_image'] -or $manifest.PSObject.Properties['original_flash_args'] -or @($manifest.debug_files).Count -ne 0 -or ($plan.Count -eq 1 -and $plan[0].Offset -eq 0) -or $payloadTotal -ge ($FlashLimit / 2)) { throw 'Arduino package contains a merged/debug/whole-flash path or is not a compact segmented payload.' }
        foreach ($file in @(Get-ChildItem -LiteralPath $PackageDir -Recurse -File -Force)) { if (Test-ForbiddenPublishedImage (Get-PackageRelativePath $PackageDir $file.FullName)) { throw 'Arduino package publishes a merged or whole-flash image.' } }

        $buildInputs = Get-RequiredProperty $manifest 'build_inputs'
        Assert-ExactPropertySet $buildInputs @('build_options', 'flash_args', 'compile_commands') 'Arduino build input identities'
        foreach ($binding in @(@('build_options', 'build.options.json'), @('flash_args', 'flash_args'), @('compile_commands', 'compile_commands.json'))) {
            $identity = Get-RequiredProperty $buildInputs $binding[0]
            Assert-ExactPropertySet $identity @('basename', 'size', 'sha256') "Arduino $($binding[0]) input identity"
            if ([string]$identity.basename -ne $binding[1] -or [int64]$identity.size -le 0 -or [string]$identity.sha256 -cnotmatch '^[0-9a-f]{64}$') { throw "Arduino $($binding[0]) build input identity is invalid." }
        }

        $buildIdentity = Get-RequiredProperty $manifest 'build_identity'
        Assert-ExactPropertySet $buildIdentity @('product_git_sha', 'project', 'sketch', 'fqbn', 'screen_define', 'primary_source', 'translation_unit', 'object', 'compile_arguments_sha256', 'application') 'Arduino canonical build identity'
        $expectedScreenDefine = if ($Item.VariantId -eq '3_4c') { 'CURRENT_SCREEN=SCREEN_3INCH_4_DSI' } elseif ($Item.VariantId -eq '4c') { 'CURRENT_SCREEN=SCREEN_4INCH_DSI' } else { throw 'Arduino CI item has no supported screen compile identity.' }
        if ([string]$buildIdentity.product_git_sha -cne $FinalSha -or [string]$buildIdentity.project -ne $Item.Project -or [string]$buildIdentity.sketch -ne $Item.Sketch -or [string]$buildIdentity.fqbn -ne $Item.Fqbn -or [string]$buildIdentity.screen_define -ne $expectedScreenDefine -or [string]$buildIdentity.compile_arguments_sha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'Arduino canonical build identity does not match the selected item.' }
        $primarySource = Get-RequiredProperty $buildIdentity 'primary_source'
        Assert-ExactPropertySet $primarySource @('basename', 'size', 'sha256', 'path') 'Arduino tracked primary source identity'
        $expectedPrimaryPath = $Item.Project.TrimEnd('/') + '/' + $Item.Sketch + '.ino'
        if ([string]$primarySource.path -ne $expectedPrimaryPath -or [string]$primarySource.basename -ne ($Item.Sketch + '.ino') -or [int64]$primarySource.size -le 0 -or [string]$primarySource.sha256 -cnotmatch '^[0-9a-f]{64}$') { throw 'Arduino tracked primary source identity is invalid.' }
        foreach ($binding in @(@('translation_unit', ($Item.Sketch + '.ino.cpp')), @('object', ($Item.Sketch + '.ino.cpp.o')))) {
            $identity = Get-RequiredProperty $buildIdentity $binding[0]
            Assert-ExactPropertySet $identity @('basename', 'size', 'sha256') "Arduino $($binding[0]) identity"
            if ([string]$identity.basename -ne $binding[1] -or [int64]$identity.size -le 0 -or [string]$identity.sha256 -cnotmatch '^[0-9a-f]{64}$') { throw "Arduino $($binding[0]) identity is invalid." }
        }
        $applicationIdentity = Get-RequiredProperty $buildIdentity 'application'
        Assert-ExactPropertySet $applicationIdentity @('source_basename', 'path', 'offset', 'size', 'sha256') 'Arduino application output identity'
        $expectedApplicationName = $Item.Sketch + '.ino.bin'
        $applicationPlan = @($plan | Where-Object { $_.Source -ceq $expectedApplicationName })
        if ($applicationPlan.Count -ne 1 -or [string]$applicationIdentity.source_basename -ne $expectedApplicationName -or [string]$applicationIdentity.path -ne [string]$applicationPlan[0].Relative -or [string]$applicationIdentity.offset -notmatch '^\d+$' -or [int64]$applicationIdentity.offset -ne [int64]$applicationPlan[0].Offset -or [int64]$applicationIdentity.size -ne [int64]$applicationPlan[0].Size -or [string]$applicationIdentity.sha256 -cne [string]$applicationPlan[0].Sha256) { throw 'Arduino application output identity does not match the segmented flash plan.' }

        if ($options.Count -ne 6 -or @($options | Where-Object { $_ -eq '--flash_mode' }).Count -ne 1 -or @($options | Where-Object { $_ -eq '--flash_freq' }).Count -ne 1 -or @($options | Where-Object { $_ -eq '--flash_size' }).Count -ne 1 -or $options[$options.IndexOf('--flash_size') + 1] -ne '32MB') { throw 'Arduino flash_args must carry the complete generated mode/frequency/32 MiB option set.' }
        $flashArgTokens = @()
        for ($index = 0; $index -lt $options.Count; $index += 2) { $flashArgTokens += $options[$index].Replace('_', '-'); $flashArgTokens += $options[$index + 1] }
        foreach ($entry in $plan) { $flashArgTokens += ('0x{0:x}' -f $entry.Offset); $flashArgTokens += $entry.Source }
        $expectedFlashArgs = 'write_flash ' + ($flashArgTokens -join ' ') + "`n"
        if ((Get-StrictUtf8Text $argsPath) -cne $expectedFlashArgs) { throw 'Packaged Arduino flash_args does not exactly match manifest segments and settings.' }

        $portableFlashTokens = @()
        for ($index = 0; $index -lt $options.Count; $index += 2) { $portableFlashTokens += $options[$index].Replace('_', '-'); $portableFlashTokens += $options[$index + 1] }
        foreach ($entry in $plan) { $portableFlashTokens += ('0x{0:x}' -f $entry.Offset); $portableFlashTokens += $entry.Relative }
        $portableTokens = @('python', '-m', 'esptool', '--chip', 'esp32p4', '--port', 'PORT', '--baud', [string]$manifest.baud, 'write_flash') + $portableFlashTokens
        $expectedPortable = $portableTokens -join ' '
        if ([string]$manifest.portable_flash_command -cne $expectedPortable) { throw 'Arduino portable flash command does not exactly match the segmented plan.' }
        $expectedShell = '#!/usr/bin/env sh' + "`n" + 'set -eu' + "`n" + 'port=${1:?usage: flash.sh PORT [BAUD]}' + "`n" + 'baud=${2:-' + [string]$manifest.baud + '}' + "`n" + 'python -m esptool --chip esp32p4 --port "$port" --baud "$baud" ' + (($portableTokens[9..($portableTokens.Count - 1)]) -join ' ') + "`n"
        $expectedBatch = '@echo off' + "`r`n" + 'set PORT=%~1' + "`r`n" + 'if "%PORT%"=="" (echo Usage: flash.bat PORT [BAUD] & exit /b 2)' + "`r`n" + 'set BAUD=%~2' + "`r`n" + 'if "%BAUD%"=="" set BAUD=' + [string]$manifest.baud + "`r`n" + 'python -m esptool --chip esp32p4 --port %PORT% --baud %BAUD% ' + (($portableTokens[9..($portableTokens.Count - 1)]) -join ' ') + "`r`n"
        if ((Get-StrictUtf8Text (Join-Path $PackageDir 'flash.sh')) -cne $expectedShell -or (Get-StrictUtf8Text (Join-Path $PackageDir 'flash.bat')) -cne $expectedBatch) { throw 'Arduino flash helper script does not exactly match the segmented plan.' }

        $expectedPaths = @('manifest.json', 'flash_args', 'flash.sh', 'flash.bat', 'SHA256SUMS') + @($plan | ForEach-Object Relative)
        $actualPaths = @(Get-ChildItem -LiteralPath $PackageDir -Recurse -File -Force | ForEach-Object { Get-PackageRelativePath $PackageDir $_.FullName })
        if (@($expectedPaths | Sort-Object -Unique).Count -ne $expectedPaths.Count -or $actualPaths.Count -ne $expectedPaths.Count -or @($actualPaths | Where-Object { $_ -notin $expectedPaths }).Count -ne 0) { throw 'Arduino ZIP contains undeclared or missing package files.' }
    } elseif ($manifest.PSObject.Properties['original_flash_args']) {
        $originalArgsJson = $manifest.original_flash_args | ConvertTo-Json -Compress -Depth 20
        if ($originalArgsJson -match '(?i)erase(?:[_-](?:flash|region))?|esp32c6') { throw 'Package manifest original flash plan contains C6 or erase instructions.' }
    }
    return [pscustomobject]@{ Plan = $plan; Baud = [int]$manifest.baud; Options = $options }
}
function Invoke-CurrentFlash($Item, [string]$SelectedPort, [string]$GhExe, [string]$PythonExe, [string]$FinalSha) {
    $paths = New-RunPaths; Add-RunLog $paths.LogPath "finalSHA=$FinalSha index=$($Item.Index) artifact=$($Item.Artifact) run=$($Item.Run) port=$SelectedPort"
    $download = (& $GhExe run download $Item.Run --repo $Repo --name $Item.Artifact --dir $paths.DownloadDir 2>&1 | Out-String); $downloadExit = $LASTEXITCODE; Add-RunLog $paths.LogPath $download
    if ($downloadExit -ne 0) { throw "Artifact download failed with exit code $downloadExit. Log: $($paths.LogPath)" }
    $flash = Test-PackageManifest (Find-PackageDirectory $paths.DownloadDir $Item) $Item $FinalSha
    $flashArguments = @('-m', 'esptool', '--chip', 'esp32p4', '--port', $SelectedPort, '--baud', [string]$flash.Baud, 'write_flash') + @($flash.Options)
    foreach ($entry in $flash.Plan) { $flashArguments += ('0x{0:X}' -f $entry.Offset); $flashArguments += $entry.Path }
    $output = (& $PythonExe @flashArguments 2>&1 | Out-String); $exit = $LASTEXITCODE; Add-RunLog $paths.LogPath $output
    return [pscustomobject]@{ Success = ($exit -eq 0 -and $output.Contains('Hash of data verified')); Output = $output; LogPath = $paths.LogPath; Detail = if ($exit -eq 0 -and $output.Contains('Hash of data verified')) { 'Flash write was verified. Check the hardware before marking PASS.' } else { 'Flash did not meet the required exit-code and hash-verification condition.' } }
}

function Write-SelfTestChecksums([string]$PackageDir) {
    $lines = @()
    foreach ($file in @(Get-ChildItem -LiteralPath $PackageDir -Recurse -File -Force | Where-Object { $_.Name -ine 'SHA256SUMS' } | Sort-Object FullName)) {
        $relative = Get-PackageRelativePath $PackageDir $file.FullName
        $lines += (Get-FileSha256 $file.FullName) + '  ' + $relative
    }
    $encoding = New-Object System.Text.UTF8Encoding -ArgumentList @($false)
    [System.IO.File]::WriteAllText((Join-Path $PackageDir 'SHA256SUMS'), (($lines -join "`n") + "`n"), $encoding)
}
function New-SelfTestZip([string]$Path, $Entries) {
    Add-Type -AssemblyName System.IO.Compression.FileSystem
    $archive = $null
    try {
        $archive = [System.IO.Compression.ZipFile]::Open($Path, [System.IO.Compression.ZipArchiveMode]::Create)
        foreach ($definition in @($Entries)) {
            $entry = $archive.CreateEntry([string]$definition.Name)
            if ($definition.PSObject.Properties['ExternalAttributes']) { $entry.ExternalAttributes = [int]$definition.ExternalAttributes }
            $payload = [System.Text.Encoding]::UTF8.GetBytes([string]$definition.Content)
            $stream = $null
            try { $stream = $entry.Open(); $stream.Write($payload, 0, $payload.Length) } finally { if ($stream) { $stream.Dispose() } }
        }
    } finally { if ($archive) { $archive.Dispose() } }
}

if ($SelfTest -or $ListOnly) {
    $PythonExe = Resolve-Python; $Items = Get-CiItems $PythonExe
    if ($SelfTest) {
        $current = $DefaultStartIndex; $confirmed = @(); while ($current -lt $Items.Count) { $next = Get-NextProgress $current $confirmed $Items.Count; $current = $next.CurrentIndex; $confirmed = @($next.ConfirmedIndexes) }
        $last = Get-NextProgress $current $confirmed $Items.Count
        $testRoot = Join-Path ([System.IO.Path]::GetTempPath()) 'ci-package'
        $absoluteTestPath = Join-Path ([System.IO.Path]::GetTempPath()) 'escape.bin'
        if (-not $last.Completed -or @($last.ConfirmedIndexes).Count -ne 62 -or (Test-SafeRelativePackagePath $testRoot '..\escape.bin') -or (Test-SafeRelativePackagePath $testRoot $absoluteTestPath) -or -not (Test-SafeRelativePackagePath $testRoot 'bin\app.bin')) { throw 'SelfTest safety or progress check failed.' }
        $arduinoOptions = @(Get-FlashOptions ([pscustomobject]@{ esptool_options = @('--flash-mode', 'dio', '--flash-freq', '80m', '--flash-size', '32MB') }))
        if (($arduinoOptions -join ' ') -ne '--flash_mode dio --flash_freq 80m --flash_size 32MB') { throw 'SelfTest did not normalize Arduino hyphen flash options.' }
        try { Get-FlashOptions ([pscustomobject]@{ esptool_options = @('--before', 'default-reset') }) | Out-Null; throw 'SelfTest accepted unsafe options.' } catch { if ($_.Exception.Message -eq 'SelfTest accepted unsafe options.') { throw } }
        try { Get-FlashOptions ([pscustomobject]@{ esptool_options = @('--flash-mode', 'dio', '--flash_mode', 'qio') }) | Out-Null; throw 'SelfTest accepted duplicate flash-option aliases.' } catch { if ($_.Exception.Message -eq 'SelfTest accepted duplicate flash-option aliases.') { throw } }
        $pendingLast = Get-StateForFinalSha ([pscustomobject]@{ FinalSha = 'expected'; CurrentIndex = 62; ConfirmedIndexes = @(1..61) }) 'expected' '' 62
        $completedLast = Get-StateForFinalSha ([pscustomobject]@{ FinalSha = 'expected'; CurrentIndex = 62; ConfirmedIndexes = @(1..62) }) 'expected' '' 62
        if (@($pendingLast.ConfirmedIndexes).Count -ne 61 -or @($completedLast.ConfirmedIndexes).Count -ne 62) { throw 'SelfTest rejected a valid final-item state.' }
        try { Get-StateForFinalSha ([pscustomobject]@{ FinalSha = 'expected'; CurrentIndex = 62; ConfirmedIndexes = @(62) }) 'expected' '' 62 | Out-Null; throw 'SelfTest accepted an invalid saved state.' } catch { if ($_.Exception.Message -eq 'SelfTest accepted an invalid saved state.') { throw } }
        try { Select-CompatibleItems $Items 'rev1_3' | Out-Null; throw 'SelfTest accepted unsupported pre-v3 silicon.' } catch { if ($_.Exception.Message -eq 'SelfTest accepted unsupported pre-v3 silicon.') { throw } }
        if (@(Select-CompatibleItems $Items 'rev3_x').Count -ne 62) { throw 'SelfTest profile selection contract failed.' }
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
        if (-not (Test-PortableArtifactPath $testRoot 'bin/app.bin') -or (Test-PortableArtifactPath $testRoot 'bin\app.bin') -or -not (Test-ForbiddenPublishedImage 'bin/demo.ino.merged.bin') -or -not (Test-ForbiddenPublishedImage 'bin/whole-flash.bin') -or (Test-ForbiddenPublishedImage 'bin/demo.ino.bootloader.bin')) { throw 'SelfTest portable-path or forbidden-image contract failed.' }

        $selfTestRoot = Join-Path ([System.IO.Path]::GetTempPath()) ('xc-flasher-selftest-' + [System.Guid]::NewGuid().ToString('N'))
        New-Item -ItemType Directory -Path $selfTestRoot | Out-Null
        try {
            $build = Join-Path $selfTestRoot 'build'; $sourceRoot = Join-Path $selfTestRoot 'source'; $package = Join-Path $selfTestRoot 'package'; $packageZip = Join-Path $selfTestRoot 'package.zip'
            New-Item -ItemType Directory -Path $build | Out-Null
            $utf8NoBom = New-Object System.Text.UTF8Encoding -ArgumentList @($false)
            $arduinoItem = @($Items | Where-Object { $_.SourceType -eq 'arduino' })[0]
            $projectSource = Join-Path $sourceRoot $arduinoItem.Project
            New-Item -ItemType Directory -Path $projectSource -Force | Out-Null
            [System.IO.File]::WriteAllText((Join-Path $projectSource ($arduinoItem.Sketch + '.ino')), "void setup() {}`nvoid loop() {}`n", $utf8NoBom)
            $fixtureScriptDirectory = Join-Path $sourceRoot '.github\scripts'
            New-Item -ItemType Directory -Path $fixtureScriptDirectory -Force | Out-Null
            Copy-Item -LiteralPath (Join-Path $RepoRoot '.github\scripts\package_build_artifact.py') -Destination (Join-Path $fixtureScriptDirectory 'package_build_artifact.py')
            $GitExe = Resolve-Git
            & $GitExe -C $sourceRoot init -q
            if ($LASTEXITCODE -ne 0) { throw 'SelfTest could not initialize the source identity repository.' }
            & $GitExe -C $sourceRoot add -- .
            if ($LASTEXITCODE -ne 0) { throw 'SelfTest could not stage the source identity fixture.' }
            & $GitExe -C $sourceRoot -c 'user.name=Artifact Test' -c 'user.email=artifact-test@example.invalid' commit -q -m fixture
            if ($LASTEXITCODE -ne 0) { throw 'SelfTest could not commit the source identity fixture.' }
            $fixtureSha = (& $GitExe -C $sourceRoot rev-parse HEAD 2>&1 | Out-String).Trim().ToLowerInvariant()
            if ($fixtureSha -notmatch '^[0-9a-f]{40}$') { throw 'SelfTest source identity SHA is invalid.' }
            $segmentNames = @('demo.ino.bootloader.bin', 'demo.ino.partitions.bin', 'boot_app0.bin', 'demo.ino.bin')
            $segmentNames[0] = $arduinoItem.Sketch + '.ino.bootloader.bin'; $segmentNames[1] = $arduinoItem.Sketch + '.ino.partitions.bin'; $segmentNames[3] = $arduinoItem.Sketch + '.ino.bin'
            for ($index = 0; $index -lt $segmentNames.Count; $index++) { [System.IO.File]::WriteAllBytes((Join-Path $build $segmentNames[$index]), [byte[]](($index + 1)..($index + 16))) }
            $sourceFlashArgs = 'write_flash --flash-mode dio --flash-freq 80m --flash-size 32MB 0x0 ' + $segmentNames[0] + ' 0x8000 ' + $segmentNames[1] + ' 0xe000 boot_app0.bin 0x10000 ' + $segmentNames[3] + "`n"
            [System.IO.File]::WriteAllText((Join-Path $build 'flash_args'), $sourceFlashArgs, $utf8NoBom)
            $screenDefinition = if ($arduinoItem.VariantId -eq '3_4c') { 'CURRENT_SCREEN=SCREEN_3INCH_4_DSI' } else { 'CURRENT_SCREEN=SCREEN_4INCH_DSI' }
            $buildOptions = [pscustomobject]@{ fqbn = $arduinoItem.Fqbn; hardwareFolders = 'C:/Users/private/AppData/Local/Arduino15/packages/esp32/hardware/esp32/3.3.11'; customBuildProperties = ('compiler.cpp.extra_flags=-I' + $projectSource + ' -D' + $screenDefinition); sketchLocation = $projectSource } | ConvertTo-Json -Compress
            [System.IO.File]::WriteAllText((Join-Path $build 'build.options.json'), $buildOptions, $utf8NoBom)
            $generatedSketch = Join-Path $build 'sketch'; New-Item -ItemType Directory -Path $generatedSketch | Out-Null
            $translationUnit = Join-Path $generatedSketch ($arduinoItem.Sketch + '.ino.cpp'); $objectFile = $translationUnit + '.o'
            [System.IO.File]::WriteAllText($translationUnit, ('#include "' + $arduinoItem.Sketch + '.ino"' + "`n"), $utf8NoBom)
            [System.IO.File]::WriteAllBytes($objectFile, [byte[]](1..16))
            $compileCommands = @([pscustomobject]@{ directory = $sourceRoot; file = $translationUnit; arguments = @('g++', ('-D' + $screenDefinition), ('-DARDUINO_FQBN="' + $arduinoItem.Fqbn + '"'), '-DARDUINO_USB_MODE=1', '-DARDUINO_USB_CDC_ON_BOOT=1', ('-I' + $projectSource), '-o', $objectFile, $translationUnit) })
            [System.IO.File]::WriteAllText((Join-Path $build 'compile_commands.json'), ((ConvertTo-Json -InputObject $compileCommands -Depth 10 -Compress) + "`n"), $utf8NoBom)
            $packagerPath = Join-Path $fixtureScriptDirectory 'package_build_artifact.py'
            $packagerArguments = @($packagerPath, 'arduino', '--build-dir', $build, '--output-dir', $package, '--zip-output', $packageZip, '--product-label', 'ESP32-P4-WIFI6-Touch-LCD-XC', '--variant', $arduinoItem.Variant, '--variant-id', $arduinoItem.VariantId, '--resolution', $arduinoItem.Resolution, '--configuration', $arduinoItem.Configuration, '--framework-version', $arduinoItem.FrameworkVersion, '--target', 'esp32p4', '--project', $arduinoItem.Project, '--sketch', $arduinoItem.Sketch, '--fqbn', $arduinoItem.Fqbn, '--profile-id', $arduinoItem.ProfileId, '--git-sha', $fixtureSha, '--bsp-sha', $arduinoItem.BspSourceSha, '--bsp-source-tree', $arduinoItem.BspSourceTree, '--bsp-component-tree', $arduinoItem.BspComponentTree, '--bsp-version', $arduinoItem.BspVersion, '--build-options', (Join-Path $build 'build.options.json'), '--source-root', $sourceRoot)
            $packagerOutput = (& $PythonExe @packagerArguments 2>&1 | Out-String); $packagerExit = $LASTEXITCODE
            if ($packagerExit -ne 0) { throw "SelfTest schema-3 fixture packaging failed: $packagerOutput" }
            $validFlash = Test-PackageManifest $package $arduinoItem $fixtureSha
            if ($validFlash.Plan.Count -ne 4 -or $validFlash.Plan[0].Offset -ne 0 -or $validFlash.Plan[1].Offset -ne 0x8000) { throw 'SelfTest rejected a legal multi-segment bootloader at offset 0x0.' }

            $download = Join-Path $selfTestRoot 'download'; New-Item -ItemType Directory -Path $download | Out-Null
            Copy-Item -LiteralPath $packageZip -Destination (Join-Path $download 'segmented-package.zip')
            $zipPackage = Find-PackageDirectory $download $arduinoItem
            $zipFlash = Test-PackageManifest $zipPackage $arduinoItem $fixtureSha
            if ($zipFlash.Plan.Count -ne 4 -or $zipFlash.Plan[0].Offset -ne 0) { throw 'SelfTest ZIP round-trip changed the segmented plan.' }

            $tampered = Join-Path $selfTestRoot 'tampered-bsp'; Copy-Item -LiteralPath $package -Destination $tampered -Recurse
            $tamperedManifestPath = Join-Path $tampered 'manifest.json'
            $tamperedManifest = (Get-StrictUtf8Text $tamperedManifestPath) | ConvertFrom-Json
            $tamperedManifest.bsp.source_sha = 'ffffffffffffffffffffffffffffffffffffffff'
            [System.IO.File]::WriteAllText($tamperedManifestPath, (($tamperedManifest | ConvertTo-Json -Depth 20) + "`n"), $utf8NoBom)
            Write-SelfTestChecksums $tampered
            $acceptedTamperedBsp = $true
            try { Test-PackageManifest $tampered $arduinoItem $fixtureSha | Out-Null } catch { $acceptedTamperedBsp = $false }
            if ($acceptedTamperedBsp) { throw 'SelfTest accepted a package with a tampered BSP source SHA.' }

            $tamperedIdentity = Join-Path $selfTestRoot 'tampered-build-identity'; Copy-Item -LiteralPath $package -Destination $tamperedIdentity -Recurse
            $tamperedIdentityManifestPath = Join-Path $tamperedIdentity 'manifest.json'
            $tamperedIdentityManifest = (Get-StrictUtf8Text $tamperedIdentityManifestPath) | ConvertFrom-Json
            $tamperedIdentityManifest.build_identity.project = 'examples/arduino/examples/substitute'
            [System.IO.File]::WriteAllText($tamperedIdentityManifestPath, (($tamperedIdentityManifest | ConvertTo-Json -Depth 20) + "`n"), $utf8NoBom)
            Write-SelfTestChecksums $tamperedIdentity
            $acceptedTamperedIdentity = $true
            try { Test-PackageManifest $tamperedIdentity $arduinoItem $fixtureSha | Out-Null } catch { $acceptedTamperedIdentity = $false }
            if ($acceptedTamperedIdentity) { throw 'SelfTest accepted a package with a tampered canonical build identity.' }

            $whole = Join-Path $selfTestRoot 'whole-at-zero'; Copy-Item -LiteralPath $package -Destination $whole -Recurse
            $wholeManifestPath = Join-Path $whole 'manifest.json'; $wholeManifest = (Get-StrictUtf8Text $wholeManifestPath) | ConvertFrom-Json
            $firstSegment = @($wholeManifest.files)[0]; $wholeManifest.files = ,$firstSegment; $wholeManifest.segment_count = 1; $wholeManifest.total_segment_bytes = [int64]$firstSegment.size; $wholeManifest.segmented_payload_total = [int64]$firstSegment.size
            [System.IO.File]::WriteAllText($wholeManifestPath, (($wholeManifest | ConvertTo-Json -Depth 20) + "`n"), $utf8NoBom)
            Write-SelfTestChecksums $whole
            $acceptedWhole = $true
            try { Test-PackageManifest $whole $arduinoItem $fixtureSha | Out-Null } catch { $acceptedWhole = $false }
            if ($acceptedWhole) { throw 'SelfTest accepted a single whole-flash plan at offset 0x0.' }

            $badChecksum = Join-Path $selfTestRoot 'bad-checksum'; Copy-Item -LiteralPath $package -Destination $badChecksum -Recurse
            [System.IO.File]::AppendAllText((Join-Path $badChecksum 'flash_args'), ' ', $utf8NoBom)
            $acceptedBadChecksum = $true
            try { Test-PackageManifest $badChecksum $arduinoItem $fixtureSha | Out-Null } catch { $acceptedBadChecksum = $false }
            if ($acceptedBadChecksum) { throw 'SelfTest accepted a package whose flash_args no longer matched SHA256SUMS.' }

            $symlinkAttributes = [System.BitConverter]::ToInt32([System.BitConverter]::GetBytes([uint32]2717843456), 0)
            $unsafeZips = @(
                [pscustomobject]@{ Name = 'traversal.zip'; Entries = @([pscustomobject]@{ Name = '../escape.txt'; Content = 'x' }) },
                [pscustomobject]@{ Name = 'duplicate.zip'; Entries = @([pscustomobject]@{ Name = 'same.txt'; Content = 'x' }, [pscustomobject]@{ Name = 'same.txt'; Content = 'y' }) },
                [pscustomobject]@{ Name = 'symlink.zip'; Entries = @([pscustomobject]@{ Name = 'link'; Content = 'target'; ExternalAttributes = $symlinkAttributes }) }
            )
            foreach ($unsafe in $unsafeZips) {
                $unsafePath = Join-Path $selfTestRoot $unsafe.Name; New-SelfTestZip $unsafePath $unsafe.Entries
                $acceptedUnsafeZip = $true
                try { Expand-SafePackageZip $unsafePath (Join-Path $selfTestRoot ($unsafe.Name + '-out')) } catch { $acceptedUnsafeZip = $false }
                if ($acceptedUnsafeZip) { throw "SelfTest accepted unsafe ZIP: $($unsafe.Name)" }
            }
        } finally {
            if (Test-Path -LiteralPath $selfTestRoot) { Remove-Item -LiteralPath $selfTestRoot -Recurse -Force }
        }
        Write-Output 'SELF_TEST_OK items=62 esp_idf=40 arduino=20 maintained_firmware=2 no_network_no_serial_no_flash'
        return
    }
    Write-Output 'LIST_ONLY items=62 esp_idf=40 arduino=20 maintained_firmware=2 no_network_no_serial_no_flash'
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
