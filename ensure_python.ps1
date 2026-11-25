# Finds Python, or installs the official python.org build for this tool only.
# Prints one path on stdout: python.exe or pythonw.exe. Status text goes to the console.

param(
    [ValidateSet("python", "pythonw")]
    [string]$Which = "pythonw"
)

$ErrorActionPreference = "Stop"
$ProgressPreference = "SilentlyContinue"
[Net.ServicePointManager]::SecurityProtocol = [Net.SecurityProtocolType]::Tls12

$Version = "3.13.5"

function Show($Message) {
    [Console]::Error.WriteLine($Message)
}

function Finish($Path) {
    Write-Output $Path
    exit 0
}

function Python-Works($PythonExe) {
    if (-not (Test-Path -LiteralPath $PythonExe)) {
        return $false
    }
    & $PythonExe -c "import tkinter" 2>$null
    return $LASTEXITCODE -eq 0
}

function Wanted-Exe($Directory) {
    $name = if ($Which -eq "pythonw") { "pythonw.exe" } else { "python.exe" }
    return Join-Path $Directory $name
}

$py = Get-Command py -ErrorAction SilentlyContinue
if ($py) {
    $printed = & $py.Source -3 -c "import tkinter,sys; print(sys.executable)" 2>$null
    if ($LASTEXITCODE -eq 0 -and $printed) {
        $installDir = Split-Path -Parent ($printed | Select-Object -Last 1).Trim()
        $wanted = Wanted-Exe $installDir
        if (Test-Path -LiteralPath $wanted) {
            Finish $wanted
        }
    }
}

$arch = $env:PROCESSOR_ARCHITEW6432
if (-not $arch) { $arch = $env:PROCESSOR_ARCHITECTURE }
$fileName = switch ($arch) {
    "ARM64" { "python-$Version-arm64.exe" }
    "x86" { "python-$Version.exe" }
    default { "python-$Version-amd64.exe" }
}
$tag = switch ($arch) {
    "ARM64" { "arm64" }
    "x86" { "win32" }
    default { "amd64" }
}

$target = Join-Path $env:LOCALAPPDATA "synthetik-save-editor\python-$Version-$tag"
$wanted = Wanted-Exe $target
if (Python-Works (Join-Path $target "python.exe")) {
    Finish $wanted
}

Show "Python was not found."
Show "Downloading Python $Version from python.org."
Show "The installer is the official one. It installs only for this tool, into:"
Show $target

$cache = Join-Path $env:LOCALAPPDATA "synthetik-save-editor\cache"
New-Item -ItemType Directory -Force -Path $cache | Out-Null
$installer = Join-Path $cache $fileName
$url = "https://www.python.org/ftp/python/$Version/$fileName"
Invoke-WebRequest -Uri $url -OutFile $installer -UseBasicParsing

Show "Starting the Python installer. You can leave the progress window alone until it closes."
$installArgs = @(
    "/passive",
    "InstallAllUsers=0",
    "PrependPath=0",
    "Include_launcher=0",
    "Include_test=0",
    "Include_doc=0",
    "Include_pip=1",
    "Include_tcltk=1",
    "Shortcuts=0",
    "AssociateFiles=0",
    "CompileAll=0",
    "TargetDir=$target"
)
$proc = Start-Process -FilePath $installer -ArgumentList $installArgs -Wait -PassThru
if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010) {
    Show "The Python installer stopped with exit code $($proc.ExitCode)."
    exit 1
}
if (-not (Python-Works (Join-Path $target "python.exe"))) {
    Show "The installer finished, but Python in $target cannot run this tool."
    exit 1
}
Finish $wanted
