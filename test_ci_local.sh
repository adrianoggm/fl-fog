#!/bin/bash
# Local CI test script for FL-Fog (Bash)
# Runs the same quality checks and tests that run in CI/CD pipeline

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Command line options
SKIP_TESTS=false
SKIP_DOCS=false
SKIP_SECURITY=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-tests)
            SKIP_TESTS=true
            shift
            ;;
        --skip-docs)
            SKIP_DOCS=true
            shift
            ;;
        --skip-security)
            SKIP_SECURITY=true
            shift
            ;;
        -h|--help)
            echo "Usage: $0 [--skip-tests] [--skip-docs] [--skip-security]"
            echo "  --skip-tests      Skip running tests"
            echo "  --skip-docs       Skip building documentation"
            echo "  --skip-security   Skip security scans"
            exit 0
            ;;
        *)
            echo "Unknown option $1"
            exit 1
            ;;
    esac
done

function print_status() {
    echo -e "${BLUE}[FL-Fog CI]${NC} $1"
}

function print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

function print_error() {
    echo -e "${RED}✗${NC} $1"
}

function print_warning() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# Start CI process
print_status "Starting FL-Fog local CI pipeline..."

# Check if we're in the right directory
if [[ ! -d "fog_node" ]] || [[ ! -f "requirements.txt" ]]; then
    print_error "Please run this script from the fl-fog directory"
    exit 1
fi

# Check Python version
if ! command -v python3 &> /dev/null; then
    print_error "Python 3 not found. Please install Python 3.8+"
    exit 1
fi

PYTHON_VERSION=$(python3 --version)
print_status "Using $PYTHON_VERSION"

# Install dependencies
print_status "Installing dependencies..."
python3 -m pip install --upgrade pip > /dev/null
if [[ -f "requirements.txt" ]]; then
    pip install -r requirements.txt > /dev/null
fi
pip install -e .[dev] > /dev/null

print_success "Dependencies installed"

# Track if we have any errors
HAS_ERRORS=false

# 1. Code Formatting
print_status "Checking code formatting..."

# Black
print_status "Running Black formatter check..."
if black --check --diff .; then
    print_success "Black formatting check passed"
else
    print_error "Black formatting check failed. Run 'black .' to fix"
    HAS_ERRORS=true
fi

# isort
print_status "Running isort import sorting check..."
if isort --check-only --diff .; then
    print_success "isort check passed"
else
    print_error "isort check failed. Run 'isort .' to fix"
    HAS_ERRORS=true
fi

# 2. Linting
print_status "Running linting checks..."

# flake8
print_status "Running flake8 linter..."
if flake8 fog_node communication tests; then
    print_success "flake8 linting passed"
else
    print_error "flake8 linting failed"
    HAS_ERRORS=true
fi

# mypy
print_status "Running mypy type checking..."
if mypy fog_node communication; then
    print_success "mypy type checking passed"
else
    print_warning "mypy type checking had issues (not blocking)"
fi

# 3. Security Checks
if [[ "$SKIP_SECURITY" != true ]]; then
    print_status "Running security checks..."
    
    # bandit
    print_status "Running bandit security scan..."
    if bandit -r fog_node communication; then
        print_success "bandit security scan passed"
    else
        print_warning "bandit found potential security issues (not blocking)"
    fi
    
    # safety
    print_status "Running safety dependency check..."
    if safety check; then
        print_success "safety dependency check passed"
    else
        print_warning "safety found vulnerable dependencies (not blocking)"
    fi
fi

# 4. Tests
if [[ "$SKIP_TESTS" != true ]]; then
    print_status "Running tests..."
    
    # Unit tests
    print_status "Running unit tests..."
    if [[ -d "tests/unit" ]]; then
        if pytest tests/unit -v --cov=fog_node --cov=communication --cov-report=term-missing; then
            print_success "Unit tests passed"
        else
            print_error "Unit tests failed"
            HAS_ERRORS=true
        fi
    else
        print_warning "No unit tests found (tests/unit directory missing)"
    fi
    
    # Integration tests (if available)
    if [[ -d "tests/integration" ]]; then
        print_status "Running integration tests..."
        if pytest tests/integration -v; then
            print_success "Integration tests passed"
        else
            print_warning "Integration tests failed (might need external services)"
        fi
    fi
fi

# 5. Documentation
if [[ "$SKIP_DOCS" != true ]]; then
    print_status "Building documentation..."
    if [[ -d "docs" ]]; then
        cd docs
        if [[ -f "Makefile" ]]; then
            if make html; then
                print_success "Documentation built successfully"
            else
                print_warning "Documentation build had issues (not blocking)"
            fi
        else
            if sphinx-build -b html . _build/html; then
                print_success "Documentation built successfully"
            else
                print_warning "Documentation build had issues (not blocking)"
            fi
        fi
        cd ..
    else
        print_warning "No docs directory found"
    fi
fi

# 6. Package Building
print_status "Testing package build..."
if python3 -m build; then
    print_success "Package build successful"
    
    # Check package
    if twine check dist/*; then
        print_success "Package validation passed"
    else
        print_warning "Package validation had issues"
    fi
else
    print_error "Package build failed"
    HAS_ERRORS=true
fi

# Summary
print_status "CI pipeline completed"

if [[ "$HAS_ERRORS" == true ]]; then
    print_error "CI pipeline failed with errors"
    exit 1
else
    print_success "All checks passed! ✨"
    print_status "Your code is ready for CI/CD pipeline"
fi
