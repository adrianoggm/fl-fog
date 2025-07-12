#!/usr/bin/env pwsh
<#
.SYNOPSIS
    Local CI test script for FL-Fog (PowerShell)

.DESCRIPTION
    Runs the same quality checks and tests that run in CI/CD pipeline.
    Useful for local development and pre-commit validation.

.PARAMETER SkipTests
    Skip running tests (useful for quick quality checks)

.PARAMETER SkipDocs
    Skip building documentation

.PARAMETER SkipSecurity
    Skip security scans

.EXAMPLE
    .\test_ci_local.ps1
    .\test_ci_local.ps1 -SkipTests
#>

param(
    [switch]$SkipTests,
    [switch]$SkipDocs,
    [switch]$SkipSecurity
)

# Colors for output
$Red = "`e[31m"
$Green = "`e[32m"
$Yellow = "`e[33m"
$Blue = "`e[34m"
$Reset = "`e[0m"

function Write-Status {
    param($Message, $Color = $Blue)
    Write-Host "${Color}[FL-Fog CI]${Reset} $Message"
}

function Write-Success {
    param($Message)
    Write-Host "${Green}✓${Reset} $Message"
}

function Write-Error {
    param($Message)
    Write-Host "${Red}✗${Reset} $Message"
}

function Write-Warning {
    param($Message)
    Write-Host "${Yellow}⚠${Reset} $Message"
}

# Start CI process
Write-Status "Starting FL-Fog local CI pipeline..."

# Check if we're in the right directory
if (!(Test-Path "fog_node") -or !(Test-Path "requirements.txt")) {
    Write-Error "Please run this script from the fl-fog directory"
    exit 1
}

# Check Python version
$pythonVersion = python --version 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Error "Python not found. Please install Python 3.8+"
    exit 1
}

Write-Status "Using $pythonVersion"

# Install dependencies
Write-Status "Installing dependencies..."
python -m pip install --upgrade pip | Out-Null
if (Test-Path "requirements.txt") {
    pip install -r requirements.txt | Out-Null
}
pip install -e .[dev] | Out-Null

if ($LASTEXITCODE -ne 0) {
    Write-Error "Failed to install dependencies"
    exit 1
}
Write-Success "Dependencies installed"

# 1. Code Formatting
Write-Status "Checking code formatting..."

# Black
Write-Status "Running Black formatter check..."
black --check --diff .
if ($LASTEXITCODE -eq 0) {
    Write-Success "Black formatting check passed"
} else {
    Write-Error "Black formatting check failed. Run 'black .' to fix"
    $hasErrors = $true
}

# isort
Write-Status "Running isort import sorting check..."
isort --check-only --diff .
if ($LASTEXITCODE -eq 0) {
    Write-Success "isort check passed"
} else {
    Write-Error "isort check failed. Run 'isort .' to fix"
    $hasErrors = $true
}

# 2. Linting
Write-Status "Running linting checks..."

# flake8
Write-Status "Running flake8 linter..."
flake8 fog_node communication tests
if ($LASTEXITCODE -eq 0) {
    Write-Success "flake8 linting passed"
} else {
    Write-Error "flake8 linting failed"
    $hasErrors = $true
}

# mypy
Write-Status "Running mypy type checking..."
mypy fog_node communication
if ($LASTEXITCODE -eq 0) {
    Write-Success "mypy type checking passed"
} else {
    Write-Warning "mypy type checking had issues (not blocking)"
}

# 3. Security Checks
if (!$SkipSecurity) {
    Write-Status "Running security checks..."
    
    # bandit
    Write-Status "Running bandit security scan..."
    bandit -r fog_node communication
    if ($LASTEXITCODE -eq 0) {
        Write-Success "bandit security scan passed"
    } else {
        Write-Warning "bandit found potential security issues (not blocking)"
    }
    
    # safety
    Write-Status "Running safety dependency check..."
    safety check
    if ($LASTEXITCODE -eq 0) {
        Write-Success "safety dependency check passed"
    } else {
        Write-Warning "safety found vulnerable dependencies (not blocking)"
    }
}

# 4. Tests
if (!$SkipTests) {
    Write-Status "Running tests..."
    
    # Unit tests
    Write-Status "Running unit tests..."
    if (Test-Path "tests/unit") {
        pytest tests/unit -v --cov=fog_node --cov=communication --cov-report=term-missing
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Unit tests passed"
        } else {
            Write-Error "Unit tests failed"
            $hasErrors = $true
        }
    } else {
        Write-Warning "No unit tests found (tests/unit directory missing)"
    }
    
    # Integration tests (if available)
    if (Test-Path "tests/integration") {
        Write-Status "Running integration tests..."
        pytest tests/integration -v
        if ($LASTEXITCODE -eq 0) {
            Write-Success "Integration tests passed"
        } else {
            Write-Warning "Integration tests failed (might need external services)"
        }
    }
}

# 5. Documentation
if (!$SkipDocs) {
    Write-Status "Building documentation..."
    if (Test-Path "docs") {
        Push-Location docs
        try {
            if (Test-Path "make.bat") {
                .\make.bat html
            } else {
                sphinx-build -b html . _build/html
            }
            if ($LASTEXITCODE -eq 0) {
                Write-Success "Documentation built successfully"
            } else {
                Write-Warning "Documentation build had issues (not blocking)"
            }
        } finally {
            Pop-Location
        }
    } else {
        Write-Warning "No docs directory found"
    }
}

# 6. Package Building
Write-Status "Testing package build..."
python -m build
if ($LASTEXITCODE -eq 0) {
    Write-Success "Package build successful"
    
    # Check package
    twine check dist/*
    if ($LASTEXITCODE -eq 0) {
        Write-Success "Package validation passed"
    } else {
        Write-Warning "Package validation had issues"
    }
} else {
    Write-Error "Package build failed"
    $hasErrors = $true
}

# Summary
Write-Status "CI pipeline completed"

if ($hasErrors) {
    Write-Error "CI pipeline failed with errors"
    exit 1
} else {
    Write-Success "All checks passed! ✨"
    Write-Status "Your code is ready for CI/CD pipeline"
}
