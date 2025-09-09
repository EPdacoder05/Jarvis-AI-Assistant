#!/bin/bash

# Jarvis AI Assistant Test Script
# This script tests the deployed Jarvis API endpoints

set -e

# Configuration
PROJECT_NAME="jarvis-ai-assistant"
ENVIRONMENT="dev"
REGION="us-east-1"
STACK_NAME="${PROJECT_NAME}-${ENVIRONMENT}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_test() {
    echo -e "${BLUE}[TEST]${NC} $1"
}

# Function to get stack outputs
get_stack_outputs() {
    print_status "Getting deployment information..."
    
    # Check if stack exists
    aws cloudformation describe-stacks --stack-name "$STACK_NAME" --region "$REGION" >/dev/null 2>&1 || {
        print_error "Stack '$STACK_NAME' not found. Please deploy first using ./scripts/deploy.sh"
        exit 1
    }
    
    # Get API endpoints
    SPEAK_ENDPOINT=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?OutputKey=='SpeakEndpoint'].OutputValue" \
        --output text)
    
    COMMAND_ENDPOINT=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?OutputKey=='CommandEndpoint'].OutputValue" \
        --output text)
    
    if [ -z "$SPEAK_ENDPOINT" ] || [ -z "$COMMAND_ENDPOINT" ]; then
        print_error "Could not retrieve API endpoints from CloudFormation stack"
        exit 1
    fi
    
    print_status "API Endpoints retrieved:"
    echo "  TTS Endpoint: $SPEAK_ENDPOINT"
    echo "  Command Endpoint: $COMMAND_ENDPOINT"
}

# Function to test TTS endpoint
test_tts_endpoint() {
    print_test "Testing TTS endpoint..."
    
    if [ -z "$API_KEY" ]; then
        print_error "API_KEY environment variable is required for testing"
        return 1
    fi
    
    # Test with valid request
    print_status "Testing valid TTS request..."
    response=$(curl -s -w "%{http_code}" -o /tmp/tts_response.json \
        -X POST "$SPEAK_ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $API_KEY" \
        -d '{
            "text": "Hello! This is a test of the Jarvis text-to-speech system.",
            "voice": "Joanna",
            "format": "mp3"
        }')
    
    http_code="${response: -3}"
    
    if [ "$http_code" -eq 200 ]; then
        print_status "✅ TTS endpoint test passed!"
        audio_url=$(cat /tmp/tts_response.json | python3 -c "import sys, json; print(json.load(sys.stdin)['audio_url'])" 2>/dev/null || echo "N/A")
        echo "   Audio URL: $audio_url"
    else
        print_error "❌ TTS endpoint test failed (HTTP $http_code)"
        cat /tmp/tts_response.json
        return 1
    fi
    
    # Test with invalid API key
    print_status "Testing invalid API key..."
    response=$(curl -s -w "%{http_code}" -o /tmp/tts_error.json \
        -X POST "$SPEAK_ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: invalid-key" \
        -d '{"text": "This should fail"}')
    
    http_code="${response: -3}"
    
    if [ "$http_code" -eq 401 ]; then
        print_status "✅ API key validation test passed!"
    else
        print_warning "⚠️  API key validation test unexpected result (HTTP $http_code)"
    fi
    
    # Test with missing text
    print_status "Testing missing text parameter..."
    response=$(curl -s -w "%{http_code}" -o /tmp/tts_error2.json \
        -X POST "$SPEAK_ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $API_KEY" \
        -d '{}')
    
    http_code="${response: -3}"
    
    if [ "$http_code" -eq 400 ]; then
        print_status "✅ Input validation test passed!"
    else
        print_warning "⚠️  Input validation test unexpected result (HTTP $http_code)"
    fi
}

# Function to test Intent endpoint
test_intent_endpoint() {
    print_test "Testing Intent endpoint..."
    
    if [ -z "$API_KEY" ]; then
        print_error "API_KEY environment variable is required for testing"
        return 1
    fi
    
    # Test with valid command
    print_status "Testing valid intent request..."
    response=$(curl -s -w "%{http_code}" -o /tmp/intent_response.json \
        -X POST "$COMMAND_ENDPOINT" \
        -H "Content-Type: application/json" \
        -H "X-API-Key: $API_KEY" \
        -d '{
            "command": "turn on the living room lights"
        }')
    
    http_code="${response: -3}"
    
    if [ "$http_code" -eq 200 ]; then
        print_status "✅ Intent endpoint test passed!"
        intent=$(cat /tmp/intent_response.json | python3 -c "import sys, json; print(json.load(sys.stdin)['intent'])" 2>/dev/null || echo "N/A")
        echo "   Detected intent: $intent"
    else
        print_error "❌ Intent endpoint test failed (HTTP $http_code)"
        cat /tmp/intent_response.json
        return 1
    fi
    
    # Test multiple command types
    commands=(
        "turn off all lights"
        "set temperature to 72 degrees"
        "play some music"
        "what's the weather like"
        "activate movie night scene"
        "lock the front door"
    )
    
    print_status "Testing various command types..."
    for cmd in "${commands[@]}"; do
        response=$(curl -s -w "%{http_code}" -o /tmp/intent_test.json \
            -X POST "$COMMAND_ENDPOINT" \
            -H "Content-Type: application/json" \
            -H "X-API-Key: $API_KEY" \
            -d "{\"command\": \"$cmd\"}")
        
        http_code="${response: -3}"
        
        if [ "$http_code" -eq 200 ]; then
            intent=$(cat /tmp/intent_test.json | python3 -c "import sys, json; print(json.load(sys.stdin)['intent'])" 2>/dev/null || echo "unknown")
            echo "   '$cmd' → $intent ✅"
        else
            echo "   '$cmd' → Failed (HTTP $http_code) ❌"
        fi
    done
}

