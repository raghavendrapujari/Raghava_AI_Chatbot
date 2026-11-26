
import os
import io
import re
import json
import uuid
import base64
import html
from pathlib import Path
from datetime import datetime, date, time as dt_time

import requests
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
    "meta-llama/llama-4-scout-17b-16e-instruct"
).strip()
WHISPER_MODEL = os.getenv(
    "GROQ_WHISPER_MODEL", "whisper-large-v3"
).strip()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "").strip()
IMAGE_MODEL = os.getenv(
    "OPENAI_IMAGE_MODEL", "gpt-image-2.6-flare"
).strip()

FAL_KEY = os.getenv("FAL_KEY", "").strip()
FAL_VIDEO_MODEL = os.getenv(
    "FAL_VIDEO_MODEL",
    "fal-ai/minimax/h3-max/text-to-video"
).strip()

JSEARCH_API_KEY = os.getenv("JSEARCH_API_KEY", "").strip()

CHATS_FILE = BASE_DIR / "chats.json"
PROJECTS_FILE = BASE_DIR / "projects.json"
SCHEDULED_FILE = BASE_DIR / "scheduled.json"

IMAGES_DIR = BASE_DIR / "images"
VIDEOS_DIR = BASE_DIR / "videos"
LIBRARY_DIR = BASE_DIR / "library"

for folder in (IMAGES_DIR, VIDEOS_DIR, LIBRARY_DIR):
    folder.mkdir(exist_ok=True)

FILE_TYPES = [
    "pdf", "docx", "txt", "png", "jpg", "jpeg", "webp"
]

USER_NAME = "Raghava"

SYSTEM_PROMPT = """
You are Raghava AI, a capable general-purpose AI assistant.

Always reply in clear English.

You can help with:
- General questions and explanations
- Programming and debugging
- Python, Java, web development and AI
- Learning and interview preparation
- Writing, editing and summarizing
- Career guidance and job searches
- Uploaded PDF, DOCX and TXT documents
- Uploaded image analysis
- Research and planning

Rules:
- Give useful, accurate answers.
- Explain difficult topics step by step.
- When writing code, provide complete runnable examples.
- Use attached documents as the main source when relevant.
- Never invent job openings, application links or factual information.
- Never claim to have generated an image, video or performed an action
  unless the operation actually succeeded.
- Clearly explain when an external service or API is unavailable.
- Do not expose API keys or private configuration.
"""

NAV_ITEMS = [
    ("chat", "New Chat", ":material/edit_square:"),
    ("search", "Search", ":material/search:"),
    ("jobs", "Find Jobs", ":material/work:"),
    ("images", "Images", ":material/image_search:"),
    ("scheduled", "Scheduled", ":material/event:"),
    ("library", "Library", ":material/library_books:"),
    ("plugins", "Features", ":material/extension:"),
    ("explore", "Explore", ":material/apps:"),
]

SUGGESTIONS = [
    ("✏️", "Write or edit", "Help me write or edit something."),
    ("💻", "Write code", "Help me write or debug Python code."),
    ("🧠", "Explain a concept", "Explain a topic step by step."),
    ("💼", "Find jobs", "Find today's fresher Python Developer jobs in India."),
    ("🖼️", "Generate an image", "Generate an image of a beautiful futuristic city."),
    ("📄", "Analyze a document", "I want to upload a document and ask questions about it."),
]

EXPLORE = {
    "Writing": [
        ("Professional email", "Write a professional email."),
        ("Improve my text", "Improve my grammar and writing."),
        ("Summarize text", "Summarize text into important points."),
    ],
    "Coding": [
        ("Explain Python", "Explain Python code line by line."),
        ("Debug code", "Help me debug my code."),
        ("Build a project", "Give me a complete beginner Python project."),
    ],
    "Career": [
        ("Find fresher jobs", "Find today's fresher jobs in India."),
        ("Resume review", "Help me improve my resume."),
        ("Mock interview", "Start a mock interview for a Python Developer role."),
    ],
}


# ============================================================
# STORAGE
# ============================================================

def load_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
        return data if isinstance(data, dict) else {}
    except Exception:
        return {}


