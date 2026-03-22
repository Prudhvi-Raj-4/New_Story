import streamlit as st
from google import genai
import json

st.set_page_config(page_title="TalentScout", page_icon="🤖", layout="centered")
st.markdown("<style>.block-container{max-width:720px;padding-top:2rem}</style>", unsafe_allow_html=True)

GEMINI_API_KEY = "AIzaSyCFcgyuUgv5x8NhCjVbPn5LRoQ5PW7Pm0A"
client = genai.Client(api_key=GEMINI_API_KEY)

def gemini_ask(prompt: str) -> str:
    response = client.models.generate_content(
        model="models/gemini-2.0-flash-lite",
        contents=prompt
    )
    return response.text.strip()

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

# ── Generate questions based on tech stack + role ─────────────────────────────
def generate_questions(tech_stack: str, role: str, experience: str) -> list:
    try:
        exp = float(experience)
    except:
        exp = 0
    level = "beginner" if exp <= 1 else "intermediate" if exp <= 3 else "advanced"

    prompt = f"""You are a technical interviewer at a top tech company.
Generate exactly 5 {level}-level technical interview questions for a candidate applying for the role of "{role}" with tech stack: {tech_stack}.

Rules:
- Questions must be SPECIFIC to {tech_stack} and the {role} role
- Do NOT ask generic questions like "What is OOP?" unless OOP is directly relevant
- Each question should test real practical knowledge
- Format: just number them 1 to 5, one question per line
- No explanations, no headers, questions only

Example for AWS role:
1. What is the difference between S3 and EBS in AWS?
2. How does Auto Scaling work in AWS EC2?
"""
    raw = gemini_ask(prompt)
    qs = []
    for line in raw.splitlines():
        line = line.strip()
        if line and line[0].isdigit() and "." in line:
            q = line.split(".", 1)[-1].strip()
            if q:
                qs.append(q)

    # fallback if parsing fails
    if len(qs) < 5:
        fallback_prompt = f"List 5 interview questions for {tech_stack} {role} developer. Number them 1-5."
        raw2 = gemini_ask(fallback_prompt)
        qs = [l.split(".",1)[-1].strip() for l in raw2.splitlines() if l.strip() and l.strip()[0].isdigit()]

    while len(qs) < 5:
        qs.append(f"Describe a real-world use case of {tech_stack.split(',')[0].strip()} in a {role} role.")

    return qs[:5]

# ── Evaluate answer with Gemini ───────────────────────────────────────────────
def evaluate_answer(question: str, answer: str, tech_stack: str) -> tuple:
    if not answer.strip() or len(answer.strip()) < 5:
        return 0, "No answer provided."

    prompt = f"""You are a strict but fair technical interviewer.
Evaluate this candidate answer and give a score out of 10.

Tech Stack: {tech_stack}
Question: {question}
Candidate Answer: {answer}

Scoring criteria:
- 9-10: Excellent, accurate, detailed with examples
- 7-8: Good, mostly correct with minor gaps
- 5-6: Average, partially correct
- 3-4: Weak, missing key concepts
- 0-2: Incorrect or irrelevant

Respond in this exact JSON format only, nothing else:
{{"score": <number 0-10>, "feedback": "<one sentence feedback>"}}"""

    try:
        raw = gemini_ask(prompt)
        raw = raw.replace("```json","").replace("```","").strip()
        result = json.loads(raw)
        score = int(result.get("score", 0))
        feedback = result.get("feedback", "No feedback.")
        return score, feedback
    except:
        # fallback: keyword-based scoring
        words = answer.lower().split()
        score = min(10, max(2, len(words) // 3))
        return score, "Answer received. Keep practicing for more depth."

# ── Conversation stages ───────────────────────────────────────────────────────
STAGES = [
    ("name",       "👤 What is your **full name**?"),
    ("email",      "📧 What is your **email address**?"),
    ("phone",      "📱 What is your **phone number**?"),
    ("experience", "💼 How many **years of experience** do you have?"),
    ("role",       "🎯 What **position** are you applying for?"),
    ("location",   "📍 What is your **current location**?"),
    ("techstack",  "💻 List your **tech stack** (e.g. AWS, Python, SQL):"),
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

        # Evaluate the answer
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
            # Final results
            scores = st.session_state.scores
            total = sum(scores)
            max_score = len(scores) * 10
            pct = int((total / max_score) * 100)

            if pct >= 80:
                verdict = "🌟 **Excellent!** Strong candidate — highly recommended."
            elif pct >= 60:
                verdict = "👍 **Good** — Solid foundation, recommended for next round."
            elif pct >= 40:
                verdict = "⚠️ **Average** — Needs improvement in key areas."
            else:
                verdict = "❌ **Below expectations** — Significant gaps in knowledge."

            score_breakdown = "\n".join([
                f"Q{i+1}: {st.session_state.scores[i]}/10" for i in range(len(scores))
            ])

            name  = st.session_state.info.get("name", "")
            email = st.session_state.info.get("email", "")

            add_bot(
                f"🎉 **Interview Complete!**\n\n"
                f"**Score Breakdown:**\n{score_breakdown}\n\n"
                f"**Total: {total}/{max_score} ({pct}%)**\n\n"
                f"{verdict}\n\n"
                f"Thank you, **{name}**! We'll contact you at **{email}** within 3 business days."
            )
            st.session_state.done = True
        return

# ── UI ────────────────────────────────────────────────────────────────────────
st.title("🤖 TalentScout Hiring Assistant")
st.caption("AI-powered screening for technology placements")

if not st.session_state.messages:
    add_bot(
        "👋 Hi! I'm the **TalentScout Hiring Assistant**.\n\n"
        "I'll collect your details and generate **personalized technical questions** "
        "based on your role and tech stack.\n\n"
        "Type **'exit'** anytime to end. Say **'hello'** to begin!"
    )

for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

# Auto-trigger question generation
if st.session_state.stage == "generating" and not st.session_state.done:
    with st.spinner("Generating your personalized questions..."):
        qs = generate_questions(
            st.session_state.info.get("techstack", "Python"),
            st.session_state.info.get("role", "Software Engineer"),
            st.session_state.info.get("experience", "0")
        )
    st.session_state.questions = qs
    st.session_state.stage = "questioning"
    st.session_state.q_index = 0
    name = st.session_state.info.get("name", "there")
    add_bot(
        f"✅ Ready **{name}**! I have 5 questions tailored to your "
        f"**{st.session_state.info.get('techstack','')}** stack and "
        f"**{st.session_state.info.get('role','')}** role.\n\n"
        f"Each answer will be scored out of 10 by AI.\n\n"
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
