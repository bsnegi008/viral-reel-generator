import streamlit as st
import google.generativeai as genai

# Monkeypatch for MoviePy compatibility with Pillow 10+
try:
    import PIL.Image
    if not hasattr(PIL.Image, 'ANTIALIAS'):
        PIL.Image.ANTIALIAS = PIL.Image.LANCZOS
except Exception as e:
    st.warning(f"PIL patch warning: {e}")

from moviepy.editor import VideoFileClip, concatenate_videoclips, vfx, AudioFileClip, CompositeAudioClip
import tempfile
import os
import json
import time
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
st.set_page_config(page_title="AI Viral Reel Generator", layout="wide")

# --- Helper Functions ---

# --- Helper Functions ---

def upload_to_gemini(path, mime_type="video/mp4"):
    """Uploads the given file to Gemini."""
    file = genai.upload_file(path, mime_type=mime_type)
    return file

def wait_for_files_active(files):
    """Waits for the given files to be active."""
    for name in (file.name for file in files):
        file = genai.get_file(name)
        while file.state.name == "PROCESSING":
            time.sleep(2)
            file = genai.get_file(name)
        if file.state.name != "ACTIVE":
            raise Exception(f"File {file.name} failed to process")

def analyze_videos_with_gemini(api_key, video_files):
    """
    Uploads videos to Gemini and asks for a 'Perfect Cut' edit.
    """
    genai.configure(api_key=api_key)
    
    uploaded_files = []
    temp_paths = []

    try:
        for i, uploaded_file in enumerate(video_files):
            tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
            tfile.write(uploaded_file.read())
            tfile.close()
            temp_paths.append(tfile.name)
            
            gemini_file = upload_to_gemini(tfile.name)
            uploaded_files.append(gemini_file)
            uploaded_file.seek(0)

        wait_for_files_active(uploaded_files)

        generation_config = {
            "temperature": 0.7, # Lower temperature for more precise editing
            "top_p": 0.95,
            "top_k": 64,
            "max_output_tokens": 8192,
            "response_mime_type": "application/json",
        }

        model = genai.GenerativeModel(
            model_name="gemini-2.0-flash",
            generation_config=generation_config,
        )

        # --- THE PERFECT CUT PROMPT ---
        prompt = """
        You are an expert Video Editor & Director. Your goal is to turn this raw footage into a polished, viral-ready social media reel.
        
        **CRITICAL INSTRUCTIONS:**
        1.  **Analyze Audio & Visuals**: Listen for speech patterns and watch for visual stability.
        2.  **Identify Best Takes**: If the speaker repeats a sentence, choose ONLY the best, most fluent version. Discard the failed attempts.
        3.  **Remove Errors**: Cut out all stumbles, "umms", "ahhs", long pauses (dead air), and filler words.
        4.  **Remove Technical Flaws**: Cut out parts with camera shake, bad lighting shifts, or setup moments (e.g., looking at the camera before starting).
        5.  **Create Flow**: Select segments that flow naturally together to create a coherent narrative.
        
        **OUTPUT FORMAT:**
        Return a strictly valid JSON list of objects. Each object represents a clip to KEEP.
        [
            {
                "source_index": 0, // Index of the video file (0-based)
                "start_time": 10.5, // Start time in seconds (precise float)
                "end_time": 15.2,   // End time in seconds (precise float)
                "reason": "Clear delivery of intro, removed stutter"
            },
            ...
        ]
        
        **IMPORTANT:** 
        - The `start_time` and `end_time` must be precise. 
        - Do NOT include the "bad" parts. Only return the "good" parts to be stitched.
        - Ensure the total duration is reasonable (e.g., 15-60 seconds) unless the content dictates otherwise.
        """

        try:
            # Try up to 3 times with exponential backoff
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    response = model.generate_content([prompt] + uploaded_files)
                    break  # Success, exit retry loop
                except Exception as e:
                    if "429" in str(e) or "Resource exhausted" in str(e):
                        if attempt < max_retries - 1:
                            wait_time = (2 ** attempt) * 2  # 2s, 4s, 8s
                            st.warning(f"⏳ Rate limit hit. Waiting {wait_time} seconds before retry {attempt + 2}/{max_retries}...")
                            time.sleep(wait_time)
                        else:
                            raise Exception("Rate limit exceeded. Please wait a few minutes and try again, or use a different API key.")
                    else:
                        raise  # Re-raise if it's not a rate limit error
        except Exception as e:
            st.error(f"Error generating content: {e}")
            st.warning("Listing available models for your API key:")
            for m in genai.list_models():
                if 'generateContent' in m.supported_generation_methods:
                    st.write(f"- {m.name}")
            return None, temp_paths
        
        # Parse JSON with fallbacks for common formatting issues
        try:
            # Try direct parsing first
            segments = json.loads(response.text)
            return segments, temp_paths
        except json.JSONDecodeError:
            # Try to extract JSON from markdown code blocks
            import re
            
            # Look for ```json ... ``` or ``` ... ```
            json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response.text, re.DOTALL)
            if json_match:
                try:
                    segments = json.loads(json_match.group(1))
                    return segments, temp_paths
                except:
                    pass
            
            # Try to find JSON array in the text
            json_match = re.search(r'(\[.*\])', response.text, re.DOTALL)
            if json_match:
                try:
                    # Remove comments (// style)
                    cleaned = re.sub(r'//.*$', '', json_match.group(1), flags=re.MULTILINE)
                    segments = json.loads(cleaned)
                    return segments, temp_paths
                except:
                    pass
            
            st.error("Failed to parse JSON from Gemini response.")
            with st.expander("View Raw Response for Debugging"):
                st.code(response.text)
            return None, temp_paths

    except Exception as e:
        st.error(f"An error occurred during AI analysis: {e}")
        return None, temp_paths

