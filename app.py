import streamlit as st
import pandas as pd
import json
from datetime import datetime
from PIL import Image
import google.generativeai as genai

# 1. Page Configuration & Native Mobile Theme
st.set_page_config(
    page_title="KSP Fitness OS Pro",
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
    <div class="ksp-title">Fitness OS • Pro Intelligence</div>
    <div class="ksp-tagline">Strategy amplified, complexity simplified.</div>
</div>
""", unsafe_allow_html=True)

# 2. Key Extraction
API_KEY = st.secrets.get("GEMINI_API_KEY", "")

# 3. Session State Initializers
if "user_profile" not in st.session_state:
    st.session_state.user_profile = {
        "name": "Athlete",
        "age": 24,
        "gender": "Male",
        "weight_kg": 72.0,
        "height_cm": 175.0,
        "activity": "Moderate (Gym 4-5 days/week)",
        "goal": "Recomposition (Build Muscle & Burn Fat)",
        "target_kcal": 2150,
        "target_p": 145,
        "target_c": 240,
        "target_f": 55,
        "body_fat_pct": None,
        "lean_mass_kg": None,
        "fat_mass_kg": None,
    }

if "meal_logs" not in st.session_state:
    st.session_state.meal_logs = []

if "workout_logs" not in st.session_state:
    st.session_state.workout_logs = []

# 4. Scientific Macro Calculator (Mifflin-St Jeor)
def compute_user_macros(weight, height, age, gender, activity_str, goal_str):
    if gender == "Male":
        bmr = (10 * weight) + (6.25 * height) - (5 * age) + 5
    else:
        bmr = (10 * weight) + (6.25 * height) - (5 * age) - 161

    act_multipliers = {
        "Sedentary (Desk Job, minimal exercise)": 1.2,
        "Light (Gym 1-3 days/week)": 1.375,
        "Moderate (Gym 4-5 days/week)": 1.55,
        "Heavy (Gym 6-7 days/week, intense)": 1.725
    }
    tdee = bmr * act_multipliers.get(activity_str, 1.55)

    if "Fat Loss" in goal_str:
        target_calories = tdee - 450
        protein_g = weight * 2.2
    elif "Lean Bulk" in goal_str:
        target_calories = tdee + 300
        protein_g = weight * 2.0
    elif "Recomposition" in goal_str:
        target_calories = tdee - 150
        protein_g = weight * 2.2
    else:
        target_calories = tdee
        protein_g = weight * 1.8

    fat_calories = target_calories * 0.25
    fat_g = fat_calories / 9.0
    protein_calories = protein_g * 4.0
    carb_calories = max(0, target_calories - (protein_calories + fat_calories))
    carb_g = carb_calories / 4.0

    return {
        "target_kcal": int(round(target_calories)),
        "target_p": int(round(protein_g)),
        "target_c": int(round(carb_g)),
        "target_f": int(round(fat_g))
    }

# 5. Master AI Vision & Text Engine
def run_gemini_query(payload, key):
    if not key:
        st.error("❌ Gemini API Key missing from Streamlit Secrets.")
        return None

    genai.configure(api_key=key)
    candidate_models = ['gemini-3.6-flash', 'gemini-2.5-flash', 'gemini-1.5-flash-latest']
    
    try:
        live_models = [
            m.name.replace('models/', '') 
            for m in genai.list_models() 
            if 'generateContent' in m.supported_generation_methods
        ]
        candidate_models = list(dict.fromkeys(candidate_models + live_models))
    except Exception:
        pass

    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name)
            response = model.generate_content(payload)
            if response and response.text:
                return response.text
        except Exception:
            continue
    return None

def analyze_nutrition_ai(user_text: str = "", pil_img: Image.Image = None, key: str = ""):
    system_prompt = """
    You are an expert sports nutritionist and computer vision AI.
    Analyze the meal input (image or text) and estimate accurate weight in grams and macronutrients.
    
    OUTPUT STRICT JSON ONLY:
    {
      "food_title": "Descriptive food name and portion",
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

    raw_resp = run_gemini_query(payload, key)
    if not raw_resp:
        st.error("❌ AI Engine failed to process food request.")
        return None

    try:
        clean_json = raw_resp.replace("```json", "").replace("```", "").strip()
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
    except Exception as e:
        st.error(f"❌ JSON Parse Error: {e}")
        return None

def analyze_physique_ai(pil_img: Image.Image, user_prof: dict, key: str):
    system_prompt = f"""
    You are a professional body composition expert and fitness physiologist.
    Analyze this user's physique photo.
    User Profile Context:
    - Gender: {user_prof['gender']}
    - Weight: {user_prof['weight_kg']} kg
    - Height: {user_prof['height_cm']} cm
    - Age: {user_prof['age']} years old
    - Goal: {user_prof['goal']}
    
    TASK:
    1. Estimate visual body fat percentage based on muscular definition, vascularity, waist tightness, and abdominal visibility.
    2. Compute estimated Lean Muscle Mass (kg) and Fat Mass (kg).
    3. Provide tailored tactical guidance for calories and training splits.
    
    OUTPUT STRICT JSON ONLY:
    {
      "estimated_body_fat_pct": float,
      "lean_mass_kg": float,
      "fat_mass_kg": float,
      "physique_assessment": "1-2 sentence honest muscularity and conditioning breakdown",
      "calorie_action_plan": "Recommended daily adjustment"
    }
    """
    img_resized = pil_img.copy()
    img_resized.thumbnail((1024, 1024))
    payload = [system_prompt, img_resized]

    raw_resp = run_gemini_query(payload, key)
    if not raw_resp:
        st.error("❌ AI Physique Engine failed to analyze image.")
        return None

    try:
        clean_json = raw_resp.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception as e:
        st.error(f"❌ Body Scan Parse Error: {e}")
        return None

# 6. Global Top Navigation (Profile & Calorie Targets)
with st.expander("👤 User Profile & Auto-Calculated Macro Targets", expanded=False):
    col_u1, col_u2, col_u3 = st.columns(3)
    with col_u1:
        u_name = st.text_input("Name:", value=st.session_state.user_profile["name"])
        u_gender = st.selectbox("Gender:", ["Male", "Female"], index=0 if st.session_state.user_profile["gender"] == "Male" else 1)
        u_age = st.number_input("Age (years):", min_value=12, max_value=90, value=int(st.session_state.user_profile["age"]))
    with col_u2:
        u_weight = st.number_input("Weight (kg):", min_value=30.0, max_value=250.0, value=float(st.session_state.user_profile["weight_kg"]), step=0.5)
        u_height = st.number_input("Height (cm):", min_value=100.0, max_value=240.0, value=float(st.session_state.user_profile["height_cm"]), step=0.5)
        u_activity = st.selectbox("Activity Level:", [
            "Moderate (Gym 4-5 days/week)",
            "Heavy (Gym 6-7 days/week, intense)",
            "Light (Gym 1-3 days/week)",
            "Sedentary (Desk Job, minimal exercise)"
        ])
    with col_u3:
        u_goal = st.selectbox("Primary Fitness Goal:", [
            "Recomposition (Build Muscle & Burn Fat)",
            "Aggressive Fat Loss (Cut)",
            "Lean Bulk (Muscle Gain)",
            "Maintenance & Strength"
        ])
        if st.button("⚡ Recalculate Scientific Macros", type="primary", use_container_width=True):
            new_targets = compute_user_macros(u_weight, u_height, u_age, u_gender, u_activity, u_goal)
            st.session_state.user_profile.update({
                "name": u_name,
                "gender": u_gender,
                "age": u_age,
                "weight_kg": u_weight,
                "height_cm": u_height,
                "activity": u_activity,
                "goal": u_goal,
                **new_targets
            })
            st.success(f"Targets Updated: {new_targets['target_kcal']} kcal | {new_targets['target_p']}g Protein | {new_targets['target_c']}g Carbs | {new_targets['target_f']}g Fat")
            st.rerun()

# 7. Real-Time Top Macro Ribbon
prof = st.session_state.user_profile
df_meals = pd.DataFrame(st.session_state.meal_logs)
curr_kcal = int(df_meals["kcal"].sum()) if not df_meals.empty else 0
curr_p = round(float(df_meals["p"].sum()), 1) if not df_meals.empty else 0.0
curr_c = round(float(df_meals["c"].sum()), 1) if not df_meals.empty else 0.0
curr_f = round(float(df_meals["f"].sum()), 1) if not df_meals.empty else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Calories", f"{curr_kcal} kcal", f"{prof['target_kcal'] - curr_kcal} remaining", delta_color="inverse")
col2.metric("Protein", f"{curr_p} g", f"{round(prof['target_p'] - curr_p, 1)}g to goal")
col3.metric("Carbs", f"{curr_c} g", f"Goal: {prof['target_c']}g")
col4.metric("Fats", f"{curr_f} g", f"Goal: {prof['target_f']}g")

st.write("---")

# 8. Main 2-Column Workstation
left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.subheader("🥗 Smart Macro & Food Engine")
    tab_text, tab_photo = st.tabs(["⚡ Direct Text / Voice Prompt", "📷 Plate / Label Photo Scanner"])
    
    with tab_text:
        meal_input = st.text_input(
            "Enter meal with quantities:",
            placeholder="e.g., 70g dry soya chunks with 100g curd, 100gm pumpkin seeds"
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
        uploaded_food = st.file_uploader("Upload meal plate or packaged label:", type=["jpg", "png", "jpeg"], key="food_uploader")
        if uploaded_food:
            f_img = Image.open(uploaded_food)
            st.image(f_img, caption="Meal Preview", use_container_width=True)
            if st.button("⚡ Scan Meal Macros", type="primary", use_container_width=True):
                with st.spinner("AI Vision is inspecting portion scale & ingredients..."):
                    result = analyze_nutrition_ai(pil_img=f_img, key=API_KEY)
                    if result:
                        st.session_state.meal_logs.insert(0, result)
                        st.success(f"✅ Identified: {result['item']} ({result['p']}g Protein, {result['kcal']} kcal)")
                        st.rerun()

    st.markdown("#### Today's Meal Log")
    if st.session_state.meal_logs:
        df_meal_disp = pd.DataFrame(st.session_state.meal_logs)[["time", "item", "p", "c", "f", "kcal", "source"]]
        df_meal_disp.columns = ["Time", "Food Item", "Protein (g)", "Carbs (g)", "Fats (g)", "Calories (kcal)", "AI Insight"]
        st.dataframe(df_meal_disp, use_container_width=True, hide_index=True)
        if st.button("Clear Meal Log"):
            st.session_state.meal_logs = []
            st.rerun()
    else:
        st.info("No meals logged yet today.")

with right_col:
    st.subheader("🏋️ Training OS & AI Body Composition")
    tab_body, tab_workout = st.tabs(["📸 AI Physique & Body Fat Scanner", "📝 Daily Workout Log"])
    
    with tab_body:
        st.markdown("#### Upload Mirror Physique Photo")
        uploaded_physique = st.file_uploader("Upload full-torso front or back physique photo:", type=["jpg", "png", "jpeg"], key="body_uploader")
        if uploaded_physique:
            p_img = Image.open(uploaded_physique)
            st.image(p_img, caption="Physique Upload", width=240)
            if st.button("⚡ Run Body Fat & Muscle Scan", type="primary", use_container_width=True):
                with st.spinner("AI is analyzing muscular definition, abdominal sharpness, and vascularity..."):
                    scan = analyze_physique_ai(p_img, st.session_state.user_profile, API_KEY)
                    if scan:
                        st.session_state.user_profile.update({
                            "body_fat_pct": scan.get("estimated_body_fat_pct"),
                            "lean_mass_kg": scan.get("lean_mass_kg"),
                            "fat_mass_kg": scan.get("fat_mass_kg")
                        })
                        st.success("Analysis Complete!")
                        c_bf1, c_bf2, c_bf3 = st.columns(3)
                        c_bf1.metric("Body Fat %", f"{scan.get('estimated_body_fat_pct')}%")
                        c_bf2.metric("Lean Muscle", f"{scan.get('lean_mass_kg')} kg")
                        c_bf3.metric("Fat Mass", f"{scan.get('fat_mass_kg')} kg")
                        st.info(f"**Assessment:** {scan.get('physique_assessment')}")
                        st.write(f"**Action Plan:** {scan.get('calorie_action_plan')}")

        if st.session_state.user_profile["body_fat_pct"] is not None:
            st.markdown(f"> **Current Stored Scan:** **{st.session_state.user_profile['body_fat_pct']}% Body Fat** | **{st.session_state.user_profile['lean_mass_kg']}kg Lean Mass**")

    with tab_workout:
        st.markdown("#### Log Training Set")
        w_split = st.selectbox("Split:", ["Push (Chest/Delts/Triceps)", "Pull (Back/Biceps)", "Legs (Quads/Hamstrings)", "Upper / Lower", "Full Body"])
        c_w1, c_w2 = st.columns(2)
        with c_w1:
            ex_name = st.text_input("Exercise Name:", placeholder="e.g., Incline DB Press")
            sets_val = st.number_input("Sets:", min_value=1, max_value=20, value=3)
        with c_w2:
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
                st.success(f"Logged: {ex_name.title()} ({sets_val}x{reps_val} @ {weight_val}kg)")
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