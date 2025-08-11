# AWS App Runner Deployment Guide

## Source Code Deployment with apprunner.yaml

This application now uses **source code deployment** with `apprunner.yaml` configuration.

## Deployment Method

1. **Push code to GitHub repository** with the `apprunner.yaml` file
2. **Create App Runner service using source code**:
   - In AWS Console, choose "Source code repository" as source
   - Connect to your GitHub repository
   - App Runner will automatically detect and use `apprunner.yaml`

## Configuration Details

The `apprunner.yaml` file configures:
- **Runtime**: Python 3.11
- **Dependencies**: Installed via `pip install -r requirements.txt`
- **Server**: Gunicorn with command `gunicorn app:app --log-file -`
- **Port**: 8080 (standard App Runner port)

## Environment Variables and Secrets

Configure these in the `apprunner.yaml`:
- `FLASK_ENV=production`
- `FLASK_DEBUG=false`
- `ALLOWED_ORIGINS` (set to your domain)
- `DEFAULT_WEIGHTS` (JSON string with default scoring weights)

Secrets from AWS Secrets Manager:
- `NOTION_API_KEY`
- `VENDORS_DB_ID`, `PARTS_DB_ID`, `SCORES_DB_ID`
- `SECRET_KEY` (Flask secret key)

**Remember to replace `ACCOUNT_ID` with your actual AWS account ID in the secret ARNs.**

## Benefits of Source Code Deployment

- No Docker image building/pushing required
- Automatic deployment on code changes
- Simpler configuration via `apprunner.yaml`
- Managed Python runtime by AWS
- Environment variables and secrets configured in one place