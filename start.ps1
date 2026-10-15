$ErrorActionPreference = 'Stop'
Set-Location -LiteralPath $PSScriptRoot
if (Test-Path -LiteralPath '.venv\Scripts\python.exe') { & '.\.venv\Scripts\python.exe' setup_judges.py @args }
elseif (Get-Command py -ErrorAction SilentlyContinue) { & py -3 setup_judges.py @args }
else { & python setup_judges.py @args }
exit $LASTEXITCODE
