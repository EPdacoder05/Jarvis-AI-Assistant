# Jarvis AI Assistant - Secure Voice & Home Automation Assistant

A secure, enterprise-grade AI assistant built on AWS with comprehensive security features, Home Assistant integration, and robust logging capabilities.

## 🔐 Security Architecture

This implementation follows security-first principles with comprehensive protection at every layer:

### Security Features
- **🔑 Secrets Management**: All API keys and tokens stored in AWS Secrets Manager
- **🛡️ API Security**: API Gateway with API Key authentication + optional Cognito integration
- **📊 Comprehensive Logging**: All commands and access attempts logged to CloudWatch and Security Hub
- **🔍 Threat Detection**: Real-time security monitoring with automated threat detection
- **🚫 Input Validation**: Comprehensive input sanitization and abuse detection
- **⚡ Rate Limiting**: API throttling and usage quotas to prevent abuse

### Security Boundaries

#### Layer 1: API Gateway Security
- **API Key Authentication**: Required for all endpoints except health checks
- **Cognito User Pools**: Optional additional authentication layer
- **Rate Limiting**: 50 requests/second, 100 burst, 10k daily quota
- **CORS Protection**: Restricted origins and headers
- **Request Validation**: JSON schema validation and parameter checking

#### Layer 2: Lambda Function Security  
- **IAM Least Privilege**: Minimal required permissions only
- **Secrets Manager Integration**: No hardcoded credentials
- **Input Sanitization**: Comprehensive validation against injection attacks
- **Session Management**: UUID-based session tracking with limits
- **Error Handling**: Secure error responses without information leakage

#### Layer 3: Infrastructure Security
- **VPC Isolation**: Lambda functions in private VPC (optional)
- **Encryption**: All data encrypted in transit and at rest
- **CloudTrail Logging**: All API calls logged
- **Security Hub Integration**: Centralized security findings
- **CloudWatch Monitoring**: Real-time metrics and alarms

#### Layer 4: Data Security
- **Secrets Rotation**: Automated secret rotation capabilities
- **Audit Logging**: Comprehensive audit trail of all operations
- **Data Classification**: Sensitive data properly tagged and protected
- **Compliance**: NIST Cybersecurity Framework alignment

## 🏠 Home Assistant Integration

Secure integration with Home Assistant for smart home control:

### Supported Commands
- **Lighting Control**: Turn lights on/off, adjust brightness
- **Climate Control**: Temperature adjustment, HVAC control  
- **Device Status**: Real-time device state monitoring
- **Security Systems**: Lock/unlock, alarm control
- **Automation**: Trigger scenes and automations

### Security Features
- **Token Security**: HA long-lived tokens stored in Secrets Manager
- **API Validation**: All HA API calls validated and logged
- **Command Auditing**: Every home control command logged with context
- **Rate Limiting**: Per-session command limits to prevent abuse

## 🚀 Quick Start

### Prerequisites
- AWS CLI configured with appropriate permissions
- Node.js 18+ and Python 3.11+
- AWS CDK v2 installed (`npm install -g aws-cdk`)

### 1. Deploy Infrastructure
```bash
# Install dependencies
pip install -r requirements.txt
npm install -g aws-cdk

# Bootstrap CDK (first time only)
cdk bootstrap

# Deploy the stack
cdk deploy
```

### 2. Configure Secrets
After deployment, update the secrets in AWS Secrets Manager:

```bash
# Configure Home Assistant
aws secretsmanager update-secret \
  --secret-id jarvis/home-assistant \
  --secret-string '{"ha_url":"https://your-ha-instance.com","ha_token":"your-long-lived-token"}'

# Configure External APIs  
aws secretsmanager update-secret \
  --secret-id jarvis/external-apis \
  --secret-string '{"openai_api_key":"sk-...","weather_api_key":"...","spotify_api_key":"..."}'
```

### 3. Test the API
```bash
# Get API details from CDK output
export API_URL=$(aws cloudformation describe-stacks --stack-name JarvisSecurityStack --query 'Stacks[0].Outputs[?OutputKey==`APIGatewayURL`].OutputValue' --output text)
export API_KEY=$(aws apigateway get-api-key --api-key $(aws cloudformation describe-stacks --stack-name JarvisSecurityStack --query 'Stacks[0].Outputs[?OutputKey==`APIKeyId`].OutputValue' --output text) --include-value --query 'value' --output text)

# Test health endpoint
curl "$API_URL/health"

# Test chat endpoint (requires API key)
curl -X POST "$API_URL/chat" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello Jarvis, what can you do?"}'

# Test Home Assistant command
curl -X POST "$API_URL/command" \
  -H "X-API-Key: $API_KEY" \
  -H "Content-Type: application/json" \
  -d '{"type": "home_assistant", "action": "turn_on", "target": "light.living_room"}'
```

