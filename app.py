import streamlit as st
import tempfile
import os
import time
from google import genai
from google.genai import types

# --- 1. SETTINGS & AUTHENTICATION ---
st.set_page_config(page_title="PromoVeo | Studio", page_icon="💬", layout="wide")
# --- HIDE STREAMLIT BRANDING ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            /* Hides the top right menu and the entire header bar */
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- THE BOUNCER (PASSWORD LOCK) ---
app_password = st.sidebar.text_input("🔐 Enter Access Password:", type="password")

if app_password != "veDio03193524#myapp@": # You can change "founder2026" to any password you want
    st.sidebar.warning("Please enter the correct password to unlock the studio.")
    st.stop() # This entirely stops the rest of the code from running!

# (Keep your API key setup right below this)
api_key = st.secrets["GOOGLE_API_KEY"]
client = genai.Client(api_key=api_key)

# --- 2. PREMIUM CSS INJECTION ---
st.markdown("""
<style>
    /* Clean, centered UI */
    .block-container {
        padding-top: 2rem !important;
        padding-bottom: 5rem !important;
        max-width: 900px !important; 
    }
    /* Premium chat input box */
    [data-testid="stChatInput"] {
        border-radius: 25px !important;
        border: 1px solid #6366F1 !important;
        box-shadow: 0px 4px 15px rgba(99, 102, 241, 0.15) !important;
    }
    /* User message styling */
    [data-testid="stChatMessage"]:nth-child(odd) {
        background-color: rgba(99, 102, 241, 0.05);
        border-radius: 15px;
        padding: 10px 20px;
        margin-bottom: 10px;
        border-left: 3px solid #6366F1;
    }
    /* AI message styling */
    [data-testid="stChatMessage"]:nth-child(even) {
        background-color: transparent;
        padding: 10px 20px;
        margin-bottom: 10px;
    }
</style>
""", unsafe_allow_html=True)

# --- 3. APP MEMORY (SESSION STATE) ---
if "messages" not in st.session_state:
    st.session_state.messages = [
        {"role": "assistant", "content": "Welcome to PromoVeo Studio. 🎬\n\nSelect your engine in the sidebar. We can chat, generate images, or render cinematic videos!"}
    ]

# --- 4. THE SIDEBAR ---
with st.sidebar:
    st.title("🎬 PromoVeo")
    
    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        st.session_state.messages = [
            {"role": "assistant", "content": "Canvas cleared. What are we building next?"}
        ]
        st.rerun() 
        
    st.divider()
    st.markdown("### ⚙️ Generation Settings")
    
    # NEW: Added Chat Assistant to the menu
    engine = st.radio("Select AI Engine:", ["💬 Chat Assistant", "📸 Image (Fast)", "🎬 Video (Cinematic)"])
    uploaded_file = st.file_uploader("Reference Photo (Required for Video)", type=["jpg", "png", "jpeg"])

# --- 5. RENDER THE CHAT HISTORY ---
# We use 'enumerate' here to give every download button a unique mathematical ID 
# so Streamlit doesn't get confused if there are 10 videos on the screen!
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # If there is an image in the memory, draw it AND add a download button
        if "image" in msg:
            st.image(msg["image"])
            st.download_button(
                label="⬇️ Download Image",
                data=msg["image"],
                file_name=f"promoveo_image_{i}.png",
                mime="image/png",
                key=f"dl_img_{i}" # Unique ID
            )
            
        # If there is a video in the memory, draw it AND add a download button
        if "video" in msg:
            st.video(msg["video"])
            # We have to open the saved video file to let the user download it
            with open(msg["video"], "rb") as file:
                st.download_button(
                    label="⬇️ Download Video",
                    data=file,
                    file_name=f"promoveo_video_{i}.mp4",
                    mime="video/mp4",
                    key=f"dl_vid_{i}" # Unique ID
                )

