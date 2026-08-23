import streamlit as st
import pandas as pd
import json
import io
from datetime import datetime
from PIL import Image
import google.generativeai as genai

# 1. Page Config & Custom Styling
st.set_page_config(
    page_title="KSP Fitness OS Pro",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    .ksp-header {
        background-color: #0F172A;
        padding: 18px 22px;
        border-radius: 12px;
        border: 1px solid #1E293B;
        margin-bottom: 20px;
    }
    .ksp-brand {
        color: #3B82F6;
        font-size: 12px;
        font-weight: 800;
        letter-spacing: 1.5px;
        text-transform: uppercase;
    }
    .ksp-title {
        color: #FFFFFF;
        font-size: 24px;
        font-weight: 900;
        margin-top: 2px;
    }
    .ksp-tagline {
        color: #94A3B8;
        font-size: 12px;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="ksp-header">
    <div class="ksp-brand">KSP Consulting & Solutions</div>
    <div class="ksp-title">Fitness OS • Pro Universal</div>
    <div class="ksp-tagline">Strategy amplified, complexity simplified.</div>
</div>
""", unsafe_allow_html=True)

# 2. Extract API Key (Streamlit Secrets or Manual Input)
api_key = st.secrets.get("GEMINI_API_KEY", "")

with st.sidebar:
    st.markdown("### ⚙️ System Settings")
    if not api_key:
        api_key = st.text_input("Enter Gemini API Key:", type="password", help="Add GEMINI_API_KEY to Streamlit Cloud secrets to bypass this.")
    st.markdown("---")
    target_kcal = st.number_input("Daily Caloric Target", value=2200, step=50)
    target_p = st.number_input("Daily Protein Target (g)", value=140, step=5)

EXERCISE_DB = {
    "Push (Chest / Shoulders / Triceps)": [
        {
            "name": "Incline Dumbbell Press",
            "target": "Upper Chest & Front Delts",
            "url": "https://www.youtube-nocookie.com/embed/8iPEnn-ltC8",
            "cues": ["Set bench to 30°", "Retract scapulae into the pad", "Control lowering phase for 3 seconds"]
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

# 3. Pure Universal Gemini Vision & Text Parser (NO MOCKING)
def universal_ai_nutrition_engine(user_text: str = "", pil_img: Image.Image = None, key: str = ""):
    if not key:
        st.error("❌ API Key Missing! Please add 'GEMINI_API_KEY' in Streamlit Secrets or enter it in the sidebar.")
        return None

    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel('gemini-1.5-flash')

        system_prompt = """
        You are an advanced, hyper-accurate Computer Vision Nutritionist.
        Analyze whatever is in the image or text with complete objectivity. NO GUESSWORK OR HARDCODED ASSUMPTIONS.
        
        RULES:
        1. If it is a PACKAGED product:
           - Read the visible nutrition label, net weight, or brand name (OCR).
           - Output the exact calories and macros for the serving or entire package visible.
        2. If it is a COOKED or PLATED meal:
           - Identify EVERY distinct food item, condiment, and ingredient visible.
           - If a kitchen scale or weight readout is in the frame, read the scale number directly.
           - Estimate realistic cooked portion weight (grams) and exact macronutrients (Protein, Carbs, Fats, Calories).
        3. If it is RAW/UNPACKAGED ingredients (fruits, vegetables, meat, legumes):
           - Identify the item and estimate raw weight and macros accurately.
        4. If it is TEXT:
           - Accurately parse the food and calculate macros according to exact quantities (e.g., '1 scoop whey', '2 rotis', '1 cup tea').
        
        OUTPUT FORMAT:
        You MUST return STRICT JSON ONLY with no extra commentary or markdown:
        {
          "food_title": "Detailed name of what was identified",
          "portion_grams": integer,
          "calories": integer,
          "protein_grams": float,
          "carbs_grams": float,
          "fats_grams": float,
          "ai_observation": "1-line factual observation of what was detected in the image/text"
        }
        """

        content_payload = [system_prompt]
        if user_text:
            content_payload.append(f"User Input Description: {user_text}")
        if pil_img:
            # Resize image to optimize network latency without losing OCR clarity
            img_optimized = pil_img.copy()
            img_optimized.thumbnail((1280, 1280))
            content_payload.append(img_optimized)

        response = model.generate_content(content_payload)
        cleaned_json = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(cleaned_json)

        return {
            "item": data.get("food_title", "Identified Food"),
            "grams": int(data.get("portion_grams", 100)),
            "kcal": int(data.get("calories", 100)),
            "p": round(float(data.get("protein_grams", 0.0)), 1),
            "c": round(float(data.get("carbs_grams", 0.0)), 1),
            "f": round(float(data.get("fats_grams", 0.0)), 1),
            "source": data.get("ai_observation", "Gemini Vision"),
            "time": datetime.now().strftime("%I:%M %p")
        }
    except Exception as e:
        st.error(f"❌ Gemini Vision API Error: {str(e)}")
        return None

# 4. Session State Initializers
if "meal_logs" not in st.session_state:
    st.session_state.meal_logs = []

if "workout_logs" not in st.session_state:
    st.session_state.workout_logs = []

# 5. Top Metrics Dashboard
df_meals = pd.DataFrame(st.session_state.meal_logs)
curr_kcal = int(df_meals["kcal"].sum()) if not df_meals.empty else 0
curr_p = round(float(df_meals["p"].sum()), 1) if not df_meals.empty else 0.0
curr_c = round(float(df_meals["c"].sum()), 1) if not df_meals.empty else 0.0
curr_f = round(float(df_meals["f"].sum()), 1) if not df_meals.empty else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Calories", f"{curr_kcal} kcal", f"{target_kcal - curr_kcal} remaining", delta_color="inverse")
col2.metric("Protein", f"{curr_p} g", f"{round(target_p - curr_p, 1)}g to goal")
col3.metric("Carbs", f"{curr_c} g")
col4.metric("Fats", f"{curr_f} g")

st.write("---")

# 6. Two Column App Structure
left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.subheader("🥗 Universal AI Nutrition Scanner")
    tab_photo, tab_text = st.tabs(["📷 Universal Photo Vision", "⚡ Direct Text / Prompt"])
    
    with tab_photo:
        uploaded_file = st.file_uploader("Upload ANY meal, package, label, fruit, or beverage photo:", type=["jpg", "png", "jpeg"])
        if uploaded_file:
            img = Image.open(uploaded_file)
            st.image(img, caption="Captured Image Preview", use_container_width=True)
            if st.button("⚡ Scan & Analyze with AI Vision", type="primary", use_container_width=True):
                with st.spinner("Analyzing image features, packaging, scale, and ingredients..."):
                    result = universal_ai_nutrition_engine(pil_img=img, key=api_key)
                    if result:
                        st.session_state.meal_logs.insert(0, result)
                        st.success(f"✅ Recognized: {result['item']} ({result['p']}g Protein, {result['kcal']} kcal)")
                        st.rerun()

    with tab_text:
        meal_input = st.text_input(
            "Describe whatever you ate:",
            placeholder="e.g., 2 bananas with 1 glass milk, 1 chicken breast, 3 parathas"
        )
        if st.button("Analyze & Log Food", type="primary", use_container_width=True):
            if meal_input:
                with st.spinner("Calculating exact nutrition..."):
                    result = universal_ai_nutrition_engine(user_text=meal_input, key=api_key)
                    if result:
                        st.session_state.meal_logs.insert(0, result)
                        st.success(f"✅ Logged: {result['item']} ({result['p']}g Protein, {result['kcal']} kcal)")
                        st.rerun()

    st.markdown("#### Today's Meal Log")
    if st.session_state.meal_logs:
        df_meal_disp = pd.DataFrame(st.session_state.meal_logs)[["time", "item", "p", "c", "f", "kcal", "source"]]
        df_meal_disp.columns = ["Time", "Food Item", "Protein (g)", "Carbs (g)", "Fats (g)", "Calories (kcal)", "AI Observation"]
        st.dataframe(df_meal_disp, use_container_width=True, hide_index=True)
        if st.button("Clear Meal Log"):
            st.session_state.meal_logs = []
            st.rerun()
    else:
        st.info("No meals logged yet. Upload an image or type a food entry above.")

with right_col:
    st.subheader("🏋️ Workout OS & Split Tracker")
    workout_tab1, workout_tab2 = st.tabs(["📝 Daily Workout Logger", "🎥 Form Guides & Splits"])
    
    with workout_tab1:
        st.markdown("#### Log Training Session")
        w_split = st.selectbox(
            "Training Split:",
            ["Push (Chest / Shoulders / Triceps)", "Pull (Back / Rear Delts / Biceps)", "Legs (Quads / Hamstrings / Calves)", "Upper / Lower", "Full Body"]
        )
        
        col_w1, col_w2 = st.columns(2)
        with col_w1:
            ex_name = st.text_input("Exercise Name:", placeholder="e.g., Incline DB Press")
            sets_val = st.number_input("Sets Completed:", min_value=1, max_value=20, value=3)
        with col_w2:
            weight_val = st.number_input("Weight (kg):", min_value=0.0, max_value=500.0, value=20.0, step=2.5)
            reps_val = st.number_input("Reps Completed:", min_value=1, max_value=100, value=10)
            
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

        st.markdown("#### Completed Exercises Today")
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