import bcrypt
import streamlit as st
import speech_recognition as sr
from helper import (load_all_pdfs, split_documents, get_embeddings,
                    create_vector_store, load_vector_store)
from prompt import prompt
from langchain_groq import ChatGroq
from langchain_core.output_parsers import StrOutputParser
from dotenv import load_dotenv
import os
import json

load_dotenv()

st.set_page_config(page_title="Medical AI Assistant", page_icon="🏥", layout="wide")

st.markdown("""
<style>
/* Main Background */
.stApp {
    background: linear-gradient(135deg, #0a0f1e 0%, #0d1b2a 50%, #0a1628 100%);
}

/* Title */
h1 {
    background: linear-gradient(90deg, #00d4ff, #0099cc);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.5rem !important;
    font-weight: 800 !important;
}

/* Subheader */
h3 {
    color: #00d4ff !important;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background: linear-gradient(180deg, #0d1b2a 0%, #0a1628 100%) !important;
    border-right: 1px solid #00d4ff33;
}

[data-testid="stSidebar"] * {
    color: #e0f4ff !important;
}

/* Chat Messages - User */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
    background: linear-gradient(135deg, #0d2137, #0a1a2e) !important;
    border: 1px solid #00d4ff44 !important;
    border-radius: 15px !important;
    padding: 10px !important;
    margin: 5px 0 !important;
}

/* Chat Messages - Assistant */
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarAssistant"]) {
    background: linear-gradient(135deg, #0a2137, #071520) !important;
    border: 1px solid #00ff8844 !important;
    border-radius: 15px !important;
    padding: 10px !important;
    margin: 5px 0 !important;
}

/* Chat Input */
[data-testid="stChatInput"] {
    background: #0d1b2a !important;
    border: 2px solid #00d4ff !important;
    border-radius: 25px !important;
    color: white !important;
}

/* Buttons */
.stButton > button {
    background: linear-gradient(90deg, #00d4ff, #0099cc) !important;
    color: #0a0f1e !important;
    border: none !important;
    border-radius: 25px !important;
    font-weight: 700 !important;
    padding: 0.5rem 2rem !important;
    transition: all 0.3s ease !important;
}

.stButton > button:hover {
    transform: scale(1.05) !important;
    box-shadow: 0 0 20px #00d4ff66 !important;
}

/* Info boxes */
.stInfo {
    background: #0d2137 !important;
    border: 1px solid #00d4ff44 !important;
    border-radius: 10px !important;
    color: #e0f4ff !important;
}

/* Success boxes */
.stSuccess {
    background: #0d2a1a !important;
    border: 1px solid #00ff8844 !important;
    border-radius: 10px !important;
}

/* Download button */
[data-testid="stDownloadButton"] > button {
    background: linear-gradient(90deg, #00ff88, #00cc66) !important;
    color: #0a0f1e !important;
    border-radius: 25px !important;
    font-weight: 700 !important;
}

/* Radio buttons */
.stRadio label {
    color: #e0f4ff !important;
}

/* Text */
p, li, label {
    color: #e0f4ff !important;
}

/* Tabs */
.stTabs [data-baseweb="tab"] {
    background: #0d1b2a !important;
    color: #00d4ff !important;
    border-radius: 10px 10px 0 0 !important;
}

.stTabs [aria-selected="true"] {
    background: linear-gradient(90deg, #00d4ff22, #0099cc22) !important;
    border-bottom: 2px solid #00d4ff !important;
}

/* Input fields */
.stTextInput input {
    background: #0d1b2a !important;
    border: 1px solid #00d4ff44 !important;
    color: #e0f4ff !important;
    border-radius: 10px !important;
}

/* Spinner */
.stSpinner {
    color: #00d4ff !important;
}

/* Scrollbar */
::-webkit-scrollbar {
    width: 6px;
}
::-webkit-scrollbar-track {
    background: #0a0f1e;
}
::-webkit-scrollbar-thumb {
    background: #00d4ff44;
    border-radius: 3px;
}
</style>
""", unsafe_allow_html=True)

