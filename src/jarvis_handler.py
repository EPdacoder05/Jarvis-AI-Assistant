"""
Jarvis AI Assistant Lambda Handler
Secure implementation with Secrets Manager integration and comprehensive logging.
"""

import json
import os
import logging
import boto3
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError


# Configure structured logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# AWS clients - lazy loaded to avoid region issues during import
secrets_client = None
securityhub_client = None
cloudwatch_client = None

def get_aws_clients():
    """Lazy load AWS clients to avoid region issues during import."""
    global secrets_client, securityhub_client, cloudwatch_client
    if secrets_client is None:
        secrets_client = boto3.client('secretsmanager')
        securityhub_client = boto3.client('securityhub')
        cloudwatch_client = boto3.client('cloudwatch')
    return secrets_client, securityhub_client, cloudwatch_client


class SecureJarvisAssistant:
    """
    Secure Jarvis AI Assistant with comprehensive security and logging.
    
    Security Features:
    - All secrets retrieved from AWS Secrets Manager
    - Comprehensive audit logging of all operations
    - Security Hub integration for security events
    - Input validation and sanitization
    """
    
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.secrets_cache = {}
        self.security_hub_enabled = os.getenv('SECURITY_HUB_ENABLED', 'false').lower() == 'true'
        
        # Log initialization with security context
        self._log_security_event(
            "SERVICE_INITIALIZED",
            "Jarvis AI Assistant service initialized",
            {"session_id": self.session_id}
        )
    
    def get_secret(self, secret_arn: str, cache_key: str) -> Dict[str, Any]:
        """
        Securely retrieve secrets from AWS Secrets Manager with caching.
        
        Args:
            secret_arn: ARN of the secret in Secrets Manager
            cache_key: Cache key for the secret
            
        Returns:
            Dict containing the secret values
            
        Raises:
            Exception: If secret retrieval fails
        """
        if cache_key in self.secrets_cache:
            logger.info(f"Retrieved secret from cache: {cache_key}")
            return self.secrets_cache[cache_key]
        
        try:
            secrets_client, _, _ = get_aws_clients()
            logger.info(f"Retrieving secret from Secrets Manager: {secret_arn}")
            response = secrets_client.get_secret_value(SecretId=secret_arn)
            secret_data = json.loads(response['SecretString'])
            
            # Cache the secret for this session
            self.secrets_cache[cache_key] = secret_data
            
            # Log successful secret retrieval (without secret values)
            self._log_security_event(
                "SECRET_ACCESSED",
                f"Successfully retrieved secret: {cache_key}",
                {
                    "secret_arn": secret_arn,
                    "session_id": self.session_id,
                    "timestamp": datetime.now(timezone.utc).isoformat()
                }
            )
            
            return secret_data
            
        except ClientError as e:
            error_msg = f"Failed to retrieve secret {cache_key}: {str(e)}"
            logger.error(error_msg)
            
            # Log failed secret access as security event
            self._log_security_event(
                "SECRET_ACCESS_FAILED",
                error_msg,
                {
                    "secret_arn": secret_arn,
                    "error_code": e.response['Error']['Code'],
                    "session_id": self.session_id
                },
                severity="HIGH"
            )
            
            raise Exception(error_msg)
    
    def _log_security_event(self, event_type: str, message: str, context: Dict[str, Any], severity: str = "INFO"):
        """
        Log security events to CloudWatch and optionally Security Hub.
        
        Args:
            event_type: Type of security event
            message: Human-readable message
            context: Additional context data
            severity: Severity level (INFO, MEDIUM, HIGH, CRITICAL)
        """
        # Structured log entry
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "message": message,
            "severity": severity,
            "session_id": self.session_id,
            "service": "jarvis-ai-assistant",
            **context
        }
        
        # Log to CloudWatch
        logger.info(json.dumps(log_entry))
        
        # Send custom metric to CloudWatch
        try:
            _, _, cloudwatch_client = get_aws_clients()
            cloudwatch_client.put_metric_data(
                Namespace='JarvisAI/Security',
                MetricData=[
                    {
                        'MetricName': f'SecurityEvent_{event_type}',
                        'Value': 1,
                        'Unit': 'Count',
                        'Dimensions': [
                            {'Name': 'Severity', 'Value': severity},
                            {'Name': 'EventType', 'Value': event_type}
                        ]
                    }
                ]
            )
        except Exception as e:
            logger.error(f"Failed to send CloudWatch metric: {str(e)}")
        
        # Send to Security Hub if enabled and severity is HIGH or CRITICAL
        if self.security_hub_enabled and severity in ['HIGH', 'CRITICAL']:
            self._send_security_hub_finding(event_type, message, context, severity)
    
    def _send_security_hub_finding(self, event_type: str, message: str, context: Dict[str, Any], severity: str):
        """Send security finding to AWS Security Hub."""
        try:
            _, securityhub_client, _ = get_aws_clients()
            finding = {
                'SchemaVersion': '2018-10-08',
                'Id': f"jarvis-ai-{event_type}-{self.session_id}",
                'ProductArn': f"arn:aws:securityhub:{os.getenv('AWS_REGION', 'us-east-1')}:{context.get('account_id', '000000000000')}:product/jarvis-ai/security-events",
                'GeneratorId': 'jarvis-ai-assistant',
                'AwsAccountId': context.get('account_id', '000000000000'),
                'Types': ['Sensitive Data Identifications/PII'],
                'CreatedAt': datetime.now(timezone.utc).isoformat(),
                'UpdatedAt': datetime.now(timezone.utc).isoformat(),
                'Severity': {
                    'Label': severity
                },
                'Title': f'Jarvis AI Security Event: {event_type}',
                'Description': message,
                'Resources': [
                    {
                        'Type': 'AwsLambdaFunction',
                        'Id': f"arn:aws:lambda:{os.getenv('AWS_REGION', 'us-east-1')}:{context.get('account_id', '000000000000')}:function:jarvis-ai",
                        'Region': os.getenv('AWS_REGION', 'us-east-1')
                    }
                ]
            }
            
            securityhub_client.batch_import_findings(Findings=[finding])
            logger.info(f"Security Hub finding created for {event_type}")
            
        except Exception as e:
            logger.error(f"Failed to send Security Hub finding: {str(e)}")
    
    def validate_input(self, user_input: str) -> bool:
        """
        Validate and sanitize user input for security.
        
        Args:
            user_input: User-provided input string
            
        Returns:
            bool: True if input is valid, False otherwise
        """
        if not user_input or len(user_input.strip()) == 0:
            return False
        
        # Check for suspicious patterns
        suspicious_patterns = [
            'eval(', 'exec(', 'import os', 'subprocess', '__import__',
            'rm -rf', 'del /f', 'format c:', 'DROP TABLE', 'DELETE FROM',
            'drop table', 'delete from', 'insert into', 'update set'
        ]
        
        user_input_lower = user_input.lower()
        for pattern in suspicious_patterns:
            if pattern in user_input_lower:
                self._log_security_event(
                    "SUSPICIOUS_INPUT_DETECTED",
                    f"Potentially malicious input detected: {pattern}",
                    {"input_sample": user_input[:100], "pattern": pattern},
                    severity="HIGH"
                )
                return False
        
        # Length check
        if len(user_input) > 5000:
            self._log_security_event(
                "INPUT_TOO_LONG",
                f"Input exceeds maximum length: {len(user_input)} characters",
                {"input_length": len(user_input)},
                severity="MEDIUM"
            )
            return False
        
        return True
    
    def process_command(self, command: str, context: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process user command with comprehensive logging and security.
        
        Args:
            command: User command to process
            context: Request context (user info, IP, etc.)
            
        Returns:
            Dict containing the response
        """
        # Log command attempt
        self._log_security_event(
            "COMMAND_RECEIVED",
            f"Processing user command",
            {
                "command_type": "chat_command",
                "user_ip": context.get('sourceIp', 'unknown'),
                "user_agent": context.get('userAgent', 'unknown'),
                "command_length": len(command)
            }
        )
        
        # Validate input
        if not self.validate_input(command):
            response = {
                "success": False,
                "message": "Invalid input detected. Please check your command and try again.",
                "error_code": "INVALID_INPUT"
            }
            
            self._log_security_event(
                "COMMAND_REJECTED",
                "Command rejected due to invalid input",
                {"rejection_reason": "input_validation_failed"},
                severity="MEDIUM"
            )
            
            return response
        
        try:
            # Get Home Assistant secrets if needed
            ha_secrets = self.get_secret(
                os.getenv('HA_SECRETS_ARN'),
                'home_assistant'
            )
            
            # Get external API secrets if needed
            api_secrets = self.get_secret(
                os.getenv('API_SECRETS_ARN'),
                'external_apis'
            )
            
            # Process the command (placeholder for actual AI logic)
            response_message = self._generate_response(command, ha_secrets, api_secrets)
            
            response = {
                "success": True,
                "message": response_message,
                "session_id": self.session_id,
                "timestamp": datetime.now(timezone.utc).isoformat()
            }
            
            # Log successful command processing
            self._log_security_event(
                "COMMAND_PROCESSED",
                "Command processed successfully",
                {
                    "command_length": len(command),
                    "response_length": len(response_message),
                    "processing_time": "calculated_in_production"
                }
            )
            
            return response
            
        except Exception as e:
            error_msg = f"Error processing command: {str(e)}"
            logger.error(error_msg)
            
            # Log processing error
            self._log_security_event(
                "COMMAND_ERROR",
                error_msg,
                {"error_type": type(e).__name__},
                severity="HIGH"
            )
            
            return {
                "success": False,
                "message": "I'm experiencing some technical difficulties. Please try again later.",
                "error_code": "PROCESSING_ERROR",
                "session_id": self.session_id
            }
    
    def _generate_response(self, command: str, ha_secrets: Dict, api_secrets: Dict) -> str:
        """
        Generate AI response using available APIs and Home Assistant integration.
        
        This is a placeholder for actual AI implementation.
        In production, this would integrate with OpenAI, Home Assistant, etc.
        """
        command_lower = command.lower()
        
        # Home Assistant commands
        if any(keyword in command_lower for keyword in ['lights', 'temperature', 'home', 'house']):
            ha_url = ha_secrets.get('ha_url', '')
            if ha_url:
                return f"I can help you control your home! I'm connected to your Home Assistant at {ha_url[:20]}... How can I assist you?"
            else:
                return "I can help with home automation, but I need your Home Assistant configuration first."
        
        # Weather commands
        elif any(keyword in command_lower for keyword in ['weather', 'temperature', 'forecast']):
            weather_key = api_secrets.get('weather_api_key', '')
            if weather_key:
                return "Let me check the weather for you! (Weather API integration would go here)"
            else:
                return "I'd love to help with weather, but I need a weather API key configured first."
        
        # Music commands
        elif any(keyword in command_lower for keyword in ['music', 'play', 'song', 'spotify']):
            spotify_key = api_secrets.get('spotify_api_key', '')
            if spotify_key:
                return "I can help you with music! What would you like to listen to?"
            else:
                return "I can help with music once Spotify integration is configured."
        
        # General AI chat
        else:
            openai_key = api_secrets.get('openai_api_key', '')
            if openai_key:
                return f"I understand you're asking: '{command}'. I'm your AI assistant and I'm here to help! (OpenAI integration would provide a more intelligent response here)"
            else:
                return f"I heard you say: '{command}'. I'm your AI assistant! While I don't have full AI capabilities configured yet, I'm here to help with home automation and basic tasks."


def lambda_handler(event, context):
    """
    AWS Lambda handler for Jarvis AI Assistant.
    
    Handles API Gateway requests with comprehensive security and logging.
    """
    try:
        # Initialize Jarvis assistant
        jarvis = SecureJarvisAssistant()
        
        # Extract request information
        request_context = {
            'requestId': context.aws_request_id,
            'sourceIp': event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown'),
            'userAgent': event.get('requestContext', {}).get('identity', {}).get('userAgent', 'unknown'),
            'apiId': event.get('requestContext', {}).get('apiId', 'unknown'),
            'stage': event.get('requestContext', {}).get('stage', 'unknown')
        }
        
        # Log API access
        jarvis._log_security_event(
            "API_ACCESS",
            "API Gateway request received",
            {
                "request_id": context.aws_request_id,
                "source_ip": request_context['sourceIp'],
                "user_agent": request_context['userAgent'],
                "api_id": request_context['apiId'],
                "stage": request_context['stage'],
                "http_method": event.get('httpMethod', 'unknown'),
                "path": event.get('path', 'unknown')
            }
        )
        
        # Parse request body
        try:
            if event.get('body'):
                body = json.loads(event['body'])
            else:
                body = {}
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'headers': {
                    'Content-Type': 'application/json',
                    'Access-Control-Allow-Origin': '*'
                },
                'body': json.dumps({
                    'success': False,
                    'message': 'Invalid JSON in request body',
                    'error_code': 'INVALID_JSON'
                })
            }
        
        # Handle different request types
        http_method = event.get('httpMethod', 'GET')
        path = event.get('path', '/')
        
        if http_method == 'GET' and path == '/health':
            # Health check endpoint
            response_body = {
                'success': True,
                'message': 'Jarvis AI Assistant is healthy',
                'timestamp': datetime.now(timezone.utc).isoformat(),
                'version': '1.0.0'
            }
        
        elif http_method == 'POST' and (path == '/chat' or path == '/command'):
            # Chat/command processing
            user_message = body.get('message', '').strip()
            
            if not user_message:
                response_body = {
                    'success': False,
                    'message': 'Message is required',
                    'error_code': 'MISSING_MESSAGE'
                }
            else:
                response_body = jarvis.process_command(user_message, request_context)
        
        else:
            # Unsupported endpoint
            jarvis._log_security_event(
                "UNSUPPORTED_ENDPOINT",
                f"Access to unsupported endpoint: {http_method} {path}",
                {
                    "http_method": http_method,
                    "path": path,
                    "source_ip": request_context['sourceIp']
                },
                severity="MEDIUM"
            )
            
            response_body = {
                'success': False,
                'message': 'Endpoint not found',
                'error_code': 'NOT_FOUND'
            }
        
        # Return response
        return {
            'statusCode': 200 if response_body.get('success', False) else 400,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'X-Request-ID': context.aws_request_id
            },
            'body': json.dumps(response_body)
        }
        
    except Exception as e:
        # Log unexpected errors
        logger.error(f"Unexpected error in lambda_handler: {str(e)}")
        
        return {
            'statusCode': 500,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({
                'success': False,
                'message': 'Internal server error',
                'error_code': 'INTERNAL_ERROR'
            })
        }