## 📡 API Reference

### Authentication
All endpoints (except `/health`) require an API key in the `X-API-Key` header.

Optional endpoints also support Cognito JWT tokens in the `Authorization` header.

### Endpoints

#### `GET /health`
Health check endpoint (no authentication required)

#### `POST /chat`
Chat with Jarvis AI assistant
- **Authentication**: API Key required
- **Body**: `{"message": "your message here"}`
- **Response**: `{"success": true, "message": "AI response", "session_id": "uuid"}`

#### `POST /command` 
Execute Home Assistant commands
- **Authentication**: API Key + optional Cognito
- **Body**: `{"type": "home_assistant", "action": "turn_on", "target": "light.bedroom"}`
- **Response**: `{"success": true, "action": "turn_on", "target": "light.bedroom"}`

### Command Types

#### Home Assistant Commands
```json
{
  "type": "home_assistant",
  "action": "turn_on|turn_off|toggle|set_brightness|set_temperature|get_state",
  "target": "entity_id",
  "brightness": 255,  // for set_brightness
  "temperature": 20   // for set_temperature  
}
```

## 🔍 Monitoring & Logging

### CloudWatch Metrics
- `JarvisAI/Security/*`: Security events and authentication
- `JarvisAI/Commands/*`: Command execution metrics
- `JarvisAI/SecurityHub/*`: Security Hub findings

### CloudWatch Logs
- `/aws/apigateway/jarvis-ai`: API Gateway access logs
- `/aws/lambda/jarvis-ai`: Lambda function logs
- `/aws/lambda/jarvis-command-processor`: Command processing logs

### Security Hub Findings
All security events create findings in AWS Security Hub:
- Authentication failures
- Suspicious input patterns
- Rate limiting violations
- Configuration errors
- Secret access events

### Log Analysis Queries

```sql
-- Failed authentication attempts
fields @timestamp, event_type, message, context.source_ip
| filter event_type = "AUTHENTICATION_FAILURE"
| sort @timestamp desc

-- Command usage patterns
fields @timestamp, event_type, context.action, context.target
| filter event_type = "HA_COMMAND_SUCCESS"
| stats count() by context.action
```

## 🛠️ Development

### Local Development
```bash
# Install development dependencies
pip install -r requirements.txt
pip install pytest pytest-cov black flake8

# Run tests
pytest tests/ -v --cov=src

# Format code
black src/ tests/
flake8 src/ tests/
```

### Adding New Features
1. Update the CDK stack in `infrastructure/jarvis_stack.py`
2. Implement Lambda functions in `src/`
3. Add comprehensive logging and security validation
4. Update this README with security implications
5. Add tests in `tests/`

## 🔒 Security Best Practices

### For Operators
1. **Rotate Secrets Regularly**: Update API keys and tokens monthly
2. **Monitor CloudWatch**: Set up alarms for suspicious activity
3. **Review Security Hub**: Investigate all HIGH/CRITICAL findings
4. **Limit API Keys**: Create separate keys for different clients
5. **Enable VPC**: Deploy Lambda functions in private VPC for production

### For Developers  
1. **Never Hardcode Secrets**: Always use Secrets Manager
2. **Validate All Input**: Sanitize and validate every user input
3. **Log Security Events**: Log all authentication and authorization events
4. **Follow Least Privilege**: Request minimal IAM permissions
5. **Handle Errors Securely**: Don't leak sensitive information in errors

## 📋 Compliance

This implementation aligns with:
- **NIST Cybersecurity Framework**: Identity management, access control, monitoring
- **AWS Well-Architected Security Pillar**: Defense in depth, least privilege
- **SOC 2 Type II**: Audit logging, access controls, encryption
- **GDPR**: Data protection, privacy by design

## 📞 Support

### Security Issues
Report security vulnerabilities privately via GitHub Security Advisories.

### General Support  
- Create GitHub issues for bugs and feature requests
- Check CloudWatch logs for troubleshooting
- Review Security Hub findings for security events

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

---

**⚠️ Security Notice**: This is a production-ready security implementation. Always review and customize security settings for your specific environment and compliance requirements.