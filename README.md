# Jarvis AI Assistant - Voice Backend

A serverless voice assistant backend built on AWS, designed to integrate securely with Home Assistant.

## Overview

This project implements a secure, cloud-native voice assistant backend using AWS services:

- **API Gateway**: Secure REST API with `/speak` and `/command` endpoints
- **Lambda Functions**: TTS processing and intent handling
- **Polly**: Text-to-speech synthesis
- **S3**: Audio file storage with presigned URLs
- **Secrets Manager**: Secure credential storage
- **Home Assistant Integration**: REST commands and automations

## Architecture

```
[Voice Input] → [API Gateway] → [Lambda Functions] → [AWS Services]
                                      ↓
[Home Assistant] ← [REST API] ← [Intent Processing]
```

## Quick Start

1. **Deploy Infrastructure**:
   ```bash
   ./scripts/deploy.sh
   ```

2. **Configure Home Assistant**:
   - Copy `homeassistant/configuration.yaml` sections to your HA config
   - Update API endpoint and keys

3. **Test Integration**:
   ```bash
   ./scripts/test.sh
   ```

## Project Structure

```
├── src/lambda/          # Lambda function source code
│   ├── tts/            # Text-to-speech Lambda
│   └── intent/         # Intent processing Lambda
├── infrastructure/     # CloudFormation templates
├── homeassistant/     # Home Assistant configuration
├── scripts/           # Deployment and utility scripts
├── tests/            # Unit and integration tests
└── docs/             # Documentation
```

## Security Features

- API key authentication
- AWS Secrets Manager integration
- HTTPS everywhere
- Least privilege IAM roles
- VPC isolation options

## License

MIT License - see LICENSE file for details.