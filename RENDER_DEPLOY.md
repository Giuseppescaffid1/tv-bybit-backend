# Deploying to Render

This guide will help you deploy the Bybit Trading Dashboard to Render.

## Prerequisites

1. A GitHub account with this repository
2. A Render account (free tier available)

## Deployment Steps

### Option 1: Using Render Dashboard (Recommended)

1. **Go to Render Dashboard**
   - Visit https://dashboard.render.com
   - Sign up or log in

2. **Create New Web Service**
   - Click "New +" → "Web Service"
   - Connect your GitHub repository
   - Select the repository containing this code

3. **Configure the Service**
   - **Name**: `bybit-trading-dashboard` (or your preferred name)
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn --bind 0.0.0.0:$PORT streamlit.app:server`
   - **Root Directory**: Leave empty (or `tv-bybit-backend` if your repo structure requires it)

4. **Advanced Settings**
   - **Python Version**: `3.11.0`
   - **Health Check Path**: `/`
   - **Auto-Deploy**: `Yes` (deploys on every push to main branch)

5. **Deploy**
   - Click "Create Web Service"
   - Render will build and deploy your app
   - Wait for the build to complete (usually 2-5 minutes)

### Option 2: Using render.yaml (Automatic)

If you've committed `render.yaml` to your repository:

1. Go to Render Dashboard
2. Click "New +" → "Blueprint"
3. Connect your GitHub repository
4. Render will automatically detect `render.yaml` and configure the service
5. Click "Apply" to deploy

## Important Notes

### Port Configuration
- Render automatically sets the `$PORT` environment variable
- The app uses `gunicorn` to bind to `0.0.0.0:$PORT`
- Never hardcode a port number in production

### Environment Variables
If you need to set environment variables:
- Go to your service → "Environment"
- Add variables like:
  - `PYTHONUNBUFFERED=1` (recommended for Python apps)

### Free Tier Limitations
- Free tier services spin down after 15 minutes of inactivity
- First request after spin-down may take 30-60 seconds
- Consider upgrading to paid tier for always-on service

### Troubleshooting

**Build Fails:**
- Check build logs in Render dashboard
- Ensure all dependencies are in `requirements.txt`
- Verify Python version compatibility

**App Crashes:**
- Check runtime logs in Render dashboard
- Ensure `server = app.server` is in `app.py`
- Verify the start command is correct

**WebSocket Issues:**
- Render free tier may have limitations with WebSocket connections
- Consider using paid tier or alternative deployment for real-time features

## Updating the App

- **Automatic**: If auto-deploy is enabled, push to your main branch
- **Manual**: Go to Render dashboard → Your service → "Manual Deploy"

## Monitoring

- View logs: Service → "Logs" tab
- View metrics: Service → "Metrics" tab
- Set up alerts: Service → "Alerts"

## Custom Domain

1. Go to your service → "Settings"
2. Click "Add Custom Domain"
3. Follow the DNS configuration instructions

