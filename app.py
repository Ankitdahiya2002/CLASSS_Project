import streamlit as st
from datetime import datetime

from src.db import (
    safe_initialize,
    get_user,
    get_user_chats,
    save_chat,
    get_uploaded_files,
    save_uploaded_file,
    delete_user_chats,
)

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
if "theme" not in st.session_state:
    st.session_state.theme = "Light"
if "chat_start_index" not in st.session_state:
    st.session_state.chat_start_index = 0


# ---------------- Theme Helper ----------------
def apply_theme(theme: str):
    if theme == "Dark":
        css = """
        <style>
        .stApp {
            background-color: #111111 !important;
            color: #FFFFFF !important;
        }
        </style>
        """
    else:
        css = """
        <style>
        .stApp {
            background-color: #FFFFFF !important;
            color: #000000 !important;
        }
        </style>
        """
    st.markdown(css, unsafe_allow_html=True)


# ---------------- Auto Scroll Helper ----------------
def scroll_to_bottom():
    st.markdown(
        """
        <script>
        var elem = window.parent.document.querySelector('.main');
        if (elem) { elem.scrollTop = elem.scrollHeight; }
        </script>
        """,
        unsafe_allow_html=True,
    )


# ---------------- Helper: Display Chat Bubble ----------------
def display_chat_bubble(sender, message, timestamp):
    theme = st.session_state.get("theme", "Light")

    if theme == "Dark":
        user_bg = "#005C4B"
        ai_bg = "#202C33"
        text_color = "white"
    else:
        user_bg = "#DCF8C6"
        ai_bg = "#F1F0F0"
        text_color = "black"

    bubble_style = (
        f"padding:10px; border-radius:12px; margin-bottom:5px; "
        f"max-width:60%; word-wrap:break-word; color:{text_color}; font-family:sans-serif;"
    )

    if sender == "user":
        st.markdown(
            f"""
            <div style='{bubble_style} background-color:{user_bg}; float:right; clear:both;'>
                <b style='color:{text_color};'>You:</b> {message}<br>
                <small style='color:{text_color};'>{timestamp}</small>
            </div>
            """,
            unsafe_allow_html=True
        )
    else:
        st.markdown(
            f"""
            <div style='{bubble_style} background-color:{ai_bg}; float:left; clear:both;'>
                <b style='color:{text_color};'>AI:</b> {message}<br>
                <small style='color:{text_color};'>{timestamp}</small>
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

    all_chats_db = get_user_chats(user_email)
    total_chats = len(all_chats_db)

    if st.session_state.chat_start_index > total_chats:
        st.session_state.chat_start_index = 0

    visible_chats = all_chats_db[st.session_state.chat_start_index:]

    # ---------- Sidebar ----------
    with st.sidebar:
        st.markdown(f"👋 Hi, **{user_name}**")

        theme_choice = st.radio(
            "Theme",
            ["Light", "Dark"],
            index=0 if st.session_state.theme == "Light" else 1,
        )
        st.session_state.theme = theme_choice

        if st.button("🆕 New Chat"):
            st.session_state.chat_start_index = total_chats
            st.success("Started a new chat (previous chats are still saved).")

        if st.button("📜 Show Previous Chat"):
            st.session_state.chat_start_index = 0
            st.success("Showing full conversation history.")

        if st.button("🧹 Clear Chat History"):
            delete_user_chats(user_email)
            st.session_state.chat_start_index = 0
            st.success("All chat history deleted from database.")

        if st.button("🔒 Logout"):
            st.session_state.user = None
            st.session_state.chat_start_index = 0
            st.rerun()

    apply_theme(st.session_state.theme)

    # ---------- File Upload ----------
    st.markdown("## 📁 Upload a File")
    uploaded_file = st.file_uploader("Upload file", type=["pdf", "txt", "xlsx", "csv"])
    if uploaded_file:
        try:
            extracted_text = extract_file(uploaded_file)
            save_uploaded_file(user_email, uploaded_file.name, uploaded_file.type, extracted_text)
            st.success("✅ File processed and saved.")
        except Exception as e:
            st.error(f"❌ Error: {e}")

    # ---------- Conversation Header + Search ----------
    col1, col2 = st.columns([5, 2])
    with col1:
        st.markdown("## 🕘 Conversation History")

    with col2:
        search_query = st.text_input(
            "Search messages",
            key="search_top",
            label_visibility="collapsed",
            placeholder="Search in conversation…",
        )

    if search_query:
        q = search_query.lower()
        displayed_chats = [
            c for c in visible_chats
            if q in c["user_input"].lower() or q in c["ai_response"].lower()
        ]
    else:
        displayed_chats = visible_chats

    for chat in displayed_chats:
        display_chat_bubble("user", chat["user_input"], chat["timestamp"])
        display_chat_bubble("ai", chat["ai_response"], chat["timestamp"])

    scroll_to_bottom()

    st.write("---")

    # ---------- Bottom chat bar ----------
    with st.form("chat_form_bottom"):
        colA, colB, colC = st.columns([5, 1.5, 1])

        with colA:
            new_message = st.text_input(
                "Message",
                key="bottom_input",
                label_visibility="collapsed",
                placeholder="Type your message...",
            )

        with colB:
            emoji = st.selectbox(
                "Emoji",
                ["", "😀", "😂", "😍", "😎", "🤖", "🙌", "👍", "👎", "❓"],
                key="emoji_picker",
                label_visibility="collapsed",
            )

        with colC:
            send_bottom = st.form_submit_button("Send")

    if send_bottom and (new_message.strip() or emoji):
        text = new_message.strip()
        if emoji:
            text = (text + " " + emoji).strip()

        context = visible_chats[-5:]
        history = "".join(
            f"User: {c['user_input']}\nAI: {c['ai_response']}\n\n"
            for c in context
        )
        prompt = history + f"User: {text}\nAI:"

        with st.spinner("Thinking... 🤖"):
            ai_reply = ai_chat_response(prompt)

        save_chat(user_email, text, ai_reply)


# ---------------- Main App ----------------
def main():
    query_params = st.query_params

    verify_tokens = query_params.get("verify_token")
    if verify_tokens:
        token = verify_tokens[0]
        if verify_user_token(token):
            st.sidebar.success("Email verified. Please log in.")
        else:
            st.sidebar.error("Invalid or expired verification link.")

    reset_tokens = query_params.get("reset_token")
    if reset_tokens:
        st.session_state.auth_mode = "reset"
        st.session_state.reset_token = reset_tokens[0]

    if not st.session_state.user:
        auth_page()
    else:
        user = get_user(st.session_state.user)
        if user.get("role") == "admin":
            show_admin_panel()
        else:
            show_user_panel()


if __name__ == "__main__":
    main()
