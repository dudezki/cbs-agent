# Deployment Guide

This guide provides step-by-step instructions for deploying the Callie Agent Platform to Google Cloud Run.

## Prerequisites

- **Google Cloud SDK** (`gcloud`) installed and configured
- **Project ID**: `callbox-core`
- **Region**: `us-central1`
- **Authentication**: Ensure you're logged in with an account that has deployment permissions

## Quick Deployment

### 1. Deploy API Service

```bash
gcloud run deploy cbs-agent-api \
  --source api/ \
  --region us-central1 \
  --allow-unauthenticated
```

**What this does:**
- Builds the API container from source using the Dockerfile in `api/`
- Deploys to Cloud Run service `cbs-agent-api`
- Makes the service publicly accessible

### 2. Build UI Image

```bash
gcloud builds submit --config ui/cloudbuild.yaml ui/
```

**What this does:**
- Uses Cloud Build to create the UI Docker image
- Pushes the image to Google Container Registry (GCR)
- Uses build-time environment variables from `ui/cloudbuild.yaml`

### 3. Deploy UI Service

```bash
gcloud run deploy cbs-agent-ui \
  --image gcr.io/callbox-core/cbs-agent-ui \
  --region us-central1 \
  --allow-unauthenticated
```

**What this does:**
- Deploys the UI image to Cloud Run service `cbs-agent-ui`
- Routes 100% of traffic to the new revision
- Makes the service publicly accessible

## Environment Variables

### UI Build Arguments

The UI build uses the following environment variables (configured in `ui/cloudbuild.yaml`):

- `VITE_API_URL`: `https://cbs-agent-api-132501877056.us-central1.run.app`
- `VITE_GOOGLE_CLIENT_ID`: `132501877056-3bv1ehe0njpfl7pt5sms4deifn93gf0a.apps.googleusercontent.com`

### API Runtime Variables

The API requires a `credentials.json` file in the `api/` directory for BigQuery and Vertex AI access. This file is **not** committed to the repository.

## Verification

After deployment, verify both services are running:

```bash
# Check API status
gcloud run services describe cbs-agent-api --region us-central1

# Check UI status
gcloud run services describe cbs-agent-ui --region us-central1
```

**Service URLs:**
- **API**: https://cbs-agent-api-132501877056.us-central1.run.app
- **UI**: https://cbs-agent-ui-132501877056.us-central1.run.app

## Local Development

### API

```bash
cd api
python main.py
```

Runs on `http://127.0.0.1:8080`

### UI

```bash
cd ui
npm run dev
```

Runs on `http://localhost:5173` with Vite proxy configured to route `/api` to the local API.

## Common Issues

### Authentication Error

If you see `Account Restricted` errors:
- Ensure you're using an account with proper permissions
- Try: `gcloud auth login`
- Verify project access: `gcloud config set project callbox-core`

### Build Timeout

UI builds can take 3-5 minutes. If Cloud Build times out:
- Check `node_modules` size
- Ensure `.dockerignore` excludes development files

### WebSocket Connection Issues

After deployment, if WebSocket connections fail:
- Verify the `VITE_API_URL` in `ui/cloudbuild.yaml` points to the correct API URL
- Check CORS settings in `api/main.py`

## Rollback

To rollback to a previous revision:

```bash
# List revisions
gcloud run revisions list --service cbs-agent-ui --region us-central1

# Route traffic to a specific revision
gcloud run services update-traffic cbs-agent-ui \
  --to-revisions REVISION_NAME=100 \
  --region us-central1
```

## Notes

- All deployments create new revisions but preserve previous ones
- Cloud Run automatically scales based on traffic
- Static IP is not required; services use auto-generated URLs
- The UI is a static SPA served by NGINX
