# Deployment Instructions

## Deploy to Streamlit Cloud (FREE)

### Step 1: Create GitHub Repository

```bash
cd /Users/apple/.gemini/antigravity/scratch/viral_reel_generator

# Initialize git
git init

# Add all files
git add .

# Commit
git commit -m "Initial commit - AI Viral Reel Generator"
```

### Step 2: Push to GitHub

1. Go to https://github.com and create a new repository
2. Name it: `viral-reel-generator`
3. Make it **Public**
4. Don't add README (we already have one)
5. Copy the commands shown and run them:

```bash
git remote add origin https://github.com/YOUR_USERNAME/viral-reel-generator.git
git branch -M main
git push -u origin main
```

### Step 3: Deploy to Streamlit Cloud

1. Go to https://share.streamlit.io
2. Click "New app"
3. Select your repository: `YOUR_USERNAME/viral-reel-generator`
4. Main file path: `app.py`
5. Click "Deploy"

### Step 4: Add Secrets (API Key)

1. In Streamlit Cloud dashboard, click your app
2. Click "⋮" → "Settings" → "Secrets"
3. Add:
```toml
GOOGLE_API_KEY = "your_gemini_api_key_here"
```
4. Click "Save"

### Step 5: Get Your Live Link

Your app will be live at:
```
https://YOUR_APP_NAME.streamlit.app
```

Share this link with your 10 testers!

## Troubleshooting

**App won't start?**
- Check the logs in Streamlit Cloud dashboard
- Make sure all dependencies are in requirements.txt
- Verify API key is set correctly

**Rate limiting?**
- Users need to wait between requests (free tier)
- Consider getting a paid Gemini API key

**Video processing slow?**
- Normal for large videos
- Consider limiting video duration/size

## Next Steps

Once testing is successful:
1. Add Google Analytics
2. Create feedback form
3. Build email collection
4. Launch on ProductHunt
