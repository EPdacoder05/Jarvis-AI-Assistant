"""
Security Hub Integration Handler
Manages security findings and compliance monitoring for Jarvis AI Assistant.
"""

import json
import os
import logging
import boto3
import uuid
from datetime import datetime, timezone
from typing import Dict, Any, List
from botocore.exceptions import ClientError


# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# AWS clients - lazy loaded
securityhub_client = None
cloudwatch_client = None

def get_aws_clients():
    """Lazy load AWS clients."""
    global securityhub_client, cloudwatch_client
    if securityhub_client is None:
        securityhub_client = boto3.client('securityhub')
        cloudwatch_client = boto3.client('cloudwatch')
    return securityhub_client, cloudwatch_client


class SecurityHubManager:
    """
    Manages Security Hub findings for Jarvis AI Assistant.
    
    Features:
    - Custom security findings creation
    - Compliance monitoring
    - Security event aggregation
    - Automated threat detection
    """
    
    def __init__(self):
        self.product_arn = self._get_product_arn()
        self.region = os.getenv('AWS_REGION', 'us-east-1')
        self.account_id = self._get_account_id()
    
    def _get_product_arn(self) -> str:
        """Generate product ARN for Security Hub findings."""
        region = os.getenv('AWS_REGION', 'us-east-1')
        account_id = self._get_account_id()
        return f"arn:aws:securityhub:{region}:{account_id}:product/jarvis-ai/security-events"
    
    def _get_account_id(self) -> str:
        """Get AWS account ID from context or default."""
        # In Lambda, you can get this from the context or use STS
        try:
            sts_client = boto3.client('sts')
            return sts_client.get_caller_identity()['Account']
        except Exception:
            return os.getenv('AWS_ACCOUNT_ID', '000000000000')
    
    def create_security_finding(
        self, 
        event_type: str, 
        title: str, 
        description: str, 
        severity: str,
        resource_id: str,
        compliance_status: str = 'PASSED',
        additional_context: Dict[str, Any] = None
    ) -> bool:
        """
        Create a security finding in AWS Security Hub.
        
        Args:
            event_type: Type of security event
            title: Finding title
            description: Detailed description
            severity: Severity level (INFORMATIONAL, LOW, MEDIUM, HIGH, CRITICAL)
            resource_id: AWS resource identifier
            compliance_status: Compliance status (PASSED, WARNING, FAILED, NOT_AVAILABLE)
            additional_context: Additional context data
            
        Returns:
            bool: True if finding was created successfully
        """
        try:
            finding_id = f"jarvis-ai-{event_type.lower()}-{uuid.uuid4()}"
            current_time = datetime.now(timezone.utc).isoformat()
            
            # Map severity levels
            severity_mapping = {
                'INFO': 'INFORMATIONAL',
                'LOW': 'LOW', 
                'MEDIUM': 'MEDIUM',
                'HIGH': 'HIGH',
                'CRITICAL': 'CRITICAL'
            }
            
            finding = {
                'SchemaVersion': '2018-10-08',
                'Id': finding_id,
                'ProductArn': self.product_arn,
                'GeneratorId': 'jarvis-ai-security-manager',
                'AwsAccountId': self.account_id,
                'Types': self._get_finding_types(event_type),
                'FirstObservedAt': current_time,
                'LastObservedAt': current_time,
                'CreatedAt': current_time,
                'UpdatedAt': current_time,
                'Severity': {
                    'Label': severity_mapping.get(severity.upper(), 'MEDIUM'),
                    'Normalized': self._get_normalized_severity(severity)
                },
                'Confidence': 100,
                'Criticality': self._get_criticality(severity),
                'Title': title,
                'Description': description,
                'Remediation': {
                    'Recommendation': {
                        'Text': self._get_remediation_text(event_type),
                        'Url': 'https://docs.aws.amazon.com/securityhub/'
                    }
                },
                'SourceUrl': 'https://github.com/EPdacoder05/Jarvis-AI-Assistant',
                'Resources': [
                    {
                        'Type': 'AwsLambdaFunction',
                        'Id': resource_id,
                        'Region': self.region,
                        'Details': {
                            'AwsLambdaFunction': {
                                'FunctionName': 'jarvis-ai-assistant',
                                'Runtime': 'python3.11'
                            }
                        }
                    }
                ],
                'WorkflowState': 'NEW',
                'Workflow': {'Status': 'NEW'},
                'RecordState': 'ACTIVE',
                'Compliance': {
                    'Status': compliance_status,
                    'RelatedRequirements': [
                        'NIST-CSF:PR.AC-1',  # Identity Management
                        'NIST-CSF:PR.AC-4',  # Access Control
                        'NIST-CSF:DE.CM-1',  # Security Monitoring
                        'NIST-CSF:DE.AE-3',  # Event Analysis
                    ]
                }
            }
            
            # Add additional context if provided
            if additional_context:
                finding['Note'] = {
                    'Text': json.dumps(additional_context),
                    'UpdatedBy': 'jarvis-ai-security-manager',
                    'UpdatedAt': current_time
                }
            
            # Submit finding to Security Hub
            securityhub_client, cloudwatch_client = get_aws_clients()
            response = securityhub_client.batch_import_findings(Findings=[finding])
            
            if response['SuccessCount'] > 0:
                logger.info(f"Security Hub finding created: {finding_id}")
                
                # Send metric to CloudWatch
                cloudwatch_client.put_metric_data(
                    Namespace='JarvisAI/SecurityHub',
                    MetricData=[
                        {
                            'MetricName': 'FindingsCreated',
                            'Value': 1,
                            'Unit': 'Count',
                            'Dimensions': [
                                {'Name': 'Severity', 'Value': severity.upper()},
                                {'Name': 'EventType', 'Value': event_type}
                            ]
                        }
                    ]
                )
                
                return True
            else:
                logger.error(f"Failed to create Security Hub finding: {response}")
                return False
                
        except Exception as e:
            logger.error(f"Error creating Security Hub finding: {str(e)}")
            return False
    
    def _get_finding_types(self, event_type: str) -> List[str]:
        """Get appropriate finding types based on event type."""
        type_mapping = {
            'AUTHENTICATION_FAILURE': ['TTPs/Defense Evasion', 'Sensitive Data Identifications'],
            'UNAUTHORIZED_ACCESS': ['TTPs/Initial Access', 'Effects/Data Exfiltration'],
            'SUSPICIOUS_ACTIVITY': ['TTPs/Discovery', 'Unusual Behaviors'],
            'CONFIGURATION_ERROR': ['Sensitive Data Identifications/PII', 'Software and Configuration Checks'],
            'API_ABUSE': ['TTPs/Impact', 'Network/Port Scan'],
            'SECRET_EXPOSURE': ['Sensitive Data Identifications/Credentials'],
            'RATE_LIMITING': ['TTPs/Impact/Network Denial of Service'],
            'INPUT_VALIDATION': ['TTPs/Initial Access/Exploit Public-Facing Application']
        }
        
        return type_mapping.get(event_type, ['Unusual Behaviors/Application'])
    
    def _get_normalized_severity(self, severity: str) -> int:
        """Get normalized severity score (0-100)."""
        severity_scores = {
            'INFO': 10,
            'LOW': 25,
            'MEDIUM': 50, 
            'HIGH': 75,
            'CRITICAL': 100
        }
        return severity_scores.get(severity.upper(), 50)
    
    def _get_criticality(self, severity: str) -> int:
        """Get criticality score (0-100)."""
        return self._get_normalized_severity(severity)
    
    def _get_remediation_text(self, event_type: str) -> str:
        """Get remediation recommendations based on event type."""
        remediation_mapping = {
            'AUTHENTICATION_FAILURE': 'Review authentication logs and consider implementing additional MFA requirements.',
            'UNAUTHORIZED_ACCESS': 'Immediately review access permissions and rotate credentials if necessary.',
            'SUSPICIOUS_ACTIVITY': 'Investigate the activity pattern and consider blocking the source if malicious.',
            'CONFIGURATION_ERROR': 'Review and correct the configuration following security best practices.',
            'API_ABUSE': 'Implement rate limiting and review API usage patterns.',
            'SECRET_EXPOSURE': 'Immediately rotate exposed secrets and review access logs.',
            'RATE_LIMITING': 'Monitor for continued abuse and consider permanent blocking.',
            'INPUT_VALIDATION': 'Review input validation logic and implement additional sanitization.'
        }
        
        return remediation_mapping.get(
            event_type, 
            'Review the security event and implement appropriate remediation measures.'
        )
    
    def process_security_events(self, events: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process multiple security events and create findings.
        
        Args:
            events: List of security events to process
            
        Returns:
            Dict containing processing results
        """
        results = {
            'processed': 0,
            'successful': 0,
            'failed': 0,
            'findings_created': []
        }
        
        for event in events:
            results['processed'] += 1
            
            try:
                success = self.create_security_finding(
                    event_type=event.get('event_type', 'UNKNOWN'),
                    title=event.get('title', 'Security Event'),
                    description=event.get('description', 'Security event detected'),
                    severity=event.get('severity', 'MEDIUM'),
                    resource_id=event.get('resource_id', 'unknown'),
                    compliance_status=event.get('compliance_status', 'WARNING'),
                    additional_context=event.get('context', {})
                )
                
                if success:
                    results['successful'] += 1
                    results['findings_created'].append(event.get('event_type', 'UNKNOWN'))
                else:
                    results['failed'] += 1
                    
            except Exception as e:
                logger.error(f"Error processing security event: {str(e)}")
                results['failed'] += 1
        
        return results


def lambda_handler(event, context):
    """
    AWS Lambda handler for Security Hub integration.
    
    Processes security events and creates Security Hub findings.
    """
    try:
        # Initialize Security Hub manager
        security_manager = SecurityHubManager()
        
        # Parse incoming event
        if 'Records' in event:
            # Handle CloudWatch Logs or SNS events
            security_events = []
            
            for record in event['Records']:
                if 'Sns' in record:
                    # SNS message
                    message = json.loads(record['Sns']['Message'])
                    security_events.append(message)
                elif 'awslogs' in record:
                    # CloudWatch Logs event
                    import gzip
                    import base64
                    
                    log_data = json.loads(gzip.decompress(base64.b64decode(record['awslogs']['data'])))
                    
                    for log_event in log_data['logEvents']:
                        try:
                            log_message = json.loads(log_event['message'])
                            if log_message.get('severity') in ['HIGH', 'CRITICAL']:
                                security_events.append({
                                    'event_type': log_message.get('event_type', 'LOG_EVENT'),
                                    'title': f"Security Log Event: {log_message.get('event_type', 'Unknown')}",
                                    'description': log_message.get('message', 'Security event from logs'),
                                    'severity': log_message.get('severity', 'MEDIUM'),
                                    'resource_id': f"arn:aws:logs:{security_manager.region}:{security_manager.account_id}:log-group:/aws/lambda/jarvis-ai",
                                    'context': log_message
                                })
                        except (json.JSONDecodeError, KeyError):
                            # Skip non-JSON or malformed log entries
                            continue
        
        elif 'security_events' in event:
            # Direct security events
            security_events = event['security_events']
        
        else:
            # Single event
            security_events = [event]
        
        # Process security events
        if security_events:
            results = security_manager.process_security_events(security_events)
            
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': True,
                    'message': f"Processed {results['processed']} security events",
                    'results': results
                })
            }
        else:
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'success': True,
                    'message': 'No security events to process'
                })
            }
            
    except Exception as e:
        logger.error(f"Error in Security Hub handler: {str(e)}")
        
        return {
            'statusCode': 500,
            'body': json.dumps({
                'success': False,
                'message': 'Failed to process security events',
                'error': str(e)
            })
        }