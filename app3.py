import streamlit as st
import requests
import json
import time

st.set_page_config(page_title="TalentScout", page_icon="🤖", layout="centered")
st.markdown("<style>.block-container{max-width:720px;padding-top:2rem}</style>", unsafe_allow_html=True)

# ── Hugging Face setup ────────────────────────────────────────────────────────
HF_TOKEN = "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"   # ← from huggingface.co/settings/tokens
API_URL  = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
HEADERS  = {"Authorization": f"Bearer {HF_TOKEN}"}

def hf_ask(prompt: str) -> str:
    payload = {
        "inputs": prompt,
        "parameters": {
            "max_new_tokens": 512,
            "temperature": 0.7,
            "return_full_text": False
        }
    }
    for attempt in range(3):
        try:
            resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=60)
            if resp.status_code == 503:
                # Model is loading, wait and retry
                wait = resp.json().get("estimated_time", 20)
                st.toast(f"Model loading, waiting {int(wait)}s...")
                time.sleep(min(wait, 30))
                continue
            if resp.status_code == 200:
                result = resp.json()
                if isinstance(result, list):
                    return result[0].get("generated_text", "").strip()
                return str(result)
        except Exception as e:
            time.sleep(5)
    return ""

# ── Session state ─────────────────────────────────────────────────────────────
defaults = {
    "stage": "greeting", "info": {}, "questions": [],
    "q_index": 0, "answers": [], "scores": [], "messages": [], "done": False,
}
for k, v in defaults.items():
    if k not in st.session_state:
        st.session_state[k] = v

EXIT_WORDS = {"exit", "quit", "bye", "stop", "end"}

def add_bot(text): st.session_state.messages.append({"role": "assistant", "content": text})
def add_user(text): st.session_state.messages.append({"role": "user", "content": text})

# ── Generate questions ────────────────────────────────────────────────────────
def generate_questions(tech_stack: str, role: str, experience: str) -> list:
    try:
        exp = float(experience)
    except:
        exp = 0
    level = "beginner" if exp <= 1 else "intermediate" if exp <= 3 else "advanced"

    prompt = f"""<s>[INST] You are a technical interviewer. Generate exactly 5 {level}-level technical interview questions for a "{role}" role with tech stack: {tech_stack}.

Rules:
- Questions must be specific to {tech_stack} and {role}
- Number them 1 to 5
- One question per line
- Questions only, no explanations

[/INST]"""

    raw = hf_ask(prompt)

    qs = []
    for line in raw.splitlines():
        line = line.strip()
        if line and line[0].isdigit() and ("." in line or ")" in line):
            parts = line.split(".", 1) if "." in line else line.split(")", 1)
            if len(parts) > 1 and parts[1].strip():
                qs.append(parts[1].strip())

    # fallback: hardcoded but tech-specific
    if len(qs) < 3:
        techs = [t.strip() for t in tech_stack.split(",")]
        fallbacks = {
            "python":  ["What are Python decorators?", "Explain list comprehensions.", "What is the GIL in Python?"],
            "aws":     ["What is the difference between S3 and EBS?", "How does AWS Lambda work?", "Explain VPC in AWS."],
            "sql":     ["What is the difference between INNER JOIN and LEFT JOIN?", "What are indexes in SQL?", "Explain ACID properties."],
            "react":   ["What are React hooks?", "Explain the virtual DOM.", "What is the difference between state and props?"],
            "machine learning": ["What is overfitting?", "Explain gradient descent.", "What is cross-validation?"],
            "ml":      ["What is overfitting?", "Explain gradient descent.", "What is a confusion matrix?"],
            "java":    ["What is the difference between JDK, JRE, and JVM?", "Explain OOP principles.", "What are Java generics?"],
            "node":    ["What is the event loop in Node.js?", "Explain middleware in Express.", "What is async/await?"],
            "docker":  ["What is the difference between image and container?", "How does Docker networking work?", "What is Docker Compose?"],
        }
        for tech in techs:
            key = tech.lower()
            for fb_key, fb_qs in fallbacks.items():
                if fb_key in key:
                    qs.extend(fb_qs)
                    break
        if not qs:
            qs = [
                f"Explain the core concepts of {tech_stack}.",
                f"How would you debug a {tech_stack} application?",
                f"What are best practices in {tech_stack}?",
                f"Describe a project you built using {tech_stack}.",
                f"What are common challenges in {role} and how do you solve them?",
            ]

    while len(qs) < 5:
        qs.append(f"Describe a real-world use case of {tech_stack.split(',')[0].strip()}.")

    return qs[:5]

