import streamlit as st
import tempfile
import os
import time
from google import genai
from google.genai import types
from supabase import create_client, Client

# --- 1. SETTINGS & AUTHENTICATION ---
st.set_page_config(page_title="PromoVeo | Studio", page_icon="💬", layout="wide")

# --- HIDE STREAMLIT BRANDING ---
hide_st_style = """
            <style>
            #MainMenu {visibility: hidden;}
            footer {visibility: hidden;}
            header {visibility: hidden;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)

# --- CONNECT TO THE BRAIN (SUPABASE) ---
@st.cache_resource
def init_supabase():
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)

supabase = init_supabase()

# --- THE FRONT DESK (LOGIN/SIGNUP) ---
st.sidebar.title("🔐 Account Access")
auth_mode = st.sidebar.radio("Choose action", ["Log In", "Sign Up"])

email_input = st.sidebar.text_input("Email")
password_input = st.sidebar.text_input("Password", type="password")

if auth_mode == "Sign Up":
    if st.sidebar.button("Create Free Account"):
        response = supabase.table("users").select("*").eq("email", email_input).execute()
        if len(response.data) > 0:
            st.sidebar.error("Email already registered. Please log in.")
        elif email_input and password_input:
            new_user = {"email": email_input, "password": password_input}
            supabase.table("users").insert(new_user).execute()
            st.sidebar.success("Account created! Please switch to Log In.")
        else:
            st.sidebar.warning("Please enter an email and password.")
            
elif auth_mode == "Log In":
    if st.sidebar.button("Log In"):
        response = supabase.table("users").select("*").eq("email", email_input).eq("password", password_input).execute()
        if len(response.data) > 0:
            st.session_state["user"] = response.data[0] 
            st.sidebar.success("Logged in successfully!")
            st.rerun() 
        else:
            st.sidebar.error("Invalid email or password.")

# --- THE LOCK ---
if "user" not in st.session_state:
    st.info("👋 Welcome to PromoVeo Studio. Please Log In or Sign Up in the sidebar to start generating.")
    st.stop() 

# --- SHOW USER STATS ---
st.sidebar.markdown("---")
st.sidebar.markdown(f"**👤 User:** {st.session_state['user']['email']}")
st.sidebar.markdown(f"**💎 Tier:** {st.session_state['user']['tier']}")
st.sidebar.markdown(f"🎬 **Video Credits:** {st.session_state['user']['video_credits']}")
st.sidebar.markdown(f"🖼️ **Image Credits:** {st.session_state['user']['image_credits']}")
st.sidebar.markdown("---")

# Setup Google AI
api_key = st.secrets["GOOGLE_API_KEY"]
client = genai.Client(api_key=api_key)

# --- 2. CLEAN UI CSS ---
st.markdown("""
<style>
    /* Center the app and give it breathing room */
    .block-container { 
        padding-top: 2rem !important; 
        padding-bottom: 5rem !important; 
        max-width: 900px !important; 
    }
    
    /* Gently round the bottom chat input box */
    [data-testid="stChatInput"] { 
        border-radius: 20px !important; 
    }
    
    /* Style the User's message bubble (soft grey background) */
    [data-testid="stChatMessage"]:nth-child(odd) { 
        background-color: rgba(150, 150, 150, 0.1); 
        border-radius: 15px; 
        padding: 10px 20px; 
        margin-bottom: 10px; 
    }
    
    /* Style the AI's message bubble (clean and transparent) */
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
        st.session_state.messages = [{"role": "assistant", "content": "Canvas cleared. What are we building next?"}]
        st.rerun() 
        
    st.divider()
    st.markdown("### ⚙️ Generation Settings")
    engine = st.radio("Select AI Engine:", ["💬 Chat Assistant", "📸 Image (Fast)", "🎬 Video (Cinematic)"])
    uploaded_file = st.file_uploader("Reference Photo (Required for Video)", type=["jpg", "png", "jpeg"])

# --- 5. RENDER THE CHAT HISTORY ---
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if "image" in msg:
            st.image(msg["image"])
            st.download_button(label="⬇️ Download Image", data=msg["image"], file_name=f"promoveo_image_{i}.png", mime="image/png", key=f"dl_img_{i}")
        if "video" in msg:
            st.video(msg["video"])
            try:
                with open(msg["video"], "rb") as file:
                    st.download_button(label="⬇️ Download Video", data=file, file_name=f"promoveo_video_{i}.mp4", mime="video/mp4", key=f"dl_vid_{i}")
            except Exception:
                pass

# --- 6. THE CHAT INPUT BAR ---
if prompt := st.chat_input("Message PromoVeo (e.g., 'Write a script for my ad...'):"):

    # Display user message instantly
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user"):
        st.markdown(prompt)

    # --- AI PROCESSING LOGIC ---
    with st.chat_message("assistant"):
        
        # --- ENGINE 1: TEXT CHAT ---
        if engine == "💬 Chat Assistant":
            with st.spinner("Thinking..."):
                try:
                    response = client.models.generate_content(model='gemini-2.5-flash', contents=prompt)
                    st.markdown(response.text)
                    st.session_state.messages.append({"role": "assistant", "content": response.text})
                except Exception as e:
                    st.error(f"Chat API Error: {e}")
                    st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})

        # --- ENGINE 2: IMAGE ---
        elif engine == "📸 Image (Fast)":
            if st.session_state["user"]["image_credits"] <= 0:
                st.error("🚫 You are out of Image Credits! Please upgrade your plan.")
                st.session_state.messages.append({"role": "assistant", "content": "🚫 You are out of Image Credits! Please upgrade."})
            else:
                with st.spinner("🎨 Rendering cinematic image..."):
                    try:
                        result = client.models.generate_content(
                            model='gemini-2.5-flash-image',
                            contents=prompt,
                            config=types.GenerateContentConfig(response_modalities=["IMAGE"], image_config=types.ImageConfig(aspect_ratio="16:9"))
                        )
                        for part in result.parts:
                            if part.inline_data:
                                img_bytes = part.inline_data.data
                                st.image(img_bytes, use_container_width=True)
                                st.session_state.messages.append({"role": "assistant", "content": "Here is your generated image!", "image": img_bytes})
                                
                        # Deduct Credit on Success!
                        new_balance = st.session_state["user"]["image_credits"] - 1
                        supabase.table("users").update({"image_credits": new_balance}).eq("email", st.session_state["user"]["email"]).execute()
                        st.session_state["user"]["image_credits"] = new_balance
                        st.rerun() 
                        
                    except Exception as e:
                        st.error(f"API Error: {e}")
                        st.session_state.messages.append({"role": "assistant", "content": f"Error: {e}"})

        # --- ENGINE 3: VIDEO ---
        elif engine == "🎬 Video (Cinematic)":
            if st.session_state["user"]["video_credits"] <= 0:
                st.error("🚫 You are out of Video Credits! Please upgrade your plan.")
                st.session_state.messages.append({"role": "assistant", "content": "🚫 You are out of Video Credits! Please upgrade."})
            elif not uploaded_file:
                st.warning("⚠️ Please upload a Reference Photo in the sidebar to generate a video.")
                st.session_state.messages.append({"role": "assistant", "content": "⚠️ Please upload a Reference Photo."})
            else:
                with st.spinner("🎬 Rendering video (takes ~60 seconds)..."):
                    try:
                        with tempfile.NamedTemporaryFile(delete=False, suffix=".jpg") as temp_file:
                            temp_file.write(uploaded_file.getvalue())
                            temp_file_path = temp_file.name

                        input_image = types.Image.from_file(location=temp_file_path)
                        
                        operation = client.models.generate_videos(
                            model='veo-3.1-fast-generate-preview',
                            prompt=prompt,
                            image=input_image,
                            config=types.GenerateVideosConfig(aspect_ratio="16:9", duration_seconds=4)
                        )
                        
                        while not operation.done:
                            time.sleep(5)
                            operation = client.operations.get(operation=operation)
                            
                        os.remove(temp_file_path)

                        if operation.error:
                            error_msg = f"⚠️ AI Error (Safety Filter): {operation.error.message}"
                            st.error(error_msg)
                            st.session_state.messages.append({"role": "assistant", "content": error_msg})
                            
                        elif operation.result and operation.result.generated_videos:
                            generated_video = operation.result.generated_videos[0]
                            if generated_video.video and hasattr(generated_video.video, 'uri'):
                                output_path = f"promo_output_{int(time.time())}.mp4" 
                                import urllib.request
                                video_uri = generated_video.video.uri
                                download_url = f"{video_uri}&key={api_key}" if "?" in video_uri else f"{video_uri}?key={api_key}"
                                urllib.request.urlretrieve(download_url, output_path)

                                st.video(output_path)
                                st.session_state.messages.append({"role": "assistant", "content": "Here is your video ad!", "video": output_path})

                                # Deduct Credit on Success!
                                new_balance = st.session_state["user"]["video_credits"] - 1
                                supabase.table("users").update({"video_credits": new_balance}).eq("email", st.session_state["user"]["email"]).execute()
                                st.session_state["user"]["video_credits"] = new_balance
                                st.rerun() 

                            else:
                                error_msg = "⚠️ The AI processed the request but returned an empty box."
                                st.error(error_msg)
                                st.session_state.messages.append({"role": "assistant", "content": error_msg})
                        else:
                            error_msg = "⚠️ The AI processed the request but returned an empty box. Likely triggered safety filter."
                            st.error(error_msg)
                            st.session_state.messages.append({"role": "assistant", "content": error_msg})

                    except Exception as e:
                        st.error(f"Video API Error: {e}")
                        st.session_state.messages.append({"role": "assistant", "content": f"Video API Error: {e}"})