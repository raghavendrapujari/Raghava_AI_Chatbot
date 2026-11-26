import os
import io
import json
import uuid
import base64
import html
from datetime import datetime, date, time as dt_time
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
from groq import Groq
from PIL import Image
from pypdf import PdfReader
from docx import Document


# ============================================================
# CONFIGURATION
# ============================================================

st.set_page_config(
    page_title="Raghava AI Assistant",
    page_icon="✦",
    layout="wide",
    initial_sidebar_state="expanded",
)

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env", override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()
CHAT_MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b").strip()
VISION_MODEL = os.getenv(
    "GROQ_VISION_MODEL",
    "meta-llama/llama-4-scout-17b-16e-instruct",
).strip()
WHISPER_MODEL = os.getenv("GROQ_WHISPER_MODEL", "whisper-large-v3").strip()

CHATS_FILE = BASE_DIR / "chats.json"
PROJECTS_FILE = BASE_DIR / "projects.json"
SCHEDULED_FILE = BASE_DIR / "scheduled.json"
IMAGES_DIR = BASE_DIR / "images"
LIBRARY_DIR = BASE_DIR / "library"
FILE_TYPES = ["pdf", "docx", "txt", "png", "jpg", "jpeg", "webp"]

USER_NAME = "Raghava"

SYSTEM_PROMPT = """
You are Raghava AI, a helpful, reliable personal AI assistant.

LANGUAGE:
- Always reply in English only.
- Do not reply in Telugu, Hindi, or any other language.
- Use clear, natural English.

STYLE:
- Be friendly, professional, and concise unless detail is requested.
- Explain programming and AI concepts step by step.
- When asked for code, provide complete, runnable examples.
- Use attached documents and images as the main source when the user asks about them.
- Never claim to have performed an action that you did not perform.
"""

SUGGESTIONS = [
    ("✏️", "Write or edit", "Help me write or edit a piece of text. Ask me what it is about."),
    ("💻", "Write or debug code", "Help me write or debug some Python code. Ask me what I am building."),
    ("🧠", "Explain a concept", "Explain a concept to me step by step. Ask me which topic."),
]

# Sidebar navigation: (view id, label, material icon)
NAV_ITEMS = [
    ("chat", "New Chat", ":material/edit_square:"),
    ("search", "Search", ":material/search:"),
    ("images", "Images", ":material/image:"),
    ("scheduled", "Scheduled", ":material/event:"),
    ("library", "Library", ":material/library_books:"),
    ("plugins", "Plugins", ":material/extension:"),
    ("explore", "Explore", ":material/apps:"),
]

# Explore page: category -> list of (title, description, prompt)
EXPLORE = {
    "Writing": [
        ("Professional email", "Draft a clear, polite email.",
         "Help me write a professional email. Ask me who it is for and what I want to say."),
        ("Improve my text", "Fix grammar and make it read better.",
         "I will paste a paragraph. Please improve its grammar, clarity and tone. Ask me for the text."),
        ("Summarize anything", "Turn long text into key points.",
         "I will paste some text. Please summarize it into short key points. Ask me for the text."),
    ],
    "Coding": [
        ("Explain Python code", "Understand code line by line.",
         "I will paste some Python code. Please explain it step by step. Ask me for the code."),
        ("Debug an error", "Find and fix a bug.",
         "Help me debug a Python error. Ask me for the code and the full error message."),
        ("Build a mini project", "Get a complete runnable example.",
         "Suggest a small Python project for practice and give me complete, runnable code for it."),
    ],
    "Study and career": [
        ("Study plan", "A realistic weekly plan.",
         "Create a weekly study plan for me. Ask me the topic, my deadline and how many hours I have per day."),
        ("Mock interview", "Practice questions one by one.",
         "Act as an interviewer and run a mock interview with me. Ask me the role first, then ask one question at a time."),
        ("Explain simply", "Any concept in plain words.",
         "Explain a concept to me in simple words with an example. Ask me which concept."),
    ],
    "Ideas and planning": [
        ("Project ideas", "Brainstorm things to build.",
         "Brainstorm 10 project ideas for me. Ask me my skills and interests first."),
        ("Plan my week", "Organize tasks and priorities.",
         "Help me plan my week. Ask me for my tasks and deadlines, then build a schedule."),
    ],
}


# ============================================================
# STORAGE (json files + images/ + library/ folders)
# ============================================================

def load_json(path: Path) -> dict:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path: Path, data: dict):
    try:
        path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception:
        pass


def save_chats():
    write_json(CHATS_FILE, st.session_state.chats)


def save_projects():
    write_json(PROJECTS_FILE, st.session_state.projects)


def save_scheduled():
    write_json(SCHEDULED_FILE, st.session_state.scheduled)


def make_title(text: str) -> str:
    text = " ".join(text.split())
    return (text[:34] + "…") if len(text) > 34 else (text or "New chat")


def save_image_file(file_bytes: bytes):
    """Save an image to the images/ folder and return its file name."""
    try:
        IMAGES_DIR.mkdir(exist_ok=True)
        name = f"{uuid.uuid4().hex[:12]}.jpg"
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        image.thumbnail((1280, 1280))
        image.save(IMAGES_DIR / name, format="JPEG", quality=86)
        return name
    except Exception:
        return None


def save_library_file(filename: str, file_bytes: bytes):
    """Keep a copy of an attached document in the library/ folder."""
    try:
        LIBRARY_DIR.mkdir(exist_ok=True)
        safe = "".join(c for c in Path(filename).name if c.isalnum() or c in "._- ") or "file"
        stored = f"{uuid.uuid4().hex[:8]}_{safe}"
        (LIBRARY_DIR / stored).write_bytes(file_bytes)
        return stored
    except Exception:
        return None


def delete_chat(chat_id: str):
    chat = st.session_state.chats.pop(chat_id, None)
    if chat:
        for message in chat.get("messages", []):
            for name in message.get("images", []) or []:
                try:
                    (IMAGES_DIR / name).unlink()
                except Exception:
                    pass
            for record in message.get("files", []) or []:
                try:
                    (LIBRARY_DIR / record.get("stored", "")).unlink()
                except Exception:
                    pass
    if st.session_state.chat_id == chat_id:
        st.session_state.chat_id = None
    save_chats()


def delete_project(project_id: str):
    st.session_state.projects.pop(project_id, None)
    for chat in st.session_state.chats.values():
        if chat.get("project") == project_id:
            chat["project"] = None
    st.session_state.active_project = None
    st.session_state.view = "chat"
    save_projects()
    save_chats()


# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "view": "chat",             # chat | images | scheduled | library | plugins | explore | project
    "chat_id": None,
    "active_project": None,
    "new_chat_project": None,   # project a brand-new chat will be added to
    "pending": None,
    "show_search": False,
    "show_new_project": False,
    "camera_enabled": False,
    "nonce": 0,                 # bump to reset file / camera / mic widgets after each send
    "think_mode": False,
    "voice_output": False,
}

if "chats" not in st.session_state:
    st.session_state.chats = load_json(CHATS_FILE)
if "projects" not in st.session_state:
    st.session_state.projects = load_json(PROJECTS_FILE)
if "scheduled" not in st.session_state:
    st.session_state.scheduled = load_json(SCHEDULED_FILE)

for state_key, default_value in DEFAULTS.items():
    if state_key not in st.session_state:
        st.session_state[state_key] = default_value

if st.session_state.chat_id not in st.session_state.chats:
    st.session_state.chat_id = None
if st.session_state.active_project not in st.session_state.projects:
    st.session_state.active_project = None
    if st.session_state.view == "project":
        st.session_state.view = "chat"
if st.session_state.new_chat_project not in st.session_state.projects:
    st.session_state.new_chat_project = None


# ============================================================
# STYLE - CHATGPT-LIKE DARK THEME
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --bg: #000000;
        --composer: #212121;
        --hover: #171717;
        --active: #212121;
        --line: #1f1f1f;
        --text: #ececec;
        --muted: #9b9b9b;
        --blue: #2f6fe4;
    }

    html, body, .stApp, [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {
        background: var(--bg) !important;
        color: var(--text);
    }
    [data-testid="stHeader"] { background: transparent !important; }

    [data-testid="stDeployButton"], [data-testid="stToolbar"],
    [data-testid="stDecoration"], #MainMenu, footer { display: none !important; }

    .block-container, [data-testid="stMainBlockContainer"] {
        max-width: 800px;
        padding-top: 5rem;
        padding-bottom: 10rem;
    }

    /* readable text everywhere in the main area */
    [data-testid="stMain"] [data-testid="stMarkdownContainer"] p,
    [data-testid="stMain"] [data-testid="stWidgetLabel"] p,
    [data-testid="stMain"] label { color: var(--text); }
    [data-testid="stCaptionContainer"],
    [data-testid="stCaptionContainer"] p { color: var(--muted) !important; }

    /* inputs in pages (Scheduled form etc.) */
    [data-baseweb="input"], [data-baseweb="textarea"], [data-baseweb="base-input"] {
        background: #141414 !important;
    }
    [data-testid="stMain"] input, [data-testid="stMain"] textarea {
        background: #141414 !important;
        color: var(--text) !important;
    }
    [data-testid="stMain"] [data-testid="stForm"] {
        border-color: #262626 !important;
        border-radius: 16px !important;
    }

    /* every Streamlit button fills its container */
    [data-testid="stButton"], [data-testid="stFormSubmitButton"],
    [data-testid="stPopover"] { width: 100%; }
    [data-testid="stButton"] button, [data-testid="stFormSubmitButton"] button,
    [data-testid="stPopover"] button { width: 100%; }

    /* ---------- Top bar ---------- */
    .st-key-topbar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 56px;
        z-index: 100;
        background: var(--bg);
        border-bottom: 1px solid var(--line);
        display: flex;
        flex-direction: column;
        align-items: center;
        justify-content: center;
    }
    body:has([data-testid="stSidebar"][aria-expanded="true"]) .st-key-topbar {
        left: 21rem;
    }
    @media (max-width: 992px) {
        body:has([data-testid="stSidebar"][aria-expanded="true"]) .st-key-topbar {
            left: 0;
        }
    }
    .topbar-title {
        font-size: 18px;
        font-weight: 600;
        letter-spacing: -.2px;
        color: #ffffff;
        text-align: center;
    }

    /* ---------- Sidebar ---------- */
    /* Keep the left navigation visible even if Streamlit remembers a
       previously-collapsed sidebar in the browser session. */
    [data-testid="stSidebar"] {
        display: block !important;
        visibility: visible !important;
        opacity: 1 !important;
        width: 280px !important;
        min-width: 280px !important;
        max-width: 280px !important;
        flex: 0 0 280px !important;
        flex-shrink: 0 !important;
        transform: translateX(0) !important;
        margin-left: 0 !important;
        background: var(--bg) !important;
        border-right: 1px solid var(--line) !important;
        overflow: visible !important;
    }
    [data-testid="stSidebar"][aria-expanded="false"] {
        display: block !important;
        visibility: visible !important;
        width: 280px !important;
        min-width: 280px !important;
        max-width: 280px !important;
        transform: translateX(0) !important;
        margin-left: 0 !important;
    }
    [data-testid="stSidebar"] > div:first-child {
        width: 280px !important;
        min-width: 280px !important;
    }
    [data-testid="stSidebar"] * { color: var(--text); }

    .brand {
        font-size: 22px;
        font-weight: 700;
        letter-spacing: -.3px;
        padding: 2px 8px;
    }
    .side-label {
        color: var(--muted) !important;
        font-size: 14px;
        padding: 20px 12px 4px 12px;
    }
    .side-muted {
        color: #6f6f6f !important;
        font-size: 14px;
        padding: 6px 12px;
    }

    [data-testid="stSidebar"] [data-testid="stButton"] button {
        justify-content: flex-start;
        text-align: left;
        min-height: 40px;
        padding: 6px 12px;
        border: none;
        border-radius: 10px;
        background: transparent;
        color: var(--text);
        font-weight: 400;
        box-shadow: none;
    }
    [data-testid="stSidebar"] [data-testid="stButton"] button > div { width: 100%; }
    [data-testid="stSidebar"] [data-testid="stButton"] button p {
        margin: 0;
        text-align: left;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        font-size: 15px;
    }
    [data-testid="stSidebar"] [data-testid="stButton"] button:hover {
        background: var(--hover);
    }
    [data-testid="stSidebar"] [data-testid="stButton"] button[kind="primary"],
    [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
        background: var(--active) !important;
        border: none !important;
    }

    /* icon-only sidebar buttons: search + new project */
    .st-key-nav_search button,
    .st-key-proj_add button {
        justify-content: center !important;
        padding: 0 !important;
    }
    .st-key-nav_search button p,
    .st-key-proj_add button p { display: none; }

    /* "..." menu on each chat */
    [data-testid="stSidebar"] [data-testid="stPopover"] button {
        min-height: 40px;
        padding: 0 !important;
        justify-content: center;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        border-radius: 10px !important;
    }
    [data-testid="stSidebar"] [data-testid="stPopover"] button:hover {
        background: var(--hover) !important;
    }
    [data-testid="stSidebar"] [data-testid="stPopover"] button p,
    [data-testid="stSidebar"] [data-testid="stPopover"] button svg { display: none; }

    [data-testid="stPopoverBody"] {
        min-width: 280px;
        background: #121212 !important;
        border: 1px solid #2a2a2a !important;
    }
    [data-testid="stPopoverBody"] * { color: var(--text); }

    [data-testid="stSidebar"] [data-testid="stTextInput"] input {
        background: #141414 !important;
        border: 1px solid var(--line) !important;
        border-radius: 12px !important;
        color: var(--text) !important;
        min-height: 40px;
    }
    [data-testid="stSidebar"] [data-testid="stForm"] {
        border: 1px solid var(--line) !important;
        border-radius: 12px !important;
        padding: 8px !important;
        background: transparent !important;
    }
    [data-testid="stSidebar"] [data-testid="stFormSubmitButton"] button {
        background: var(--composer) !important;
        border: none !important;
        border-radius: 10px !important;
        color: var(--text) !important;
    }
    [data-testid="stSidebar"] hr { border-color: var(--line); }

    /* user row at the bottom of the sidebar */
    .st-key-sidebar_user {
        position: sticky;
        bottom: 0;
        z-index: 5;
        background: var(--bg);
        border-top: 1px solid var(--line);
        margin-top: 24px;
        padding: 12px 8px 6px 8px;
    }
    .user-row { display: flex; align-items: center; gap: 12px; }
    .avatar {
        width: 34px;
        height: 34px;
        border-radius: 50%;
        background: #3a3a3a;
        display: flex;
        align-items: center;
        justify-content: center;
        font-size: 13px;
        font-weight: 600;
    }
    .user-name { font-size: 15px; font-weight: 600; line-height: 1.2; }
    .user-plan { font-size: 13px; color: var(--muted) !important; }

    /* ---------- Pages ---------- */
    .page-title {
        font-size: 28px;
        font-weight: 600;
        color: #ffffff;
        margin: 4px 0 4px 0;
    }
    .page-sub {
        color: var(--muted);
        font-size: 15px;
        margin-bottom: 22px;
    }
    .section-title {
        font-size: 18px;
        font-weight: 600;
        color: #ffffff;
        margin: 26px 0 10px 0;
    }
    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: #262626 !important;
        border-radius: 16px !important;
    }

    /* ---------- Welcome screen ---------- */
    .welcome {
        text-align: center;
        font-size: clamp(26px, 3.2vw, 34px);
        font-weight: 500;
        color: #ffffff;
        margin: 16vh 0 10px 0;
    }
    .welcome-sub {
        text-align: center;
        color: var(--muted);
        font-size: 15px;
        margin-bottom: 18px;
    }

    /* buttons in the main area (suggestions, Open chat, page actions) */
    [data-testid="stMain"] [data-testid="stButton"] button {
        justify-content: flex-start;
        border: none;
        background: transparent;
        color: var(--text);
        font-weight: 400;
        font-size: 16px;
        min-height: 46px;
        padding-left: 18px;
        border-radius: 12px;
        box-shadow: none;
    }
    [data-testid="stMain"] [data-testid="stButton"] button:hover {
        background: var(--hover);
    }
    [data-testid="stMain"] [data-testid="stDownloadButton"] button {
        background: transparent;
        border: 1px solid #2a2a2a;
        color: var(--text);
        border-radius: 12px;
    }

    /* ---------- Messages ---------- */
    div[data-testid="stChatMessage"] {
        background: transparent !important;
        border: none !important;
        padding: .6rem 0 !important;
        gap: 0 !important;
    }
    [data-testid="stChatMessageAvatarUser"],
    [data-testid="stChatMessageAvatarAssistant"],
    [data-testid="stChatMessageAvatarCustom"] { display: none !important; }

    div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {
        flex-direction: row-reverse;
    }
    div[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"])
    [data-testid="stChatMessageContent"] {
        flex: 0 1 auto;
        width: fit-content;
        max-width: 75%;
        background: var(--composer);
        border-radius: 22px;
        padding: 10px 18px;
    }

    /* ---------- Message bar position ---------- */
    .st-key-composer_fixed {
        position: fixed;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: min(800px, calc(100vw - 2rem));
        z-index: 99;
        background: var(--bg);
        padding: 10px 0 22px 0;
    }
    body:has([data-testid="stSidebar"][aria-expanded="true"]) .st-key-composer_fixed {
        left: calc(50% + 10.5rem);
        width: min(800px, calc(100vw - 23rem));
    }
    @media (max-width: 992px) {
        .st-key-composer_fixed,
        body:has([data-testid="stSidebar"][aria-expanded="true"]) .st-key-composer_fixed {
            left: 50% !important;
            width: calc(100vw - 2rem) !important;
        }
    }

    .chip-row {
        color: var(--muted);
        font-size: 13px;
        padding: 0 16px 8px 16px;
    }

    .st-key-composer_fixed [data-testid="stCameraInput"],
    .st-key-composer_inline [data-testid="stCameraInput"] {
        max-width: 300px;
        margin-bottom: 8px;
    }

    /* ---------- Message bar (pill) ---------- */
    .st-key-pill {
        background: var(--composer);
        border-radius: 32px;
        padding: 6px 10px;
    }

    .st-key-pill [data-testid="stForm"] {
        border: none !important;
        padding: 0 !important;
        background: transparent !important;
    }

    /* icon buttons: plus + camera */
    .st-key-pill [data-testid="stButton"],
    .st-key-pill [data-testid="stPopover"] {
        display: flex;
        justify-content: center;
    }
    .st-key-pill [data-testid="stButton"] button,
    .st-key-pill [data-testid="stPopover"] button {
        justify-content: center !important;
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        width: 42px;
        min-width: 42px;
        height: 42px;
        min-height: 42px;
        padding: 0 !important;
        border-radius: 50% !important;
        color: var(--text) !important;
    }
    .st-key-pill [data-testid="stButton"] button:hover,
    .st-key-pill [data-testid="stPopover"] button:hover {
        background: #2f2f2f !important;
    }
    .st-key-pill [data-testid="stButton"] button p,
    .st-key-pill [data-testid="stPopover"] button p { display: none; }
    .st-key-pill [data-testid="stPopover"] button svg { display: none; }
    .st-key-pill [data-testid="stIconMaterial"] {
        font-size: 26px !important;
        color: var(--text) !important;
    }
    /* camera icon turns blue while the camera is on */
    .st-key-pill .st-key-cam_toggle button[kind="primary"],
    .st-key-pill .st-key-cam_toggle [data-testid="stBaseButton-primary"] {
        background: #1d3f87 !important;
    }

    /* mic */
    .st-key-pill [data-testid="stAudioInput"],
    .st-key-pill [data-testid="stAudioInput"] > div {
        background: transparent !important;
        border: none !important;
        min-width: 0;
    }
    .st-key-pill [data-testid="stAudioInput"] button {
        background: transparent !important;
        border: none !important;
        min-height: 42px;
    }

    /* text field */
    .st-key-pill [data-testid="stTextInput"] input,
    .st-key-pill [data-baseweb="input"],
    .st-key-pill [data-baseweb="base-input"] {
        background: transparent !important;
        border: none !important;
        box-shadow: none !important;
        color: var(--text) !important;
        font-size: 16px;
    }
    .st-key-pill [data-testid="stTextInput"] input {
        min-height: 44px;
        padding-left: 6px !important;
    }
    .st-key-pill [data-testid="stTextInput"] input::placeholder { color: var(--muted); }

    /* send button */
    .st-key-pill [data-testid="stFormSubmitButton"] {
        display: flex;
        justify-content: flex-end;
    }
    .st-key-pill [data-testid="stFormSubmitButton"] button {
        background: var(--blue) !important;
        border: none !important;
        border-radius: 50% !important;
        min-height: 40px;
        height: 40px;
        width: 40px;
        min-width: 40px;
        padding: 0 !important;
        display: flex;
        justify-content: center;
    }
    .st-key-pill [data-testid="stFormSubmitButton"] button,
    .st-key-pill [data-testid="stFormSubmitButton"] button * {
        color: #ffffff !important;
        font-weight: 700;
        font-size: 20px;
    }
    .st-key-pill [data-testid="stFormSubmitButton"] button:hover {
        background: #4b85f0 !important;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# GROQ CLIENT
# ============================================================

@st.cache_resource
def get_groq_client(api_key: str):
    return Groq(api_key=api_key)


client = None
if GROQ_API_KEY:
    try:
        client = get_groq_client(GROQ_API_KEY)
    except Exception:
        client = None


# ============================================================
# FILE / IMAGE / AUDIO HELPERS
# ============================================================

def extract_document_text(filename: str, file_bytes: bytes) -> str:
    lower_name = filename.lower()
    try:
        if lower_name.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(file_bytes))
            return "\n".join(page.extract_text() or "" for page in reader.pages)
        if lower_name.endswith(".docx"):
            document = Document(io.BytesIO(file_bytes))
            return "\n".join(p.text for p in document.paragraphs)
        if lower_name.endswith(".txt"):
            return file_bytes.decode("utf-8", errors="replace")
        return ""
    except Exception as exc:
        return f"[Could not read {filename}: {exc}]"


def image_bytes_to_data_url(file_bytes: bytes):
    try:
        image = Image.open(io.BytesIO(file_bytes)).convert("RGB")
        image.thumbnail((1280, 1280))
        output = io.BytesIO()
        image.save(output, format="JPEG", quality=86)
        encoded = base64.b64encode(output.getvalue()).decode("ascii")
        return f"data:image/jpeg;base64,{encoded}"
    except Exception:
        return None


def transcribe_audio(audio_file):
    if client is None:
        return None, "Groq API key is missing. Check your .env file."
    try:
        audio_bytes = audio_file.getvalue()
        audio_name = getattr(audio_file, "name", None) or "voice_recording.wav"
        result = client.audio.transcriptions.create(
            file=(audio_name, audio_bytes),
            model=WHISPER_MODEL,
            language="en",
        )
        return result.text.strip(), None
    except Exception as exc:
        return None, f"Voice transcription failed: {exc}"


# ============================================================
# AI RESPONSE (STREAMING)
# ============================================================

def generate_response(history_msgs, user_prompt, document_text, image_urls):
    if client is None:
        return "Groq API key is missing. Add GROQ_API_KEY to your .env file."

    system_prompt = SYSTEM_PROMPT
    if st.session_state.think_mode:
        system_prompt += (
            "\nThink carefully, check the relevant details, "
            "and provide a structured, accurate answer."
        )
    if document_text:
        system_prompt += (
            "\n\nThe user attached documents. Use their content when relevant. "
            "Extracted document text:\n" + document_text[:35000]
        )

    history = [
        {"role": m["role"], "content": m["content"]}
        for m in history_msgs
        if m["role"] in ("user", "assistant")
    ]

    if image_urls:
        content = [{
            "type": "text",
            "text": user_prompt or "Please analyze the attached image(s).",
        }]
        for url in image_urls:
            content.append({"type": "image_url", "image_url": {"url": url}})
        current_message = {"role": "user", "content": content}
        selected_model = VISION_MODEL
    else:
        current_message = {
            "role": "user",
            "content": user_prompt or "Please analyze my attached document.",
        }
        selected_model = CHAT_MODEL

    request_messages = [
        {"role": "system", "content": system_prompt},
        *history,
        current_message,
    ]

    try:
        stream = client.chat.completions.create(
            model=selected_model,
            messages=request_messages,
            stream=True,
            max_completion_tokens=2048,
        )

        answer = ""
        output = st.empty()
        output.markdown("▍")

        for chunk in stream:
            if not chunk.choices:
                continue
            piece = chunk.choices[0].delta.content
            if piece:
                answer += piece
                output.markdown(answer + " ▍")

        output.markdown(answer or "I couldn't generate a response.")
        return answer or "I couldn't generate a response."

    except Exception as exc:
        return (
            "I couldn't generate a response from Groq.\n\n"
            f"**Error:** {exc}\n\n"
            "Check that your API key is valid and that the selected model "
            "is available to your Groq account."
        )


def speak_english(text: str):
    """Read the answer aloud with the browser's English voice (best effort)."""
    try:
        safe_text = json.dumps(text)
        page = f"""
        <script>
        const phrase = {safe_text};
        if ("speechSynthesis" in window) {{
            window.speechSynthesis.cancel();
            const utterance = new SpeechSynthesisUtterance(phrase);
            utterance.lang = "en-US";
            const voices = window.speechSynthesis.getVoices();
            const english = voices.find(v => v.lang.toLowerCase().startsWith("en"));
            if (english) utterance.voice = english;
            window.speechSynthesis.speak(utterance);
        }}
        </script>
        """
        st.components.v1.html(page, height=0)
    except Exception:
        pass


# ============================================================
# TURN HANDLING
# ============================================================

def start_turn(prompt, document_text, image_urls, attachment_names, image_names, file_records):
    """Store the user message, queue the AI reply, and rerun."""
    chat_id = st.session_state.chat_id
    if chat_id is None:
        chat_id = uuid.uuid4().hex[:8]
        st.session_state.chats[chat_id] = {
            "title": make_title(prompt),
            "messages": [],
            "project": st.session_state.new_chat_project,
            "pinned": False,
        }
        st.session_state.chat_id = chat_id
        st.session_state.new_chat_project = None

    st.session_state.chats[chat_id]["messages"].append({
        "role": "user",
        "content": prompt,
        "attachments": attachment_names,
        "images": image_names,
        "files": file_records,
    })
    st.session_state.view = "chat"
    st.session_state.pending = {
        "document_text": document_text,
        "image_urls": image_urls,
    }
    st.session_state.nonce += 1               # resets file / camera / mic widgets
    st.session_state.camera_enabled = False
    save_chats()
    st.rerun()


def handle_submission(text, files, audio, photo_bytes):
    prompt = (text or "").strip()

    if audio is not None:
        with st.spinner("Transcribing your voice..."):
            transcript, audio_error = transcribe_audio(audio)
        if transcript:
            prompt = f"{prompt}\n{transcript}".strip() if prompt else transcript
        elif audio_error and not prompt:
            prompt = "My voice recording could not be transcribed. Please tell me to try again."

    document_chunks, image_urls, names = [], [], []
    image_names, file_records = [], []

    for f in files:
        lower = f.name.lower()
        data = f.getvalue()
        if lower.endswith((".pdf", ".docx", ".txt")):
            document_chunks.append(f"FILE: {f.name}\n{extract_document_text(f.name, data)}")
            names.append(f.name)
            stored = save_library_file(f.name, data)
            if stored:
                file_records.append({"name": f.name, "stored": stored})
        elif lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
            url = image_bytes_to_data_url(data)
            if url:
                image_urls.append(url)
                names.append(f.name)
                saved = save_image_file(data)
                if saved:
                    image_names.append(saved)

    if photo_bytes:
        camera_url = image_bytes_to_data_url(photo_bytes)
        if camera_url:
            image_urls.append(camera_url)
            names.append("camera photo")
            saved = save_image_file(photo_bytes)
            if saved:
                image_names.append(saved)

    document_text = "\n\n".join(document_chunks)

    if not prompt and (document_text or image_urls):
        prompt = "Please analyze the attached file(s) and explain the important information."

    if prompt:
        start_turn(prompt, document_text, image_urls, names, image_names, file_records)


# ============================================================
# SIDEBAR HELPERS
# ============================================================

def project_label(project_id):
    if project_id is None:
        return "No project"
    project = st.session_state.projects.get(project_id)
    return project["name"] if project else "No project"


def render_chat_row(chat_id: str, chat: dict, current_view: str):
    """One chat in the sidebar: title button + '...' menu (pin, move, delete)."""
    row_left, row_right = st.columns([0.84, 0.16], gap="small", vertical_alignment="center")

    with row_left:
        is_active = current_view == "chat" and chat_id == st.session_state.chat_id
        if st.button(
            chat["title"],
            key=f"chat_{chat_id}",
            type="primary" if is_active else "secondary",
        ):
            st.session_state.view = "chat"
            st.session_state.chat_id = chat_id
            st.rerun()

    with row_right:
        with st.popover("More", icon=":material/more_horiz:"):
            pinned = bool(chat.get("pinned"))
            if st.button(
                "Unpin chat" if pinned else "Pin chat",
                key=f"pin_{chat_id}",
                icon=":material/push_pin:",
            ):
                chat["pinned"] = not pinned
                save_chats()
                st.rerun()

            project_ids = [None] + list(st.session_state.projects.keys())
            current_project = chat.get("project")
            if current_project not in project_ids:
                current_project = None
            choice = st.selectbox(
                "Move to project",
                project_ids,
                index=project_ids.index(current_project),
                format_func=project_label,
                key=f"mv_{chat_id}",
            )
            if choice != current_project:
                chat["project"] = choice
                save_chats()
                st.rerun()

            if st.button("Delete chat", key=f"delx_{chat_id}", icon=":material/delete:"):
                delete_chat(chat_id)
                st.rerun()


# ============================================================
# PAGES
# ============================================================

def page_header(title: str, subtitle: str):
    st.markdown(f'<div class="page-title">{html.escape(title)}</div>', unsafe_allow_html=True)
    st.markdown(f'<div class="page-sub">{html.escape(subtitle)}</div>', unsafe_allow_html=True)


def render_images_page():
    page_header("Images", "Photos and images you sent in your chats.")

    gallery = []
    for cid, chat in reversed(list(st.session_state.chats.items())):
        for message in chat.get("messages", []):
            for name in message.get("images", []) or []:
                path = IMAGES_DIR / name
                if path.exists():
                    gallery.append((cid, chat["title"], path))

    if not gallery:
        st.info("No images yet. Attach an image with ＋ or take a photo with the camera icon.")
        return

    columns = st.columns(3)
    for index, (cid, title, path) in enumerate(gallery):
        with columns[index % 3]:
            st.image(str(path))
            st.caption(title)
            if st.button("Open chat", key=f"img_open_{index}"):
                st.session_state.view = "chat"
                st.session_state.chat_id = cid
                st.rerun()


def parse_due(task: dict) -> datetime:
    try:
        return datetime.strptime(task.get("due", ""), "%Y-%m-%d %H:%M")
    except Exception:
        return datetime.max


def count_due_tasks() -> int:
    now = datetime.now()
    return sum(
        1
        for task in st.session_state.scheduled.values()
        if not task.get("done") and parse_due(task) <= now
    )


def render_scheduled_page():
    page_header(
        "Scheduled",
        "Plan tasks and prompts. Tasks that reach their time show as due here.",
    )

    with st.form("schedule_form", clear_on_submit=True):
        task_title = st.text_input("Title", placeholder="e.g. Practice SQL questions")
        task_prompt = st.text_area(
            "What should Raghava AI do?",
            placeholder="e.g. Give me 5 SQL interview questions with answers.",
            height=90,
        )
        col_date, col_time = st.columns(2)
        with col_date:
            task_date = st.date_input("Date", value=date.today())
        with col_time:
            task_time = st.time_input("Time", value=dt_time(9, 0))
        add_clicked = st.form_submit_button("Add scheduled task")

    if add_clicked:
        if task_title.strip():
            task_id = uuid.uuid4().hex[:8]
            st.session_state.scheduled[task_id] = {
                "title": task_title.strip()[:80],
                "prompt": task_prompt.strip(),
                "due": datetime.combine(task_date, task_time).strftime("%Y-%m-%d %H:%M"),
                "done": False,
            }
            save_scheduled()
            st.rerun()
        else:
            st.warning("Add a title for the task.")

    tasks = sorted(
        st.session_state.scheduled.items(),
        key=lambda item: (bool(item[1].get("done")), parse_due(item[1])),
    )

    if not tasks:
        st.info("No scheduled tasks yet.")
        return

    now = datetime.now()
    for task_id, task in tasks:
        due = parse_due(task)
        done = bool(task.get("done"))
        if done:
            status = "✅ Done"
        elif due <= now:
            status = "⏰ Due now"
        else:
            status = "🕒 Upcoming"

        with st.container(border=True):
            st.markdown(f"**{task['title']}**")
            due_text = due.strftime("%d %b %Y, %I:%M %p") if due != datetime.max else "No date"
            st.caption(f"{status}  ·  {due_text}")
            if task.get("prompt"):
                st.caption(task["prompt"][:200])

            col_run, col_done, col_delete = st.columns(3)
            with col_run:
                if task.get("prompt") and st.button(
                    "Run now", key=f"run_{task_id}", icon=":material/play_arrow:"
                ):
                    st.session_state.chat_id = None
                    st.session_state.new_chat_project = None
                    start_turn(task["prompt"], "", [], [], [], [])
            with col_done:
                if st.button(
                    "Reopen" if done else "Mark done",
                    key=f"done_{task_id}",
                    icon=":material/check_circle:",
                ):
                    task["done"] = not done
                    save_scheduled()
                    st.rerun()
            with col_delete:
                if st.button("Delete", key=f"deltask_{task_id}", icon=":material/delete:"):
                    st.session_state.scheduled.pop(task_id, None)
                    save_scheduled()
                    st.rerun()


def render_library_page():
    page_header("Library", "Documents you attached in your chats.")

    library = []
    for cid, chat in reversed(list(st.session_state.chats.items())):
        for message in chat.get("messages", []):
            for record in message.get("files", []) or []:
                path = LIBRARY_DIR / record.get("stored", "")
                if path.exists():
                    library.append((cid, chat["title"], record["name"], path))

    if not library:
        st.info("No documents yet. Attach a PDF, DOCX or TXT file with ＋ in a chat.")
        return

    for index, (cid, title, name, path) in enumerate(library[:100]):
        with st.container(border=True):
            st.markdown(f"**📄 {name}**")
            st.caption(f"From chat: {title}")
            col_open, col_download = st.columns(2)
            with col_open:
                if st.button("Open chat", key=f"lib_open_{index}", icon=":material/chat_bubble_outline:"):
                    st.session_state.view = "chat"
                    st.session_state.chat_id = cid
                    st.rerun()
            with col_download:
                try:
                    st.download_button(
                        "Download",
                        data=path.read_bytes(),
                        file_name=name,
                        key=f"lib_dl_{index}",
                        icon=":material/download:",
                    )
                except Exception:
                    st.caption("File unavailable")


def render_plugins_page():
    page_header("Plugins", "Turn Raghava AI features on or off.")

    with st.container(border=True):
        st.session_state.think_mode = st.toggle(
            "🧠 Think mode",
            value=st.session_state.think_mode,
            key="w_think",
        )
        st.caption("Raghava AI reasons more carefully before it answers.")

    with st.container(border=True):
        st.session_state.voice_output = st.toggle(
            "🔊 Speak responses",
            value=st.session_state.voice_output,
            key="w_voice",
        )
        st.caption("Reads each answer aloud with your browser's English voice.")

    with st.container(border=True):
        st.markdown("**📄 Document reader** · always on")
        st.caption("Reads PDF, DOCX and TXT files you attach with the ＋ button.")

    with st.container(border=True):
        st.markdown("**🎤 Voice input** · always on")
        st.caption("Record with the mic in the message bar. Whisper turns it into text.")

    with st.container(border=True):
        st.markdown("**🖼️ Vision** · always on")
        st.caption("Understands images you attach or take with the camera icon.")

    st.caption(
        f"Chat model: {CHAT_MODEL}  ·  Vision model: {VISION_MODEL}  ·  "
        f"Speech model: {WHISPER_MODEL}"
    )


def render_profile_page():
    page_header("Profile", "Your Raghava AI assistant profile.")
    with st.container(border=True):
        initials = html.escape(USER_NAME[:2].upper())
        st.markdown(
            f"""
            <div class="user-row" style="padding: 12px 4px;">
                <div class="avatar" style="width: 48px; height: 48px; font-size: 16px;">{initials}</div>
                <div>
                    <div class="user-name" style="font-size: 18px;">{html.escape(USER_NAME)}</div>
                    <div class="user-plan">Personal assistant</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
        st.divider()
        st.markdown("**Assistant**")
        st.caption("Raghava AI Assistant")
        st.markdown("**AI provider**")
        st.caption("Groq API")
        st.markdown("**Chat storage**")
        st.caption("Your chats and projects are stored locally in JSON files in this app folder.")


def render_explore_page():
    page_header("Explore", "Pick a starting point and Raghava AI opens a new chat for it.")

    for category, items in EXPLORE.items():
        st.markdown(f'<div class="section-title">{html.escape(category)}</div>', unsafe_allow_html=True)
        columns = st.columns(2)
        for index, (title, description, prompt_text) in enumerate(items):
            with columns[index % 2]:
                with st.container(border=True):
                    st.markdown(f"**{title}**")
                    st.caption(description)
                    if st.button(
                        "Start chat",
                        key=f"explore_{category}_{index}",
                        icon=":material/arrow_forward:",
                    ):
                        st.session_state.chat_id = None
                        st.session_state.new_chat_project = None
                        start_turn(prompt_text, "", [], [], [], [])


def render_project_page():
    project_id = st.session_state.active_project
    project = st.session_state.projects.get(project_id)
    if not project:
        st.session_state.view = "chat"
        st.rerun()
        return

    project_chats = [
        (cid, chat)
        for cid, chat in reversed(list(st.session_state.chats.items()))
        if chat.get("project") == project_id
    ]

    page_header(f"📁 {project['name']}", f"{len(project_chats)} chat(s) in this project.")

    if st.button("New chat in this project", key="proj_new_chat", icon=":material/edit_square:"):
        st.session_state.view = "chat"
        st.session_state.chat_id = None
        st.session_state.new_chat_project = project_id
        st.rerun()

    for cid, chat in project_chats:
        if st.button(chat["title"], key=f"pchat_{cid}", icon=":material/chat_bubble_outline:"):
            st.session_state.view = "chat"
            st.session_state.chat_id = cid
            st.rerun()

    st.write("")
    if st.button("Delete project", key="proj_delete", icon=":material/delete:"):
        delete_project(project_id)
        st.rerun()


PAGES = {
    "images": render_images_page,
    "scheduled": render_scheduled_page,
    "library": render_library_page,
    "plugins": render_plugins_page,
    "explore": render_explore_page,
    "project": render_project_page,
    "profile": render_profile_page,
}


# ============================================================
# SIDEBAR: search, nav, Pinned, Projects, Recents, user row
# ============================================================

view = st.session_state.view

with st.sidebar:
    # --- sidebar brand ---
    st.markdown('<div class="brand">Raghava AI</div>', unsafe_allow_html=True)

    search = ""
    if st.session_state.show_search:
        search = st.text_input(
            "Search chats",
            placeholder="Search chats…",
            label_visibility="collapsed",
            key="chat_search",
        ).strip().lower()

    # --- main navigation ---
    due_count = count_due_tasks()
    for nav_id, nav_label, nav_icon in NAV_ITEMS:
        if nav_id == "chat":
            is_active = view == "chat" and st.session_state.chat_id is None
        elif nav_id == "search":
            is_active = st.session_state.show_search
        else:
            is_active = view == nav_id

        label = nav_label
        if nav_id == "scheduled" and due_count:
            label = f"{nav_label} ({due_count})"

        if st.button(
            label,
            key=f"nav_{nav_id}",
            icon=nav_icon,
            type="primary" if is_active else "secondary",
        ):
            if nav_id == "search":
                st.session_state.show_search = not st.session_state.show_search
            else:
                st.session_state.view = nav_id
                if nav_id == "chat":
                    st.session_state.chat_id = None
                    st.session_state.new_chat_project = None
            st.rerun()

    visible_chats = [
        (cid, chat)
        for cid, chat in reversed(list(st.session_state.chats.items()))
        if search in chat["title"].lower()
    ]
    pinned_chats = [item for item in visible_chats if item[1].get("pinned")]
    recent_chats = [item for item in visible_chats if not item[1].get("pinned")]

    # --- chat history ---
    st.markdown('<div class="side-label">Chat History</div>', unsafe_allow_html=True)

    # --- pinned ---
    if pinned_chats:
        st.markdown('<div class="side-label">Pinned</div>', unsafe_allow_html=True)
        for cid, chat in pinned_chats[:20]:
            render_chat_row(cid, chat, view)

    # --- projects ---
    proj_left, proj_right = st.columns([0.8, 0.2], gap="small", vertical_alignment="bottom")
    with proj_left:
        st.markdown('<div class="side-label">Projects</div>', unsafe_allow_html=True)
    with proj_right:
        if st.button("New project", key="proj_add", icon=":material/add:", help="New project"):
            st.session_state.show_new_project = not st.session_state.show_new_project
            st.rerun()

    if st.session_state.show_new_project:
        with st.form("new_project_form", clear_on_submit=True):
            new_project_name = st.text_input(
                "Project name",
                placeholder="Project name",
                label_visibility="collapsed",
            )
            create_clicked = st.form_submit_button("Create project")
        if create_clicked and new_project_name.strip():
            new_project_id = uuid.uuid4().hex[:8]
            st.session_state.projects[new_project_id] = {"name": new_project_name.strip()[:40]}
            st.session_state.show_new_project = False
            save_projects()
            st.rerun()

    if not st.session_state.projects:
        st.markdown('<div class="side-muted">No projects</div>', unsafe_allow_html=True)
    for pid, project in st.session_state.projects.items():
        if st.button(
            project["name"],
            key=f"proj_{pid}",
            icon=":material/folder:",
            type="primary" if (view == "project" and st.session_state.active_project == pid) else "secondary",
        ):
            st.session_state.view = "project"
            st.session_state.active_project = pid
            st.rerun()

    # --- recent chats ---
    st.markdown('<div class="side-label">Recent Chats</div>', unsafe_allow_html=True)
    if not recent_chats:
        st.markdown('<div class="side-muted">No chats yet</div>', unsafe_allow_html=True)
    for cid, chat in recent_chats[:40]:
        render_chat_row(cid, chat, view)

    # --- profile shortcut and user row ---
    if st.button(
        "Profile",
        key="nav_profile",
        icon=":material/account_circle:",
        type="primary" if view == "profile" else "secondary",
    ):
        st.session_state.view = "profile"
        st.rerun()

    with st.container(key="sidebar_user"):
        initials = html.escape(USER_NAME[:2].upper())
        st.markdown(
            f"""
            <div class="user-row">
                <div class="avatar">{initials}</div>
                <div>
                    <div class="user-name">{html.escape(USER_NAME)}</div>
                    <div class="user-plan">Personal assistant</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )


# ============================================================
# TOP BAR
# ============================================================

with st.container(key="topbar"):
    st.markdown(
        '<div class="topbar-title">✦ Raghava AI Assistant</div>',
        unsafe_allow_html=True,
    )

if view in PAGES:
    PAGES[view]()
    st.stop()


# ============================================================
# CHAT VIEW
# ============================================================

active_chat = st.session_state.chats.get(st.session_state.chat_id)
messages = active_chat["messages"] if active_chat else []

# Layout order: top (welcome or history) -> message bar -> suggestions.
# The message bar is pinned to the bottom once a chat has started.
top_area = st.container()
composer_area = st.container(key="composer_fixed" if messages else "composer_inline")
bottom_area = st.container()

n = st.session_state.nonce
photo = None

# ---------- Message bar: + | camera | mic | text | send ----------
with composer_area:
    chips_area = st.container()

    if st.session_state.camera_enabled:
        photo = st.camera_input(
            "Take a photo",
            key=f"cam_{n}",
            label_visibility="collapsed",
        )

    with st.container(key="pill"):
        plus_col, cam_col, mic_col, msg_col = st.columns(
            [0.07, 0.07, 0.17, 0.69],
            vertical_alignment="center",
            gap="small",
        )

        with plus_col:
            with st.popover("Add files", icon=":material/add:"):
                st.markdown("**Add files**")
                picked = st.file_uploader(
                    "Add files",
                    type=FILE_TYPES,
                    accept_multiple_files=True,
                    key=f"files_{n}",
                    label_visibility="collapsed",
                )

        with cam_col:
            if st.button(
                "Camera",
                key="cam_toggle",
                icon=":material/photo_camera:",
                help="Camera",
                type="primary" if st.session_state.camera_enabled else "secondary",
            ):
                st.session_state.camera_enabled = not st.session_state.camera_enabled
                st.rerun()

        with mic_col:
            recorded = st.audio_input(
                "Voice",
                key=f"mic_{n}",
                label_visibility="collapsed",
            )

        with msg_col:
            with st.form("composer_form", clear_on_submit=True):
                text_col, send_col = st.columns(
                    [0.86, 0.14], vertical_alignment="center", gap="small"
                )
                with text_col:
                    typed = st.text_input(
                        "Message",
                        placeholder="Ask Raghava AI anything",
                        label_visibility="collapsed",
                        key="composer_text",
                    )
                with send_col:
                    submitted = st.form_submit_button("↑")

    # attachment chips above the bar
    labels = [f"📎 {html.escape(f.name)}" for f in (picked or [])]
    if photo is not None:
        labels.append("📷 Photo")
    if recorded is not None:
        labels.append("🎤 Voice note")
    if labels:
        with chips_area:
            st.markdown(
                f'<div class="chip-row">{"  ·  ".join(labels)}</div>',
                unsafe_allow_html=True,
            )

if submitted:
    handle_submission(
        typed,
        picked or [],
        recorded,
        photo.getvalue() if photo is not None else None,
    )

# ---------- Welcome screen or conversation ----------
if not messages:
    with top_area:
        st.markdown(
            '<div class="welcome">What’s on your mind today?</div>',
            unsafe_allow_html=True,
        )
        if st.session_state.new_chat_project:
            st.markdown(
                f'<div class="welcome-sub">New chat in project: '
                f'{html.escape(project_label(st.session_state.new_chat_project))}</div>',
                unsafe_allow_html=True,
            )
    with bottom_area:
        for icon, label, prompt_text in SUGGESTIONS:
            if st.button(f"{icon}   {label}", key=f"sug_{label}"):
                start_turn(prompt_text, "", [], [], [], [])
else:
    with top_area:
        for message in messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                for image_name in message.get("images", []) or []:
                    image_path = IMAGES_DIR / image_name
                    if image_path.exists():
                        st.image(str(image_path), width=220)
                if message.get("attachments"):
                    st.caption("📎 " + ", ".join(message["attachments"]))

        # ---------- Generate the reply for the message just sent ----------
        if st.session_state.pending:
            pending = st.session_state.pending
            st.session_state.pending = None

            with st.chat_message("assistant"):
                answer = generate_response(
                    messages[:-1],
                    messages[-1]["content"],
                    pending["document_text"],
                    pending["image_urls"],
                )

            messages.append({"role": "assistant", "content": answer})
            save_chats()

            if st.session_state.voice_output:
                speak_english(answer)