def write_json(path, data):
    try:
        path.write_text(
            json.dumps(data, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    except Exception:
        pass


def save_chats():
    write_json(CHATS_FILE, st.session_state.chats)


def save_projects():
    write_json(PROJECTS_FILE, st.session_state.projects)


def save_scheduled():
    write_json(SCHEDULED_FILE, st.session_state.scheduled)


def make_title(text):
    text = " ".join((text or "").split())
    return text[:34] + ("…" if len(text) > 34 else "") or "New chat"


def save_image(data, extension="jpg"):
    try:
        name = f"{uuid.uuid4().hex[:12]}.{extension}"
        path = IMAGES_DIR / name
        path.write_bytes(data)
        return name
    except Exception:
        return None


def save_library_file(filename, data):
    try:
        safe = "".join(
            c for c in Path(filename).name
            if c.isalnum() or c in "._- "
        ) or "file"

        stored = f"{uuid.uuid4().hex[:8]}_{safe}"
        (LIBRARY_DIR / stored).write_bytes(data)
        return stored
    except Exception:
        return None


# ============================================================
# SESSION STATE
# ============================================================

DEFAULTS = {
    "view": "chat",
    "chat_id": None,
    "active_project": None,
    "new_chat_project": None,
    "pending": None,
    "show_search": False,
    "show_new_project": False,
    "camera_enabled": False,
    "nonce": 0,
    "think_mode": False,
    "voice_output": False,
    "sidebar_open_v2": False,
    "job_query": "",
}

if "chats" not in st.session_state:
    st.session_state.chats = load_json(CHATS_FILE)

if "projects" not in st.session_state:
    st.session_state.projects = load_json(PROJECTS_FILE)

if "scheduled" not in st.session_state:
    st.session_state.scheduled = load_json(SCHEDULED_FILE)

for key, value in DEFAULTS.items():
    if key not in st.session_state:
        st.session_state[key] = value

if st.session_state.chat_id not in st.session_state.chats:
    st.session_state.chat_id = None

if st.session_state.active_project not in st.session_state.projects:
    st.session_state.active_project = None


# ============================================================
# GROQ CLIENT
# ============================================================

@st.cache_resource
def get_groq_client(key):
    return Groq(api_key=key)


client = None

if GROQ_API_KEY:
    try:
        client = get_groq_client(GROQ_API_KEY)
    except Exception:
        client = None


# ============================================================
# DOCUMENT AND IMAGE HELPERS
# ============================================================

def extract_document_text(filename, data):
    name = filename.lower()

    try:
        if name.endswith(".pdf"):
            reader = PdfReader(io.BytesIO(data))
            return "\n".join(
                page.extract_text() or ""
                for page in reader.pages
            )

        if name.endswith(".docx"):
            doc = Document(io.BytesIO(data))
            return "\n".join(
                paragraph.text for paragraph in doc.paragraphs
            )

        if name.endswith(".txt"):
            return data.decode("utf-8", errors="replace")

        return ""

    except Exception as exc:
        return f"Could not read {filename}: {exc}"


def image_to_data_url(data):
    try:
        image = Image.open(io.BytesIO(data)).convert("RGB")
        image.thumbnail((1280, 1280))

        output = io.BytesIO()
        image.save(output, format="JPEG", quality=85)

        encoded = base64.b64encode(
            output.getvalue()
        ).decode("ascii")

        return "data:image/jpeg;base64," + encoded

    except Exception:
        return None


def transcribe_audio(audio):
    if not client:
        return None, "Groq API key is not configured."

    try:
        result = client.audio.transcriptions.create(
            file=(
                getattr(audio, "name", "recording.wav"),
                audio.getvalue(),
            ),
            model=WHISPER_MODEL,
            language="en",
        )
        return result.text.strip(), None

    except Exception as exc:
        return None, str(exc)


# ============================================================
# WEBPAGE LINK READER
# ============================================================

def read_webpage(url):
    url = (url or "").strip()

    if not re.match(r"^https?://", url, re.I):
        return "Please provide a valid HTTP or HTTPS webpage link."

    try:
        from bs4 import BeautifulSoup

        response = requests.get(
            url,
            timeout=20,
            headers={"User-Agent": "Mozilla/5.0 RaghavaAI/1.0"},
        )
        response.raise_for_status()

        soup = BeautifulSoup(response.text, "html.parser")

        for tag in soup([
            "script", "style", "nav", "footer", "header",
            "noscript", "svg",
        ]):
            tag.decompose()

        text = soup.get_text(separator="\n", strip=True)
        return text[:18000] or "No readable page text was found."

    except Exception as exc:
        return f"Could not read this webpage: {exc}"


# ============================================================
# LIVE JOB SEARCH
# ============================================================

def is_job_request(prompt):
    terms = [
        "job", "jobs", "opening", "openings", "vacancy",
        "vacancies", "hiring", "fresher", "internship",
        "employment", "career", "work from home",
        "remote job", "job search",
    ]
    text = (prompt or "").lower()
    return any(term in text for term in terms)


def build_job_query(prompt, document_text=""):
    prompt = (prompt or "").strip()

    skills = [
        "Python", "Java", "JavaScript", "SQL", "MySQL",
        "FastAPI", "Django", "Flask", "React",
        "Machine Learning", "Artificial Intelligence",
        "Generative AI", "LLM", "RAG", "OpenCV",
        "YOLO", "Pandas", "NumPy", "Scikit-learn",
        "AWS", "Data Analyst", "Software Developer",
        "Computer Vision", "REST API",
    ]

    found = []

    if document_text:
        lower = document_text.lower()
        found = [
            skill for skill in skills
            if skill.lower() in lower
        ]

    if document_text and (
        "resume" in prompt.lower()
        or "cv" in prompt.lower()
        or "matching" in prompt.lower()
        or "based on my" in prompt.lower()
    ):
        if found:
            prompt += " " + " ".join(found[:8])

    return prompt[:400]


def search_jobs(query, date_posted="all", country="in"):
    if not JSEARCH_API_KEY:
        return [], "Job search is not configured. Add JSEARCH_API_KEY to your environment variables."

    params = {
        "query": query,
        "page": "1",
        "num_pages": "1",
        "country": country.lower(),
        "date_posted": date_posted,
    }

    headers = {
        "X-RapidAPI-Key": JSEARCH_API_KEY,
        "X-RapidAPI-Host": "jsearch.p.rapidapi.com",
    }

    try:
        response = requests.get(
            "https://jsearch.p.rapidapi.com/search",
            params=params,
            headers=headers,
            timeout=30,
        )

        response.raise_for_status()
        payload = response.json()

        jobs = []

        for item in payload.get("data", []):
            experience = item.get("job_required_experience") or {}

            location_parts = [
                item.get("job_city"),
                item.get("job_state"),
                item.get("job_country"),
            ]

            location = ", ".join(
                str(x) for x in location_parts if x
            ) or "Location not provided"

            jobs.append({
                "title": item.get("job_title") or "Job title unavailable",
                "company": item.get("employer_name") or "Company not provided",
                "location": location,
                "remote": bool(item.get("job_is_remote")),
                "type": item.get("job_employment_type") or "Not specified",
                "experience": (
                    experience.get("required_experience_in_months")
                    if experience else None
                ),
                "no_experience": experience.get("no_experience_required", False),
                "salary_min": item.get("job_min_salary"),
                "salary_max": item.get("job_max_salary"),
                "salary_currency": item.get("job_salary_currency") or "",
                "posted": item.get("job_posted_at_datetime_utc") or "",
                "description": (item.get("job_description") or "")[:1200],
                "url": item.get("job_apply_link") or "",
            })

        return jobs, None

    except requests.HTTPError as exc:
        return [], f"Job provider returned an error: {exc}"
    except Exception as exc:
        return [], f"Job search failed: {exc}"


def render_jobs(jobs):
    if not jobs:
        st.info("No job listings were returned for this search.")
        return

    st.markdown(f"### Found {len(jobs)} job listing(s)")

    for index, job in enumerate(jobs):
        with st.container(border=True):
            st.markdown(f"**{html.escape(job['title'])}**")
            st.markdown(f"🏢 {html.escape(job['company'])}")
            st.caption(
                f"📍 {job['location']}  ·  "
                f"{'Remote' if job['remote'] else 'On-site / unspecified'}"
            )

            details = [job["type"]]

            if job["no_experience"]:
                details.append("No experience required")
            elif job["experience"] is not None:
                details.append(
                    f"{job['experience']} months experience"
                )

            if job["salary_min"] is not None:
                salary = (
                    f"{job['salary_currency']} "
                    f"{job['salary_min']}"
                )
                if job["salary_max"] is not None:
                    salary += f" - {job['salary_max']}"
                details.append(salary)

            if job["posted"]:
                details.append(f"Posted: {job['posted'][:10]}")

            st.caption(" · ".join(details))

            if job["description"]:
                with st.expander("Job description"):
                    st.write(job["description"])

            url = job.get("url", "")

            if url.startswith("https://") or url.startswith("http://"):
                st.link_button(
                    "Apply for this job",
                    url,
                    use_container_width=True,
                )
            else:
                st.caption("Application link not provided by the job source.")


def render_jobs_page():
    st.title("💼 Find Jobs")
    st.caption(
        "Search job openings, fresher roles, internships and remote jobs."
    )

    with st.form("job_search_form"):
        query = st.text_input(
            "What job are you looking for?",
            placeholder="Python Developer fresher jobs in Bengaluru",
        )

        col1, col2 = st.columns(2)

        with col1:
            country = st.selectbox(
                "Country",
                ["India", "United States", "United Kingdom", "Canada", "Australia"],
            )

        with col2:
            posted = st.selectbox(
                "Posted",
                ["All", "Today", "Last 3 days", "Last week", "Last month"],
            )

        submitted = st.form_submit_button(
            "Search jobs",
            use_container_width=True,
        )

    if submitted:
        if not query.strip():
            st.warning("Enter a job title or skill.")
        else:
            date_map = {
                "All": "all",
                "Today": "today",
                "Last 3 days": "3days",
                "Last week": "week",
                "Last month": "month",
            }

            country_map = {
                "India": "in",
                "United States": "us",
                "United Kingdom": "gb",
                "Canada": "ca",
                "Australia": "au",
            }

            with st.spinner("Searching live job listings..."):
                jobs, error = search_jobs(
                    query,
                    date_map[posted],
                    country_map[country],
                )

            if error:
                st.error(error)
            else:
                st.session_state.job_results_page = jobs

    if st.session_state.get("job_results_page") is not None:
        render_jobs(st.session_state.job_results_page)


# ============================================================
# IMAGE GENERATION
# ============================================================

def generate_image(prompt):
    if not OPENAI_API_KEY:
        return None, "Image generation is not configured. Add OPENAI_API_KEY."

    try:
        response = requests.post(
            "https://api.openai.com/v1/images/generations",
            headers={
                "Authorization": f"Bearer {OPENAI_API_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "model": IMAGE_MODEL,
                "prompt": prompt,
                "n": 1,
                "size": "1024x1024",
                "quality": "medium",
            },
            timeout=180,
        )

        response.raise_for_status()
        result = response.json()

        encoded = result["data"][0].get("b64_json")

        if not encoded:
            return None, "The image provider returned no image data."

        return base64.b64decode(encoded), None

    except Exception as exc:
        return None, f"Image generation failed: {exc}"


# ============================================================
# VIDEO GENERATION
# ============================================================

def generate_video(prompt):
    if not FAL_KEY:
        return None, "Video generation is not configured. Add FAL_KEY."

    try:
        response = requests.post(
            f"https://fal.run/{FAL_VIDEO_MODEL}",
            headers={
                "Authorization": f"Key {FAL_KEY}",
                "Content-Type": "application/json",
            },
            json={
                "prompt": prompt,
            },
            timeout=600,
        )

        response.raise_for_status()
        result = response.json()

        video_url = (
            result.get("video", {}).get("url")
            or result.get("video_url")
            or result.get("url")
        )

        if not video_url:
            return None, (
                "The video provider did not return a video URL. "
                "Check the selected model's input and output requirements."
            )

        return video_url, None

    except requests.Timeout:
        return None, (
            "Video generation timed out. Try again with a shorter prompt "
            "or use the provider's queue-based workflow."
        )
    except Exception as exc:
        return None, f"Video generation failed: {exc}"


# ============================================================
# CHAT INTENT DETECTION
# ============================================================

def wants_image(prompt):
    text = prompt.lower()
    return any(x in text for x in [
        "generate an image", "generate image",
        "create an image", "create image",
        "make an image", "draw me",
        "generate a picture", "create a picture",
    ])


def wants_video(prompt):
    text = prompt.lower()
    return any(x in text for x in [
        "generate a video", "generate video",
        "create a video", "create video",
        "make a video", "text to video",
    ])


def wants_link_reading(prompt):
    return bool(re.search(r"https?://\S+", prompt or "", re.I))


# ============================================================
# AI CHAT
# ============================================================

def generate_response(
    history,
    prompt,
    document_text="",
    image_urls=None,
    extra_context="",
):
    if not client:
        return "Groq API key is missing. Configure GROQ_API_KEY."

    system = SYSTEM_PROMPT

    if st.session_state.think_mode:
        system += "\nThink carefully and give a structured answer."

    if document_text:
        system += (
            "\n\nThe user attached documents. Use the following extracted "
            "content when answering:\n"
            + document_text[:35000]
        )

    if extra_context:
        system += "\n\nAdditional verified context:\n" + extra_context[:18000]

    history_messages = [
        {"role": item["role"], "content": item["content"]}
        for item in history
        if item.get("role") in ("user", "assistant")
        and isinstance(item.get("content"), str)
    ]

    if image_urls:
        content = [
            {
                "type": "text",
                "text": prompt or "Please analyze these images.",
            }
        ]

        for url in image_urls:
            content.append({
                "type": "image_url",
                "image_url": {"url": url},
            })

        current = {"role": "user", "content": content}
        model = VISION_MODEL

    else:
        current = {
            "role": "user",
            "content": prompt or "Please analyze the attached document.",
        }
        model = CHAT_MODEL

    try:
        stream = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system},
                *history_messages,
                current,
            ],
            stream=True,
            max_completion_tokens=3000,
        )

        output = st.empty()
        answer = ""

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
            f"Error: {exc}\n\n"
            "Check your API key and model configuration."
        )


# ============================================================
# SPEECH OUTPUT
# ============================================================

def speak_english(text):
    try:
        safe_text = json.dumps(text)

        st.components.v1.html(
            f"""
            <script>
            const text = {safe_text};
            if ("speechSynthesis" in window) {{
                window.speechSynthesis.cancel();
                const u = new SpeechSynthesisUtterance(text);
                u.lang = "en-US";
                window.speechSynthesis.speak(u);
            }}
            </script>
            """,
            height=0,
        )
    except Exception:
        pass


# ============================================================
# TURN HANDLING
# ============================================================

def start_turn(
    prompt,
    document_text="",
    image_urls=None,
    attachment_names=None,
    image_names=None,
    file_records=None,
):
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
        "attachments": attachment_names or [],
        "images": image_names or [],
        "files": file_records or [],
    })

    st.session_state.pending = {
        "document_text": document_text,
        "image_urls": image_urls or [],
    }

    st.session_state.view = "chat"
    st.session_state.nonce += 1
    st.session_state.camera_enabled = False

    save_chats()
    st.rerun()


def handle_submission(text, files, audio, photo_bytes):
    prompt = (text or "").strip()

    if audio is not None:
        with st.spinner("Transcribing voice..."):
            transcript, error = transcribe_audio(audio)

        if transcript:
            prompt = (prompt + "\n" + transcript).strip()
        elif error:
            st.warning(error)

    document_chunks = []
    image_urls = []
    names = []
    image_names = []
    file_records = []

    for file in files or []:
        filename = file.name
        data = file.getvalue()
        lower = filename.lower()

        if lower.endswith((".pdf", ".docx", ".txt")):
            document_chunks.append(
                f"FILE: {filename}\n"
                + extract_document_text(filename, data)
            )

            names.append(filename)

            stored = save_library_file(filename, data)

            if stored:
                file_records.append({
                    "name": filename,
                    "stored": stored,
                })

        elif lower.endswith((".png", ".jpg", ".jpeg", ".webp")):
            url = image_to_data_url(data)

            if url:
                image_urls.append(url)
                names.append(filename)

                saved = save_image(data)

                if saved:
                    image_names.append(saved)

    if photo_bytes:
        url = image_to_data_url(photo_bytes)

        if url:
            image_urls.append(url)
            names.append("Camera photo")

            saved = save_image(photo_bytes)

            if saved:
                image_names.append(saved)

    document_text = "\n\n".join(document_chunks)

    if not prompt and (document_text or image_urls):
        prompt = "Please analyze my attached file or image and explain it."

    if prompt:
        start_turn(
            prompt,
            document_text,
            image_urls,
            names,
            image_names,
            file_records,
        )


# ============================================================
# JOB RESULTS PAGE / MESSAGE DISPLAY
# ============================================================

def render_message_extras(message):
    jobs = message.get("jobs", [])

    if jobs:
        render_jobs(jobs)

    image_name = message.get("generated_image")

    if image_name:
        path = IMAGES_DIR / image_name
        if path.exists():
            st.image(str(path), use_container_width=True)

            st.download_button(
                "Download generated image",
                data=path.read_bytes(),
                file_name="raghava_generated_image.png",
                mime="image/png",
                key=f"download_image_{image_name}",
            )

    video_url = message.get("generated_video")

    if video_url:
        st.video(video_url)
        st.markdown(f"[Open generated video]({video_url})")


# ============================================================
# CHAT PROCESSING
# ============================================================

def process_pending(messages):
    pending = st.session_state.pending

    if not pending:
        return

    st.session_state.pending = None

    prompt = messages[-1]["content"]
    document_text = pending.get("document_text", "")
    image_urls = pending.get("image_urls", [])

    jobs = []
    job_error = None
    generated_image = None
    generated_video = None
    extra_context = ""

    # 1. Image generation
    if wants_image(prompt):
        with st.spinner("Generating your image..."):
            image_data, error = generate_image(prompt)

        if image_data:
            generated_image = save_image(image_data, "png")
            answer = "Your image has been generated."
        else:
            answer = error or "Image generation failed."

    # 2. Video generation
    elif wants_video(prompt):
        with st.spinner("Generating your video. This may take a while..."):
            generated_video, error = generate_video(prompt)

        answer = (
            "Your video has been generated."
            if generated_video
            else error or "Video generation failed."
        )

    else:
        # 3. Job search
        if is_job_request(prompt):
            query = build_job_query(prompt, document_text)

            date_posted = "all"
            lower = prompt.lower()

            if "today" in lower or "today's" in lower:
                date_posted = "today"
            elif "last 3 days" in lower or "3 days" in lower:
                date_posted = "3days"
            elif "this week" in lower or "last week" in lower:
                date_posted = "week"

            with st.spinner("Searching live job openings..."):
                jobs, job_error = search_jobs(
                    query,
                    date_posted=date_posted,
                    country="in",
                )

            if jobs:
                extra_context = (
                    "The following job listings were retrieved from the "
                    "job search provider. The UI will display the actual "
                    "application links separately. Do not invent additional "
                    "job listings.\n"
                    + json.dumps(jobs[:10], ensure_ascii=False)
                )

        # 4. Webpage reading
        if wants_link_reading(prompt):
            urls = re.findall(r"https?://\S+", prompt)

            if urls:
                with st.spinner("Reading the webpage..."):
                    page_text = read_webpage(urls[0])

                extra_context += (
                    "\n\nWebpage content from " + urls[0] + ":\n"
                    + page_text[:15000]
                )

        with st.chat_message("assistant"):
            answer = generate_response(
                messages[:-1],
                prompt,
                document_text,
                image_urls,
                extra_context,
            )

            if job_error:
                st.warning(job_error)

            if jobs:
                render_jobs(jobs)

    assistant_message = {
        "role": "assistant",
        "content": answer,
        "jobs": jobs,
        "generated_image": generated_image,
        "generated_video": generated_video,
    }

    messages.append(assistant_message)
    save_chats()

    if generated_image:
        st.rerun()

    if st.session_state.voice_output:
        speak_english(answer)


# ============================================================
# SIDEBAR HELPERS
# ============================================================

def project_label(project_id):
    if not project_id:
        return "No project"

    project = st.session_state.projects.get(project_id)
    return project["name"] if project else "No project"


def delete_chat(chat_id):
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


def render_chat_row(chat_id, chat):
    left, right = st.columns([0.84, 0.16])

    with left:
        active = chat_id == st.session_state.chat_id

        if st.button(
            chat.get("title", "Chat"),
            key=f"chat_{chat_id}",
            type="primary" if active else "secondary",
        ):
            st.session_state.view = "chat"
            st.session_state.chat_id = chat_id
            st.rerun()

    with right:
        with st.popover("More", icon=":material/more_horiz:"):
            if st.button("Pin / Unpin", key=f"pin_{chat_id}"):
                chat["pinned"] = not chat.get("pinned", False)
                save_chats()
                st.rerun()

            project_ids = [None] + list(st.session_state.projects.keys())
            current = chat.get("project")

            if current not in project_ids:
                current = None

            choice = st.selectbox(
                "Move to project",
                project_ids,
                index=project_ids.index(current),
                format_func=project_label,
                key=f"move_{chat_id}",
            )

            if choice != current:
                chat["project"] = choice
                save_chats()
                st.rerun()

            if st.button("Delete chat", key=f"delete_{chat_id}"):
                delete_chat(chat_id)
                st.rerun()


# ============================================================
# OTHER PAGES
# ============================================================

def render_images_page():
    st.title("Images")
    st.caption("Images from your conversations.")

    found = []

    for chat_id, chat in st.session_state.chats.items():
        for message in chat.get("messages", []):
            for name in message.get("images", []) or []:
                path = IMAGES_DIR / name
                if path.exists():
                    found.append((chat_id, chat.get("title", ""), path))

            generated = message.get("generated_image")
            if generated:
                path = IMAGES_DIR / generated
                if path.exists():
                    found.append((chat_id, chat.get("title", ""), path))

    if not found:
        st.info("No images yet.")
        return

    cols = st.columns(3)

    for index, (chat_id, title, path) in enumerate(found):
        with cols[index % 3]:
            st.image(str(path))
            st.caption(title)

            if st.button("Open chat", key=f"image_chat_{index}"):
                st.session_state.chat_id = chat_id
                st.session_state.view = "chat"
                st.rerun()


def render_library_page():
    st.title("Library")
    st.caption("Documents uploaded in your conversations.")

    found = []

    for chat_id, chat in st.session_state.chats.items():
        for message in chat.get("messages", []):
            for record in message.get("files", []) or []:
                path = LIBRARY_DIR / record.get("stored", "")
                if path.exists():
                    found.append((chat_id, chat.get("title", ""), record, path))

    if not found:
        st.info("No documents uploaded yet.")
        return

    for index, (chat_id, title, record, path) in enumerate(found):
        with st.container(border=True):
            st.markdown(f"📄 **{record['name']}**")
            st.caption(f"Chat: {title}")

            st.download_button(
                "Download",
                data=path.read_bytes(),
                file_name=record["name"],
                key=f"file_dl_{index}",
            )

            if st.button("Open chat", key=f"file_chat_{index}"):
                st.session_state.chat_id = chat_id
                st.session_state.view = "chat"
                st.rerun()


def render_scheduled_page():
    st.title("Scheduled")
    st.caption("Create and manage your tasks.")

    with st.form("schedule_form"):
        title = st.text_input("Task title")
        prompt = st.text_area("Task prompt")
        col1, col2 = st.columns(2)

        with col1:
            due_date = st.date_input("Date", value=date.today())

        with col2:
            due_time = st.time_input("Time", value=dt_time(9, 0))

        submitted = st.form_submit_button("Add task")

    if submitted and title.strip():
        task_id = uuid.uuid4().hex[:8]

        st.session_state.scheduled[task_id] = {
            "title": title.strip(),
            "prompt": prompt.strip(),
            "due": datetime.combine(
                due_date, due_time
            ).strftime("%Y-%m-%d %H:%M"),
            "done": False,
        }

        save_scheduled()
        st.rerun()

    for task_id, task in list(st.session_state.scheduled.items()):
        with st.container(border=True):
            st.markdown(f"**{task['title']}**")
            st.caption(task.get("due", ""))

            col1, col2, col3 = st.columns(3)

            with col1:
                if st.button("Run", key=f"task_run_{task_id}"):
                    st.session_state.chat_id = None
                    start_turn(task.get("prompt", task["title"]))

            with col2:
                if st.button("Done / Undo", key=f"task_done_{task_id}"):
                    task["done"] = not task.get("done", False)
                    save_scheduled()
                    st.rerun()

            with col3:
                if st.button("Delete", key=f"task_del_{task_id}"):
                    st.session_state.scheduled.pop(task_id, None)
                    save_scheduled()
                    st.rerun()


def render_plugins_page():
    st.title("Features")

    st.session_state.think_mode = st.toggle(
        "🧠 Think mode",
        value=st.session_state.think_mode,
    )

    st.session_state.voice_output = st.toggle(
        "🔊 Speak responses",
        value=st.session_state.voice_output,
    )

    st.divider()

    features = [
        ("Chat", "Groq-powered AI assistant"),
        ("Vision", "Understand uploaded images"),
        ("Documents", "PDF, DOCX and TXT reader"),
        ("Voice", "Whisper voice transcription"),
        ("Jobs", "Live JSearch job listings"),
        ("Image generation", "OpenAI Images API"),
        ("Video generation", "fal.ai video generation"),
        ("Webpage reader", "Read accessible public webpage links"),
    ]

    for title, description in features:
        with st.container(border=True):
            st.markdown(f"**{title}**")
            st.caption(description)

    st.caption(f"Chat model: {CHAT_MODEL}")
    st.caption(f"Vision model: {VISION_MODEL}")


def render_profile_page():
    st.title("Profile")

    with st.container(border=True):
        st.markdown(f"### ✦ {USER_NAME}")
        st.caption("Raghava AI Assistant")
        st.caption("Personal AI workspace")

    st.markdown("### API configuration")

    services = [
        ("Groq chat", bool(GROQ_API_KEY)),
        ("OpenAI image generation", bool(OPENAI_API_KEY)),
        ("fal.ai video generation", bool(FAL_KEY)),
        ("JSearch job search", bool(JSEARCH_API_KEY)),
    ]

    for name, configured in services:
        st.write(
            ("🟢 " if configured else "⚪ ")
            + name
            + (" configured" if configured else " not configured")
        )


def render_explore_page():
    st.title("Explore")
    st.caption("Choose a task to start a new chat.")

    for category, items in EXPLORE.items():
        st.markdown(f"### {category}")

        cols = st.columns(2)

        for index, (title, prompt) in enumerate(items):
            with cols[index % 2]:
                with st.container(border=True):
                    st.markdown(f"**{title}**")

                    if st.button(
                        "Start",
                        key=f"explore_{category}_{index}",
                    ):
                        st.session_state.chat_id = None
                        start_turn(prompt)


def render_project_page():
    project_id = st.session_state.active_project
    project = st.session_state.projects.get(project_id)

    if not project:
        st.session_state.view = "chat"
        st.rerun()
        return

    st.title("📁 " + project["name"])

    if st.button("New chat in project"):
        st.session_state.chat_id = None
        st.session_state.new_chat_project = project_id
        st.session_state.view = "chat"
        st.rerun()

    for chat_id, chat in st.session_state.chats.items():
        if chat.get("project") == project_id:
            if st.button(chat.get("title", "Chat"), key=f"project_chat_{chat_id}"):
                st.session_state.chat_id = chat_id
                st.session_state.view = "chat"
                st.rerun()


PAGES = {
    "jobs": render_jobs_page,
    "images": render_images_page,
    "scheduled": render_scheduled_page,
    "library": render_library_page,
    "plugins": render_plugins_page,
    "explore": render_explore_page,
    "profile": render_profile_page,
    "project": render_project_page,
}


# ============================================================
# STYLE
# ============================================================

st.markdown(
    """
    <style>
    :root {
        --bg: #000;
        --panel: #171717;
        --line: #292929;
        --text: #ececec;
        --muted: #999;
        --blue: #2f6fe4;
    }

    html, body, .stApp,
    [data-testid="stAppViewContainer"],
    [data-testid="stMain"] {
        background: var(--bg) !important;
        color: var(--text) !important;
    }

    [data-testid="stHeader"] {
        background: transparent !important;
    }

    [data-testid="stDeployButton"],
    [data-testid="stToolbar"],
    [data-testid="stDecoration"],
    #MainMenu, footer {
        display: none !important;
    }

    .block-container {
        max-width: 850px;
        padding-top: 5rem;
        padding-bottom: 9rem;
    }

    section[data-testid="stSidebar"] {
        background: #000 !important;
        border-right: 1px solid var(--line);
    }

    [data-testid="stSidebar"] * {
        color: var(--text);
    }

    [data-testid="stSidebar"] [data-testid="stButton"] button {
        width: 100%;
        min-height: 40px;
        justify-content: flex-start;
        text-align: left;
        border: none;
        border-radius: 10px;
        background: transparent;
        color: var(--text);
    }

    [data-testid="stSidebar"] [data-testid="stButton"] button:hover {
        background: #202020;
    }

    [data-testid="stSidebar"] [data-testid="stBaseButton-primary"] {
        background: #252525 !important;
    }

    .brand {
        font-size: 23px;
        font-weight: 700;
        padding: 8px 6px 20px;
    }

    .side-label {
        color: var(--muted);
        font-size: 13px;
        padding: 18px 8px 6px;
    }

    .side-muted {
        color: var(--muted);
        padding: 6px 8px;
        font-size: 13px;
    }

    .page-title {
        font-size: 28px;
        font-weight: 650;
    }

    .page-sub {
        color: var(--muted);
        margin-bottom: 22px;
    }

    .welcome {
        text-align: center;
        font-size: clamp(26px, 4vw, 36px);
        margin: 16vh 0 20px;
        color: white;
    }

    [data-testid="stVerticalBlockBorderWrapper"] {
        border-color: #292929 !important;
        border-radius: 16px !important;
    }

    [data-testid="stMain"] input,
    [data-testid="stMain"] textarea,
    [data-baseweb="input"],
    [data-baseweb="textarea"] {
        background: #151515 !important;
        color: white !important;
    }

    [data-testid="stChatMessage"] {
        background: transparent !important;
        border: none !important;
    }

    .st-key-topbar {
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        height: 56px;
        z-index: 100;
        display: flex;
        align-items: center;
        justify-content: center;
        background: #000;
        border-bottom: 1px solid var(--line);
        pointer-events: none;
    }

    .topbar-title {
        font-size: 18px;
        font-weight: 600;
        color: white;
    }

    .st-key-composer_fixed {
        position: fixed;
        bottom: 0;
        left: 50%;
        transform: translateX(-50%);
        width: min(850px, calc(100vw - 2rem));
        z-index: 99;
        background: #000;
        padding: 10px 0 20px;
    }

    .st-key-pill {
        background: #212121;
        border-radius: 28px;
        padding: 7px 10px;
    }

    .st-key-pill [data-testid="stForm"] {
        border: none !important;
        background: transparent !important;
        padding: 0 !important;
    }

    .st-key-pill [data-testid="stTextInput"] input {
        background: transparent !important;
        border: none !important;
        color: white !important;
    }

    .st-key-pill [data-testid="stButton"] button,
    .st-key-pill [data-testid="stPopover"] button {
        background: transparent !important;
        border: none !important;
        border-radius: 50% !important;
        min-height: 40px;
    }

    .st-key-pill [data-testid="stFormSubmitButton"] button {
        background: var(--blue) !important;
        border-radius: 50% !important;
        color: white !important;
        width: 40px;
        height: 40px;
        min-height: 40px;
    }

    .st-key-sidebar_toggle {
        position: fixed !important;
        top: 72vh !important;
        left: 12px !important;
        width: 46px !important;
        z-index: 10002 !important;
    }

    .st-key-sidebar_toggle button {
        width: 44px !important;
        height: 44px !important;
        min-height: 44px !important;
        border-radius: 12px !important;
        background: #202020 !important;
        border: 1px solid #383838 !important;
        color: white !important;
        font-size: 26px !important;
    }

    @media(max-width: 600px) {
        .st-key-composer_fixed {
            width: calc(100vw - 1rem);
        }
    }
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# COLLAPSIBLE SIDEBAR
# ============================================================

sidebar_open = st.session_state.sidebar_open_v2
transform = "translateX(0)" if sidebar_open else "translateX(-105%)"
pointer = "auto" if sidebar_open else "none"

st.markdown(
    f"""
    <style>
    section[data-testid="stSidebar"] {{
        position: fixed !important;
        top: 0 !important;
        left: 0 !important;
        bottom: 0 !important;
        width: 280px !important;
        min-width: 280px !important;
        max-width: 280px !important;
        height: 100vh !important;
        transform: {transform} !important;
        pointer-events: {pointer} !important;
        transition: transform .28s ease-in-out !important;
        z-index: 10000 !important;
        background: #000 !important;
    }}

    section[data-testid="stSidebar"] > div {{
        height: 100vh !important;
        overflow-y: auto !important;
    }}

    [data-testid="stSidebarExpandButton"],
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"] {{
        display: none !important;
    }}

    @media(max-width:600px) {{
        section[data-testid="stSidebar"] {{
            width: 85vw !important;
            min-width: 85vw !important;
            max-width: 85vw !important;
        }}
    }}
    </style>
    """,
    unsafe_allow_html=True,
)


# ============================================================
# SIDEBAR CONTENT
# ============================================================

view = st.session_state.view

with st.sidebar:
    st.markdown(
        '<div class="brand">✦ Raghava AI</div>',
        unsafe_allow_html=True,
    )

    search_text = ""

    if st.session_state.show_search:
        search_text = st.text_input(
            "Search chats",
            placeholder="Search chats...",
            label_visibility="collapsed",
            key="sidebar_search",
        ).lower()

    for nav_id, label, icon in NAV_ITEMS:
        active = (
            (nav_id == "chat" and view == "chat" and not st.session_state.chat_id)
            or (nav_id == view)
            or (nav_id == "search" and st.session_state.show_search)
        )

        if st.button(
            label,
            key=f"nav_{nav_id}",
            icon=icon,
            type="primary" if active else "secondary",
        ):
            if nav_id == "search":
                st.session_state.show_search = not st.session_state.show_search
            else:
                st.session_state.view = nav_id

                if nav_id == "chat":
                    st.session_state.chat_id = None

            st.rerun()

    st.markdown(
        '<div class="side-label">Projects</div>',
        unsafe_allow_html=True,
    )

    if st.button("＋ New project", key="new_project_toggle"):
        st.session_state.show_new_project = not st.session_state.show_new_project
        st.rerun()

    if st.session_state.show_new_project:
        with st.form("project_create_form"):
            project_name = st.text_input("Project name")
            create = st.form_submit_button("Create project")

        if create and project_name.strip():
            pid = uuid.uuid4().hex[:8]
            st.session_state.projects[pid] = {
                "name": project_name.strip()[:40]
            }
            save_projects()
            st.session_state.show_new_project = False
            st.rerun()

    for pid, project in st.session_state.projects.items():
        if st.button(
            project["name"],
            key=f"project_{pid}",
            icon=":material/folder:",
        ):
            st.session_state.active_project = pid
            st.session_state.view = "project"
            st.rerun()

    st.markdown(
        '<div class="side-label">Recent Chats</div>',
        unsafe_allow_html=True,
    )

    chat_items = list(reversed(list(st.session_state.chats.items())))

    filtered = [
        (cid, chat)
        for cid, chat in chat_items
        if search_text in chat.get("title", "").lower()
    ]

    for cid, chat in filtered[:35]:
        render_chat_row(cid, chat)

    st.divider()

    if st.button(
        "Raghava Profile",
        key="profile_button",
        icon=":material/account_circle:",
    ):
        st.session_state.view = "profile"
        st.rerun()


# ============================================================
# TOP BAR AND SIDEBAR ARROW
# ============================================================

with st.container(key="topbar"):
    st.markdown(
        '<div class="topbar-title">✦ Raghava AI Assistant</div>',
        unsafe_allow_html=True,
    )

if st.button(
    "‹" if sidebar_open else "›",
    key="sidebar_toggle",
    help="Close or open sidebar",
):
    st.session_state.sidebar_open_v2 = not sidebar_open
    st.rerun()


# ============================================================
# PAGE ROUTING
# ============================================================

if view in PAGES:
    PAGES[view]()
    st.stop()


# ============================================================
# CHAT VIEW
# ============================================================

active_chat = st.session_state.chats.get(
    st.session_state.chat_id
)

messages = active_chat["messages"] if active_chat else []

top_area = st.container()

composer_area = st.container(
    key="composer_fixed" if messages else "composer_inline"
)

bottom_area = st.container()

nonce = st.session_state.nonce
photo = None
picked = []
recorded = None
submitted = False
typed = ""


# ============================================================
# CHAT COMPOSER
# ============================================================

with composer_area:
    if st.session_state.camera_enabled:
        photo = st.camera_input(
            "Take a photo",
            key=f"camera_{nonce}",
            label_visibility="collapsed",
        )

    with st.container(key="pill"):
        plus_col, camera_col, mic_col, message_col = st.columns(
            [0.08, 0.08, 0.15, 0.69],
            vertical_alignment="center",
        )

        with plus_col:
            with st.popover(
                "Attach",
                icon=":material/add:",
            ):
                picked = st.file_uploader(
                    "Upload documents or images",
                    type=FILE_TYPES,
                    accept_multiple_files=True,
                    key=f"upload_{nonce}",
                )

        with camera_col:
            if st.button(
                "Camera",
                key="camera_toggle",
                icon=":material/photo_camera:",
                type="primary" if st.session_state.camera_enabled else "secondary",
            ):
                st.session_state.camera_enabled = not st.session_state.camera_enabled
                st.rerun()

        with mic_col:
            recorded = st.audio_input(
                "Voice",
                key=f"audio_{nonce}",
                label_visibility="collapsed",
            )

        with message_col:
            with st.form("composer_form", clear_on_submit=True):
                text_col, send_col = st.columns([0.86, 0.14])

                with text_col:
                    typed = st.text_input(
                        "Message",
                        placeholder="Ask Raghava AI anything...",
                        label_visibility="collapsed",
                        key="composer_text",
                    )

                with send_col:
                    submitted = st.form_submit_button("↑")


if submitted:
    handle_submission(
        typed,
        picked or [],
        recorded,
        photo.getvalue() if photo is not None else None,
    )


# ============================================================
# WELCOME SCREEN
# ============================================================

if not messages:
    with top_area:
        st.markdown(
            '<div class="welcome">What’s on your mind today?</div>',
            unsafe_allow_html=True,
        )

        st.markdown(
            "<p style='text-align:center;color:#999'>"
            "Ask anything, upload a file, search jobs or create something."
            "</p>",
            unsafe_allow_html=True,
        )

    with bottom_area:
        columns = st.columns(2)

        for index, (icon, label, prompt) in enumerate(SUGGESTIONS):
            with columns[index % 2]:
                if st.button(
                    f"{icon}  {label}",
                    key=f"suggestion_{index}",
                ):
                    st.session_state.chat_id = None
                    start_turn(prompt)


# ============================================================
# DISPLAY CONVERSATION
# ============================================================

else:
    with top_area:
        for message in messages:
            with st.chat_message(message["role"]):
                st.markdown(message.get("content", ""))

                for image_name in message.get("images", []) or []:
                    image_path = IMAGES_DIR / image_name

                    if image_path.exists():
                        st.image(str(image_path), width=240)

                if message.get("attachments"):
                    st.caption(
                        "📎 " + ", ".join(message["attachments"])
                    )

                render_message_extras(message)

        if st.session_state.pending:
            process_pending(messages)

            # Re-render the new assistant response.
            st.rerun()
