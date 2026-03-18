import streamlit as st
import tempfile
import os
import time
from google import genai
from google.genai import types
from supabase import create_client, Client
import uuid
import json

# --- 1. SETTINGS & AUTHENTICATION ---
st.set_page_config(page_title="PromoVeo | Studio", page_icon="💬", layout="wide")

# --- HIDE STREAMLIT BRANDING (THE FEATHER-TOUCH METHOD) ---
hide_st_style = """
            <style>
            /* 1. Hide the Deploy button specifically */
            .stAppDeployButton {display: none !important;}
            
            /* 2. Hide the 3-dots Main Menu */
            #MainMenu {display: none !important;}
            
            /* 3. Hide the colored decoration line at the top */
            [data-testid="stDecoration"] {display: none !important;}
            </style>
            """
st.markdown(hide_st_style, unsafe_allow_html=True)
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

# --- SHOW USER STATS & ACTIONS ---
st.sidebar.markdown("---")
st.sidebar.markdown(f"**👤 User:** {st.session_state['user']['email']}")
st.sidebar.markdown(f"**💎 Tier:** {st.session_state['user']['tier']}")
st.sidebar.markdown(f"🎬 **Video Credits:** {st.session_state['user']['video_credits']}")
st.sidebar.markdown(f"🖼️ **Image Credits:** {st.session_state['user']['image_credits']}")

# --- NEW: LOGOUT BUTTON ---
if st.sidebar.button("🚪 Log Out", use_container_width=True):
    # Delete user from memory and reset the chat
    del st.session_state["user"]
    st.session_state.messages = [{"role": "assistant", "content": "Welcome to PromoVeo Studio. 🎬\n\nSelect your engine in the sidebar. We can chat, generate images, or render cinematic videos!"}]
    st.rerun() # Refresh to lock the app

# --- NEW: SAVE CHAT BUTTON ---
# We wrap this in an 'if' statement so it doesn't crash on a hard refresh!
if "messages" in st.session_state:
    chat_text = "\n\n".join([f"{msg['role'].upper()}:\n{msg['content']}" for msg in st.session_state.messages if "content" in msg])
    st.sidebar.download_button(
        label="💾 Download Chat History",
        data=chat_text,
        file_name="promoveo_chat_history.txt",
        mime="text/plain",
        use_container_width=True
    )
st.sidebar.markdown("---")

# Setup Google AI
api_key = st.secrets["GOOGLE_API_KEY"]
client = genai.Client(api_key=api_key)

# --- 2. MOBILE-OPTIMIZED CLEAN UI CSS ---
# --- 2. MOBILE-OPTIMIZED CLEAN UI CSS (v1.0.1) ---
st.markdown(f"""
<style>
    /* ... (rest of your CSS code here) ... */
</style>
""", unsafe_allow_html=True)
st.markdown("""
<style>
    /* 1. Base Desktop Styling (Mac) */
    .block-container { 
        padding-top: 2rem !important; 
        padding-bottom: 6rem !important; 
        max-width: 900px !important; 
    }
    [data-testid="stChatInput"] { border-radius: 20px !important; }
    [data-testid="stChatMessage"]:nth-child(odd) { 
        background-color: rgba(150, 150, 150, 0.1); 
        border-radius: 15px; 
        padding: 10px 20px; 
        margin-bottom: 10px; 
    }
    [data-testid="stChatMessage"]:nth-child(even) { 
        background-color: transparent; 
        padding: 10px 20px; 
        margin-bottom: 10px; 
    }

    /* 2. iPhone / Mobile Responsiveness Fix */
    @media (max-width: 768px) {
        .block-container { 
            padding-top: 1rem !important; 
            /* Extra padding at the bottom so the iOS Safari URL bar doesn't hide the chat input */
            padding-bottom: 8rem !important; 
            padding-left: 0.5rem !important;
            padding-right: 0.5rem !important;
        }
        
        /* Make chat bubbles slightly tighter so text doesn't squish */
        [data-testid="stChatMessage"]:nth-child(odd) { 
            padding: 12px 15px !important; 
            border-radius: 12px;
        }
        [data-testid="stChatMessage"]:nth-child(even) { 
            padding: 10px 10px !important; 
        }
    }
</style>
""", unsafe_allow_html=True)
# --- 3. APP MEMORY (SESSION STATE) ---
if "messages" not in st.session_state:
    st.session_state.messages = [{"role": "assistant", "content": "Welcome to PromoVeo Studio. 🎬\n\nSelect your engine in the sidebar. We can chat, generate images, or render cinematic videos!"}]
if "current_chat_id" not in st.session_state:
    st.session_state["current_chat_id"] = None

# HELPER FUNCTION: Safely save cloud URLs to the database
def get_clean_messages_for_db():
    clean_msgs = []
    for msg in st.session_state.messages:
        clean_msg = {"role": msg["role"], "content": msg["content"]}
        # Catch the image and video URLs!
        if "image_url" in msg:
            clean_msg["image_url"] = msg["image_url"]
        if "video_url" in msg:
            clean_msg["video_url"] = msg["video_url"]
        clean_msgs.append(clean_msg)
    return clean_msgs
