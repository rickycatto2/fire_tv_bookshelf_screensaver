param(
    [Parameter(Mandatory = $true)]
    [string]$Serial,

    [string]$ApkPath = "",

    [string]$HostName = "bookshelf.pixelwood.co",

    [switch]$SkipInstall
)

$ErrorActionPreference = "Stop"
$repoRoot = Split-Path -Parent $PSScriptRoot
$adb = Join-Path $env:ANDROID_HOME "platform-tools\adb.exe"

if (-not (Test-Path -LiteralPath $adb)) {
    throw "adb not found at $adb. Set ANDROID_HOME first."
}

if ($Serial -match ":\d+$") {
    Write-Host "Connecting to $Serial ..."
    & $adb connect $Serial | Out-Null
    Start-Sleep -Seconds 3
}

$devices = & $adb devices
if (-not ($devices -match "(?m)^$([regex]::Escape($Serial))\s+device$")) {
    throw "Device $Serial is not connected/authorized. Enable ADB debugging on the Fire TV and accept the prompt."
}

$tokenPath = Join-Path $repoRoot "data\public_token.txt"
if (-not (Test-Path -LiteralPath $tokenPath)) {
    throw "Missing $tokenPath. Start the compose service first so it can create the token."
}
$token = (Get-Content -LiteralPath $tokenPath -Raw).Trim()
if (-not $token) {
    throw "public_token.txt is empty."
}

$manifestUrl = "https://$HostName/s/$token/panorama.json"
Write-Host "Checking $manifestUrl ..."
try {
    $manifest = Invoke-WebRequest -Uri $manifestUrl -UseBasicParsing -TimeoutSec 20
    if ($manifest.StatusCode -ne 200) {
        throw "HTTP $($manifest.StatusCode)"
    }
    Write-Host "Manifest OK: $($manifest.Content.Trim())"
} catch {
    throw "The public manifest is not reachable: $($_.Exception.Message)"
}

if (-not $ApkPath) {
    $candidates = @(
        (Join-Path $repoRoot "dist\PanoramaScreensaver-1.0.0.apk"),
        (Join-Path $repoRoot "..\PanoramaScreensaver\dist\PanoramaScreensaver-1.0.0.apk"),
        (Join-Path $env:USERPROFILE "Downloads\PanoramaScreensaver-1.0.0.apk")
    )
    $ApkPath = $candidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
}
if (-not $SkipInstall) {
    if (-not $ApkPath -or -not (Test-Path -LiteralPath $ApkPath)) {
        throw "APK not found. Pass -ApkPath or place it in dist\PanoramaScreensaver-1.0.0.apk."
    }
    Write-Host "Installing $ApkPath ..."
    & $adb -s $Serial install -r $ApkPath | Out-Host
    if ($LASTEXITCODE -ne 0) {
        throw "adb install failed."
    }
}

Write-Host "Configuring the screensaver URL ..."
& $adb -s $Serial shell am force-stop com.ricky.panoramascreensaver | Out-Null
& $adb -s $Serial shell am start `
    -n com.ricky.panoramascreensaver/.SettingsActivity `
    --es image_url $manifestUrl `
    --ei refresh_seconds 300 `
    --ei pan_seconds 90 `
    --ez pan_enabled true | Out-Host

try {
    & $adb -s $Serial shell settings put secure screensaver_components `
        com.ricky.panoramascreensaver/.PanoramaDreamService | Out-Null
    Write-Host "Fire TV screensaver component set."
} catch {
    Write-Warning "Could not set screensaver_components automatically. Choose it manually in Settings."
}

Write-Host ""
Write-Host "Fire TV manifest: $manifestUrl"
Write-Host "Now choose Settings -> Display & Sounds -> Screen Saver -> Panorama Screensaver."
Write-Host "Or press Preview in the app to verify the HTTPS image first."
