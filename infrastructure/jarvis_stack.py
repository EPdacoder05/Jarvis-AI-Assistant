"""
Jarvis AI Assistant Security Stack
Implements comprehensive security with Secrets Manager, API Gateway security, and logging.
"""

import aws_cdk as cdk
from aws_cdk import (
    Stack,
    aws_lambda as _lambda,
    aws_apigateway as apigateway,
    aws_secretsmanager as secretsmanager,
    aws_iam as iam,
    aws_logs as logs,
    aws_cognito as cognito,
    aws_cloudwatch as cloudwatch,
    aws_securityhub as securityhub,
    Duration,
    RemovalPolicy
)
from constructs import Construct


class JarvisSecurityStack(Stack):
    """
    Main security stack for Jarvis AI Assistant.
    
    Security Features:
    - All tokens stored in Secrets Manager
    - API Gateway with API Key + optional Cognito auth
    - Comprehensive CloudWatch + Security Hub logging
    - Least privilege IAM policies
    """

    def __init__(self, scope: Construct, construct_id: str, **kwargs) -> None:
        super().__init__(scope, construct_id, **kwargs)

        # 1. SECRETS MANAGER - Store all HA tokens and API keys
        self.create_secrets_manager()
        
        # 2. COGNITO - Optional user authentication
        self.create_cognito_user_pool()
        
        # 3. LAMBDA FUNCTIONS - Core assistant functionality
        self.create_lambda_functions()
        
        # 4. API GATEWAY - Secure API with keys and Cognito
        self.create_api_gateway()
        
        # 5. CLOUDWATCH & SECURITY HUB - Comprehensive logging
        self.create_logging_infrastructure()
        
        # 6. OUTPUTS - For application configuration
        self.create_outputs()

    def create_secrets_manager(self):
        """Create Secrets Manager for storing all sensitive tokens and API keys."""
        
        # Home Assistant tokens and configuration
        self.ha_secrets = secretsmanager.Secret(
            self, "HomeAssistantSecrets",
            description="Home Assistant API tokens and configuration",
            secret_name="jarvis/home-assistant",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"ha_url": "", "ha_token": ""}',
                generate_string_key="ha_long_lived_token",
                exclude_characters=' "%@\\\'',
            )
        )
        
        # External API keys (OpenAI, weather, etc.)
        self.api_secrets = secretsmanager.Secret(
            self, "ExternalAPISecrets", 
            description="External API keys for Jarvis AI services",
            secret_name="jarvis/external-apis",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"openai_api_key": "", "weather_api_key": "", "spotify_api_key": ""}',
                generate_string_key="master_encryption_key",
                exclude_characters=' "%@\\\'',
            )
        )
        
        # API Gateway API keys for client access
        self.gateway_secrets = secretsmanager.Secret(
            self, "APIGatewaySecrets",
            description="API Gateway keys and authentication secrets", 
            secret_name="jarvis/api-gateway",
            generate_secret_string=secretsmanager.SecretStringGenerator(
                secret_string_template='{"api_key_1": "", "api_key_2": ""}',
                generate_string_key="jwt_secret",
                exclude_characters=' "%@\\\'',
            )
        )

    def create_cognito_user_pool(self):
        """Create Cognito User Pool for optional authentication."""
        
        self.user_pool = cognito.UserPool(
            self, "JarvisUserPool",
            user_pool_name="jarvis-ai-users",
            sign_in_aliases=cognito.SignInAliases(
                username=True,
                email=True
            ),
            auto_verify=cognito.AutoVerifiedAttrs(email=True),
            password_policy=cognito.PasswordPolicy(
                min_length=12,
                require_digits=True,
                require_lowercase=True,
                require_symbols=True,
                require_uppercase=True
            ),
            mfa=cognito.Mfa.OPTIONAL,
            mfa_second_factor=cognito.MfaSecondFactor(
                sms=True,
                otp=True
            ),
            removal_policy=RemovalPolicy.DESTROY  # For development
        )
        
        self.user_pool_client = self.user_pool.add_client(
            "JarvisUserPoolClient",
            user_pool_client_name="jarvis-web-client",
            generate_secret=True,
            auth_flows=cognito.AuthFlow(
                user_password=True,
                user_srp=True
            ),
            o_auth=cognito.OAuthSettings(
                flows=cognito.OAuthFlows(
                    authorization_code_grant=True
                ),
                scopes=[cognito.OAuthScope.OPENID, cognito.OAuthScope.EMAIL],
                callback_urls=["https://localhost:3000/callback"]  # Update for production
            )
        )

    def create_lambda_functions(self):
        """Create Lambda functions for Jarvis AI functionality."""
        
        # IAM role for Lambda with minimum required permissions
        lambda_role = iam.Role(
            self, "JarvisLambdaRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        # Grant access to secrets
        self.ha_secrets.grant_read(lambda_role)
        self.api_secrets.grant_read(lambda_role)
        self.gateway_secrets.grant_read(lambda_role)
        
        # Grant CloudWatch logging permissions
        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "logs:CreateLogGroup",
                "logs:CreateLogStream", 
                "logs:PutLogEvents",
                "logs:PutMetricData"
            ],
            resources=["arn:aws:logs:*:*:*"]
        ))
        
        # Grant Security Hub permissions
        lambda_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "securityhub:BatchImportFindings",
                "securityhub:CreateInsight"
            ],
            resources=["*"]
        ))
        
        # Main Jarvis AI Lambda function
        self.jarvis_function = _lambda.Function(
            self, "JarvisAIFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="jarvis_handler.lambda_handler",
            code=_lambda.Code.from_asset("src"),
            timeout=Duration.seconds(30),
            memory_size=512,
            role=lambda_role,
            environment={
                "HA_SECRETS_ARN": self.ha_secrets.secret_arn,
                "API_SECRETS_ARN": self.api_secrets.secret_arn,
                "GATEWAY_SECRETS_ARN": self.gateway_secrets.secret_arn,
                "LOG_LEVEL": "INFO",
                "SECURITY_HUB_ENABLED": "true"
            },
            description="Secure Jarvis AI Assistant with comprehensive logging"
        )
        
        # Command processing Lambda
        self.command_processor = _lambda.Function(
            self, "CommandProcessorFunction", 
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="command_processor.lambda_handler",
            code=_lambda.Code.from_asset("src"),
            timeout=Duration.seconds(15),
            memory_size=256,
            role=lambda_role,
            environment={
                "HA_SECRETS_ARN": self.ha_secrets.secret_arn,
                "LOG_LEVEL": "INFO"
            },
            description="Secure command processor with access logging"
        )

    def create_api_gateway(self):
        """Create secure API Gateway with API Key and optional Cognito auth."""
        
        # API Gateway with logging enabled
        self.api = apigateway.RestApi(
            self, "JarvisAPI",
            rest_api_name="Jarvis AI Assistant API",
            description="Secure API for Jarvis AI Assistant with authentication and logging",
            default_cors_preflight_options=apigateway.CorsOptions(
                allow_origins=["https://localhost:3000"],  # Update for production
                allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
                allow_headers=["Content-Type", "X-Amz-Date", "Authorization", "X-Api-Key"]
            ),
            cloud_watch_role=True,
            deploy_options=apigateway.StageOptions(
                stage_name="prod",
                throttling_rate_limit=100,
                throttling_burst_limit=200,
                logging_level=apigateway.MethodLoggingLevel.INFO,
                data_trace_enabled=True,
                metrics_enabled=True
            )
        )
        
        # API Key for client authentication
        self.api_key = self.api.add_api_key(
            "JarvisAPIKey",
            api_key_name="jarvis-client-key",
            description="API key for Jarvis AI client applications"
        )
        
        # Usage plan with rate limiting
        usage_plan = self.api.add_usage_plan(
            "JarvisUsagePlan",
            name="Jarvis API Usage Plan",
            description="Rate limiting and quotas for Jarvis API",
            throttle=apigateway.ThrottleSettings(
                rate_limit=50,
                burst_limit=100
            ),
            quota=apigateway.QuotaSettings(
                limit=10000,
                period=apigateway.Period.DAY
            )
        )
        usage_plan.add_api_key(self.api_key)
        usage_plan.add_api_stage(stage=self.api.deployment_stage)
        
        # Cognito authorizer for optional enhanced security
        cognito_authorizer = apigateway.CognitoUserPoolsAuthorizer(
            self, "JarvisCognitoAuthorizer",
            cognito_user_pools=[self.user_pool],
            authorizer_name="jarvis-cognito-auth"
        )
        
        # Lambda integrations
        jarvis_integration = apigateway.LambdaIntegration(
            self.jarvis_function,
            request_templates={"application/json": '{"statusCode": "200"}'}
        )
        
        command_integration = apigateway.LambdaIntegration(
            self.command_processor,
            request_templates={"application/json": '{"statusCode": "200"}'}
        )
        
        # API Resources with security
        # /chat endpoint - requires API key
        chat_resource = self.api.root.add_resource("chat")
        chat_resource.add_method(
            "POST", 
            jarvis_integration,
            api_key_required=True,
            request_validator=apigateway.RequestValidator(
                self, "ChatRequestValidator",
                rest_api=self.api,
                validate_request_body=True,
                validate_request_parameters=True
            )
        )
        
        # /command endpoint - requires API key + optional Cognito
        command_resource = self.api.root.add_resource("command")
        command_resource.add_method(
            "POST",
            command_integration, 
            api_key_required=True,
            authorizer=cognito_authorizer,  # Optional Cognito auth
            authorization_type=apigateway.AuthorizationType.COGNITO
        )
        
        # /health endpoint - public for monitoring
        health_resource = self.api.root.add_resource("health")
        health_resource.add_method("GET", jarvis_integration)

    def create_logging_infrastructure(self):
        """Create comprehensive logging with CloudWatch and Security Hub."""
        
        # CloudWatch Log Groups with retention
        self.api_log_group = logs.LogGroup(
            self, "JarvisAPILogs",
            log_group_name="/aws/apigateway/jarvis-ai",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        self.lambda_log_group = logs.LogGroup(
            self, "JarvisLambdaLogs", 
            log_group_name="/aws/lambda/jarvis-ai",
            retention=logs.RetentionDays.ONE_MONTH,
            removal_policy=RemovalPolicy.DESTROY
        )
        
        # CloudWatch Alarms for security monitoring
        self.failed_auth_alarm = cloudwatch.Alarm(
            self, "FailedAuthAlarm",
            alarm_name="jarvis-failed-authentication",
            alarm_description="Alert on failed authentication attempts",
            metric=cloudwatch.Metric(
                namespace="AWS/ApiGateway",
                metric_name="4XXError",
                dimensions_map={"ApiName": self.api.rest_api_name}
            ),
            threshold=10,
            evaluation_periods=2,
            datapoints_to_alarm=1
        )
        
        # Security Hub findings Lambda for custom security events
        security_hub_role = iam.Role(
            self, "SecurityHubRole",
            assumed_by=iam.ServicePrincipal("lambda.amazonaws.com"),
            managed_policies=[
                iam.ManagedPolicy.from_aws_managed_policy_name("service-role/AWSLambdaBasicExecutionRole")
            ]
        )
        
        security_hub_role.add_to_policy(iam.PolicyStatement(
            effect=iam.Effect.ALLOW,
            actions=[
                "securityhub:BatchImportFindings",
                "securityhub:GetFindings"
            ],
            resources=["*"]
        ))
        
        self.security_hub_function = _lambda.Function(
            self, "SecurityHubFunction",
            runtime=_lambda.Runtime.PYTHON_3_11,
            handler="security_hub_handler.lambda_handler", 
            code=_lambda.Code.from_asset("src"),
            timeout=Duration.seconds(10),
            role=security_hub_role,
            description="Security Hub integration for Jarvis AI security events"
        )

    def create_outputs(self):
        """Create CloudFormation outputs for application configuration."""
        
        cdk.CfnOutput(
            self, "APIGatewayURL",
            value=self.api.url,
            description="Jarvis AI API Gateway URL"
        )
        
        cdk.CfnOutput(
            self, "APIKeyId", 
            value=self.api_key.key_id,
            description="API Key ID for client configuration"
        )
        
        cdk.CfnOutput(
            self, "UserPoolId",
            value=self.user_pool.user_pool_id,
            description="Cognito User Pool ID"
        )
        
        cdk.CfnOutput(
            self, "UserPoolClientId",
            value=self.user_pool_client.user_pool_client_id,
            description="Cognito User Pool Client ID"
        )
        
        cdk.CfnOutput(
            self, "SecretsManagerArns",
            value=f"HA:{self.ha_secrets.secret_arn},API:{self.api_secrets.secret_arn},Gateway:{self.gateway_secrets.secret_arn}",
            description="Secrets Manager ARNs for configuration"
        )