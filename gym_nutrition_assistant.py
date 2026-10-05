import os
import streamlit as st
from groq import Groq

# ---------------------------------------------------------------- page setup
st.set_page_config(page_title="FitFuel | Gym & Nutrition Assistant", page_icon="💪", layout="centered")

MODEL = "openai/gpt-oss-120b"  # llama-3.3-70b-versatile retired Aug 2026
MAX_HISTORY = 10                    # last N messages sent to the model

st.markdown(
    """
    <style>
    .block-container {padding-top: 2rem; max-width: 820px;}
    .stChatMessage {border-radius: 12px;}
    </style>
    """,
    unsafe_allow_html=True,
)


# ------------------------------------------------------------------- client
@st.cache_resource
def get_client():
    key = os.environ.get("GROQ_API_KEY", "")
    if not key:
        try:
            key = st.secrets["GROQ_API_KEY"]
        except Exception:
            key = ""
    if not key:
        st.error("GROQ_API_KEY not found. Add it to .streamlit/secrets.toml or set it as an environment variable.")
        st.stop()
    return Groq(api_key=key)


# ------------------------------------------------------------- calculators
ACTIVITY = {
    "Sedentary (desk job, little exercise)": 1.2,
    "Light (1-3 workouts/week)": 1.375,
    "Moderate (3-5 workouts/week)": 1.55,
    "Very active (6-7 workouts/week)": 1.725,
}
GOALS = {
    "Fat loss": (-500, 2.2),
    "Maintain": (0, 1.8),
    "Muscle gain": (300, 2.0),
}


def calc_targets(sex, age, height_cm, weight_kg, activity, goal):
    bmr = 10 * weight_kg + 6.25 * height_cm - 5 * age + (5 if sex == "Male" else -161)
    tdee = bmr * ACTIVITY[activity]
    delta, protein_per_kg = GOALS[goal]
    calories = round(tdee + delta)
    protein = round(weight_kg * protein_per_kg)
    fat = round(calories * 0.25 / 9)
    carbs = round((calories - protein * 4 - fat * 9) / 4)
    return {"bmr": round(bmr), "tdee": round(tdee), "calories": calories,
            "protein": protein, "carbs": carbs, "fat": fat}


# ------------------------------------------------------------------ sidebar
with st.sidebar:
    st.header("👤 Your Profile")
    sex = st.radio("Sex", ["Male", "Female"], horizontal=True)
    age = st.number_input("Age", 14, 80, 22)
    height = st.number_input("Height (cm)", 120, 220, 170)
    weight = st.number_input("Weight (kg)", 30.0, 200.0, 70.0, step=0.5)
    activity = st.selectbox("Activity level", list(ACTIVITY.keys()), index=2)
    goal = st.selectbox("Goal", list(GOALS.keys()), index=2)
    diet = st.selectbox("Diet preference", ["No preference", "Vegetarian", "Eggetarian", "Vegan", "Non-vegetarian"])

    t = calc_targets(sex, age, height, weight, activity, goal)

    st.markdown("---")
    st.subheader("🎯 Daily Targets")
    c1, c2 = st.columns(2)
    c1.metric("Calories", f"{t['calories']} kcal")
    c2.metric("Protein", f"{t['protein']} g")
    c1.metric("Carbs", f"{t['carbs']} g")
    c2.metric("Fat", f"{t['fat']} g")
    st.caption(f"BMR {t['bmr']} kcal | Maintenance {t['tdee']} kcal (Mifflin-St Jeor estimate)")

    st.markdown("---")
    if st.button("🗑️ Clear chat", use_container_width=True):
        st.session_state.messages = []
        st.rerun()


# ------------------------------------------------------------ system prompt
def build_system_prompt():
    return f"""You are FitFuel, a friendly and accurate gym, fitness and nutrition assistant.

USER PROFILE (use it when relevant, e.g. for personalised plans):
- Sex: {sex}, Age: {age}, Height: {height} cm, Weight: {weight} kg
- Activity: {activity}
- Goal: {goal}
- Diet preference: {diet}
- Estimated daily targets: {t['calories']} kcal, {t['protein']} g protein, {t['carbs']} g carbs, {t['fat']} g fat

WHAT YOU HELP WITH:
- Calories, protein, carbs, fats and fibre in foods, drinks, supplements and full meals
- Diet plans, meal prep ideas, grocery lists, cutting / bulking / maintenance advice
- Workout plans, exercises, form tips, splits, progressive overload, recovery, sleep
- Supplements (whey, creatine, caffeine, etc.) with an evidence-based view

RULES:
1. For any food question, give a small table: Food | Quantity | Calories | Protein | Carbs | Fat.
   Always state the quantity and whether it is raw or cooked. Values are approximate, so say so briefly.
2. Keep answers short, clear and practical. Use bullet points and tables, no long essays.
3. For plans, tailor them to the user's profile and diet preference above.
4. Do not diagnose or treat medical conditions. For injuries, medical conditions, pregnancy or eating
   disorders, advise seeing a doctor or registered dietitian.
5. Never recommend steroids, extreme crash diets or dangerously low calorie intakes.
6. If the question is unrelated to fitness, nutrition or health, politely steer back to those topics."""


# --------------------------------------------------------------------- main
st.title("💪 FitFuel")
st.caption("Your gym & nutrition assistant: calories, protein, macros, meal plans and workouts.")

if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending" not in st.session_state:
    st.session_state.pending = None

# Quick-start buttons (only on an empty chat)
if not st.session_state.messages:
    st.markdown("#### Try asking")
    examples = [
        "How much protein is in 100g of paneer?",
        "Calories in 2 boiled eggs and 2 slices of toast",
        "Make me a 1-day meal plan for my goal",
        "Best 4-day gym split for beginners",
    ]
    cols = st.columns(2)
    for i, ex in enumerate(examples):
        if cols[i % 2].button(ex, use_container_width=True):
            st.session_state.pending = ex
            st.rerun()

# Show chat history
for m in st.session_state.messages:
    with st.chat_message(m["role"], avatar="🧑‍💻" if m["role"] == "user" else "💪"):
        st.markdown(m["content"])

# Input
user_input = st.chat_input("Ask about calories, protein, meals, workouts...")
prompt = user_input or st.session_state.pending
st.session_state.pending = None

if prompt:
    st.session_state.messages.append({"role": "user", "content": prompt})
    with st.chat_message("user", avatar="🧑‍💻"):
        st.markdown(prompt)

    with st.chat_message("assistant", avatar="💪"):
        try:
            client = get_client()
            history = st.session_state.messages[-MAX_HISTORY:]
            stream = client.chat.completions.create(
                model=MODEL,
                messages=[{"role": "system", "content": build_system_prompt()}] + history,
                temperature=0.5,
                max_tokens=2048,
                stream=True,
            )

            def token_stream():
                for chunk in stream:
                    delta = chunk.choices[0].delta.content
                    if delta:
                        yield delta

            reply = st.write_stream(token_stream())
        except Exception as e:
            reply = f"Sorry, something went wrong while contacting the AI service: {e}"
            st.error(reply)

    st.session_state.messages.append({"role": "assistant", "content": reply})

st.markdown("---")
st.caption("⚠️ Nutrition values are estimates. This is general fitness information, not medical advice.")