"""
Command Processor Lambda Handler
Handles specific Home Assistant and IoT commands with enhanced security.
"""

import json
import os
import logging
import boto3
import uuid
import requests
from datetime import datetime, timezone
from typing import Dict, Any, Optional
from botocore.exceptions import ClientError


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS clients - lazy loaded
secrets_client = None
cloudwatch_client = None

def get_aws_clients():
    """Lazy load AWS clients."""
    global secrets_client, cloudwatch_client
    if secrets_client is None:
        secrets_client = boto3.client('secretsmanager')
        cloudwatch_client = boto3.client('cloudwatch')
    return secrets_client, cloudwatch_client


class SecureCommandProcessor:
    """
    Secure command processor for Home Assistant and IoT device control.
    
    Features:
    - Secure Home Assistant API integration
    - Command validation and sanitization
    - Comprehensive audit logging
    - Rate limiting and abuse detection
    """
    
    def __init__(self):
        self.session_id = str(uuid.uuid4())
        self.command_count = 0
        self.max_commands_per_session = 100
        
    def get_ha_config(self) -> Dict[str, str]:
        """Retrieve Home Assistant configuration from Secrets Manager."""
        try:
            secrets_client, _ = get_aws_clients()
            secret_arn = os.getenv('HA_SECRETS_ARN')
            response = secrets_client.get_secret_value(SecretId=secret_arn)
            ha_config = json.loads(response['SecretString'])
            
            # Log successful config retrieval
            self._log_command_event(
                "HA_CONFIG_RETRIEVED",
                "Home Assistant configuration retrieved successfully",
                {"session_id": self.session_id}
            )
            
            return ha_config
            
        except Exception as e:
            logger.error(f"Failed to retrieve HA config: {str(e)}")
            self._log_command_event(
                "HA_CONFIG_ERROR",
                f"Failed to retrieve HA config: {str(e)}",
                {"error": str(e)},
                severity="HIGH"
            )
            raise
    
    def _log_command_event(self, event_type: str, message: str, context: Dict[str, Any], severity: str = "INFO"):
        """Log command events with structured format."""
        log_entry = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "event_type": event_type,
            "message": message,
            "severity": severity,
            "session_id": self.session_id,
            "service": "command-processor",
            **context
        }
        
        logger.info(json.dumps(log_entry))
        
        # Send metric to CloudWatch
        try:
            _, cloudwatch_client = get_aws_clients()
            cloudwatch_client.put_metric_data(
                Namespace='JarvisAI/Commands',
                MetricData=[
                    {
                        'MetricName': f'Command_{event_type}',
                        'Value': 1,
                        'Unit': 'Count'
                    }
                ]
            )
        except Exception as e:
            logger.error(f"Failed to send CloudWatch metric: {str(e)}")
    
    def validate_command(self, command: Dict[str, Any]) -> bool:
        """Validate command structure and parameters."""
        required_fields = ['action', 'target']
        
        # Check required fields
        for field in required_fields:
            if field not in command:
                self._log_command_event(
                    "COMMAND_VALIDATION_FAILED",
                    f"Missing required field: {field}",
                    {"command": command, "missing_field": field},
                    severity="MEDIUM"
                )
                return False
        
        # Validate action types
        allowed_actions = [
            'turn_on', 'turn_off', 'toggle', 'set_brightness', 
            'set_temperature', 'get_state', 'lock', 'unlock'
        ]
        
        if command['action'] not in allowed_actions:
            self._log_command_event(
                "INVALID_ACTION",
                f"Invalid action: {command['action']}",
                {"command": command, "action": command['action']},
                severity="HIGH"
            )
            return False
        
        # Check session command limit
        self.command_count += 1
        if self.command_count > self.max_commands_per_session:
            self._log_command_event(
                "RATE_LIMIT_EXCEEDED",
                f"Session command limit exceeded: {self.command_count}",
                {"session_id": self.session_id, "command_count": self.command_count},
                severity="HIGH"
            )
            return False
        
        return True
    
    def execute_ha_command(self, command: Dict[str, Any]) -> Dict[str, Any]:
        """Execute Home Assistant command via API."""
        try:
            # Get HA configuration
            ha_config = self.get_ha_config()
            ha_url = ha_config.get('ha_url', '').rstrip('/')
            ha_token = ha_config.get('ha_token', '')
            
            if not ha_url or not ha_token:
                raise ValueError("Home Assistant URL or token not configured")
            
            # Build API request
            headers = {
                'Authorization': f'Bearer {ha_token}',
                'Content-Type': 'application/json'
            }
            
            action = command['action']
            target = command['target']
            
            # Log command execution attempt
            self._log_command_event(
                "HA_COMMAND_EXECUTING",
                f"Executing HA command: {action} on {target}",
                {
                    "action": action,
                    "target": target,
                    "ha_url_masked": ha_url[:20] + "..." if len(ha_url) > 20 else ha_url
                }
            )
            
            # Map commands to HA API calls
            if action in ['turn_on', 'turn_off', 'toggle']:
                # Light/switch control
                service = 'light' if 'light' in target else 'switch'
                api_url = f"{ha_url}/api/services/{service}/{action}"
                payload = {"entity_id": target}
                
            elif action == 'set_brightness':
                # Brightness control
                api_url = f"{ha_url}/api/services/light/turn_on"
                payload = {
                    "entity_id": target,
                    "brightness": command.get('brightness', 255)
                }
                
            elif action == 'set_temperature':
                # Climate control
                api_url = f"{ha_url}/api/services/climate/set_temperature"
                payload = {
                    "entity_id": target,
                    "temperature": command.get('temperature', 20)
                }
                
            elif action == 'get_state':
                # Get entity state
                api_url = f"{ha_url}/api/states/{target}"
                response = requests.get(api_url, headers=headers, timeout=10)
                
                if response.status_code == 200:
                    state_data = response.json()
                    self._log_command_event(
                        "HA_STATE_RETRIEVED",
                        f"Retrieved state for {target}",
                        {"target": target, "state": state_data.get('state', 'unknown')}
                    )
                    return {
                        "success": True,
                        "action": action,
                        "target": target,
                        "state": state_data.get('state'),
                        "attributes": state_data.get('attributes', {})
                    }
                else:
                    raise Exception(f"HA API error: {response.status_code}")
            
            else:
                raise ValueError(f"Unsupported action: {action}")
            
            # Execute command (for non-state requests)
            if action != 'get_state':
                response = requests.post(api_url, headers=headers, json=payload, timeout=10)
                
                if response.status_code in [200, 201]:
                    self._log_command_event(
                        "HA_COMMAND_SUCCESS",
                        f"HA command executed successfully: {action} on {target}",
                        {"action": action, "target": target, "status_code": response.status_code}
                    )
                    return {
                        "success": True,
                        "action": action,
                        "target": target,
                        "message": f"Successfully executed {action} on {target}"
                    }
                else:
                    raise Exception(f"HA API error: {response.status_code} - {response.text}")
            
        except Exception as e:
            error_msg = f"Failed to execute HA command: {str(e)}"
            logger.error(error_msg)
            
            self._log_command_event(
                "HA_COMMAND_FAILED",
                error_msg,
                {"command": command, "error": str(e)},
                severity="HIGH"
            )
            
            return {
                "success": False,
                "action": command.get('action', 'unknown'),
                "target": command.get('target', 'unknown'),
                "error": error_msg
            }
    
    def process_command(self, command_data: Dict[str, Any], context: Dict[str, Any]) -> Dict[str, Any]:
        """Process incoming command with validation and execution."""
        # Log command received
        self._log_command_event(
            "COMMAND_RECEIVED",
            "Command received for processing",
            {
                "command_type": command_data.get('type', 'unknown'),
                "source_ip": context.get('sourceIp', 'unknown'),
                "user_agent": context.get('userAgent', 'unknown')
            }
        )
        
        # Validate command
        if not self.validate_command(command_data):
            return {
                "success": False,
                "message": "Command validation failed",
                "error_code": "INVALID_COMMAND"
            }
        
        # Execute command based on type
        command_type = command_data.get('type', 'home_assistant')
        
        if command_type == 'home_assistant':
            result = self.execute_ha_command(command_data)
        else:
            # Future: Add support for other IoT platforms
            result = {
                "success": False,
                "message": f"Unsupported command type: {command_type}",
                "error_code": "UNSUPPORTED_TYPE"
            }
        
        # Add session context to result
        result['session_id'] = self.session_id
        result['timestamp'] = datetime.now(timezone.utc).isoformat()
        
        return result


def lambda_handler(event, context):
    """
    AWS Lambda handler for command processing.
    """
    try:
        # Initialize command processor
        processor = SecureCommandProcessor()
        
        # Extract request context
        request_context = {
            'requestId': context.aws_request_id,
            'sourceIp': event.get('requestContext', {}).get('identity', {}).get('sourceIp', 'unknown'),
            'userAgent': event.get('requestContext', {}).get('identity', {}).get('userAgent', 'unknown')
        }
        
        # Parse request body
        try:
            if event.get('body'):
                command_data = json.loads(event['body'])
            else:
                return {
                    'statusCode': 400,
                    'headers': {'Content-Type': 'application/json'},
                    'body': json.dumps({
                        'success': False,
                        'message': 'Request body is required',
                        'error_code': 'MISSING_BODY'
                    })
                }
        except json.JSONDecodeError:
            return {
                'statusCode': 400,
                'headers': {'Content-Type': 'application/json'},
                'body': json.dumps({
                    'success': False,
                    'message': 'Invalid JSON in request body',
                    'error_code': 'INVALID_JSON'
                })
            }
        
        # Process the command
        result = processor.process_command(command_data, request_context)
        
        # Return response
        status_code = 200 if result.get('success', False) else 400
        
        return {
            'statusCode': status_code,
            'headers': {
                'Content-Type': 'application/json',
                'Access-Control-Allow-Origin': '*',
                'X-Request-ID': context.aws_request_id
            },
            'body': json.dumps(result)
        }
        
    except Exception as e:
        logger.error(f"Unexpected error in command processor: {str(e)}")
        
        return {
            'statusCode': 500,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                'success': False,
                'message': 'Internal server error',
                'error_code': 'INTERNAL_ERROR'
            })
        }