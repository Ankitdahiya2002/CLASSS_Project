import streamlit as st
from datetime import datetime
from src.db import safe_initialize, get_user, get_user_chats, save_chat, get_uploaded_files, save_uploaded_file
from src.auth import auth_page, verify_user_token
from src.admin import show_admin_panel
from src.helper import ai_chat_response
from src.file_reader import extract_file
from src.translation import to_english, to_hindi

# ---------------- Page Config ----------------
st.set_page_config(page_title="WINGMAN AI Assistant", page_icon="🤖", layout="wide")

# ---------------- DB Initialization ----------------
safe_initialize()

# ---------------- Session Defaults ----------------
if "user" not in st.session_state:
    st.session_state.user = None
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

# ---------------- Helper: Display Chat Bubble ----------------
# ---------------- Helper: Display Chat Bubble ----------------
def display_chat_bubble(sender, message, timestamp):
    bubble_style = (
        "padding:10px; border-radius:12px; margin-bottom:5px; "
        "max-width:60%; word-wrap:break-word; color:black; font-family:sans-serif;"
    )

    if sender == "user":
        st.markdown(
            f"""
            <div style='{bubble_style} background-color:#DCF8C6; float:right; clear:both;'>
                <b style='color:black;'>You:</b> {message}<br>
                <small style='color:black;'>{timestamp}</small>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"""
            <div style='{bubble_style} background-color:#F1F0F0; float:left; clear:both;'>
                <b style='color:black;'>AI:</b> {message}<br>
                <small style='color:black;'>{timestamp}</small>
            </div>
            """,
            unsafe_allow_html=True
        )


# ---------------- User Panel ----------------
def show_user_panel():
    if not st.session_state.user:
        st.warning("Please log in first.")
        st.stop()

    user_email = st.session_state.user
    user = get_user(user_email)
    user_name = user.get("name", "User")

    # Sidebar
    with st.sidebar:
        st.markdown(f"👋 Hi, **{user_name}**")
        if st.button("🔒 Logout"):
            st.session_state.user = None
            st.session_state.chat_history = []
            st.rerun()
        st.title("⚙️ Settings")
        language = st.selectbox("🌐 Language", ["English 🇺🇸", "Hindi 🇮🇳"], index=0, disabled=True)

    # File Upload
    st.markdown("## 📁 Upload a File")
    uploaded_file = st.file_uploader("Choose a file", type=["pdf", "txt", "xlsx", "csv"])
    if uploaded_file:
        file_name = uploaded_file.name
        file_type = uploaded_file.type
        try:
            extracted_text = extract_file(uploaded_file)
            save_uploaded_file(user_email, file_name, file_type, extracted_text)
            st.success(f"✅ File `{file_name}` processed and saved.")
            with st.expander("📄 Preview Extracted Text"):
                st.text_area("Content", extracted_text[:2000], height=300)
        except Exception as e:
            st.error(f"❌ Error processing file: {e}")

    # Show uploaded files
    st.markdown("## 🗂️ Your Uploaded Files")
    uploaded_files = get_uploaded_files(user_email)
    if uploaded_files:
        for file in uploaded_files:
            with st.expander(f"{file['file_name']} ({file['file_type']}) - {file['timestamp']}"):
                st.markdown(f"**File Name:** {file['file_name']}")
                st.markdown(f"**Type:** {file['file_type']}")
                st.markdown(f"**Uploaded on:** {file['timestamp']}")
    else:
        st.info("You haven't uploaded any files yet.")

    # Chat Input
    with st.form("chat_form"):
        user_input = st.text_input("Type your message here:")
        submitted = st.form_submit_button("Send")

    if submitted and user_input.strip():
        text = user_input.strip()
        translated_input = to_english(text) if language.startswith("Hindi") else text

        # Load last 5 chats for context
        past_chats = get_user_chats(user_email)[-5:]
        history = ""
        for chat in past_chats:
            history += f"User: {chat['user_input'][:500]}\nAI: {chat['ai_response'][:500]}\n\n"
        prompt = history + f"User: {translated_input}\nAI:"

        with st.spinner("Thinking... 🤖"):
            response = ai_chat_response(prompt)
            if language.startswith("Hindi"):
                response = to_hindi(response)

        # Save chat to session and DB
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        st.session_state.chat_history.append({"user": text, "ai": response, "timestamp": timestamp})
        save_chat(user_email, text, response, thread_id=None)

    # Display chat history
    st.markdown("## 🕘 Conversation History")
    for chat in st.session_state.get("chat_history", []):
        display_chat_bubble("user", chat["user"], chat["timestamp"])
        display_chat_bubble("ai", chat["ai"], chat["timestamp"])

# ---------------- Main App ----------------
def main():
    query_params = st.query_params  # Use only st.query_params

    # Email verification via URL token
    verify_tokens = query_params.get("verify_token")
    if verify_tokens:
        token = verify_tokens[0]
        if verify_user_token(token):
            st.sidebar.success("✅ Email verified. Please log in.")
        else:
            st.sidebar.error("❌ Invalid or expired verification link.")

    # Password reset via URL token
    reset_tokens = query_params.get("reset_token")
    if reset_tokens:
        st.session_state.auth_mode = "reset"
        st.session_state.reset_token = reset_tokens[0]

    # Show login/signup/reset if not logged in
    if not st.session_state.user:
        auth_page()
    else:
        user_email = st.session_state.user
        user = get_user(user_email)
        if user.get("role") == "admin":
            show_admin_panel()
        else:
            show_user_panel()

if __name__ == "__main__":
    main()
