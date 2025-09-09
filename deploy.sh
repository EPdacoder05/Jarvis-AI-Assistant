#!/bin/bash
# Deploy Jarvis AI Assistant with Security Features

set -e  # Exit on any error

echo "🚀 Deploying Jarvis AI Assistant with Security Features..."

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Check prerequisites
echo "🔍 Checking prerequisites..."

if ! command -v aws &> /dev/null; then
    echo -e "${RED}❌ AWS CLI not found. Please install it first.${NC}"
    exit 1
fi

if ! command -v cdk &> /dev/null; then
    echo -e "${RED}❌ AWS CDK not found. Installing...${NC}"
    npm install -g aws-cdk
fi

if ! command -v python3 &> /dev/null; then
    echo -e "${RED}❌ Python 3 not found. Please install Python 3.11+${NC}"
    exit 1
fi

# Verify AWS credentials
echo "🔐 Verifying AWS credentials..."
if ! aws sts get-caller-identity &> /dev/null; then
    echo -e "${RED}❌ AWS credentials not configured. Run 'aws configure' first.${NC}"
    exit 1
fi

AWS_ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
AWS_REGION=$(aws configure get region)
echo -e "${GREEN}✅ AWS Account: ${AWS_ACCOUNT_ID}, Region: ${AWS_REGION}${NC}"

# Install Python dependencies
echo "📦 Installing Python dependencies..."
if [ ! -d "venv" ]; then
    python3 -m venv venv
fi
source venv/bin/activate
pip install -r requirements.txt

# Bootstrap CDK if needed
echo "🏗️ Bootstrapping CDK environment..."
cdk bootstrap aws://${AWS_ACCOUNT_ID}/${AWS_REGION}

# Synthesize the CDK app to check for errors
echo "🔧 Synthesizing CDK application..."
cdk synth

# Deploy the stack
echo "🚀 Deploying infrastructure..."
cdk deploy --require-approval never

# Get stack outputs
echo "📊 Retrieving stack outputs..."
API_URL=$(aws cloudformation describe-stacks --stack-name JarvisSecurityStack --query 'Stacks[0].Outputs[?OutputKey==`APIGatewayURL`].OutputValue' --output text)
API_KEY_ID=$(aws cloudformation describe-stacks --stack-name JarvisSecurityStack --query 'Stacks[0].Outputs[?OutputKey==`APIKeyId`].OutputValue' --output text)
USER_POOL_ID=$(aws cloudformation describe-stacks --stack-name JarvisSecurityStack --query 'Stacks[0].Outputs[?OutputKey==`UserPoolId`].OutputValue' --output text)

# Get the actual API key value
API_KEY=$(aws apigateway get-api-key --api-key ${API_KEY_ID} --include-value --query 'value' --output text)

echo -e "${GREEN}✅ Deployment completed successfully!${NC}"
echo ""
echo "🔗 API Gateway URL: ${API_URL}"
echo "🔑 API Key ID: ${API_KEY_ID}"
echo "👥 Cognito User Pool ID: ${USER_POOL_ID}"
echo ""
echo -e "${YELLOW}⚠️  IMPORTANT SECURITY SETUP:${NC}"
echo "1. Update secrets in AWS Secrets Manager:"
echo "   - jarvis/home-assistant: Add your HA URL and token"
echo "   - jarvis/external-apis: Add OpenAI, weather, and other API keys"
echo ""
echo "2. Test the deployment:"
echo "   curl \"${API_URL}/health\""
echo "   curl -X POST \"${API_URL}/chat\" -H \"X-API-Key: ${API_KEY}\" -H \"Content-Type: application/json\" -d '{\"message\": \"Hello Jarvis\"}'"
echo ""
echo "3. Monitor security:"
echo "   - Check CloudWatch logs: /aws/lambda/jarvis-ai"
echo "   - Review Security Hub findings"
echo "   - Monitor CloudWatch metrics: JarvisAI/*"
echo ""
echo -e "${GREEN}🎉 Jarvis AI Assistant is ready with enterprise security!${NC}"