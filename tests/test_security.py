"""
Test suite for Jarvis AI Assistant Security Implementation
"""

import json
import pytest
import boto3
from moto import mock_secretsmanager, mock_lambda, mock_apigateway
from unittest.mock import patch, MagicMock
import sys
import os

# Add src to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))

from jarvis_handler import SecureJarvisAssistant, lambda_handler
from command_processor import SecureCommandProcessor
from security_hub_handler import SecurityHubManager


class TestSecureJarvisAssistant:
    """Test security features of Jarvis AI Assistant."""
    
    @mock_secretsmanager
    def test_secret_retrieval_success(self):
        """Test successful secret retrieval from Secrets Manager."""
        # Setup mock secrets
        secrets_client = boto3.client('secretsmanager', region_name='us-east-1')
        secrets_client.create_secret(
            Name='test-secret',
            SecretString='{"api_key": "test-key", "url": "https://test.com"}'
        )
        
        # Test secret retrieval
        assistant = SecureJarvisAssistant()
        with patch.dict(os.environ, {'AWS_DEFAULT_REGION': 'us-east-1'}):
            secret = assistant.get_secret('test-secret', 'test')
            
        assert secret['api_key'] == 'test-key'
        assert secret['url'] == 'https://test.com'
    
    @mock_secretsmanager  
    def test_secret_retrieval_failure(self):
        """Test proper error handling for secret retrieval failures."""
        assistant = SecureJarvisAssistant()
        
        with pytest.raises(Exception) as exc_info:
            assistant.get_secret('non-existent-secret', 'test')
        
        assert 'Failed to retrieve secret' in str(exc_info.value)
    
    def test_input_validation_success(self):
        """Test input validation with valid input."""
        assistant = SecureJarvisAssistant()
        
        valid_inputs = [
            "Turn on the lights",
            "What's the weather like?",
            "Play some music",
            "Set temperature to 20 degrees"
        ]
        
        for input_text in valid_inputs:
            assert assistant.validate_input(input_text) == True
    
    def test_input_validation_security_rejection(self):
        """Test input validation rejects malicious input."""
        assistant = SecureJarvisAssistant()
        
        malicious_inputs = [
            "eval('import os; os.system(\"rm -rf /\")')",
            "exec(open('malicious.py').read())",
            "import subprocess; subprocess.call(['rm', '-rf', '/'])",
            "DROP TABLE users;",
            "__import__('os').system('cat /etc/passwd')"
        ]
        
        for input_text in malicious_inputs:
            assert assistant.validate_input(input_text) == False
    
    def test_input_validation_length_limit(self):
        """Test input validation rejects oversized input."""
        assistant = SecureJarvisAssistant()
        
        # Test input at limit
        valid_input = 'a' * 5000
        assert assistant.validate_input(valid_input) == True
        
        # Test input over limit
        invalid_input = 'a' * 5001
        assert assistant.validate_input(invalid_input) == False
    
    def test_input_validation_empty_input(self):
        """Test input validation handles empty input."""
        assistant = SecureJarvisAssistant()
        
        assert assistant.validate_input('') == False
        assert assistant.validate_input('   ') == False
        assert assistant.validate_input(None) == False


class TestSecureCommandProcessor:
    """Test security features of the command processor."""
    
    def test_command_validation_success(self):
        """Test valid command passes validation."""
        processor = SecureCommandProcessor()
        
        valid_commands = [
            {'action': 'turn_on', 'target': 'light.bedroom'},
            {'action': 'set_temperature', 'target': 'climate.living_room', 'temperature': 22},
            {'action': 'get_state', 'target': 'sensor.temperature'}
        ]
        
        for command in valid_commands:
            assert processor.validate_command(command) == True
    
    def test_command_validation_missing_fields(self):
        """Test command validation rejects incomplete commands."""
        processor = SecureCommandProcessor()
        
        invalid_commands = [
            {'action': 'turn_on'},  # Missing target
            {'target': 'light.bedroom'},  # Missing action
            {}  # Missing both
        ]
        
        for command in invalid_commands:
            assert processor.validate_command(command) == False
    
    def test_command_validation_invalid_action(self):
        """Test command validation rejects invalid actions."""
        processor = SecureCommandProcessor()
        
        invalid_command = {
            'action': 'delete_database',  # Invalid action
            'target': 'light.bedroom'
        }
        
        assert processor.validate_command(invalid_command) == False
    
    def test_rate_limiting(self):
        """Test rate limiting prevents excessive commands."""
        processor = SecureCommandProcessor()
        processor.max_commands_per_session = 3  # Lower limit for testing
        
        valid_command = {'action': 'turn_on', 'target': 'light.test'}
        
        # First 3 commands should pass
        for i in range(3):
            assert processor.validate_command(valid_command) == True
        
        # 4th command should fail due to rate limiting
        assert processor.validate_command(valid_command) == False


