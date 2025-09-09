# 🤖 Jarvis Personal AI Assistant (SecOps-First, HA-Integrated)

A private, secure, serverless voice assistant backend designed for integration with Home Assistant and other smart home platforms. Built with AWS (API Gateway, Lambda, Polly, Transcribe, S3) and a security-first mindset.

---

## 🎯 Project Objective

- **Voice→Intent→Action:** Convert voice commands to secure smart home actions.
- **Privacy by Design:** All secrets stored in AWS Secrets Manager. No third-party data leaks.
- **API Security:** API Gateway with API Key (optionally Cognito), strict IAM, encrypted storage.
- **Home Assistant Integration:** REST commands, automations, and secure token use.

---

## 🏗️ Architecture

```
Home Assistant/Client
      |
      v
   API Gateway
      |
      +--- /speak  --> Lambda: Polly TTS --> S3 (audio) --> presigned URL
      |
      +--- /command --> Lambda: Intent parse --> Secure HTTPS to HA API
      |
    [Secrets in AWS Secrets Manager]
```

---

## 🚀 Quick Start

### Prerequisites

- AWS account (IAM user with least-privilege, MFA enabled)
- Node.js/Python (for Lambda)
- Home Assistant (HA) instance with HTTPS and Long-Lived Access Token

### 1. Clone & Install

```bash
git clone https://github.com/yourusername/jarvis-personal-assistant.git
cd jarvis-personal-assistant/infra
pip install -r requirements.txt  # or npm install
```

### 2. Deploy Infrastructure

- Define AWS resources using Pulumi/Terraform (see infra/).
- Store all secrets (HA token, API keys) in Secrets Manager.

### 3. Integrate with Home Assistant

- Add `rest_command` to HA `configuration.yaml` to call API Gateway endpoints with API Key.
- Use HA automations/scripts to trigger voice/intent actions.

---

## 🔒 Security Best Practices

- **Secrets:** Never hardcode. Always use AWS Secrets Manager or SSM Parameter Store.
- **IAM:** Use narrowly scoped roles for Lambda/API Gateway.
- **API Gateway:** API Key required for all endpoints; consider Cognito for multi-user.
- **S3:** All audio files encrypted at rest, presigned URLs expire quickly.
- **Logging:** All access/events logged in CloudWatch (audit-ready).

---

## 🛂 Feature Roadmap

- [ ] Voice command to intent (NLU)
- [ ] Home Assistant state query/response
- [ ] User authentication with Cognito
- [ ] Automated security scanning (CI/CD)
- [ ] Multi-environment deploys (dev, staging, prod)

---

## 🤝 Contributing

- Fork, branch, and PR (feat/refactor/fix/chore).
- All code must pass security and lint checks before merge.
- See `CONTRIBUTING.md` for details.

---

## 📄 License

MIT License. See `LICENSE` for details.

---
