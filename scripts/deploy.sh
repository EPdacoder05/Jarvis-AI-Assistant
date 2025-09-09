#!/bin/bash

# Jarvis AI Assistant Deployment Script
# This script deploys the complete Jarvis infrastructure to AWS

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

# Function to check if required tools are installed
check_dependencies() {
    print_status "Checking dependencies..."
    
    command -v aws >/dev/null 2>&1 || { print_error "AWS CLI is required but not installed. Aborting."; exit 1; }
    command -v zip >/dev/null 2>&1 || { print_error "zip is required but not installed. Aborting."; exit 1; }
    
    # Check AWS credentials
    aws sts get-caller-identity >/dev/null 2>&1 || { print_error "AWS credentials not configured. Run 'aws configure' first."; exit 1; }
    
    print_status "Dependencies check passed!"
}

# Function to validate parameters
validate_parameters() {
    if [ -z "$API_KEY" ]; then
        print_error "API_KEY environment variable is required"
        echo "Usage: API_KEY=your-secret-key HA_URL=https://homeassistant.local:8123 HA_TOKEN=your-token ./deploy.sh"
        exit 1
    fi
    
    if [ -z "$HA_URL" ]; then
        print_error "HA_URL environment variable is required"
        echo "Usage: API_KEY=your-secret-key HA_URL=https://homeassistant.local:8123 HA_TOKEN=your-token ./deploy.sh"
        exit 1
    fi
    
    if [ -z "$HA_TOKEN" ]; then
        print_error "HA_TOKEN environment variable is required"
        echo "Usage: API_KEY=your-secret-key HA_URL=https://homeassistant.local:8123 HA_TOKEN=your-token ./deploy.sh"
        exit 1
    fi
    
    if [ ${#API_KEY} -lt 16 ]; then
        print_error "API_KEY must be at least 16 characters long"
        exit 1
    fi
}

# Function to package Lambda functions
package_lambda() {
    local function_name=$1
    local source_dir="src/lambda/${function_name}"
    local package_dir="/tmp/${function_name}-package"
    local zip_file="/tmp/${function_name}-deployment.zip"
    
    print_status "Packaging ${function_name} Lambda function..."
    
    # Clean up previous packages
    rm -rf "$package_dir" "$zip_file"
    mkdir -p "$package_dir"
    
    # Copy source code
    cp -r "$source_dir"/* "$package_dir/"
    
    # Install dependencies if requirements.txt exists
    if [ -f "$package_dir/requirements.txt" ]; then
        print_status "Installing dependencies for ${function_name}..."
        pip install -r "$package_dir/requirements.txt" -t "$package_dir/"
    fi
    
    # Create deployment package
    cd "$package_dir"
    zip -r "$zip_file" .
    cd - > /dev/null
    
    echo "$zip_file"
}

# Function to deploy CloudFormation stack
deploy_stack() {
    print_status "Deploying CloudFormation stack..."
    
    # Package Lambda functions
    TTS_PACKAGE=$(package_lambda "tts")
    INTENT_PACKAGE=$(package_lambda "intent")
    
    # Create S3 bucket for deployment artifacts (if it doesn't exist)
    DEPLOYMENT_BUCKET="${PROJECT_NAME}-deployment-${REGION}"
    aws s3 mb "s3://${DEPLOYMENT_BUCKET}" --region "$REGION" 2>/dev/null || true
    
    # Upload Lambda packages to S3
    TTS_S3_KEY="lambda-packages/tts-$(date +%s).zip"
    INTENT_S3_KEY="lambda-packages/intent-$(date +%s).zip"
    
    aws s3 cp "$TTS_PACKAGE" "s3://${DEPLOYMENT_BUCKET}/${TTS_S3_KEY}"
    aws s3 cp "$INTENT_PACKAGE" "s3://${DEPLOYMENT_BUCKET}/${INTENT_S3_KEY}"
    
    # Deploy CloudFormation stack
    aws cloudformation deploy \
        --template-file infrastructure/cloudformation-template.yaml \
        --stack-name "$STACK_NAME" \
        --parameter-overrides \
            ProjectName="$PROJECT_NAME" \
            Environment="$ENVIRONMENT" \
            ApiKeyValue="$API_KEY" \
            HomeAssistantUrl="$HA_URL" \
            HomeAssistantToken="$HA_TOKEN" \
        --capabilities CAPABILITY_NAMED_IAM \
        --region "$REGION"
    
    # Update Lambda function code
    print_status "Updating Lambda function code..."
    
    # Get function names from stack outputs
    TTS_FUNCTION_NAME=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?OutputKey=='TTSLambdaFunctionName'].OutputValue" \
        --output text)
    
    INTENT_FUNCTION_NAME=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?OutputKey=='IntentLambdaFunctionName'].OutputValue" \
        --output text)
    
    # Update function code
    aws lambda update-function-code \
        --function-name "$TTS_FUNCTION_NAME" \
        --s3-bucket "$DEPLOYMENT_BUCKET" \
        --s3-key "$TTS_S3_KEY" \
        --region "$REGION"
    
    aws lambda update-function-code \
        --function-name "$INTENT_FUNCTION_NAME" \
        --s3-bucket "$DEPLOYMENT_BUCKET" \
        --s3-key "$INTENT_S3_KEY" \
        --region "$REGION"
    
    # Clean up temporary files
    rm -f "$TTS_PACKAGE" "$INTENT_PACKAGE"
    
    print_status "Deployment completed successfully!"
}

# Function to display deployment outputs
show_outputs() {
    print_status "Deployment outputs:"
    
    aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query "Stacks[0].Outputs" \
        --output table
    
    # Get API endpoints
    API_URL=$(aws cloudformation describe-stacks \
        --stack-name "$STACK_NAME" \
        --region "$REGION" \
        --query "Stacks[0].Outputs[?OutputKey=='ApiGatewayUrl'].OutputValue" \
        --output text)
    
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
    
    echo ""
    print_status "API Endpoints:"
    echo "  Base URL: $API_URL"
    echo "  TTS Endpoint: $SPEAK_ENDPOINT"
    echo "  Command Endpoint: $COMMAND_ENDPOINT"
    echo ""
    print_status "Next steps:"
    echo "  1. Update your Home Assistant configuration with the endpoints above"
    echo "  2. Use API Key: $API_KEY"
    echo "  3. Test the integration using the test script: ./scripts/test.sh"
}

# Main execution
main() {
    print_status "Starting Jarvis AI Assistant deployment..."
    
    check_dependencies
    validate_parameters
    deploy_stack
    show_outputs
    
    print_status "Deployment completed! 🎉"
}

# Check if script is being sourced or executed
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi