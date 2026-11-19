import os
import json
import requests
import streamlit as st
from groq import Groq
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = ("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")

st.set_page_config(
    page_title="Chat with Raghava AI",
    page_icon="🤖",
    layout="centered"
)

st.markdown("""
<style>
.block-container {
    max-width: 850px;
    padding-top: 2rem;
}

.hero-card {
    background: linear-gradient(135deg, #111827, #020617);
    border: 1px solid rgba(34,197,94,0.40);
    border-radius: 24px;
    padding: 26px;
    margin-bottom: 20px;
    box-shadow: 0 12px 40px rgba(0,0,0,0.20);
}

.brand-title {
    font-size: 34px;
    font-weight: 800;
    color: #f8fafc;
    margin-bottom: 6px;
}

.brand-subtitle {
    font-size: 16px;
    color: #d1d5db;
}

.green {
    color: #22c55e;
}

.small-note {
    color: #9ca3af;
    font-size: 13px;
    margin-top: 8px;
}

.stButton button {
    border-radius: 12px;
    background-color: #22c55e;
    color: #052e16;
    font-weight: 700;
    border: none;
}

.stButton button:hover {
    background-color: #16a34a;
    color: #052e16;
}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="hero-card">
    <div class="brand-title">
        Raghava AI <span class="green">Local AI Chatbot</span>
    </div>
    <div class="brand-subtitle">
        Build your Generative AI app using Python, Streamlit,
        Ollama and Groq.
    </div>
    <div class="small-note">
        Chat UI + Memory + Streaming + Temperature Control
    </div>
</div>
""", unsafe_allow_html=True)

# --------------------------------------------------
# PROVIDER CONFIGURATION
# --------------------------------------------------

OLLAMA_URL = "http://localhost:11434/api/chat"

OLLAMA_MODELS = [
    "llama3.2",
    "llama3.1",
    "llama3",
    "mistral",
    "gemma2",
    "qwen2.5",
    "qwen2.5:3b"
]

GROQ_MODELS = [
    "openai/gpt-oss-20b",
    "openai/gpt-oss-120b",
    "llama-3.3-70b-versatile",
    "llama-3.1-8b-instant"
]

# --------------------------------------------------
# SESSION MEMORY
# --------------------------------------------------

if "messages" not in st.session_state:
    st.session_state.messages = []

with st.sidebar:
    st.title("⚙️ Settings")

    provider = st.selectbox(
        "Choose AI Provider",
        [ "Groq (Cloud)"]
    )

    model = st.selectbox(
    "Choose Groq Model",
     GROQ_MODELS,
     index=0
     )

    temperature = st.slider(
        "Temperature / Creativity",
        min_value=0.0,
        max_value=1.0,
        value=0.7,
        step=0.1,
        help="0 = focused, 1 = more creative"
    )

    system_prompt = st.text_area(
        "System Prompt",
        value=(
            "You are a helpful AI assistant. "
            "Explain concepts clearly and simply. "
            "When useful, respond with examples."
        ),
        height=120
    )

    if st.button("Clear Chat"):
        st.session_state.messages = []
        st.rerun()

    st.markdown("---")
    st.markdown("### Teaching Notes")
    st.markdown("- Ollama runs models locally")
    st.markdown("- Groq runs models in the cloud")
    st.markdown("- Chat history provides conversation context")
    st.markdown("- Streaming displays responses as they arrive")
    st.markdown("- Temperature controls creativity")

def check_ollama_running():
    try:
        response = requests.get(
            "http://localhost:11434",
            timeout=3
        )
        return response.status_code == 200

    except requests.exceptions.RequestException:
        return False


for message in st.session_state.messages:
    with st.chat_message(message["role"]):
        st.markdown(message["content"])

user_prompt = st.chat_input(
    "Ask anything... Try Telugu also: Generative AI ante enti?"
)

if user_prompt:

    st.session_state.messages.append({
        "role": "user",
        "content": user_prompt
    })

    with st.chat_message("user"):
        st.markdown(user_prompt)

    messages_for_model = [
        {
            "role": "system",
            "content": system_prompt
        }
    ]

    messages_for_model.extend(st.session_state.messages)

    with st.chat_message("assistant"):

        response_placeholder = st.empty()
        full_response = ""

        try:


            if provider == "Ollama (Local)":

                if not check_ollama_running():
                    raise RuntimeError(
                        "Ollama is not running. "
                        "Start Ollama on your computer and try again."
                    )

                payload = {
                    "model": model,
                    "messages": messages_for_model,
                    "stream": True,
                    "options": {
                        "temperature": temperature
                    }
                }

                with requests.post(
                    OLLAMA_URL,
                    json=payload,
                    stream=True,
                    timeout=120
                ) as response:

                    response.raise_for_status()

                    for line in response.iter_lines():

                        if not line:
                            continue

                        chunk = json.loads(
                            line.decode("utf-8")
                        )

                        content = chunk.get(
                            "message", {}
                        ).get("content", "")

                        if content:
                            full_response += content

                            response_placeholder.markdown(
                                full_response + "▌"
                            )

                        if chunk.get("done", False):
                            break


            elif provider == "Groq (Cloud)":

                if not GROQ_API_KEY:
                    raise RuntimeError(
                        "GROQ_API_KEY is missing. "
                        "Add it in Render Environment settings."
                    )

                client = Groq(
                    api_key=GROQ_API_KEY
                )

                stream = client.chat.completions.create(
                    model=model,
                    messages=messages_for_model,
                    temperature=temperature,
                    stream=True
                )

                for chunk in stream:

                    content = (
                        chunk.choices[0].delta.content
                    )

                    if content:
                        full_response += content

                        response_placeholder.markdown(
                            full_response + "▌"
                        )

            response_placeholder.markdown(full_response)

        except Exception as e:

            full_response = f"Error: {str(e)}"

            response_placeholder.error(full_response)

    st.session_state.messages.append({
        "role": "assistant",
        "content": full_response
    })