# ── Load Doctors ──────────────────────────────────────────────────────────────
if os.path.exists("doctors.json"):
    with open("doctors.json", "r") as f:
        DOCTORS = json.load(f)
else:
    DOCTORS = {
        "sanskar": "bit2022",
        "ankit": "bit2022",
        "doctor1": "medic123"
    }

# ── Chat History ──────────────────────────────────────────────────────────────
def save_chat_history(messages):
    with open("chat_history.json", "w") as f:
        json.dump(messages, f)

def load_chat_history():
    if os.path.exists("chat_history.json"):
        with open("chat_history.json", "r") as f:
            return json.load(f)
    return []

# ── Login Check ───────────────────────────────────────────────────────────────
def check_login(username, password):
    if username in DOCTORS:
        stored = DOCTORS[username]
        # Support both old plain text and new hashed passwords
        if stored.startswith("$2b$"):
            return bcrypt.checkpw(password.encode(), stored.encode())
        else:
            return stored == password
    return False

# ── Session State Init ────────────────────────────────────────────────────────
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False
if "username" not in st.session_state:
    st.session_state.username = ""
if "messages" not in st.session_state:
    st.session_state.messages = load_chat_history()

# ── Login Page ────────────────────────────────────────────────────────────────
def login_page():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align: center;'>🏥 Medical AI Assistant</h1>", unsafe_allow_html=True)
        st.markdown("<h4 style='text-align: center; color: gray;'>Doctor Portal</h4>", unsafe_allow_html=True)
        st.markdown("---")

        tab1, tab2 = st.tabs(["🔐 Login", "📝 Sign Up"])

        with tab1:
            username = st.text_input("👨‍⚕️ Username", key="login_user")
            password = st.text_input("🔒 Password", type="password", key="login_pass")
            if st.button("Login", use_container_width=True):
                if check_login(username, password):
                    st.session_state.logged_in = True
                    st.session_state.username = username
                    st.rerun()
                else:
                    st.error("❌ Invalid username or password!")

        with tab2:
            new_name = st.text_input("👨‍⚕️ Full Name", key="signup_name")
            new_user = st.text_input("👤 Username", key="signup_user")
            new_pass = st.text_input("🔒 Password", type="password", key="signup_pass")
            confirm_pass = st.text_input("🔒 Confirm Password", type="password", key="confirm_pass")

            if st.button("Sign Up", use_container_width=True):
                if not new_name or not new_user or not new_pass:
                    st.error("❌ Please fill all fields!")
                elif new_pass != confirm_pass:
                    st.error("❌ Passwords do not match!")
                elif new_user in DOCTORS:
                    st.error("❌ Username already exists!")
                else:
                   # Hash password before saving
                   hashed = bcrypt.hashpw(new_pass.encode(), bcrypt.gensalt()).decode()
                   DOCTORS[new_user] = hashed
                   with open("doctors.json", "w") as f:
                       json.dump(DOCTORS, f)
    st.success(f"✅ Account created! Welcome Dr. {new_name}!")
    st.info("Please login now!")

# ── Show Login if not logged in ───────────────────────────────────────────────
if not st.session_state.logged_in:
    login_page()
    st.stop()

# ── LLM & Vector Store ────────────────────────────────────────────────────────
@st.cache_resource
def load_llm():
    return ChatGroq(
        groq_api_key=os.getenv("GROQ_API_KEY"),
        model_name="llama-3.3-70b-versatile",
        temperature=0.2,
        max_tokens=200
    )

@st.cache_resource
def initialize_vectorstore():
    embeddings = get_embeddings()
    try:
        vectorstore = load_vector_store(embeddings)
        st.sidebar.success("✅ Knowledge Base Loaded!")
    except:
        st.sidebar.warning("⚠️ Creating Knowledge Base...")
        docs = load_all_pdfs("data/")
        chunks = split_documents(docs)
        vectorstore = create_vector_store(chunks, embeddings)
        st.sidebar.success("✅ Knowledge Base Created!")
    return vectorstore