# ── Evaluate answer ───────────────────────────────────────────────────────────
def evaluate_answer(question: str, answer: str, tech_stack: str) -> tuple:
    if not answer.strip() or len(answer.strip().split()) < 3:
        return 0, "No meaningful answer provided."

    prompt = f"""<s>[INST] You are a strict technical interviewer. Evaluate this answer and respond ONLY in JSON.

Tech Stack: {tech_stack}
Question: {question}
Answer: {answer}

Score out of 10:
- 9-10: Excellent, accurate, detailed
- 7-8: Good, mostly correct
- 5-6: Average, partially correct
- 3-4: Weak, missing key points
- 0-2: Incorrect or irrelevant

Respond ONLY with this JSON, nothing else:
{{"score": <0-10>, "feedback": "<one sentence>"}}
[/INST]"""

    raw = hf_ask(prompt)

    try:
        start = raw.find("{")
        end   = raw.rfind("}") + 1
        if start != -1 and end > start:
            result  = json.loads(raw[start:end])
            score   = max(0, min(10, int(result.get("score", 5))))
            feedback= result.get("feedback", "Answer received.")
            return score, feedback
    except:
        pass

    # fallback scoring by word count + keywords
    words = answer.lower().split()
    tech_keywords = [t.strip().lower() for t in tech_stack.split(",")]
    keyword_hits  = sum(1 for w in words if any(k in w for k in tech_keywords))
    score = min(10, max(2, len(words) // 4 + keyword_hits))
    feedback = "Good effort! Try to include more technical details." if score >= 5 else "Try to elaborate more with specific examples."
    return score, feedback

# ── Stages ────────────────────────────────────────────────────────────────────
STAGES = [
    ("name",       "👤 What is your **full name**?"),
    ("email",      "📧 What is your **email address**?"),
    ("phone",      "📱 What is your **phone number**?"),
    ("experience", "💼 How many **years of experience** do you have?"),
    ("role",       "🎯 What **position** are you applying for?"),
    ("location",   "📍 What is your **current location**?"),
    ("techstack",  "💻 List your **tech stack** (e.g. Python, SQL, AWS):"),
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
            add_bot("⏳ Generating questions tailored to your tech stack and role...")
        return

    if stage == "questioning":
        add_user(user_text)
        idx = st.session_state.q_index
        with st.spinner("Evaluating your answer..."):
            score, feedback = evaluate_answer(
                st.session_state.questions[idx],
                user_text,
                st.session_state.info.get("techstack", "")
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

            if pct >= 80:   verdict = "🌟 **Excellent!** Highly recommended."
            elif pct >= 60: verdict = "👍 **Good** — Recommended for next round."
            elif pct >= 40: verdict = "⚠️ **Average** — Needs improvement."
            else:           verdict = "❌ **Below expectations** — Significant gaps."

            breakdown = "\n".join([f"Q{i+1}: {st.session_state.scores[i]}/10" for i in range(len(scores))])
            name  = st.session_state.info.get("name", "")
            email = st.session_state.info.get("email", "")

            add_bot(
                f"🎉 **Interview Complete!**\n\n"
                f"**Score Breakdown:**\n{breakdown}\n\n"
                f"**Total: {total}/{max_score} ({pct}%)**\n\n"
                f"{verdict}\n\n"
                f"Thank you, **{name}**! We'll contact you at **{email}** within 3 business days."
            )
            st.session_state.done = True
        return

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🤖 TalentScout Hiring Assistant")
st.caption("Powered by Mistral-7B via Hugging Face")

if not st.session_state.messages:
    add_bot(
        "👋 Hi! I'm the **TalentScout Hiring Assistant**.\n\n"
        "I'll collect your details and generate **personalized technical questions** "
        "based on your role and tech stack. Each answer is **scored by AI out of 10**.\n\n"
        "Type **'exit'** anytime to end. Say **'hello'** to begin!"
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
    st.session_state.questions = qs
    st.session_state.stage     = "questioning"
    st.session_state.q_index   = 0
    name = st.session_state.info.get("name", "there")
    add_bot(
        f"✅ Ready **{name}**! I have 5 questions tailored to your "
        f"**{st.session_state.info.get('techstack','')}** stack and "
        f"**{st.session_state.info.get('role','')}** role.\n\n"
        f"Each answer will be **scored out of 10** by AI.\n\n"
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

























# import streamlit as st
# import requests
# import json
# import time
# import re

# st.set_page_config(page_title="TalentScout", page_icon="🤖", layout="centered")
# st.markdown("<style>.block-container{max-width:720px;padding-top:2rem}</style>", unsafe_allow_html=True)

# # ── Hugging Face setup ────────────────────────────────────────────────────────
# HF_TOKEN = "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"
# API_URL  = "https://api-inference.huggingface.co/models/mistralai/Mistral-7B-Instruct-v0.3"
# HEADERS  = {"Authorization": f"Bearer {HF_TOKEN}"}

# def hf_ask(prompt: str) -> str:
#     payload = {
#         "inputs": prompt,
#         "parameters": {
#             "max_new_tokens": 600,
#             "temperature": 0.7,
#             "return_full_text": False
#         }
#     }
#     for attempt in range(4):
#         try:
#             resp = requests.post(API_URL, headers=HEADERS, json=payload, timeout=120)

#             # model still loading
#             if resp.status_code == 503:
#                 data = resp.json()
#                 wait = data.get("estimated_time", 25)
#                 st.toast(f"⏳ Model loading... waiting {int(wait)}s (attempt {attempt+1}/4)")
#                 time.sleep(min(float(wait), 40))
#                 continue

#             # rate limited
#             if resp.status_code == 429:
#                 st.toast("Rate limited, waiting 30s...")
#                 time.sleep(30)
#                 continue

#             if resp.status_code == 200:
#                 result = resp.json()
#                 if isinstance(result, list) and len(result) > 0:
#                     text = result[0].get("generated_text", "").strip()
#                     if text:
#                         return text
#                 elif isinstance(result, dict):
#                     text = result.get("generated_text", "").strip()
#                     if text:
#                         return text

#             # any other error — show it
#             st.warning(f"API Error {resp.status_code}: {resp.text[:200]}")

#         except requests.exceptions.Timeout:
#             st.toast(f"Timeout on attempt {attempt+1}, retrying...")
#             time.sleep(5)
#         except Exception as e:
#             st.toast(f"Error: {str(e)[:100]}")
#             time.sleep(5)

#     return None   # explicit None so caller knows it failed

# # ── Experience → Level ────────────────────────────────────────────────────────
# def get_level_info(experience: str) -> dict:
#     try:
#         exp = float(experience)
#     except:
#         exp = 0

#     if exp == 0:
#         return {"level": "fresher",      "label": "🟢 Fresher (0 years)",     "desc": "very basic definitions and concepts only, no coding expected",           "style": "What is X? What does X do? Name some features of X."}
#     elif exp <= 1:
#         return {"level": "beginner",     "label": "🟡 Beginner (up to 1 yr)", "desc": "simple practical usage, basic syntax, common errors",                    "style": "How do you use X? What is the difference between A and B?"}
#     elif exp <= 2:
#         return {"level": "junior",       "label": "🟠 Junior (1-2 years)",    "desc": "real usage scenarios, debugging, simple design patterns",                "style": "How would you handle X? Write a simple example of X."}
#     elif exp <= 4:
#         return {"level": "intermediate", "label": "🔵 Mid-level (2-4 years)", "desc": "architecture decisions, performance, system design basics",              "style": "How would you optimize X? Design a simple system using X."}
#     elif exp <= 7:
#         return {"level": "advanced",     "label": "🟣 Senior (4-7 years)",    "desc": "complex system design, scalability, trade-offs, production challenges",  "style": "Design X at scale. How do you handle Y failure in production?"}
#     else:
#         return {"level": "expert",       "label": "🔴 Expert (7+ years)",     "desc": "large scale architecture, deep internals, mentoring, incident handling", "style": "Architect X for millions of users. Explain internals of Y."}

# # ── Parse numbered questions from raw text ────────────────────────────────────
# def parse_questions(raw: str) -> list:
#     qs = []
#     # try numbered lines: 1. or 1)
#     for line in raw.splitlines():
#         line = line.strip()
#         if not line:
#             continue
#         match = re.match(r'^[1-5][.)]\s*(.+)', line)
#         if match:
#             q = match.group(1).strip()
#             if len(q) > 10:
#                 qs.append(q)

#     # fallback: split on digit patterns
#     if len(qs) < 3:
#         parts = re.split(r'\n?\s*[1-5][.)]\s+', raw)
#         qs = [p.strip() for p in parts if p.strip() and len(p.strip()) > 10]

#     # last resort: split on newlines and take non-empty lines
#     if len(qs) < 3:
#         lines = [l.strip() for l in raw.splitlines() if l.strip() and len(l.strip()) > 15]
#         qs = lines

#     return qs[:5]

# # ── Generate questions ────────────────────────────────────────────────────────
# def generate_questions(tech_stack: str, role: str, experience: str) -> list:
#     li = get_level_info(experience)

#     prompt = f"""<s>[INST] You are a technical interviewer. Generate 5 interview questions.

# Role: {role}
# Tech Stack: {tech_stack}
# Level: {li['level']} — {li['desc']}
# Style: {li['style']}

# Output ONLY 5 numbered questions about {tech_stack}, nothing else.

# [/INST]
# 1."""

#     raw = hf_ask(prompt)

#     if raw is None:
#         return []

#     raw = "1." + raw
#     return parse_questions(raw)

# # ── Evaluate answer ───────────────────────────────────────────────────────────
# def evaluate_answer(question: str, answer: str, tech_stack: str, experience: str) -> tuple:
#     if not answer.strip() or len(answer.strip().split()) < 3:
#         return 0, "No meaningful answer provided."

#     li = get_level_info(experience)

#     prompt = f"""<s>[INST] Evaluate this interview answer. Respond ONLY in JSON.

# Level: {li['level']}
# Tech: {tech_stack}
# Question: {question}
# Answer: {answer}

# JSON format only:
# {{"score": <0-10>, "feedback": "<one sentence>"}}
# [/INST]"""

#     raw = hf_ask(prompt)

#     if raw:
#         try:
#             start = raw.find("{")
#             end   = raw.rfind("}") + 1
#             if start != -1 and end > start:
#                 result   = json.loads(raw[start:end])
#                 score    = max(0, min(10, int(result.get("score", 5))))
#                 feedback = result.get("feedback", "Answer received.")
#                 return score, feedback
#         except:
#             pass

#     words = answer.strip().split()
#     score = min(10, max(2, len(words) // 5 + 2))
#     return score, "Answer received. Try to add more technical depth."

# # ── Session state ─────────────────────────────────────────────────────────────
# defaults = {
#     "stage": "greeting", "info": {}, "questions": [],
#     "q_index": 0, "answers": [], "scores": [], "messages": [], "done": False,
# }
# for k, v in defaults.items():
#     if k not in st.session_state:
#         st.session_state[k] = v

# EXIT_WORDS = {"exit", "quit", "bye", "stop", "end"}
# def add_bot(t):  st.session_state.messages.append({"role": "assistant", "content": t})
# def add_user(t): st.session_state.messages.append({"role": "user",      "content": t})

# STAGES = [
#     ("name",       "👤 What is your **full name**?"),
#     ("email",      "📧 What is your **email address**?"),
#     ("phone",      "📱 What is your **phone number**?"),
#     ("experience", "💼 How many **years of experience** do you have? (enter 0 if fresher)"),
#     ("role",       "🎯 What **position** are you applying for?"),
#     ("location",   "📍 What is your **current location**?"),
#     ("techstack",  "💻 What is your **tech stack**? (any tech — Python, MLOps, DevOps, Rust, etc.)"),
# ]
# STAGE_KEYS = [s[0] for s in STAGES]

# def handle_input(user_text: str):
#     if any(w in user_text.lower() for w in EXIT_WORDS):
#         add_user(user_text)
#         add_bot("Thanks for chatting with TalentScout! 👋 Goodbye!")
#         st.session_state.done = True
#         return

#     stage = st.session_state.stage

#     if stage == "greeting":
#         add_user(user_text)
#         st.session_state.stage = "name"
#         add_bot("Great! Let's get started.\n\n" + STAGES[0][1])
#         return

#     if stage in STAGE_KEYS:
#         add_user(user_text)
#         st.session_state.info[stage] = user_text
#         idx = STAGE_KEYS.index(stage)
#         if idx + 1 < len(STAGES):
#             st.session_state.stage = STAGE_KEYS[idx + 1]
#             add_bot(STAGES[idx + 1][1])
#         else:
#             st.session_state.stage = "generating"
#             li = get_level_info(st.session_state.info.get("experience", "0"))
#             add_bot(
#                 f"⏳ Generating **{li['label']}** level questions for **{user_text}**...\n\n"
#                 f"Please wait 15–30 seconds while AI generates your questions."
#             )
#         return

#     if stage == "questioning":
#         add_user(user_text)
#         idx = st.session_state.q_index
#         with st.spinner("Evaluating your answer..."):
#             score, feedback = evaluate_answer(
#                 st.session_state.questions[idx],
#                 user_text,
#                 st.session_state.info.get("techstack", ""),
#                 st.session_state.info.get("experience", "0")
#             )
#         st.session_state.answers.append({"q": st.session_state.questions[idx], "a": user_text})
#         st.session_state.scores.append(score)
#         add_bot(f"📊 **Score: {score}/10** — {feedback}")

#         st.session_state.q_index += 1
#         nxt = st.session_state.q_index

#         if nxt < len(st.session_state.questions):
#             add_bot(f"**Q{nxt+1}:** {st.session_state.questions[nxt]}")
#         else:
#             scores    = st.session_state.scores
#             total     = sum(scores)
#             max_score = len(scores) * 10
#             pct       = int((total / max_score) * 100)
#             li        = get_level_info(st.session_state.info.get("experience", "0"))

#             if pct >= 80:   verdict = "🌟 **Excellent!** Highly recommended."
#             elif pct >= 60: verdict = "👍 **Good** — Recommended for next round."
#             elif pct >= 40: verdict = "⚠️ **Average** — Needs improvement."
#             else:           verdict = "❌ **Below expectations** — Significant gaps."

#             breakdown = "\n".join([f"Q{i+1}: {scores[i]}/10" for i in range(len(scores))])
#             name  = st.session_state.info.get("name", "")
#             email = st.session_state.info.get("email", "")

#             add_bot(
#                 f"🎉 **Interview Complete!**\n\n"
#                 f"**Level:** {li['label']}\n"
#                 f"**Tech Stack:** {st.session_state.info.get('techstack', '')}\n\n"
#                 f"**Score Breakdown:**\n{breakdown}\n\n"
#                 f"**Total: {total}/{max_score} ({pct}%)**\n\n"
#                 f"{verdict}\n\n"
#                 f"Thank you, **{name}**! We'll contact you at **{email}** within 3 business days. 🌟"
#             )
#             st.session_state.done = True
#         return

# # ── UI ────────────────────────────────────────────────────────────────────────
# st.title("🤖 TalentScout Hiring Assistant")
# st.caption("AI-powered screening — works for ANY technology stack")

# if not st.session_state.messages:
#     add_bot(
#         "👋 Hi! I'm the **TalentScout Hiring Assistant**.\n\n"
#         "I generate **AI-powered interview questions for any tech stack** — "
#         "MLOps, DevOps, Rust, Flutter, Solidity, anything!\n\n"
#         "**Questions adapt to your experience level:**\n"
#         "- 0 yrs → 🟢 Fresher (basic definitions)\n"
#         "- ≤1 yr → 🟡 Beginner (simple practical)\n"
#         "- 1–2 yrs → 🟠 Junior (real scenarios)\n"
#         "- 2–4 yrs → 🔵 Mid-level (architecture)\n"
#         "- 4–7 yrs → 🟣 Senior (system design)\n"
#         "- 7+ yrs → 🔴 Expert (at scale)\n\n"
#         "Type **'exit'** anytime. Say **'hello'** to begin!"
#     )

# for msg in st.session_state.messages:
#     with st.chat_message(msg["role"]):
#         st.markdown(msg["content"])

# # ── Auto-trigger question generation ─────────────────────────────────────────
# if st.session_state.stage == "generating" and not st.session_state.done:
#     with st.spinner("AI is generating your personalized questions..."):
#         qs = generate_questions(
#             st.session_state.info.get("techstack", "Python"),
#             st.session_state.info.get("role", "Software Engineer"),
#             st.session_state.info.get("experience", "0")
#         )

#     if not qs:
#         # DO NOT end session — retry button instead
#         st.error("⚠️ AI model did not respond. Click below to retry.")
#         if st.button("🔄 Retry generating questions"):
#             st.rerun()
#     else:
#         st.session_state.questions = qs
#         st.session_state.stage     = "questioning"
#         st.session_state.q_index   = 0
#         li   = get_level_info(st.session_state.info.get("experience", "0"))
#         name = st.session_state.info.get("name", "there")
#         add_bot(
#             f"✅ Ready **{name}**!\n\n"
#             f"**Level:** {li['label']}\n"
#             f"**Tech:** {st.session_state.info.get('techstack', '')}\n\n"
#             f"5 questions generated by AI. Each answer scored out of 10.\n\n"
#             f"**Q1:** {qs[0]}"
#         )
#         st.rerun()

# elif not st.session_state.done:
#     user_input = st.chat_input("Type your answer here...")
#     if user_input:
#         handle_input(user_input)
#         st.rerun()
# else:
#     st.info("Session ended. Refresh the page to start a new interview.")