# --- 6. THE CHAT INPUT BAR ---
if prompt := st.chat_input("Message PromoVeo (e.g., 'Write a script for my ad...'):"):
    
    # Save and display user message
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # AI Processing Logic
    with st.chat_message("assistant"):
        
        # --- ENGINE 1: TEXT CHAT ---
        if engine == "💬 Chat Assistant":
            with st.spinner("Thinking..."):
                try:
                    response = client.models.generate_content(
                        model='gemini-2.5-flash',
                        contents=prompt
                    )
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Chat API Error: {e}")
                    st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})

        # --- ENGINE 2: IMAGE ---
        elif engine == "📸 Image (Fast)":
            with st.spinner("🎨 Rendering cinematic image..."):
                try:
                    result = client.models.generate_content(
                        model='gemini-2.5-flash-image',
                        contents=prompt,
                        config=types.GenerateContentConfig(
                            response_modalities=["IMAGE"],
                            image_config=types.ImageConfig(aspect_ratio="16:9")
                        )
                    )
                    for part in result.parts:
                        if part.inline_data:
                            img_bytes = part.inline_data.data
                            st.image(img_bytes, use_container_width=True)
                            st.session_state.messages.append({
                                "role": "assistant", 
                                "content": "Here is your generated image! Anything else you'd like to try?", 
                                "image": img_bytes
                            })
                except Exception as e:
                    st.error(f"API Error: {e}")
                    st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})

       # --- ENGINE 3: VIDEO ---
        elif engine == "🎬 Video (Cinematic)":
            if not uploaded_file:
                st.warning("⚠️ Please upload a Reference Photo in the sidebar to generate a video.")
                st.session_state.messages.append({"role": "assistant", "content": "⚠️ Please upload a Reference Photo."})
            else:
                with st.spinner("🎬 Rendering video (takes ~60 seconds)..."):
                    try:
                        # 1. Use the bulletproof Temp File method that the Veo API strictly requires
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                            temp_file.write(uploaded_file.getvalue())
                            temp_file_path = temp_file.name

                        input_image = types.Image.from_file(location=temp_file_path)
                        
                        # 2. Start the video generation
                        operation = client.models.generate_videos(
                            model='veo-3.1-fast-generate-preview',
                            prompt=prompt,
                            image=input_image,
                            config=types.GenerateVideosConfig(aspect_ratio="16:9", duration_seconds=4)
                        )

                        # 3. Wait for it to finish
                        while not operation.done:
                            time.sleep(5)
                            operation = client.operations.get(operation=operation)

                        # 4. Clean up the temp file immediately
                        os.remove(temp_file_path)

                        # 5. Safely check if Google blocked the video (Safety Filters)
                        if operation.error:
                            error_msg = f"⚠️ AI Error (Safety Filter): {operation.error.message}"
                            st.error(error_msg)
                            st.session_state.messages.append({"role": "assistant", "content": error_msg})
                            
                       # 6. Safely extract and download the video
                        elif operation.result and operation.result.generated_videos:
                            generated_video = operation.result.generated_videos[0]
                            
                            # NEW: The Video object has a 'uri' (a download link), not a 'name'
                            if generated_video.video and hasattr(generated_video.video, 'uri'):
                                output_path = f"promo_output_{int(time.time())}.mp4" 
                                
                                # Use Python's built-in downloader to fetch the massive video file
                                import urllib.request
                                video_uri = generated_video.video.uri
                                
                                # Attach your API key to the link so Google knows you have permission to download it
                                download_url = f"{video_uri}&key={api_key}" if "?" in video_uri else f"{video_uri}?key={api_key}"
                                
                                urllib.request.urlretrieve(download_url, output_path)

                                st.video(output_path)
                                
                                # Save to memory and trigger the download button we built earlier!
                                st.session_state.messages.append({
                                    "role": "assistant", 
                                    "content": "Here is your video ad!", 
                                    "video": output_path
                                })
                            else:
                                error_msg = "⚠️ The AI processed the request but returned an empty box. Your prompt likely triggered a strict safety filter."
                                st.error(error_msg)
                                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                        # 7. Catch-all for silent failures
                        else:
                            error_msg = "⚠️ The AI processed the request but returned an empty box. Your prompt likely triggered a strict human/deepfake safety filter."
                            st.error(error_msg)
                            st.session_state.messages.append({"role": "assistant", "content": error_msg})

                    except Exception as e:
                        st.error(f"Video API Error: {e}")
                        st.session_state.messages.append({"role": "assistant", "content": f"Video API Error: {e}"})