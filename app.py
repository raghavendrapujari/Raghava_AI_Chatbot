
import os
import json
import requests
import streamlit as st

from pathlib import Path
from dotenv import load_dotenv
from groq import Groq


# =========================================================
# 1. PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Chat With Raghava AI ",
    page_icon="🤖",
    layout="wide",
    initial_sidebar_state="expanded"
)


# =========================================================
# 2. ENVIRONMENT VARIABLES
# =========================================================

BASE_DIR = Path(__file__).resolve().parent

load_dotenv(BASE_DIR / ".env", override=True)

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "").strip()

OLLAMA_URL = os.getenv(
    "OLLAMA_URL",
    "http://localhost:11434"
).rstrip("/")


# =========================================================
# 3. AVAILABLE MODELS
# =========================================================

GROQ_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile"
]

OLLAMA_MODELS = [
    "llama3.2",
    "llama3.1",
    "llama3",
    "mistral",
    "gemma2",
    "qwen2.5",
    "qwen2.5:3b"
]


# =========================================================
# 4. SYSTEM PROMPT
# =========================================================

SYSTEM_PROMPT = """
You are Raghava AI, a helpful personal AI assistant.

STRICT LANGUAGE RULES:
- Always respond in English only.
- Never respond in Telugu, Hindi, or another language.
- Understand messages written or spoken in other languages,
  but always reply in English.
- Use clear and natural English.
- Be friendly, helpful and accurate.
- Explain technical topics in simple language.
- Never claim to perform actions you cannot perform.
"""


def build_system_prompt(extra_prompt=""):
    if extra_prompt.strip():
        return SYSTEM_PROMPT + "\nAdditional instructions:\n" + extra_prompt

    return SYSTEM_PROMPT


# =========================================================
# 5. GROQ CLIENT
# =========================================================


def get_groq_client():
    if not GROQ_API_KEY:
        st.error(
            "Groq API key not found. "
            "Check your .env file location and variable name."
        )
        return None

    try:
        return Groq(api_key = "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")

    except Exception as e:
        st.error(f"Groq connection error: {e}")
        return None



# =========================================================
# 6. VOICE RECOGNITION
# =========================================================

def transcribe_audio(audio_file):

    try:
        client = get_groq_client()

        audio_bytes = audio_file.getvalue()

        if not audio_bytes:
            raise ValueError("The audio recording is empty.")

        result = client.audio.transcriptions.create(
            file=(
                audio_file.name or "recording.wav",
                audio_bytes,
                audio_file.type or "audio/wav"
            ),
            model="whisper-large-v3",
            language="en",
            prompt=(
                "This is an English conversation with a personal "
                "AI assistant named Raghava AI. Recognize names, "
                "technical words and complete sentences accurately. "
                "Transcribe only what is spoken."
            ),
            response_format="json",
            temperature=0.0
        )

        return result.text.strip()

    except Exception as e:
        st.error(f"Voice recognition failed: {e}")
        return ""


# =========================================================
# 7. TEXT TO SPEECH
# =========================================================

def speak_text(text_to_speak):

    try:
        import io
        import streamlit.components.v1 as components

        if not text_to_speak.strip():
            return

        safe_text = json.dumps(text_to_speak)

        html_code = f"""
        <script>
        const message = {safe_text};

        if ("speechSynthesis" in window) {{
            window.speechSynthesis.cancel();

            const speech = new SpeechSynthesisUtterance(message);
            speech.lang = "en-US";
            speech.rate = 1.0;
            speech.pitch = 1.0;

            window.speechSynthesis.speak(speech);
        }}
        </script>
        """

        components.html(html_code, height=0)

    except Exception as e:
        st.warning(f"Speech output unavailable: {e}")


# =========================================================
# 8. OLLAMA CONNECTION
# =========================================================

def check_ollama():

    try:
        response = requests.get(
            f"{OLLAMA_URL}/api/tags",
            timeout=5
        )

        return response.status_code == 200

    except requests.RequestException:
        return False


def get_ollama_response(messages, model, temperature):

    response = requests.post(
        f"{OLLAMA_URL}/api/chat",
        json={
            "model": model,
            "messages": messages,
            "stream": True,
            "options": {
                "temperature": temperature
            }
        },
        stream=True,
        timeout=(10, 180)
    )

    response.raise_for_status()

    for line in response.iter_lines():

        if line:

            data = json.loads(line.decode("utf-8"))

            content = data.get("message", {}).get("content", "")

            if content:
                yield content


# =========================================================
# 9. GROQ STREAMING
# =========================================================

def get_groq_response(messages, model, temperature):

    client = get_groq_client()

    stream = client.chat.completions.create(
        model=model,
        messages=messages,
        temperature=temperature,
        stream=True
    )

    for chunk in stream:

        if chunk.choices:

            content = chunk.choices[0].delta.content

            if content:
                yield content


# =========================================================
# 10. SESSION STATE
# =========================================================

if "messages" not in st.session_state:
    st.session_state.messages = []

if "pending_voice_text" not in st.session_state:
    st.session_state.pending_voice_text = ""

if "last_response" not in st.session_state:
    st.session_state.last_response = ""


# =========================================================
# 11. CUSTOM CSS
# =========================================================

st.markdown("""
<style>

.stApp {
    background-color: #0e1117;
    color: #ffffff;
}

.block-container {
    padding-top: 1.5rem;
    max-width: 1200px;
}

.brand-title {
    font-size: 36px;
    font-weight: 800;
    color: #ffffff;
    margin-bottom: 8px;
}

.green {
    color: #00d68f;
}

.brand-subtitle {
    font-size: 16px;
    color: #c5cbd5;
    margin-bottom: 8px;
}

.small-note {
    font-size: 13px;
    color: #00d68f;
    margin-bottom: 20px;
}

div[data-testid="stChatMessage"] {
    border-radius: 12px;
    padding: 12px;
}

div[data-testid="stChatInput"] {
    border-radius: 14px;
}

section[data-testid="stSidebar"] {
    background-color: #151922;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# 12. BRANDING
# =========================================================

st.markdown("""
<div class="brand-title">
    🤖  Chat With Raghava AI
    <span class="green"></span>
</div>


""", unsafe_allow_html=True)


# =========================================================
# 13. SIDEBAR
# =========================================================

with st.sidebar:

    st.title("⚙️ Settings")

    st.subheader("AI Provider")

    provider = st.selectbox(
        "Select AI provider",
        ["Groq (Cloud)", "Ollama (Local)"]
    )

    if provider == "Groq (Cloud)":

        selected_model = st.selectbox(
            "Select Groq model",
            GROQ_MODELS
        )

        st.caption("Groq runs using a cloud API.")

    else:

        selected_model = st.selectbox(
            "Select Ollama model",
            OLLAMA_MODELS
        )

        st.caption("Ollama runs models on your computer.")

        if check_ollama():
            st.success("Ollama is connected.")
        else:
            st.warning(
                "Ollama is not responding. "
                "Start Ollama and try again."
            )

    st.divider()

    st.subheader("Response settings")

    temperature = st.slider(
        "Temperature",
        min_value=0.0,
        max_value=1.5,
        value=0.3,
        step=0.1
    )

    extra_prompt = st.text_area(
        "Additional system instructions",
        placeholder="Add your instructions here..."
    )

    st.divider()

    st.subheader("🎤 Voice settings")

    voice_output = st.toggle(
        "Speak AI responses",
        value=False
    )

    st.caption(
        "Turn ON to enable browser speech output. "
        "Your browser must support speech synthesis."
    )

    st.divider()

    if st.button("🗑️ Clear Chat", use_container_width=True):

        st.session_state.messages = []
        st.session_state.pending_voice_text = ""
        st.session_state.last_response = ""

        st.rerun()

    st.caption("Raghava AI | Personal AI Assistant")


# =========================================================
# 14. DISPLAY CHAT HISTORY
# =========================================================

for message in st.session_state.messages:

    with st.chat_message(message["role"]):

        st.markdown(message["content"])


# =========================================================
# 15. CHAT INPUT WITH MICROPHONE
# =========================================================

try:

    user_prompt = st.chat_input(
        "Message Raghava AI...",
        accept_audio=True,
        audio_sample_rate=16000,
        key="raghava_chat_input"
    )

except TypeError:

    st.error(
        "Your Streamlit version does not support audio chat input. "
        "Upgrade Streamlit using: "
        "python -m pip install --upgrade streamlit"
    )

    user_prompt = None


# =========================================================
# 16. HANDLE TEXT AND AUDIO INPUT
# =========================================================

if user_prompt is not None:

    actual_prompt = ""

    if isinstance(user_prompt, str):

        actual_prompt = user_prompt.strip()

    else:

        typed_text = getattr(user_prompt, "text", None)

        audio_data = getattr(user_prompt, "audio", None)

        if typed_text:
            actual_prompt = typed_text.strip()

        if audio_data is not None:

            with st.spinner("🎤 Recognizing your speech..."):

                recognized_text = transcribe_audio(audio_data)

            if recognized_text:

                st.success("Voice recognized!")

                st.caption(
                    f"Recognized speech: {recognized_text}"
                )

                if actual_prompt:
                    actual_prompt = (
                        actual_prompt + " " + recognized_text
                    )
                else:
                    actual_prompt = recognized_text

    if actual_prompt:

        st.session_state.messages.append({
            "role": "user",
            "content": actual_prompt
        })

        with st.chat_message("user"):
            st.markdown(actual_prompt)

        messages_for_model = [
            {
                "role": "system",
                "content": build_system_prompt(extra_prompt)
            }
        ]

        messages_for_model.extend(
            st.session_state.messages[-20:]
        )

        response_placeholder = st.empty()

        try:

            with st.chat_message("assistant"):

                response_placeholder = st.empty()

                full_response = ""

                with st.spinner("Raghava AI is thinking..."):

                    if provider == "Groq (Cloud)":

                        response_stream = get_groq_response(
                            messages_for_model,
                            selected_model,
                            temperature
                        )

                    else:

                        response_stream = get_ollama_response(
                            messages_for_model,
                            selected_model,
                            temperature
                        )

                    for token in response_stream:

                        full_response += token

                        response_placeholder.markdown(
                            full_response + "▌"
                        )

                response_placeholder.markdown(full_response)

            if full_response.strip():

                st.session_state.messages.append({
                    "role": "assistant",
                    "content": full_response
                })

                st.session_state.last_response = full_response

                if voice_output:
                    speak_text(full_response)

            else:
                st.warning("The AI returned an empty response.")

        except Exception as e:

            st.error(f"AI response failed: {e}")


# =========================================================
# 17. FOOTER
# =========================================================

st.markdown("""
<hr>
<div style="text-align:center;color:#888;font-size:12px;">
    🤖 Raghava AI | Built with Python, Streamlit,
    Groq and Ollama
</div>
""", unsafe_allow_html=True)