# HELPER FUNCTION: Save current chat to Supabase (with Loud Debugger)
def save_chat_to_cloud(user_prompt):
    try:
        # Grab the clean messages
        clean_msgs = get_clean_messages_for_db()
        
        if st.session_state["current_chat_id"] is None:
            # Create a brand new chat
            title = user_prompt[:25] + "..." if len(user_prompt) > 25 else user_prompt
            new_chat = {
                "user_email": st.session_state["user"]["email"],
                "title": title,
                "messages": clean_msgs # Supabase SDK usually handles this, but let's be safe
            }
            res = supabase.table("conversations").insert(new_chat).execute()
            
            # Save the new database ID to memory
            if res.data:
                st.session_state["current_chat_id"] = res.data[0]["id"]
        else:
            # Update the existing chat
            supabase.table("conversations").update({"messages": clean_msgs}).eq("id", st.session_state["current_chat_id"]).execute()
            
    except Exception as e:
        # THE LOUD DEBUGGER: If it fails silently, force it to show us why!
        st.error(f"🚨 Cloud Save Error: {e}")

# --- 4. THE SIDEBAR ---
with st.sidebar:
    st.title("🎬 PromoVeo")
    if st.button("➕ New Chat", use_container_width=True, type="primary"):
        st.session_state.messages = [{"role": "assistant", "content": "Canvas cleared. What are we building next?"}]
        st.rerun() 
    st.divider()
    
    # --- FETCH & DISPLAY PAST CHATS ---
    st.markdown("### 🕰️ Past Chats")
    try:
        # Fetch the last 5 conversations from Supabase
        past_chats = supabase.table("conversations").select("id, title").eq("user_email", st.session_state["user"]["email"]).order("created_at", desc=True).limit(5).execute()
        
        if past_chats.data:
            for chat in past_chats.data:
                # If they click an old chat, load it from the database into memory!
                if st.button(f"💬 {chat['title']}", key=chat["id"], use_container_width=True):
                    full_chat = supabase.table("conversations").select("messages").eq("id", chat["id"]).execute()
                    if full_chat.data:
                        st.session_state.messages = full_chat.data[0]["messages"]
                        st.session_state["current_chat_id"] = chat["id"]
                        st.rerun()
        else:
            st.caption("No past chats yet.")
    except Exception as e:
        st.caption("Could not load past chats.")
        
    st.divider()    
    st.divider()
    st.markdown("### ⚙️ Generation Settings")
    engine = st.radio("Select AI Engine:", ["💬 Chat Assistant", "📸 Image (Fast)", "🎬 Video (Cinematic)"])
    uploaded_file = st.file_uploader("Reference Photo (Required for Video)", type=["jpg", "png", "jpeg"])

# --- 5. RENDER THE CHAT HISTORY ---
for i, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        
        # Draw Image from Cloud
        if "image_url" in msg:
            st.image(msg["image_url"])
            st.markdown(f"[⬇️ Download Image]({msg['image_url']})")
            
        # Draw Video from Cloud
        if "video_url" in msg:
            st.video(msg["video_url"])
            st.markdown(f"[⬇️ Open Video to Download]({msg['video_url']})")

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

                    save_chat_to_cloud(prompt) # SAVE TO DATABASE
                    st.rerun() # <--- ADD THIS LINE! Forces the sidebar to update instantly!

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
                                # --- UPLOAD TO SUPABASE CLOUD ---
                                file_name = f"image_{uuid.uuid4().hex}.png"
                                supabase.storage.from_("promoveo_assets").upload(file=img_bytes, path=file_name, file_options={"content-type": "image/png"})
                                public_url = supabase.storage.from_("promoveo_assets").get_public_url(file_name)
                                
                                # Save URL to memory and display
                                st.session_state.messages.append({"role": "assistant", "content": "Here is your generated image!", "image_url": public_url})
                                
                                
                        save_chat_to_cloud(prompt) # SAVE TO DATABASE
                                
                        # Deduct Credit on Success!
                        save_chat_to_cloud(prompt)
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
                                urllib.request.urlretrieve(download_url, output_path)

                                # --- UPLOAD TO SUPABASE CLOUD ---
                                file_name = f"video_{uuid.uuid4().hex}.mp4"
                                with open(output_path, "rb") as f:
                                    supabase.storage.from_("promoveo_assets").upload(file=f, path=file_name, file_options={"content-type": "video/mp4"})
                                public_url = supabase.storage.from_("promoveo_assets").get_public_url(file_name)

                                # Save URL to memory and display
                                st.session_state.messages.append({"role": "assistant", "content": "Here is your video ad!", "video_url": public_url})
                                st.video(public_url)

                                save_chat_to_cloud(prompt) # SAVE TO DATABASE
                                # Deduct Credit on Success!
                                save_chat_to_cloud(prompt)
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