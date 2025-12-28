$ErrorActionPreference = "Stop"

$version = "0.25.0"
$projectRoot = Split-Path -Parent $PSScriptRoot
$dest = Join-Path $projectRoot "public/assets/pyodide/v$version/full"
$tmpDir = Join-Path $env:TEMP "quantdinger-pyodide-$version"
$archive = Join-Path $tmpDir "pyodide-$version.tar.bz2"
$extractRoot = Join-Path $tmpDir "extract"

New-Item -ItemType Directory -Force -Path $tmpDir | Out-Null
New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null

Write-Host "Downloading Pyodide $version ..."
$url = "https://github.com/pyodide/pyodide/releases/download/$version/pyodide-$version.tar.bz2"
Invoke-WebRequest -Uri $url -OutFile $archive

Write-Host "Extracting archive ..."
if (Test-Path $extractRoot) { Remove-Item -Recurse -Force $extractRoot }
New-Item -ItemType Directory -Force -Path $extractRoot | Out-Null
tar -xjf $archive -C $extractRoot

# Try to locate a folder that contains pyodide.js
$pyodideJs = Get-ChildItem -Path $extractRoot -Recurse -File -Filter "pyodide.js" | Select-Object -First 1
if (-not $pyodideJs) {
  throw "pyodide.js not found after extraction. Please check the archive structure."
}

$sourceDir = Split-Path -Parent $pyodideJs.FullName
Write-Host "Found Pyodide files at: $sourceDir"

Write-Host "Copying to: $dest"
if (Test-Path $dest) { Remove-Item -Recurse -Force $dest }
New-Item -ItemType Directory -Force -Path $dest | Out-Null
Copy-Item -Path (Join-Path $sourceDir "*") -Destination $dest -Recurse -Force

Write-Host "Done."
Write-Host "You can now load Pyodide locally from: /assets/pyodide/v$version/full/pyodide.js"
Write-Host "Note: quantdinger_vue/.gitignore ignores /public/assets/pyodide/ by default."


