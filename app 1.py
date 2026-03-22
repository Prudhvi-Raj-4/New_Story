import streamlit as st
from google import genai

st.set_page_config(page_title="TalentScout", page_icon="🤖", layout="centered")
st.markdown("<style>.block-container{max-width:720px;padding-top:2rem}</style>", unsafe_allow_html=True)

# ── Hardcoded API key for local VS Code run ───────────────────────────────────
GEMINI_API_KEY = "AIzaSyCQAbg30LQC-XkJ_uqqKnzjkRuedrUaxNk"
client = genai.Client(api_key=GEMINI_API_KEY)

def gemini_ask(prompt: str) -> str:
    try:
        return client.models.generate_content(
            model="gemini-2.0-flash", contents=prompt
        ).text.strip()
    except Exception:
        return "1. What is OOP?\n2. Explain REST APIs.\n3. What is a database index?\n4. What is Git?\n5. Explain recursion."

defaults = {
    "stage": "greeting", "info": {}, "questions": [],
    "q_index": 0, "answers": [], "messages": [], "done": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

EXIT_WORDS = {"exit", "quit", "bye", "stop", "end"}

def add_bot(text): st.session_state.messages.append({"role": "assistant", "content": text})
def add_user(text): st.session_state.messages.append({"role": "user", "content": text})

def generate_questions(tech_stack: str, experience: str) -> list:
    try:
        exp = float(experience)
    except:
        exp = 0
    level = "beginner" if exp <= 1 else "intermediate" if exp <= 3 else "advanced"
    prompt = (
        f"Generate exactly 5 {level}-level technical interview questions "
        f"for a candidate with this tech stack: {tech_stack}.\n"
        "Rules: numbered 1-5, one per line, questions only, no explanations."
    )
    raw = gemini_ask(prompt)
    qs = [l.split(".", 1)[-1].strip() for l in raw.splitlines() if l.strip() and l.strip()[0].isdigit()]
    while len(qs) < 5:
        qs.append(f"Explain a core concept in {tech_stack.split(',')[0].strip()}.")
    return qs[:5]

STAGES = [
    ("name",       "👤 What is your **full name**?"),
    ("email",      "📧 What is your **email address**?"),
    ("phone",      "📱 What is your **phone number**?"),
    ("experience", "💼 How many **years of experience** do you have?"),
    ("role",       "🎯 What **position(s)** are you applying for?"),
    ("location",   "📍 What is your **current location**?"),
    ("techstack",  "💻 List your **tech stack** (e.g. Python, SQL, React):"),
]
STAGE_KEYS = [s[0] for s in STAGES]

def handle_input(user_text: str):
    if any(w in user_text.lower() for w in EXIT_WORDS):
        add_user(user_text)
        add_bot("Thanks for chatting with TalentScout! 👋 Goodbye!")
        st.session_state.done = True
        return

    stage = st.session_state.stage

    if stage == "greeting":
        add_user(user_text)
        st.session_state.stage = "name"
        add_bot("Great! Let's get started.\n\n" + STAGES[0][1])
        return

    if stage in STAGE_KEYS:
        add_user(user_text)
        st.session_state.info[stage] = user_text
        idx = STAGE_KEYS.index(stage)
        if idx + 1 < len(STAGES):
            st.session_state.stage = STAGE_KEYS[idx + 1]
            add_bot(STAGES[idx + 1][1])
        else:
            st.session_state.stage = "generating"
            add_bot("⏳ Generating your technical questions...")
        return

    if stage == "questioning":
        add_user(user_text)
        idx = st.session_state.q_index
        st.session_state.answers.append({
            "q": st.session_state.questions[idx],
            "a": user_text
        })
        st.session_state.q_index += 1
        nxt = st.session_state.q_index
        if nxt < len(st.session_state.questions):
            add_bot(f"**Q{nxt+1}:** {st.session_state.questions[nxt]}")
        else:
            name  = st.session_state.info.get("name", "")
            email = st.session_state.info.get("email", "")
            add_bot(
                f"🎉 **Interview Complete!**\n\n"
                f"Thank you, **{name}**! Our team will review your responses and "
                f"contact you at **{email}** within 3 business days.\n\nBest of luck! 🌟"
            )
            st.session_state.done = True
        return

st.title("🤖 TalentScout Hiring Assistant")
st.caption("AI-powered screening for technology placements")

if not st.session_state.messages:
    add_bot(
        "👋 Hi! I'm the **TalentScout Hiring Assistant**.\n\n"
        "I'll collect your details and ask technical questions based on your tech stack.\n\n"
        "Type **'exit'** anytime to end. Say **'hello'** to begin!"
    )

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if st.session_state.stage == "generating" and not st.session_state.done:
    qs = generate_questions(
        st.session_state.info.get("techstack", "Python"),
        st.session_state.info.get("experience", "0")
    )
    st.session_state.questions = qs
    st.session_state.stage = "questioning"
    st.session_state.q_index = 0
    name = st.session_state.info.get("name", "there")
    add_bot(f"✅ Ready {name}! Here's your first question:\n\n**Q1:** {qs[0]}")
    st.rerun()

if not st.session_state.done:
    user_input = st.chat_input("Type your answer here...")
    if user_input:
        handle_input(user_input)
        st.rerun()
else:
    st.info("Session ended. Refresh the page to start a new interview.")