# Function to test CORS
test_cors() {
    print_test "Testing CORS configuration..."
    
    # Test OPTIONS request
    response=$(curl -s -w "%{http_code}" -o /tmp/cors_response.txt \
        -X OPTIONS "$SPEAK_ENDPOINT" \
        -H "Origin: https://example.com" \
        -H "Access-Control-Request-Method: POST" \
        -H "Access-Control-Request-Headers: Content-Type,X-API-Key")
    
    http_code="${response: -3}"
    
    if [ "$http_code" -eq 200 ]; then
        print_status "✅ CORS preflight test passed!"
    else
        print_warning "⚠️  CORS preflight test failed (HTTP $http_code)"
    fi
}

# Function to run performance test
test_performance() {
    print_test "Running basic performance test..."
    
    if [ -z "$API_KEY" ]; then
        print_warning "Skipping performance test - API_KEY not provided"
        return 0
    fi
    
    print_status "Testing TTS response time (5 requests)..."
    
    total_time=0
    successful_requests=0
    
    for i in {1..5}; do
        start_time=$(date +%s.%N)
        
        response=$(curl -s -w "%{http_code}" -o /dev/null \
            -X POST "$SPEAK_ENDPOINT" \
            -H "Content-Type: application/json" \
            -H "X-API-Key: $API_KEY" \
            -d "{\"text\": \"Performance test message number $i\"}")
        
        end_time=$(date +%s.%N)
        http_code="${response: -3}"
        
        if [ "$http_code" -eq 200 ]; then
            request_time=$(echo "$end_time - $start_time" | bc -l 2>/dev/null || echo "0")
            total_time=$(echo "$total_time + $request_time" | bc -l 2>/dev/null || echo "$total_time")
            successful_requests=$((successful_requests + 1))
            echo "   Request $i: ${request_time}s ✅"
        else
            echo "   Request $i: Failed (HTTP $http_code) ❌"
        fi
    done
    
    if [ "$successful_requests" -gt 0 ]; then
        avg_time=$(echo "scale=3; $total_time / $successful_requests" | bc -l 2>/dev/null || echo "N/A")
        print_status "Average response time: ${avg_time}s ($successful_requests/$i successful)"
    fi
}

# Function to clean up test files
cleanup() {
    rm -f /tmp/tts_response.json /tmp/tts_error.json /tmp/tts_error2.json
    rm -f /tmp/intent_response.json /tmp/intent_test.json
    rm -f /tmp/cors_response.txt
}

# Function to display test results summary
show_summary() {
    echo ""
    echo "=================================="
    print_status "Test Summary"
    echo "=================================="
    echo "TTS Endpoint: $SPEAK_ENDPOINT"
    echo "Command Endpoint: $COMMAND_ENDPOINT"
    echo ""
    echo "Tests completed! Check the results above."
    echo ""
    print_status "Next steps:"
    echo "  1. If tests passed, integrate with Home Assistant"
    echo "  2. Configure your voice assistant to use these endpoints"
    echo "  3. Test with real voice commands"
    echo ""
    print_status "Example curl commands:"
    echo "  # Test TTS:"
    echo "  curl -X POST \"$SPEAK_ENDPOINT\" \\"
    echo "    -H \"Content-Type: application/json\" \\"
    echo "    -H \"X-API-Key: \$API_KEY\" \\"
    echo "    -d '{\"text\": \"Hello World\", \"voice\": \"Joanna\"}'"
    echo ""
    echo "  # Test Command:"
    echo "  curl -X POST \"$COMMAND_ENDPOINT\" \\"
    echo "    -H \"Content-Type: application/json\" \\"
    echo "    -H \"X-API-Key: \$API_KEY\" \\"
    echo "    -d '{\"command\": \"turn on the lights\"}'"
}

# Main execution
main() {
    print_status "Starting Jarvis AI Assistant API tests..."
    
    # Trap to ensure cleanup
    trap cleanup EXIT
    
    get_stack_outputs
    
    echo ""
    test_tts_endpoint
    echo ""
    test_intent_endpoint
    echo ""
    test_cors
    echo ""
    test_performance
    
    show_summary
    
    print_status "Testing completed! 🎉"
}

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi