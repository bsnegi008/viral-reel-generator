# AI Viral Reel Generator

Automatically transform raw footage into polished, viral-ready social media reels using AI.

## Features

- 🤖 AI-powered video analysis (removes mistakes, selects best takes)
- ✂️ Automatic editing and cutting
- 🎨 Visual themes and filters
- 🎵 Background music support
- 📱 Perfect 9:16 vertical format for TikTok/Instagram

## How to Use

1. Upload your raw video footage (1-4 videos)
2. Choose a visual theme and transition style
3. Add background music (optional)
4. Click "Auto-Edit & Generate Reel"
5. Download your viral-ready reel!

## Setup (Local Development)

```bash
# Install dependencies
pip install -r requirements.txt

# Set your Gemini API key
echo "GOOGLE_API_KEY=your_key_here" > .env

# Run the app
streamlit run app.py
```

## Deployment to Streamlit Cloud

See DEPLOYMENT.md for instructions.

## Tech Stack

- **Streamlit**: Web interface
- **Google Gemini 2.0 Flash**: AI video analysis
- **MoviePy**: Video processing
- **Python**: Backend logic

## License

MIT
# viral-reel-generator
