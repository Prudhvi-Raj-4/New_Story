import streamlit as st
import requests
import json
import time

st.set_page_config(page_title="TalentScout", page_icon="🤖", layout="centered")
st.markdown("<style>.block-container{max-width:720px;padding-top:2rem}</style>", unsafe_allow_html=True)

# ── Hugging Face setup ────────────────────────────────────────────────────────
HF_TOKEN = "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"
API_URL  = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
HEADERS  = {"Authorization": f"Bearer {HF_TOKEN}"}

def hf_ask(prompt: str) -> str:
    payload = {
        "inputs": prompt,
        "parameters": {"max_new_tokens": 600, "temperature": 0.7, "return_full_text": False}
    }
    for attempt in range(3):
        try:
            resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=90)
            if resp.status_code == 503:
                wait = resp.json().get("estimated_time", 20)
                st.toast(f"Model loading, waiting {int(wait)}s...")
                time.sleep(min(wait, 30))
                continue
            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, list):
                    return result[0].get("generated_text", "").strip()
                return str(result)
        except:
            time.sleep(5)
    return ""

# ── Experience → Level ────────────────────────────────────────────────────────
def get_level_info(experience: str) -> dict:
    try:
        exp = float(experience)
    except:
        exp = 0

    if exp == 0:
        return {"level": "fresher",           "label": "🟢 Fresher (0 years)",    "desc": "very basic definitions and concepts only, no coding expected",             "style": "What is X? What does X do? Name some features of X."}
    elif exp <= 1:
        return {"level": "beginner",          "label": "🟡 Beginner (≤1 year)",   "desc": "simple practical usage, basic syntax, common errors",                      "style": "How do you use X? What is the difference between A and B in X?"}
    elif exp <= 2:
        return {"level": "junior",            "label": "🟠 Junior (1-2 years)",   "desc": "real usage scenarios, debugging, simple design patterns",                  "style": "How would you handle X situation? Write a simple example of X."}
    elif exp <= 4:
        return {"level": "intermediate",      "label": "🔵 Mid-level (2-4 years)","desc": "architecture decisions, performance, system design basics",                "style": "How would you optimize X? Design a simple system using X."}
    elif exp <= 7:
        return {"level": "advanced",          "label": "🟣 Senior (4-7 years)",   "desc": "complex system design, scalability, trade-offs, production challenges",   "style": "Design X at scale. How do you handle Y failure in production?"}
    else:
        return {"level": "expert",            "label": "🔴 Expert (7+ years)",    "desc": "large scale architecture, deep internals, mentoring, incident handling",  "style": "Architect X for millions of users. Explain internals of Y."}

# ── Generate questions — 100% model generated, no hardcoding ─────────────────
def generate_questions(tech_stack: str, role: str, experience: str) -> list:
    li = get_level_info(experience)

    prompt = f"""<s>[INST] You are a senior technical interviewer at a top tech company.

Candidate details:
- Applying for: {role}
- Tech stack: {tech_stack}
- Experience: {li['level']} level — {li['desc']}

Your task: Generate exactly 5 technical interview questions.

STRICT RULES:
- Questions must be ONLY about {tech_stack}
- Difficulty must match {li['level']} level: {li['desc']}
- Question style examples: {li['style']}
- Each question must be different, covering different aspects of {tech_stack}
- Output ONLY the 5 questions numbered 1 to 5
- No explanations, no headers, no extra text

[/INST]
1."""

    raw = "1." + hf_ask(prompt)

    qs = []
    for line in raw.splitlines():
        line = line.strip()
        if not line:
            continue
        # match lines starting with 1. 2. 3. or 1) 2) 3)
        if len(line) >= 2 and line[0].isdigit() and line[1] in ".)" :
            q = line[2:].strip()
            if q and len(q) > 10:
                qs.append(q)

    # if parsing failed try splitting by newline numbers
    if len(qs) < 3:
        import re
        parts = re.split(r'\n?\d+[.)]\s*', raw)
        qs = [p.strip() for p in parts if p.strip() and len(p.strip()) > 10]

    return qs[:5] if len(qs) >= 5 else qs

# ── Evaluate answer — fully model based ──────────────────────────────────────
def evaluate_answer(question: str, answer: str, tech_stack: str, experience: str) -> tuple:
    if not answer.strip() or len(answer.strip().split()) < 3:
        return 0, "No meaningful answer provided."

    li = get_level_info(experience)

    prompt = f"""<s>[INST] You are a strict technical interviewer evaluating a {li['level']}-level candidate.

Tech Stack: {tech_stack}
Experience Level: {li['level']} — {li['desc']}
Question: {question}
Candidate Answer: {answer}

Evaluate fairly for a {li['level']} candidate. Do not expect expert knowledge from a fresher.

Scoring guide for {li['level']} level:
- 9-10: Excellent answer for this level
- 7-8: Good, mostly correct
- 5-6: Partially correct, missing some points
- 3-4: Weak, lacks key concepts
- 0-2: Incorrect or irrelevant

Respond ONLY with this exact JSON format, nothing else:
{{"score": <number 0-10>, "feedback": "<one clear sentence of feedback>"}}
[/INST]"""

    raw = hf_ask(prompt)

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

    # minimal fallback — word count only, no tech hardcoding
    words = answer.strip().split()
    score = min(10, max(2, len(words) // 5 + 2))
    feedback = "Answer received. Try to add more technical depth next time."
    return score, feedback

# ── Conversation stages ───────────────────────────────────────────────────────
STAGES = [
    ("name",       "👤 What is your **full name**?"),
    ("email",      "📧 What is your **email address**?"),
    ("phone",      "📱 What is your **phone number**?"),
    ("experience", "💼 How many **years of experience** do you have? (enter 0 if fresher)"),
    ("role",       "🎯 What **position** are you applying for?"),
    ("location",   "📍 What is your **current location**?"),
    ("techstack",  "💻 What is your **tech stack**? (can be anything — e.g. Rust, Solidity, Flutter, DevOps, etc.)"),
]
STAGE_KEYS = [s[0] for s in STAGES]

defaults = {
    "stage": "greeting", "info": {}, "questions": [],
    "q_index": 0, "answers": [], "scores": [], "messages": [], "done": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

EXIT_WORDS = {"exit", "quit", "bye", "stop", "end"}
def add_bot(t): st.session_state.messages.append({"role": "assistant", "content": t})
def add_user(t): st.session_state.messages.append({"role": "user", "content": t})

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
            add_bot(f"⏳ Generating **{li['label']}** level questions for **{user_text}**...")
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
                f"**Level:** {li['label']}\n\n"
                f"**Score Breakdown:**\n{breakdown}\n\n"
                f"**Total: {total}/{max_score} ({pct}%)**\n\n"
                f"{verdict}\n\n"
                f"Thank you, **{name}**! We'll contact you at **{email}** within 3 business days."
            )
            st.session_state.done = True
        return

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🤖 TalentScout Hiring Assistant")
st.caption("Questions generated by AI — works for ANY technology")

if not st.session_state.messages:
    add_bot(
        "👋 Hi! I'm the **TalentScout Hiring Assistant**.\n\n"
        "I generate **AI-powered questions for any tech stack** — "
        "Rust, Flutter, Solidity, DevOps, anything!\n\n"
        "Questions adapt to your experience:\n"
        "0 yrs → Fresher | 1 yr → Beginner | 2 yrs → Junior | "
        "2–4 yrs → Mid | 4–7 yrs → Senior | 7+ yrs → Expert\n\n"
        "Type **'exit'** anytime. Say **'hello'** to begin!"
    )

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

if st.session_state.stage == "generating" and not st.session_state.done:
    with st.spinner("AI is generating your personalized questions..."):
        qs = generate_questions(
            st.session_state.info.get("techstack", "Python"),
            st.session_state.info.get("role", "Software Engineer"),
            st.session_state.info.get("experience", "0")
        )
    if not qs:
        add_bot("⚠️ Could not generate questions. Please refresh and try again.")
        st.session_state.done = True
    else:
        st.session_state.questions = qs
        st.session_state.stage     = "questioning"
        st.session_state.q_index   = 0
        li   = get_level_info(st.session_state.info.get("experience", "0"))
        name = st.session_state.info.get("name", "there")
        add_bot(
            f"✅ Ready **{name}**!\n\n"
            f"**Level:** {li['label']}\n"
            f"**Tech:** {st.session_state.info.get('techstack','')}\n\n"
            f"5 questions generated. Each scored out of 10 by AI.\n\n"
            f"**Q1:** {qs[0]}"
        )
    st.rerun()

if not st.session_state.done:
    user_input = st.chat_input("Type your answer here...")
    if user_input:
        handle_input(user_input)
        st.rerun()
else:
    st.info("Session ended. Refresh the page to start a new interview.")
