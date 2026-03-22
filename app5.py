import streamlit as st
import requests
import json
import re
import time

st.set_page_config(page_title="TalentScout", page_icon="🤖", layout="centered")
st.markdown("<style>.block-container{max-width:720px;padding-top:2rem}</style>", unsafe_allow_html=True)

# ─────────────────────────────────────────────────────────────────────────────
#  API KEY — Get FREE key from: https://console.groq.com  (instant, no card)
#  Groq gives you: llama3, mixtral, gemma — all FREE and FAST
# ─────────────────────────────────────────────────────────────────────────────
GROQ_API_KEY = "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"

def ask_llm(prompt: str) -> str:
    url     = "https://api.groq.com/openai/v1/chat/completions"
    headers = {
        "Authorization": f"Bearer {GROQ_API_KEY}",
        "Content-Type":  "application/json"
    }
    payload = {
        "model": "llama-3.3-70b-versatile",   # free, fast, reliable
        "messages":    [{"role": "user", "content": prompt}],
        "max_tokens":  600,
        "temperature": 0.7
    }
    try:
        resp = requests.post(url, headers=headers, json=payload, timeout=30)
        if resp.status_code == 200:
            return resp.json()["choices"][0]["message"]["content"].strip()
        else:
            st.error(f"API Error {resp.status_code}: {resp.json().get('error', {}).get('message', resp.text)[:200]}")
            return None
    except Exception as e:
        st.error(f"Request failed: {str(e)}")
        return None

# ── Experience → Level ────────────────────────────────────────────────────────
def get_level_info(experience: str) -> dict:
    try:
        exp = float(experience)
    except:
        exp = 0

    if exp == 0:
        return {"level": "fresher",      "label": "🟢 Fresher (0 years)",     "desc": "very basic definitions only, no coding expected",              "style": "What is X? What does X do? Name some features of X."}
    elif exp <= 1:
        return {"level": "beginner",     "label": "🟡 Beginner (≤1 year)",    "desc": "simple practical usage, basic syntax, common errors",          "style": "How do you use X? What is the difference between A and B?"}
    elif exp <= 2:
        return {"level": "junior",       "label": "🟠 Junior (1-2 years)",    "desc": "real usage scenarios, debugging, simple design patterns",      "style": "How would you handle X? Give a simple example."}
    elif exp <= 4:
        return {"level": "intermediate", "label": "🔵 Mid-level (2-4 years)", "desc": "architecture decisions, performance, system design basics",    "style": "How would you optimize X? Design a simple system using X."}
    elif exp <= 7:
        return {"level": "advanced",     "label": "🟣 Senior (4-7 years)",    "desc": "complex system design, scalability, production challenges",    "style": "Design X at scale. How do you handle Y in production?"}
    else:
        return {"level": "expert",       "label": "🔴 Expert (7+ years)",     "desc": "deep internals, large scale architecture, incident handling",  "style": "Architect X for millions of users. Explain internals of Y."}

# ── Generate 5 questions ──────────────────────────────────────────────────────
def generate_questions(tech_stack: str, role: str, experience: str) -> list:
    li = get_level_info(experience)
    prompt = f"""You are a technical interviewer. Generate exactly 5 interview questions.

Candidate: applying for {role}, tech stack is {tech_stack}, experience level is {li['level']}.
Level description: {li['desc']}
Question style: {li['style']}

Rules:
- Questions must be specific to {tech_stack}
- Match {li['level']} difficulty exactly
- Output ONLY 5 questions numbered 1 to 5
- No extra text, no explanations

Output format:
1. <question>
2. <question>
3. <question>
4. <question>
5. <question>"""

    raw = ask_llm(prompt)
    if not raw:
        return []

    qs = []
    for line in raw.splitlines():
        line = line.strip()
        m = re.match(r'^[1-5][.)]\s*(.+)', line)
        if m:
            q = m.group(1).strip()
            if len(q) > 10:
                qs.append(q)

    if len(qs) < 3:
        parts = re.split(r'\n?\s*[1-5][.)]\s+', "\n" + raw)
        qs = [p.strip() for p in parts if p.strip() and len(p.strip()) > 10]

    return qs[:5]

# ── Evaluate answer ───────────────────────────────────────────────────────────
def evaluate_answer(question: str, answer: str, tech_stack: str, experience: str) -> tuple:
    if not answer.strip() or len(answer.strip().split()) < 3:
        return 0, "No meaningful answer provided."

    li = get_level_info(experience)
    prompt = f"""You are evaluating a {li['level']}-level candidate on {tech_stack}.

Question: {question}
Candidate Answer: {answer}

Score fairly for {li['level']} level (don't expect expert answers from freshers).
Scoring: 9-10=Excellent, 7-8=Good, 5-6=Average, 3-4=Weak, 0-2=Incorrect

Respond ONLY in this JSON format:
{{"score": <0-10>, "feedback": "<one clear sentence>"}}"""

    raw = ask_llm(prompt)
    if raw:
        try:
            start = raw.find("{")
            end   = raw.rfind("}") + 1
            if start != -1 and end > start:
                result   = json.loads(raw[start:end])
                score    = max(0, min(10, int(result.get("score", 5))))
                feedback = result.get("feedback", "Answer received.")
                return score, feedback
        except:
            pass

    words = answer.strip().split()
    score = min(10, max(2, len(words) // 4 + 1))
    return score, "Answer noted. Be more specific and detailed next time."

# ── Session state ─────────────────────────────────────────────────────────────
defaults = {
    "stage": "greeting", "info": {}, "questions": [],
    "q_index": 0, "answers": [], "scores": [], "messages": [], "done": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

EXIT_WORDS = {"exit", "quit", "bye", "stop", "end"}
def add_bot(t):  st.session_state.messages.append({"role": "assistant", "content": t})
def add_user(t): st.session_state.messages.append({"role": "user",      "content": t})

STAGES = [
    ("name",       "👤 What is your **full name**?"),
    ("email",      "📧 What is your **email address**?"),
    ("phone",      "📱 What is your **phone number**?"),
    ("experience", "💼 Years of experience? (enter **0** if fresher)"),
    ("role",       "🎯 What **position** are you applying for?"),
    ("location",   "📍 Your **current location**?"),
    ("techstack",  "💻 Your **tech stack**? (any tech — WordPress, GCP, MLOps, Flutter, etc.)"),
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
            li = get_level_info(st.session_state.info.get("experience", "0"))
            add_bot(
                f"⏳ Generating **{li['label']}** questions for **{user_text}**...\n\n"
                f"Please wait a few seconds."
            )
        return

    if stage == "questioning":
        add_user(user_text)
        idx = st.session_state.q_index
        with st.spinner("Evaluating your answer..."):
            score, feedback = evaluate_answer(
                st.session_state.questions[idx],
                user_text,
                st.session_state.info.get("techstack", ""),
                st.session_state.info.get("experience", "0")
            )
        st.session_state.answers.append({"q": st.session_state.questions[idx], "a": user_text})
        st.session_state.scores.append(score)
        add_bot(f"📊 **Score: {score}/10** — {feedback}")

        st.session_state.q_index += 1
        nxt = st.session_state.q_index

        if nxt < len(st.session_state.questions):
            add_bot(f"**Q{nxt+1}:** {st.session_state.questions[nxt]}")
        else:
            scores    = st.session_state.scores
            total     = sum(scores)
            max_score = len(scores) * 10
            pct       = int((total / max_score) * 100)
            li        = get_level_info(st.session_state.info.get("experience", "0"))

            if pct >= 80:   verdict = "🌟 **Excellent!** Highly recommended."
            elif pct >= 60: verdict = "👍 **Good** — Recommended for next round."
            elif pct >= 40: verdict = "⚠️ **Average** — Needs improvement."
            else:           verdict = "❌ **Below expectations** — Significant gaps."

            breakdown = "\n".join([f"Q{i+1}: {scores[i]}/10" for i in range(len(scores))])
            name  = st.session_state.info.get("name", "")
            email = st.session_state.info.get("email", "")
            add_bot(
                f"🎉 **Interview Complete!**\n\n"
                f"**Level:** {li['label']}\n"
                f"**Tech Stack:** {st.session_state.info.get('techstack', '')}\n\n"
                f"**Score Breakdown:**\n{breakdown}\n\n"
                f"**Total: {total}/{max_score} ({pct}%)**\n\n"
                f"{verdict}\n\n"
                f"Thank you, **{name}**! We'll contact you at **{email}** within 3 business days. 🌟"
            )
            st.session_state.done = True
        return

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🤖 TalentScout Hiring Assistant")
st.caption("Powered by Groq (LLaMA3) — Fast & Free")

if not st.session_state.messages:
    add_bot(
        "👋 Hi! I'm the **TalentScout Hiring Assistant**.\n\n"
        "I generate **AI-powered interview questions for any tech stack** — "
        "WordPress, GCP, MLOps, DevOps, Flutter, anything!\n\n"
        "**Questions adapt to your experience level:**\n"
        "- 0 yrs → 🟢 Fresher | ≤1 yr → 🟡 Beginner\n"
        "- 1–2 yrs → 🟠 Junior | 2–4 yrs → 🔵 Mid-level\n"
        "- 4–7 yrs → 🟣 Senior | 7+ yrs → 🔴 Expert\n\n"
        "Type **'exit'** anytime. Say **'hello'** to begin!"
    )

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if st.session_state.stage == "generating" and not st.session_state.done:
    with st.spinner("Generating your personalized questions..."):
        qs = generate_questions(
            st.session_state.info.get("techstack", "Python"),
            st.session_state.info.get("role", "Software Engineer"),
            st.session_state.info.get("experience", "0")
        )

    if not qs:
        st.error("⚠️ Could not generate questions. Check your API key and click Retry.")
        if st.button("🔄 Retry"):
            st.rerun()
    else:
        st.session_state.questions = qs
        st.session_state.stage     = "questioning"
        st.session_state.q_index   = 0
        li   = get_level_info(st.session_state.info.get("experience", "0"))
        name = st.session_state.info.get("name", "there")
        add_bot(
            f"✅ Ready **{name}**!\n\n"
            f"**Level:** {li['label']}\n"
            f"**Tech:** {st.session_state.info.get('techstack', '')}\n\n"
            f"5 questions generated. Each scored out of 10 by AI.\n\n"
            f"**Q1:** {qs[0]}"
        )
        st.rerun()

elif not st.session_state.done:
    user_input = st.chat_input("Type your answer here...")
    if user_input:
        handle_input(user_input)
        st.rerun()
else:
    st.info("Session ended. Refresh the page to start a new interview.")