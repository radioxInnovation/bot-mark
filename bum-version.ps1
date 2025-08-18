#!/usr/bin/env pwsh
# PowerShell script to bump version in setup.py and create git tag
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [string]$Version
)

# Check if version argument is provided
if (-not $Version) {
    Write-Error "Error: Version number argument is required."
    exit 1
}

Write-Host "Bumping version to $Version"

# Update version in setup.py using Python
$pythonScript = @"
import re, pathlib, sys
p = pathlib.Path("setup.py")
s = p.read_text(encoding="utf-8")
s = re.sub(r'version\s*=\s*([\'"])[0-9][^\'"]*\1', f'version="{sys.argv[1]}"', s, count=1)
p.write_text(s, encoding="utf-8")
"@

# Execute Python script
python -c $pythonScript $Version

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to update version in setup.py"
    exit 1
}

# Git operations
try {
    Write-Host "Adding setup.py to git..."
    git add setup.py
    if ($LASTEXITCODE -ne 0) { throw "Failed to add setup.py" }

    Write-Host "Committing changes..."
    git commit -m "Bump version to $Version"
    if ($LASTEXITCODE -ne 0) { throw "Failed to commit changes" }

    Write-Host "Creating git tag..."
    git tag "$Version"
    if ($LASTEXITCODE -ne 0) { throw "Failed to create tag" }

    Write-Host "Pushing to origin..."
    git push origin HEAD
    if ($LASTEXITCODE -ne 0) { throw "Failed to push commit" }

    Write-Host "Pushing tag to origin..."
    git push origin "$Version"
    if ($LASTEXITCODE -ne 0) { throw "Failed to push tag" }

    Write-Host "Successfully bumped version to $Version and pushed to origin" -ForegroundColor Green
}
catch {
    Write-Error "Git operation failed: $_"
    exit 1
}
