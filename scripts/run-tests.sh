#!/bin/bash

# Test runner script for Jarvis AI Assistant
# Runs all unit tests and generates coverage report

set -e

# Configuration
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
TESTS_DIR="$PROJECT_ROOT/tests"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Function to check dependencies
check_dependencies() {
    print_status "Checking test dependencies..."
    
    # Check if Python is available
    command -v python3 >/dev/null 2>&1 || { print_error "Python 3 is required but not installed. Aborting."; exit 1; }
    
    # Check if pip is available
    command -v pip3 >/dev/null 2>&1 || { print_error "pip3 is required but not installed. Aborting."; exit 1; }
    
    print_status "Dependencies check passed!"
}

# Function to install test dependencies
install_test_deps() {
    print_status "Installing test dependencies..."
    
    # Install required packages for testing
    pip3 install --user pytest pytest-cov boto3 requests
    
    print_status "Test dependencies installed!"
}

# Function to run unit tests
run_unit_tests() {
    print_status "Running unit tests..."
    
    cd "$PROJECT_ROOT"
    
    # Set PYTHONPATH to include source directories
    export PYTHONPATH="$PROJECT_ROOT/src/lambda/tts:$PROJECT_ROOT/src/lambda/intent:$PYTHONPATH"
    
    # Run tests with pytest
    if command -v pytest >/dev/null 2>&1; then
        pytest "$TESTS_DIR" -v --tb=short
    else
        # Fallback to unittest if pytest is not available
        python3 -m unittest discover "$TESTS_DIR" -v
    fi
    
    test_exit_code=$?
    
    if [ $test_exit_code -eq 0 ]; then
        print_status "✅ All unit tests passed!"
    else
        print_error "❌ Some unit tests failed!"
        return $test_exit_code
    fi
}

# Function to run coverage analysis
run_coverage() {
    print_status "Running coverage analysis..."
    
    cd "$PROJECT_ROOT"
    
    # Set PYTHONPATH
    export PYTHONPATH="$PROJECT_ROOT/src/lambda/tts:$PROJECT_ROOT/src/lambda/intent:$PYTHONPATH"
    
    if command -v pytest >/dev/null 2>&1; then
        # Run with coverage
        pytest "$TESTS_DIR" --cov=lambda_function --cov-report=term-missing --cov-report=html
        
        print_status "Coverage report generated in htmlcov/"
    else
        print_warning "pytest-cov not available, skipping coverage analysis"
    fi
}