def process_video_segments(segments, temp_paths, transition_type="None", audio_file=None, filter_type="None"):
    """
    Cuts, crops, and stitches the video segments with transitions, music, and filters.
    """
    clips = []
    
    try:
        for segment in segments:
            idx = segment['source_index']
            start = segment['start_time']
            end = segment['end_time']
            
            if idx >= len(temp_paths):
                continue
                
            original_clip = VideoFileClip(temp_paths[idx])
            
            # Validation
            if end > original_clip.duration:
                end = original_clip.duration
            if start >= end:
                continue
            if (end - start) < 0.5: # Skip extremely short clips (< 0.5s) that might be glitches
                continue
                
            sub = original_clip.subclip(start, end)
            
            # --- ZERO DISTORTION CROP & RESIZE ---
            
            target_w, target_h = 1080, 1920
            target_ratio = target_w / target_h  # 0.5625
            
            orig_w, orig_h = sub.w, sub.h
            orig_ratio = orig_w / orig_h
            
            # Step 1: Crop to exact 9:16 ratio
            if orig_ratio > target_ratio:
                # Landscape - crop width
                crop_w = int(orig_h * target_ratio)
                crop_h = orig_h
                x1 = (orig_w - crop_w) // 2
                y1 = 0
            else:
                # Portrait or square - crop height  
                crop_w = orig_w
                crop_h = int(orig_w / target_ratio)
                x1 = 0
                y1 = (orig_h - crop_h) // 2
            
            cropped = sub.crop(x1=x1, y1=y1, width=crop_w, height=crop_h)
            
            # Step 2: Resize to 1080x1920
            final_clip_base = cropped.resize((target_w, target_h))
            
            # --- Filters ---
            if filter_type == "Black & White":
                final_clip_base = final_clip_base.fx(vfx.blackwhite)
            elif filter_type == "Vibrant":
                final_clip_base = final_clip_base.fx(vfx.colorx, 1.3)
            elif filter_type == "Cinematic":
                final_clip_base = final_clip_base.fx(vfx.lum_contrast, 0, 30, 128)
            elif filter_type == "Vintage":
                final_clip_base = final_clip_base.fx(vfx.gamma_corr, 1.2)
                
            # --- Transitions ---
            if transition_type == "Crossfade (0.5s)":
                final_clip = final_clip_base.crossfadein(0.5)
            elif transition_type == "Fade In/Out":
                final_clip = final_clip_base.fadein(0.5).fadeout(0.5)
            else:
                final_clip = final_clip_base
                
            clips.append(final_clip)
            
        if not clips:
            return None

        final_video = concatenate_videoclips(clips, method="compose")
        
        # Add Background Music
        if audio_file:
            audio_temp = tempfile.NamedTemporaryFile(delete=False, suffix=".mp3")
            audio_temp.write(audio_file.read())
            audio_temp.close()
            
            music = AudioFileClip(audio_temp.name)
            
            if music.duration < final_video.duration:
                music = music.fx(vfx.loop, duration=final_video.duration)
            else:
                music = music.subclip(0, final_video.duration)
                
            music = music.volumex(0.2) # Lower volume for background
            
            final_audio = CompositeAudioClip([final_video.audio, music]) if final_video.audio else music
            final_video = final_video.set_audio(final_audio)
            
            os.remove(audio_temp.name)
        
        output_tfile = tempfile.NamedTemporaryFile(delete=False, suffix=".mp4")
        final_video.write_videofile(output_tfile.name, codec="libx264", audio_codec="aac", fps=24, preset='medium', threads=4)
        
        for clip in clips:
            clip.close()
            
        return output_tfile.name

    except Exception as e:
        st.error(f"Error processing video: {e}")
        return None

# --- Main UI ---

st.title("🎬 AI Director: The Perfect Cut")
st.markdown("Upload raw, messy footage. Get a **flawless, viral-ready reel** in seconds.")

# Sidebar
with st.sidebar:
    st.header("⚙️ Settings")
    api_key_input = st.text_input("Google Gemini API Key", type="password")
    api_key = api_key_input if api_key_input else os.getenv("GOOGLE_API_KEY")
    
    st.divider()
    
    st.header("🎨 Creative Studio")
    
    # Filters
    st.subheader("1. Visual Theme")
    filter_option = st.selectbox(
        "Choose a Look",
        ["None", "Black & White", "Vibrant", "Cinematic", "Vintage"]
    )
    
    # Transitions
    st.subheader("2. Transitions")
    transition_option = st.selectbox(
        "Transition Effect",
        ["None", "Crossfade (0.5s)", "Fade In/Out"]
    )
    
    # Music
    st.subheader("3. Audio Library")
    music_source = st.radio("Select Music Source", ["Upload MP3", "No Music"])
    
    bg_music = None
    if music_source == "Upload MP3":
        bg_music = st.file_uploader("Choose File", type=["mp3"])
    
    if not api_key:
        st.warning("Please enter your Google API Key.")

# Main Layout
col1, col2 = st.columns([1, 1])

with col1:
    st.subheader("📹 Raw Footage")
    uploaded_files = st.file_uploader("Upload 1 or more video files", type=["mp4", "mov"], accept_multiple_files=True)

    if uploaded_files and len(uploaded_files) > 4:
        st.error("Please upload a maximum of 4 videos.")
        uploaded_files = uploaded_files[:4]

    st.markdown("---")
    generate_btn = st.button("✨ Auto-Edit & Generate Reel", use_container_width=True)

with col2:
    st.subheader("🍿 Final Reel")
    result_placeholder = st.empty()


if generate_btn:
    if not api_key:
        st.error("API Key is missing!")
    elif not uploaded_files:
        st.error("Please upload at least one video.")
    else:
        with st.status("AI Director is working...", expanded=True) as status:
            # Step 1: AI Analysis
            status.write("🧠 Analyzing footage for best takes & removing errors...")
            segments, temp_paths = analyze_videos_with_gemini(api_key, uploaded_files)
            
            if segments:
                status.write("✅ Analysis Complete! Found the best segments.")
                with st.expander("View Edit Decision List"):
                    st.json(segments)
                
                # Step 2: Processing
                status.write(f"✂️ Stitching seamless reel with '{filter_option}' theme...")
                final_video_path = process_video_segments(segments, temp_paths, transition_option, bg_music, filter_option)
                
                if final_video_path:
                    status.update(label="Reel Ready!", state="complete", expanded=False)
                    
                    # Display in the second column
                    with result_placeholder.container():
                        st.video(final_video_path)
                        
                        with open(final_video_path, "rb") as file:
                            st.download_button(
                                label="Download Reel 📥",
                                data=file,
                                file_name="viral_reel.mp4",
                                mime="video/mp4",
                                use_container_width=True
                            )
                else:
                    status.update(label="Failed to generate video", state="error")
            else:
                status.update(label="Could not analyze videos", state="error")
            
        # Cleanup
        for path in temp_paths:
            try:
                os.remove(path)
            except:
                pass
