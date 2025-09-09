# Jarvis AI Assistant - Deployment Guide

## Prerequisites

Before deploying Jarvis AI Assistant, ensure you have:

1. **AWS Account** with appropriate permissions
2. **AWS CLI** configured with credentials
3. **Home Assistant** instance running
4. **Python 3.8+** for local development and testing

### Required AWS Permissions

Your AWS user/role needs permissions for:
- CloudFormation (full access)
- Lambda (full access)
- API Gateway (full access)
- S3 (full access)
- IAM (create/update roles and policies)
- Secrets Manager (full access)
- Amazon Polly (synthesize speech)

## Step 1: Prepare Home Assistant

1. **Generate Long-lived Access Token**:
   - Go to Home Assistant → Profile → Long-lived Access Tokens
   - Click "Create Token"
   - Give it a name (e.g., "Jarvis AI Assistant")
   - Copy the token (you'll need it during deployment)

2. **Note your Home Assistant URL**:
   - Should be accessible from the internet or your VPC
   - Example: `https://homeassistant.local:8123` or `https://your-domain.duckdns.org:8123`

## Step 2: Generate API Key

Generate a secure API key for protecting your endpoints:

```bash
# Generate a random 32-character API key
openssl rand -hex 32

# Or use Python
python3 -c "import secrets; print(secrets.token_hex(32))"
```

## Step 3: Deploy Infrastructure

```bash
# Clone the repository
git clone https://github.com/EPdacoder05/Jarvis-AI-Assistant
cd Jarvis-AI-Assistant

# Deploy with your credentials
API_KEY=your-generated-api-key \
HA_URL=https://homeassistant.local:8123 \
HA_TOKEN=your-long-lived-token \
./scripts/deploy.sh
```

### Deployment Options

You can customize the deployment by setting environment variables:

```bash
# Custom environment and region
export AWS_REGION=us-west-2
export ENVIRONMENT=production
export PROJECT_NAME=my-jarvis

API_KEY=your-api-key \
HA_URL=your-ha-url \
HA_TOKEN=your-ha-token \
./scripts/deploy.sh
```

## Step 4: Configure Home Assistant

1. **Add REST Commands**:
   Copy the configuration from `homeassistant/configuration.yaml` to your Home Assistant configuration file.

2. **Update Endpoints**:
   Replace `YOUR_API_GATEWAY_URL` and `YOUR_API_KEY` with the values from the deployment output.

3. **Restart Home Assistant**:
   ```bash
   # From Home Assistant
   Developer Tools → Services → homeassistant.restart
   ```

## Step 5: Test the Integration

```bash
# Run the test suite
API_KEY=your-api-key ./scripts/test.sh
```

### Manual Testing

Test the endpoints directly:

```bash
# Test TTS endpoint
curl -X POST "https://your-api-gateway-url/speak" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "text": "Hello! This is Jarvis speaking.",
    "voice": "Joanna",
    "format": "mp3"
  }'

# Test Command endpoint
curl -X POST "https://your-api-gateway-url/command" \
  -H "Content-Type: application/json" \
  -H "X-API-Key: your-api-key" \
  -d '{
    "command": "turn on the living room lights"
  }'
```

## Step 6: Voice Integration

### Option A: Google Assistant (via IFTTT)

1. Create IFTTT applet:
   - Trigger: Google Assistant "Say a phrase"
   - Action: Webhooks
   - URL: `https://your-homeassistant-url/api/webhook/google_assistant_jarvis`
   - Method: POST
   - Content-Type: `application/json`
   - Body: `{"command": "{{TextField}}"}`

2. Add webhook automation to Home Assistant:
   ```yaml
   automation:
     - alias: "Google Assistant to Jarvis"
       trigger:
         - platform: webhook
           webhook_id: google_assistant_jarvis
       action:
         - service: script.jarvis_process_command
           data:
             command: "{{ trigger.data.command }}"
   ```

### Option B: Amazon Alexa

1. Create Alexa Skill
2. Configure skill to call your API Gateway endpoints
3. Handle intents in your skill Lambda function

### Option C: Local Speech-to-Text

Integrate with local STT services like:
- Rhasspy
- Mozilla DeepSpeech
- OpenAI Whisper

## Troubleshooting

### Common Issues

1. **CloudFormation Stack Creation Failed**:
   - Check AWS permissions
   - Verify parameter values (API key length, HA URL format)
   - Check CloudFormation console for detailed error messages

2. **Lambda Function Errors**:
   - Check CloudWatch logs: `/aws/lambda/jarvis-ai-assistant-tts-dev`
   - Verify environment variables are set correctly
   - Test Lambda functions individually in AWS console

3. **API Gateway 401 Errors**:
   - Verify X-API-Key header is being sent
   - Check API key matches deployment parameter
   - Ensure header name is exactly "X-API-Key" (case-sensitive)

4. **Home Assistant Connection Issues**:
   - Verify HA URL is accessible from Lambda (internet connectivity)
   - Check long-lived token is valid and has necessary permissions
   - Test HA API manually: `curl -H "Authorization: Bearer TOKEN" HA_URL/api/states`

5. **Audio Files Not Playing**:
   - Check S3 bucket permissions
   - Verify presigned URLs are not expired
   - Test audio URLs directly in browser

### Debugging Commands

```bash
# Check CloudFormation stack status
aws cloudformation describe-stacks --stack-name jarvis-ai-assistant-dev

# View Lambda logs
aws logs tail /aws/lambda/jarvis-ai-assistant-tts-dev --follow

# Test S3 bucket access
aws s3 ls s3://jarvis-ai-assistant-audio-dev-ACCOUNT-ID

# Check Secrets Manager
aws secretsmanager get-secret-value --secret-id jarvis-ai-assistant/homeassistant/dev
```

## Security Considerations

1. **API Key Management**:
   - Use strong, randomly generated API keys
   - Rotate keys regularly
   - Never commit keys to source control

2. **Home Assistant Security**:
   - Use HTTPS for Home Assistant
   - Use strong, unique long-lived tokens
   - Limit token permissions if possible

3. **AWS Security**:
   - Use least-privilege IAM policies
   - Enable CloudTrail logging
   - Monitor API Gateway and Lambda metrics

4. **Network Security**:
   - Consider VPC endpoints for Lambda
   - Use security groups and NACLs appropriately
   - Enable AWS WAF for API Gateway if needed

## Performance Optimization

1. **Lambda Optimization**:
   - Increase memory allocation if needed
   - Use Lambda layers for common dependencies
   - Implement connection pooling for HA API calls

2. **S3 Optimization**:
   - Use appropriate storage class
   - Implement lifecycle policies for old audio files
   - Consider CloudFront distribution for global access

3. **API Gateway Optimization**:
   - Enable caching for appropriate responses
   - Use request/response compression
   - Implement throttling and usage plans

## Cost Management

- **Lambda**: ~$0.20 per million requests + compute time
- **API Gateway**: ~$3.50 per million requests
- **S3**: ~$0.023 per GB stored + requests
- **Polly**: ~$4.00 per million characters
- **Secrets Manager**: ~$0.40 per secret per month

Expected monthly cost for moderate usage (1000 voice commands): **$5-15**

## Monitoring and Alerts

Set up CloudWatch alarms for:
- Lambda function errors
- API Gateway 4xx/5xx errors
- S3 storage usage
- Estimated charges

```bash
# Example: Create error rate alarm
aws cloudwatch put-metric-alarm \
  --alarm-name "Jarvis-Lambda-Errors" \
  --alarm-description "Alert on Lambda errors" \
  --metric-name Errors \
  --namespace AWS/Lambda \
  --statistic Sum \
  --period 300 \
  --threshold 5 \
  --comparison-operator GreaterThanThreshold \
  --dimensions Name=FunctionName,Value=jarvis-ai-assistant-tts-dev
```