# ── Sidebar ───────────────────────────────────────────────────────────────────
st.sidebar.title("📋 About")
st.sidebar.info("""
**Medical AI Assistant**
- Built with RAG Pipeline
- Powered by Groq (Llama3)
- ChromaDB Vector Store
- BIT Mesra CS400 Project
""")

st.sidebar.title("🌍 Response Language")
language = st.sidebar.radio("Choose Language:", ["English", "Hindi", "Spanish"], index=0)

st.sidebar.title("👨‍💻 Developer")
st.sidebar.info("""
**Sanskar Agrawal**
BTECH/10589/22
BIT Mesra
""")

st.sidebar.markdown("---")
st.sidebar.title("👨‍⚕️ Welcome!")
st.sidebar.info(f"Dr. {st.session_state.username.capitalize()}")
if st.sidebar.button("🚪 Logout"):
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.messages = []
    st.rerun()

# ── Main App ──────────────────────────────────────────────────────────────────
st.title("🏥 Medical AI Assistant")
st.subheader("Intelligent Clinical Query Resolution System for Doctors")

vectorstore = initialize_vectorstore()
llm = load_llm()


def voice_input():
    r = sr.Recognizer()
    with sr.Microphone() as source:
        st.info("🎤 Listening... Speak now!")
        r.adjust_for_ambient_noise(source, duration=1)
        try:
            audio = r.listen(source, timeout=5, phrase_time_limit=10)
            text = r.recognize_google(audio)
            return text
        except sr.WaitTimeoutError:
            st.error("⏱️ Timeout! Please try again.")
            return None
        except sr.UnknownValueError:
            st.error("❌ Could not understand! Please try again.")
            return None
        except sr.RequestError:
            st.error("❌ Internet connection required for voice input!")
            return None

# ── Get Answer ────────────────────────────────────────────────────────────────
def get_answer(query, vectorstore, llm, language="English"):
    retriever = vectorstore.as_retriever(search_kwargs={"k": 3})
    docs = retriever.invoke(query)
    context = "\n".join([doc.page_content for doc in docs])

    history = ""
    for msg in st.session_state.messages[-6:]:
        role = "Doctor" if msg["role"] == "user" else "Assistant"
        history += f"{role}: {msg['content']}\n"

    chain = prompt | llm | StrOutputParser()
    answer = chain.invoke({
        "context": context,
        "question": query,
        "history": history,
        "language": language
    })
    return answer

# Voice Input Button
col1, col2 = st.columns([6, 1])
with col2:
    if st.button("🎤 Voice"):
        voice_text = voice_input()
        if voice_text:
            st.session_state.voice_query = voice_text
            st.success(f"✅ You said: {voice_text}")
            st.rerun()

# Check voice query
if "voice_query" in st.session_state and st.session_state.voice_query:
    query = st.session_state.voice_query
    st.session_state.voice_query = None
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)
    with st.chat_message("assistant"):
        with st.spinner("🔍 Searching medical knowledge base..."):
            answer = get_answer(query, vectorstore, llm, language)
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            save_chat_history(st.session_state.messages)


# ── Chat Interface ────────────────────────────────────────────────────────────
st.markdown("### 💬 Ask a Medical Question")

for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

if query := st.chat_input("e.g. What is the best treatment for Type-2 Diabetes?"):
    st.session_state.messages.append({"role": "user", "content": query})
    with st.chat_message("user"):
        st.markdown(query)

    with st.chat_message("assistant"):
        with st.spinner("🔍 Searching medical knowledge base..."):
            answer = get_answer(query, vectorstore, llm, language)
            st.markdown(answer)
            st.session_state.messages.append({"role": "assistant", "content": answer})
            save_chat_history(st.session_state.messages)

# ── Download Chat History ─────────────────────────────────────────────────────
if st.session_state.messages:
    chat_text = ""
    for msg in st.session_state.messages:
        role = "Doctor" if msg["role"] == "user" else "Medical AI"
        chat_text += f"{role}: {msg['content']}\n\n"

    st.download_button(
        label="📥 Download Chat History",
        data=chat_text,
        file_name="medical_chat_history.txt",
        mime="text/plain"
    )