import streamlit as st
import hashlib
import uuid
from datetime import datetime, timedelta

from src.db import (
    create_user, get_user, update_reset_token,
    verify_user_credentials, reset_user_password_by_token,
    verify_user_token
)
from src.email_utils import send_verification_email, send_reset_email

# ---------------- Default auth mode ----------------
if "auth_mode" not in st.session_state:
    st.session_state.auth_mode = "login"

# ---------------- Main Auth Page ----------------
def auth_page():
    st.title("🔐 OMNISCIENT AI Assistant - Login")

    # Handle reset token in URL using st.query_params
    reset_tokens = st.query_params.get("reset_token")
    if reset_tokens:
        st.session_state.auth_mode = "reset"
        st.session_state.reset_token = reset_tokens[0]

    # Handle verify token in URL using st.query_params
    verify_tokens = st.query_params.get("verify_token")
    if verify_tokens:
        token = verify_tokens[0]
        if verify_user_token(token):
            st.sidebar.success("✅ Email verified. Please log in.")
        else:
            st.sidebar.error("❌ Invalid or expired verification link.")

    mode = st.session_state.get("auth_mode", "login")
    if mode == "login":
        login_form()
    elif mode == "signup":
        signup_form()
    elif mode == "forgot":
        forgot_password_form()
    elif mode == "reset":
        reset_password_form()

# ---------------- Login Form ----------------
def login_form():
    st.subheader("🔑 Login")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Login"):
        if email and password:
            if verify_user_credentials(email, password):
                st.session_state.user = email
                st.session_state.auth_mode = None
                st.success("✅ Logged in successfully.")
            else:
                st.error("❌ Invalid email or password.")
        else:
            st.warning("Please enter both email and password.")

    st.markdown("---")
    if st.button("👉 Sign Up"):
        st.session_state.auth_mode = "signup"
    if st.button("🔁 Forgot Password"):
        st.session_state.auth_mode = "forgot"

# ---------------- Signup Form ----------------
def signup_form():
    st.subheader("📝 Create Account")
    name = st.text_input("Name")
    profession = st.text_input("Profession")
    email = st.text_input("Email")
    password = st.text_input("Password", type="password")

    if st.button("Sign Up"):
        if name and email and password:
            hashed = hashlib.sha256(password.encode()).hexdigest()
            token = str(uuid.uuid4())
            success = create_user(email, hashed, name, profession, token)
            if success:
                send_verification_email(email, token)
                st.success("✅ Account created! Check your email to verify.")
                st.session_state.auth_mode = "login"
            else:
                st.error("❌ User already exists or error occurred.")
        else:
            st.warning("Please fill all fields.")

    if st.button("🔙 Back to Login"):
        st.session_state.auth_mode = "login"

# ---------------- Forgot Password Form ----------------
def forgot_password_form():
    st.subheader("🔁 Forgot Password")
    email = st.text_input("Enter your registered email")

    if st.button("Send Reset Link"):
        user = get_user(email)
        if user:
            token = str(uuid.uuid4())
            expiry = datetime.now() + timedelta(hours=1)
            update_reset_token(email, token, expiry)
            send_reset_email(email, token)
            st.success("📧 Reset link sent to your email.")
            st.session_state.auth_mode = "login"
        else:
            st.error("❌ Email not found.")

    if st.button("🔙 Back to Login"):
        st.session_state.auth_mode = "login"

# ---------------- Reset Password Form ----------------
def reset_password_form():
    st.subheader("🔑 Set New Password")
    token = st.session_state.get("reset_token")
    if not token:
        st.error("❌ Invalid or missing reset token.")
        return

    new_password = st.text_input("New Password", type="password")
    confirm_password = st.text_input("Confirm Password", type="password")

    if st.button("Reset Password"):
        if new_password != confirm_password:
            st.error("❌ Passwords do not match.")
            return

        hashed = hashlib.sha256(new_password.encode()).hexdigest()
        if reset_user_password_by_token(token, hashed):
            st.success("✅ Password reset successfully. You can now log in.")
            st.session_state.auth_mode = "login"
            st.session_state.pop("reset_token", None)
        else:
            st.error("❌ Invalid or expired token.")

    if st.button("🔙 Back to Login"):
        st.session_state.auth_mode = "login"