# Function to lint Python code
lint_code() {
    print_status "Linting Python code..."
    
    # Check if pylint or flake8 is available
    if command -v flake8 >/dev/null 2>&1; then
        print_status "Running flake8..."
        flake8 "$PROJECT_ROOT/src/lambda" --max-line-length=100 --ignore=E501,W503 || true
    elif command -v pylint >/dev/null 2>&1; then
        print_status "Running pylint..."
        pylint "$PROJECT_ROOT/src/lambda"/*/*.py || true
    else
        print_warning "No linter available (install flake8 or pylint for code quality checks)"
    fi
}

# Function to validate CloudFormation template
validate_cloudformation() {
    print_status "Validating CloudFormation template..."
    
    if command -v aws >/dev/null 2>&1; then
        aws cloudformation validate-template \
            --template-body file://"$PROJECT_ROOT/infrastructure/cloudformation-template.yaml" \
            >/dev/null 2>&1
        
        if [ $? -eq 0 ]; then
            print_status "✅ CloudFormation template is valid!"
        else
            print_error "❌ CloudFormation template validation failed!"
            return 1
        fi
    else
        print_warning "AWS CLI not available, skipping CloudFormation validation"
    fi
}

# Function to test lambda package creation
test_lambda_packaging() {
    print_status "Testing Lambda package creation..."
    
    # Test TTS Lambda packaging
    TTS_TEST_DIR="/tmp/test-tts-package"
    rm -rf "$TTS_TEST_DIR"
    mkdir -p "$TTS_TEST_DIR"
    
    cp -r "$PROJECT_ROOT/src/lambda/tts"/* "$TTS_TEST_DIR/"
    
    if [ -f "$TTS_TEST_DIR/requirements.txt" ]; then
        # Try to install dependencies
        pip3 install -r "$TTS_TEST_DIR/requirements.txt" -t "$TTS_TEST_DIR/" >/dev/null 2>&1 || true
    fi
    
    # Check if lambda_function.py is present and importable
    cd "$TTS_TEST_DIR"
    python3 -c "import lambda_function; print('TTS Lambda module imports successfully')" 2>/dev/null
    tts_result=$?
    
    # Test Intent Lambda packaging
    INTENT_TEST_DIR="/tmp/test-intent-package"
    rm -rf "$INTENT_TEST_DIR"
    mkdir -p "$INTENT_TEST_DIR"
    
    cp -r "$PROJECT_ROOT/src/lambda/intent"/* "$INTENT_TEST_DIR/"
    
    if [ -f "$INTENT_TEST_DIR/requirements.txt" ]; then
        pip3 install -r "$INTENT_TEST_DIR/requirements.txt" -t "$INTENT_TEST_DIR/" >/dev/null 2>&1 || true
    fi
    
    cd "$INTENT_TEST_DIR"
    python3 -c "import lambda_function; print('Intent Lambda module imports successfully')" 2>/dev/null
    intent_result=$?
    
    # Clean up
    rm -rf "$TTS_TEST_DIR" "$INTENT_TEST_DIR"
    cd "$PROJECT_ROOT"
    
    if [ $tts_result -eq 0 ] && [ $intent_result -eq 0 ]; then
        print_status "✅ Lambda packaging test passed!"
    else
        print_error "❌ Lambda packaging test failed!"
        return 1
    fi
}

# Function to run integration tests (mock)
run_integration_tests() {
    print_status "Running integration tests..."
    
    # Mock integration test - check if endpoints would be accessible
    # This would normally test against deployed infrastructure
    
    print_status "✅ Integration tests completed (mocked)"
    print_warning "Run './scripts/test.sh' against deployed infrastructure for real integration tests"
}

# Function to generate test report
generate_report() {
    print_status "Generating test report..."
    
    cat > "/tmp/jarvis-test-report.txt" << EOF
Jarvis AI Assistant - Test Report
Generated: $(date)
================================

Test Results:
- Unit Tests: $([ $UNIT_TEST_RESULT -eq 0 ] && echo "PASSED" || echo "FAILED")
- CloudFormation Validation: $([ $CF_VALIDATION_RESULT -eq 0 ] && echo "PASSED" || echo "FAILED")
- Lambda Packaging: $([ $PACKAGING_TEST_RESULT -eq 0 ] && echo "PASSED" || echo "FAILED")
- Integration Tests: PASSED (mocked)

Project Structure:
- TTS Lambda: src/lambda/tts/
- Intent Lambda: src/lambda/intent/
- Infrastructure: infrastructure/
- Home Assistant Config: homeassistant/
- Tests: tests/

Next Steps:
1. Deploy infrastructure: ./scripts/deploy.sh
2. Run integration tests: ./scripts/test.sh
3. Configure Home Assistant with provided templates

EOF

    print_status "Test report saved to /tmp/jarvis-test-report.txt"
}

# Main execution
main() {
    print_status "Starting Jarvis AI Assistant test suite..."
    
    check_dependencies
    install_test_deps
    
    # Run all tests and capture results
    UNIT_TEST_RESULT=0
    CF_VALIDATION_RESULT=0
    PACKAGING_TEST_RESULT=0
    
    run_unit_tests || UNIT_TEST_RESULT=$?
    echo ""
    
    run_coverage || true
    echo ""
    
    lint_code || true
    echo ""
    
    validate_cloudformation || CF_VALIDATION_RESULT=$?
    echo ""
    
    test_lambda_packaging || PACKAGING_TEST_RESULT=$?
    echo ""
    
    run_integration_tests || true
    echo ""
    
    generate_report
    
    # Calculate overall result
    OVERALL_RESULT=0
    if [ $UNIT_TEST_RESULT -ne 0 ] || [ $CF_VALIDATION_RESULT -ne 0 ] || [ $PACKAGING_TEST_RESULT -ne 0 ]; then
        OVERALL_RESULT=1
    fi
    
    if [ $OVERALL_RESULT -eq 0 ]; then
        print_status "🎉 All tests passed! Ready for deployment."
    else
        print_error "❌ Some tests failed. Please fix issues before deployment."
    fi
    
    return $OVERALL_RESULT
}

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi