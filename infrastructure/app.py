#!/usr/bin/env python3
"""
Jarvis AI Assistant Infrastructure App
Secure, scalable infrastructure for AI assistant with comprehensive security.
"""

import aws_cdk as cdk
import sys
import os

# Add the current directory to the path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from jarvis_stack import JarvisSecurityStack

app = cdk.App()

# Get environment configuration
env = cdk.Environment(
    account=app.node.try_get_context("account"),
    region=app.node.try_get_context("region") or "us-east-1"
)

# Create the main security stack
jarvis_stack = JarvisSecurityStack(
    app, 
    "JarvisSecurityStack",
    env=env,
    description="Secure Jarvis AI Assistant with Secrets Manager, API Gateway security, and comprehensive logging"
)

# Add security tags to all resources
cdk.Tags.of(app).add("Project", "JarvisAIAssistant")
cdk.Tags.of(app).add("Environment", "Production")
cdk.Tags.of(app).add("SecurityLevel", "High")
cdk.Tags.of(app).add("DataClassification", "Sensitive")

app.synth()