class TestSecurityHubManager:
    """Test Security Hub integration functionality."""
    
    def test_security_hub_initialization(self):
        """Test Security Hub manager initializes correctly."""
        with patch('boto3.client'):
            manager = SecurityHubManager()
            assert manager.region == 'us-east-1'
            assert 'jarvis-ai' in manager.product_arn
    
    def test_finding_types_mapping(self):
        """Test security finding types are mapped correctly."""
        manager = SecurityHubManager()
        
        # Test different event types
        auth_types = manager._get_finding_types('AUTHENTICATION_FAILURE')
        assert 'TTPs/Defense Evasion' in auth_types
        
        access_types = manager._get_finding_types('UNAUTHORIZED_ACCESS')
        assert 'TTPs/Initial Access' in access_types
        
        # Test default case
        unknown_types = manager._get_finding_types('UNKNOWN_EVENT')
        assert 'Unusual Behaviors/Application' in unknown_types
    
    def test_severity_normalization(self):
        """Test severity level normalization."""
        manager = SecurityHubManager()
        
        assert manager._get_normalized_severity('INFO') == 10
        assert manager._get_normalized_severity('LOW') == 25
        assert manager._get_normalized_severity('MEDIUM') == 50
        assert manager._get_normalized_severity('HIGH') == 75
        assert manager._get_normalized_severity('CRITICAL') == 100
        
        # Test default case
        assert manager._get_normalized_severity('UNKNOWN') == 50


class TestLambdaHandlers:
    """Test Lambda function handlers."""
    
    @mock_secretsmanager
    def test_lambda_handler_health_check(self):
        """Test health check endpoint."""
        # Mock event for health check
        event = {
            'httpMethod': 'GET',
            'path': '/health',
            'requestContext': {
                'requestId': 'test-request-id',
                'identity': {'sourceIp': '127.0.0.1', 'userAgent': 'test-agent'},
                'apiId': 'test-api',
                'stage': 'test'
            }
        }
        
        context = MagicMock()
        context.aws_request_id = 'test-request-id'
        
        with patch.dict(os.environ, {'AWS_DEFAULT_REGION': 'us-east-1'}):
            response = lambda_handler(event, context)
        
        assert response['statusCode'] == 200
        body = json.loads(response['body'])
        assert body['success'] == True
        assert 'healthy' in body['message']
    
    def test_lambda_handler_invalid_json(self):
        """Test proper handling of invalid JSON in request body."""
        event = {
            'httpMethod': 'POST',
            'path': '/chat',
            'body': 'invalid json',
            'requestContext': {
                'requestId': 'test-request-id',
                'identity': {'sourceIp': '127.0.0.1', 'userAgent': 'test-agent'},
                'apiId': 'test-api',
                'stage': 'test'
            }
        }
        
        context = MagicMock()
        context.aws_request_id = 'test-request-id'
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] == False
        assert body['error_code'] == 'INVALID_JSON'
    
    def test_lambda_handler_missing_message(self):
        """Test proper handling of missing message in chat request."""
        event = {
            'httpMethod': 'POST',
            'path': '/chat',
            'body': '{}',
            'requestContext': {
                'requestId': 'test-request-id',
                'identity': {'sourceIp': '127.0.0.1', 'userAgent': 'test-agent'},
                'apiId': 'test-api',
                'stage': 'test'
            }
        }
        
        context = MagicMock()
        context.aws_request_id = 'test-request-id'
        
        response = lambda_handler(event, context)
        
        assert response['statusCode'] == 400
        body = json.loads(response['body'])
        assert body['success'] == False
        assert body['error_code'] == 'MISSING_MESSAGE'


class TestSecurityLogging:
    """Test security logging functionality."""
    
    def test_security_event_logging(self):
        """Test security events are properly logged."""
        assistant = SecureJarvisAssistant()
        
        with patch('boto3.client') as mock_boto:
            mock_cloudwatch = MagicMock()
            mock_boto.return_value = mock_cloudwatch
            
            # Test logging a security event
            assistant._log_security_event(
                "TEST_EVENT",
                "Test security event",
                {"test_context": "test_value"},
                "HIGH"
            )
            
            # Verify CloudWatch metric was sent
            mock_cloudwatch.put_metric_data.assert_called_once()
            call_args = mock_cloudwatch.put_metric_data.call_args[1]
            assert call_args['Namespace'] == 'JarvisAI/Security'
            assert call_args['MetricData'][0]['MetricName'] == 'SecurityEvent_TEST_EVENT'


if __name__ == '__main__':
    pytest.main([__file__, '-v'])