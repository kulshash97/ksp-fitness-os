import streamlit as st
import pandas as pd
import json
from datetime import datetime
from PIL import Image
import google.generativeai as genai

# 1. Page Configuration & Native Mobile Dark Theme
st.set_page_config(
    page_title="KSP Fitness OS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .stApp {
        background-color: #070B14;
        color: #F8FAFC;
    }
    .ksp-header {
        background-color: #0F172A;
        padding: 16px 20px;
        border-radius: 12px;
        border: 1px solid #1E293B;
        margin-bottom: 16px;
    }
    .ksp-brand {
        color: #3B82F6;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 1.5px;
        text-transform: uppercase;
    }
    .ksp-title {
        color: #FFFFFF;
        font-size: 22px;
        font-weight: 900;
        margin-top: 2px;
    }
    .ksp-tagline {
        color: #94A3B8;
        font-size: 12px;
        font-style: italic;
    }
    div[data-testid="stMetricValue"] {
        font-size: 24px !important;
        font-weight: 800 !important;
    }
    .stButton>button {
        border-radius: 8px;
        font-weight: 700;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="ksp-header">
    <div class="ksp-brand">KSP Consulting & Solutions</div>
    <div class="ksp-title">Fitness OS • Live</div>
    <div class="ksp-tagline">Strategy amplified, complexity simplified.</div>
</div>
""", unsafe_allow_html=True)

# 2. Key Extraction (Secrets or Sidebar Fallback)
API_KEY = st.secrets.get("GEMINI_API_KEY", "")

with st.sidebar:
    st.markdown("### ⚙️ System Setup")
    if not API_KEY:
        API_KEY = st.text_input("Enter Gemini API Key:", type="password", help="Add to Streamlit Cloud secrets to bypass this.")
    st.markdown("---")
    target_kcal = st.number_input("Daily Caloric Goal", value=2200, step=50)
    target_p = st.number_input("Daily Protein Goal (g)", value=140, step=5)

# 3. Master Exercise Form Library
EXERCISE_DB = {
    "Push (Chest / Shoulders / Triceps)": [
        {
            "name": "Incline Dumbbell Press",
            "target": "Upper Chest & Front Delts",
            "url": "https://www.youtube-nocookie.com/embed/8iPEnn-ltC8",
            "cues": ["Set bench to 30°", "Retract scapulae into the pad", "Lower smoothly for 3 seconds"]
        },
        {
            "name": "Flat Barbell Bench Press",
            "target": "Mid / Lower Chest",
            "url": "https://www.youtube-nocookie.com/embed/rT7DgCr-3pg",
            "cues": ["Drive feet into the floor", "Touch bar smoothly to lower sternum", "Lock elbows smoothly at top"]
        }
    ],
    "Pull (Back / Rear Delts / Biceps)": [
        {
            "name": "Chest-Supported Row",
            "target": "Upper Back & Lats",
            "url": "https://www.youtube-nocookie.com/embed/0UBRfiO4zDs",
            "cues": ["Pull elbows back toward hips", "Squeeze shoulder blades for 1 second", "Avoid shrugging shoulders"]
        },
        {
            "name": "Lat Pulldown",
            "target": "Latissimus Dorsi",
            "url": "https://www.youtube-nocookie.com/embed/CAwf7n6Luuc",
            "cues": ["Slight backward lean in upper chest", "Drive elbows straight down", "Full controlled stretch at top"]
        }
    ],
    "Legs (Quads / Hamstrings / Calves)": [
        {
            "name": "Barbell Back Squat",
            "target": "Quads & Glutes",
            "url": "https://www.youtube-nocookie.com/embed/bEv6CCg2BC8",
            "cues": ["Brace core with a deep belly breath", "Knees track outward with toes", "Reach parallel depth cleanly"]
        }
    ]
}

# 4. Universal Gemini Nutrition Engine (Multi-Model Fallback)
def analyze_nutrition_ai(user_text: str = "", pil_img: Image.Image = None, key: str = ""):
    if not key:
        st.error("❌ Gemini API Key is missing. Please add `GEMINI_API_KEY` to your Streamlit Secrets or sidebar.")
        return None

    genai.configure(api_key=key)

    system_prompt = """
    You are an expert sports nutritionist and computer vision AI specialized in Indian and global diets.
    
    TASK:
    Analyze the user input (image or text description) and estimate the precise portion weight and macronutrients.
    
    GUIDELINES:
    - If an image has a kitchen scale or packaging/nutrition label, read the numbers directly via OCR.
    - If cooked food (e.g. Soya Chunks sabzi, Paneer, Dahi, Pumpkin seeds, Dal, Rice, Rotis), calculate realistic portion grams and macros.
    - If raw seeds/nuts (e.g. '100gm pumpkin seeds' -> ~574 kcal, ~30g protein, ~49g fat, ~15g carbs).
    - If beverage (e.g. '1 cup tea' -> ~75 kcal, ~2g protein, ~10g carbs, ~2.5g fat).
    
    OUTPUT FORMAT:
    You MUST return STRICT JSON ONLY (no markdown blocks, no commentary):
    {
      "food_title": "Descriptive food name and quantity",
      "portion_grams": integer,
      "calories": integer,
      "protein_grams": float,
      "carbs_grams": float,
      "fats_grams": float,
      "ai_observation": "1-line observation"
    }
    """

    payload = [system_prompt]
    if user_text:
        payload.append(f"Input: {user_text}")
    if pil_img:
        img_resized = pil_img.copy()
        img_resized.thumbnail((1024, 1024))
        payload.append(img_resized)

    # Multi-model discovery to prevent 404 version mismatch
    candidate_models = ['gemini-1.5-flash', 'gemini-1.5-flash-latest', 'gemini-1.5-pro', 'gemini-2.0-flash']
    response = None
    last_err = None

    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(payload)
            if response and response.text:
                break
        except Exception as e:
            last_err = e
            continue

    if not response or not response.text:
        st.error(f"❌ AI Engine Error: {last_err}")
        return None

    try:
        clean_json = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_json)
        return {
            "item": data.get("food_title", user_text or "Scanned Meal"),
            "grams": int(data.get("portion_grams", 100)),
            "kcal": int(data.get("calories", 100)),
            "p": round(float(data.get("protein_grams", 0.0)), 1),
            "c": round(float(data.get("carbs_grams", 0.0)), 1),
            "f": round(float(data.get("fats_grams", 0.0)), 1),
            "source": data.get("ai_observation", "AI Verified"),
            "time": datetime.now().strftime("%I:%M %p")
        }
    except Exception as parse_err:
        st.error(f"❌ JSON Parse Error: {parse_err}. Response: {response.text}")
        return None

# 5. Session State
if "meal_logs" not in st.session_state:
    st.session_state.meal_logs = []

if "workout_logs" not in st.session_state:
    st.session_state.workout_logs = []

# 6. Top Metrics Dashboard
df_meals = pd.DataFrame(st.session_state.meal_logs)
curr_kcal = int(df_meals["kcal"].sum()) if not df_meals.empty else 0
curr_p = round(float(df_meals["p"].sum()), 1) if not df_meals.empty else 0.0
curr_c = round(float(df_meals["c"].sum()), 1) if not df_meals.empty else 0.0
curr_f = round(float(df_meals["f"].sum()), 1) if not df_meals.empty else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Calories", f"{curr_kcal} kcal", f"{target_kcal - curr_kcal} rem", delta_color="inverse")
col2.metric("Protein", f"{curr_p} g", f"{round(target_p - curr_p, 1)}g left")
col3.metric("Carbs", f"{curr_c} g")
col4.metric("Fats", f"{curr_f} g")

st.write("---")

# 7. Two-Column Modular Layout
left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.subheader("🥗 Smart Macro Tracker")
    tab_text, tab_photo = st.tabs(["⚡ Direct Text / Prompt", "📷 Live Photo Vision"])
    
    with tab_text:
        meal_input = st.text_input(
            "Enter what you ate:",
            placeholder="e.g., 100gm pumpkin seeds, 70g soya chunks with 100g dahi, 1 scoop pea protein"
        )
        if st.button("Log Food Entry", type="primary", use_container_width=True):
            if meal_input:
                with st.spinner("Calculating macros..."):
                    result = analyze_nutrition_ai(user_text=meal_input, key=API_KEY)
                    if result:
                        st.session_state.meal_logs.insert(0, result)
                        st.success(f"✅ Logged: {result['item']} ({result['p']}g Protein, {result['kcal']} kcal)")
                        st.rerun()

    with tab_photo:
        uploaded_file = st.file_uploader("Upload any plate, packaged item, or kitchen scale image:", type=["jpg", "png", "jpeg"])
        if uploaded_file:
            img = Image.open(uploaded_file)
            st.image(img, caption="Meal Preview", use_container_width=True)
            if st.button("⚡ Scan & Calculate Image Macros", type="primary", use_container_width=True):
                with st.spinner("AI Vision scanning packaging, ingredients, and portion scale..."):
                    result = analyze_nutrition_ai(pil_img=img, key=API_KEY)
                    if result:
                        st.session_state.meal_logs.insert(0, result)
                        st.success(f"✅ Identified: {result['item']} ({result['p']}g Protein, {result['kcal']} kcal)")
                        st.rerun()

    st.markdown("#### Today's Meal Log")
    if st.session_state.meal_logs:
        df_meal_disp = pd.DataFrame(st.session_state.meal_logs)[["time", "item", "p", "c", "f", "kcal", "source"]]
        df_meal_disp.columns = ["Time", "Food Item", "Protein (g)", "Carbs (g)", "Fats (g)", "Calories (kcal)", "AI Insight"]
        st.dataframe(df_meal_disp, use_container_width=True, hide_index=True)
        if st.button("Clear Meals"):
            st.session_state.meal_logs = []
            st.rerun()
    else:
        st.info("No meals logged yet today.")

with right_col:
    st.subheader("🏋️ Workout OS & Split Tracker")
    workout_tab1, workout_tab2 = st.tabs(["📝 Daily Workout Logger", "🎥 Form Guides & Splits"])
    
    with workout_tab1:
        st.markdown("#### Log Training Set")
        w_split = st.selectbox(
            "Split:",
            ["Push (Chest / Shoulders / Triceps)", "Pull (Back / Rear Delts / Biceps)", "Legs (Quads / Hamstrings / Calves)", "Upper / Lower", "Full Body"]
        )
        
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            ex_name = st.text_input("Exercise Name:", placeholder="e.g., Incline DB Press")
            sets_val = st.number_input("Sets:", min_value=1, max_value=20, value=3)
        with col_w2:
            weight_val = st.number_input("Weight (kg):", min_value=0.0, max_value=500.0, value=20.0, step=2.5)
            reps_val = st.number_input("Reps:", min_value=1, max_value=100, value=10)
            
        rpe_val = st.slider("Intensity (RPE Scale 1-10):", min_value=5.0, max_value=10.0, value=8.5, step=0.5)
        
        if st.button("⚡ Save Workout Log", type="primary", use_container_width=True):
            if ex_name:
                w_entry = {
                    "time": datetime.now().strftime("%I:%M %p"),
                    "split": w_split,
                    "exercise": ex_name.title(),
                    "sets": int(sets_val),
                    "reps": int(reps_val),
                    "weight": float(weight_val),
                    "rpe": float(rpe_val)
                }
                st.session_state.workout_logs.insert(0, w_entry)
                st.success(f"Logged: {ex_name.title()} ({sets_val} sets x {reps_val} reps @ {weight_val}kg)")
                st.rerun()

        st.markdown("#### Today's Completed Sets")
        if st.session_state.workout_logs:
            df_w_disp = pd.DataFrame(st.session_state.workout_logs)[["time", "split", "exercise", "sets", "reps", "weight", "rpe"]]
            df_w_disp.columns = ["Time", "Split", "Exercise", "Sets", "Reps", "Weight (kg)", "RPE"]
            st.dataframe(df_w_disp, use_container_width=True, hide_index=True)
            if st.button("Clear Workout Logs"):
                st.session_state.workout_logs = []
                st.rerun()
        else:
            st.info("No workout sets logged yet today.")

    with workout_tab2:
        muscle_choice = st.radio(
            "Select Muscle Target:",
            ["Push (Chest / Shoulders / Triceps)", "Pull (Back / Rear Delts / Biceps)", "Legs (Quads / Hamstrings / Calves)"],
            horizontal=True
        )
        st.write("---")
        for ex in EXERCISE_DB[muscle_choice]:
            with st.expander(f"▶ {ex['name']} ({ex['target']})", expanded=True):
                st.markdown(
                    f'<iframe width="100%" height="260" src="{ex["url"]}?autoplay=0&controls=1" frameborder="0" allowfullscreen></iframe>',
                    unsafe_allow_html=True
                )
                st.markdown("**Form Execution Checklist:**")
                for cue in ex["cues"]:
                    st.markdown(f"- {cue}")