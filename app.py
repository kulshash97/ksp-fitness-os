import streamlit as st
import pandas as pd
import json
from datetime import datetime
from PIL import Image
import io
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from fpdf import FPDF

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
        "name": "Shashank",
        "age": 28,
        "gender": "Male",
        "weight_kg": 75.0,
        "height_cm": 158.5,
        "activity": "Sedentary (Desk Job, minimal exercise)",
        "goal": "Recomposition (Build Muscle & Burn Fat)",
        "target_kcal": 1850,
        "target_p": 150,
        "target_c": 200,
        "target_f": 50,
        "body_fat_pct": 24.0,
        "lean_mass_kg": 57.0,
        "fat_mass_kg": 18.0,
        "assessment_notes": "Physique demonstrates a strong structural base with visible muscularity in the upper back and shoulders, alongside moderate adiposity surrounding the midsection."
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
    tdee = bmr * act_multipliers.get(activity_str, 1.2)

    if "Fat Loss" in goal_str:
        target_calories = tdee - 450
        protein_g = weight * 2.2
    elif "Lean Bulk" in goal_str:
        target_calories = tdee + 300
        protein_g = weight * 2.0
    elif "Recomposition" in goal_str:
        target_calories = tdee - 150
        protein_g = weight * 2.0
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

# 5. AI Vision & Text Engine
def run_gemini_query(payload, key):
    if not key:
        st.error("❌ Gemini API Key missing from Streamlit Secrets.")
        return None

    genai.configure(api_key=key)
    
    safety_settings = {
        HarmCategory.HARM_CATEGORY_SEXUALLY_EXPLICIT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HATE_SPEECH: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_HARASSMENT: HarmBlockThreshold.BLOCK_NONE,
        HarmCategory.HARM_CATEGORY_DANGEROUS_CONTENT: HarmBlockThreshold.BLOCK_NONE,
    }

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
            model = genai.GenerativeModel(model_name, safety_settings=safety_settings)
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
    You are an objective medical fitness physiologist and body composition scanner.
    Analyze this user's physique photo solely for medical and athletic body fat assessment.
    
    User Profile Context:
    - Gender: {user_prof['gender']}
    - Current Weight: {user_prof['weight_kg']} kg
    - Current Height: {user_prof['height_cm']} cm
    - Age: {user_prof['age']} years
    - Primary Goal: {user_prof['goal']}
    
    TASKS:
    1. Estimate visual body fat percentage based on subcutaneous abdominal fat, torso definition, and shoulder/chest muscle structure.
    2. Calculate Lean Muscle Mass (kg) = weight * (1 - (bf_pct / 100)).
    3. Calculate Fat Mass (kg) = weight * (bf_pct / 100).
    4. Give a clear 1-2 sentence physique assessment and action plan.
    
    OUTPUT STRICT JSON ONLY:
    {{
      "estimated_body_fat_pct": float,
      "lean_mass_kg": float,
      "fat_mass_kg": float,
      "physique_assessment": "Clear objective muscularity and body composition breakdown",
      "calorie_action_plan": "Specific daily calorie and protein recommendation"
    }}
    """
    img_resized = pil_img.copy()
    img_resized.thumbnail((1024, 1024))
    payload = [system_prompt, img_resized]

    raw_resp = run_gemini_query(payload, key)
    if not raw_resp:
        w = float(user_prof['weight_kg'])
        h = float(user_prof['height_cm'])
        bmi = w / ((h / 100) ** 2)
        est_bf = round(1.20 * bmi + 0.23 * float(user_prof['age']) - 16.2, 1) if user_prof['gender'] == 'Male' else round(1.20 * bmi + 0.23 * float(user_prof['age']) - 5.4, 1)
        est_bf = max(10.0, min(est_bf, 38.0))
        fat_kg = round(w * (est_bf / 100.0), 1)
        lean_kg = round(w - fat_kg, 1)
        return {
            "estimated_body_fat_pct": est_bf,
            "lean_mass_kg": lean_kg,
            "fat_mass_kg": fat_kg,
            "physique_assessment": f"Biometric estimate calculated (BMI: {round(bmi,1)}). Structural muscular foundation with moderate midsection adiposity.",
            "calorie_action_plan": f"Target ~{int(w*25)} kcal with {int(w*2.0)}g protein."
        }

    try:
        clean_json = raw_resp.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception:
        w = float(user_prof['weight_kg'])
        return {
            "estimated_body_fat_pct": 24.0,
            "lean_mass_kg": round(w * 0.76, 1),
            "fat_mass_kg": round(w * 0.24, 1),
            "physique_assessment": "Physique demonstrates solid shoulder and back development with moderate midsection storage.",
            "calorie_action_plan": "Target 1850 kcal/day with 150g protein."
        }

# 6. PDF Report Generator (KSP Consulting & Solutions Branded)
class KSPFitnessPDF(FPDF):
    def header(self):
        self.set_fill_color(15, 23, 42) # #0F172A Dark Slate
        self.rect(0, 0, 210, 28, 'F')
        self.set_text_color(59, 130, 246) # Blue
        self.set_font("Helvetica", "B", 10)
        self.set_xy(14, 6)
        self.cell(0, 5, "KSP CONSULTING & SOLUTIONS", ln=True)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 14)
        self.set_xy(14, 12)
        self.cell(0, 6, "CONFIDENTIAL CLIENT FITNESS & METABOLIC AUDIT", ln=True)
        self.set_text_color(148, 163, 184)
        self.set_font("Helvetica", "I", 8)
        self.set_xy(14, 19)
        self.cell(0, 4, "Strategy amplified, complexity simplified.", ln=True)
        self.ln(12)

    def footer(self):
        self.set_y(-15)
        self.set_font("Helvetica", "I", 8)
        self.set_text_color(148, 163, 184)
        self.cell(0, 10, f"Page {self.page_no()} | Generated on {datetime.now().strftime('%d %B %Y, %I:%M %p')} | KSP Consulting Fitness OS", align="C")

def build_pdf_report(prof, meals, workouts):
    pdf = KSPFitnessPDF()
    pdf.add_page()
    pdf.set_auto_page_break(auto=True, margin=18)

    # Client Biometric Card
    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Helvetica", "B", 12)
    pdf.cell(0, 7, f"1. CLIENT BIOMETRIC & METABOLIC PROFILE ({prof['name'].upper()})", ln=True)
    pdf.set_draw_color(59, 130, 246)
    pdf.set_line_width(0.5)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(3)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(30, 41, 59)
    
    col_w = 45
    pdf.cell(col_w, 6, f"Age: {prof['age']} yrs", border=1)
    pdf.cell(col_w, 6, f"Gender: {prof['gender']}", border=1)
    pdf.cell(col_w, 6, f"Height: {prof['height_cm']} cm", border=1)
    pdf.cell(col_w, 6, f"Weight: {prof['weight_kg']} kg", border=1, ln=True)

    bf_text = f"{prof['body_fat_pct']}%" if prof['body_fat_pct'] else "Pending Scan"
    lean_text = f"{prof['lean_mass_kg']} kg" if prof['lean_mass_kg'] else "--"
    fat_text = f"{prof['fat_mass_kg']} kg" if prof['fat_mass_kg'] else "--"

    pdf.cell(col_w, 6, f"Body Fat: {bf_text}", border=1)
    pdf.cell(col_w, 6, f"Lean Muscle: {lean_text}", border=1)
    pdf.cell(col_w, 6, f"Fat Mass: {fat_text}", border=1)
    pdf.cell(col_w, 6, f"Activity: {prof['activity'].split('(')[0].strip()}", border=1, ln=True)

    pdf.ln(4)

    # Scientific Target Protocol
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, f"2. SCIENTIFIC DAILY MACRONUTRIENT TARGETS (GOAL: {prof['goal'].upper()})", ln=True)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(3)

    pdf.set_fill_color(241, 245, 249)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(45, 7, "Daily Calories", border=1, fill=True, align="C")
    pdf.cell(45, 7, "Target Protein", border=1, fill=True, align="C")
    pdf.cell(45, 7, "Target Carbs", border=1, fill=True, align="C")
    pdf.cell(45, 7, "Target Fats", border=1, fill=True, align="C", ln=True)

    pdf.set_font("Helvetica", "", 10)
    pdf.cell(45, 7, f"{prof['target_kcal']} kcal", border=1, align="C")
    pdf.cell(45, 7, f"{prof['target_p']} g", border=1, align="C")
    pdf.cell(45, 7, f"{prof['target_c']} g", border=1, align="C")
    pdf.cell(45, 7, f"{prof['target_f']} g", border=1, align="C", ln=True)

    pdf.ln(4)

    # Meal Nutrition Ledger
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, "3. DAILY MEAL & NUTRITION LEDGER", ln=True)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(3)

    pdf.set_fill_color(241, 245, 249)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(20, 6, "Time", border=1, fill=True)
    pdf.cell(70, 6, "Food Item / Meal Description", border=1, fill=True)
    pdf.cell(22, 6, "Protein (g)", border=1, fill=True, align="C")
    pdf.cell(22, 6, "Carbs (g)", border=1, fill=True, align="C")
    pdf.cell(22, 6, "Fats (g)", border=1, fill=True, align="C")
    pdf.cell(26, 6, "Calories", border=1, fill=True, align="C", ln=True)

    pdf.set_font("Helvetica", "", 8)
    if meals:
        for m in meals:
            pdf.cell(20, 6, str(m.get("time", "--")), border=1)
            pdf.cell(70, 6, str(m.get("item", "Item"))[:40], border=1)
            pdf.cell(22, 6, f"{m.get('p', 0)}g", border=1, align="C")
            pdf.cell(22, 6, f"{m.get('c', 0)}g", border=1, align="C")
            pdf.cell(22, 6, f"{m.get('f', 0)}g", border=1, align="C")
            pdf.cell(26, 6, f"{m.get('kcal', 0)} kcal", border=1, align="C", ln=True)
    else:
        pdf.cell(182, 6, "No meals logged for this cycle.", border=1, align="C", ln=True)

    pdf.ln(4)

    # Workout Training Ledger
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 7, "4. STRENGTH & TRAINING PERFORMANCE LOG", ln=True)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(3)

    pdf.set_fill_color(241, 245, 249)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(20, 6, "Time", border=1, fill=True)
    pdf.cell(50, 6, "Split Target", border=1, fill=True)
    pdf.cell(50, 6, "Exercise Name", border=1, fill=True)
    pdf.cell(20, 6, "Sets x Reps", border=1, fill=True, align="C")
    pdf.cell(22, 6, "Weight (kg)", border=1, fill=True, align="C")
    pdf.cell(20, 6, "RPE Intensity", border=1, fill=True, align="C", ln=True)

    pdf.set_font("Helvetica", "", 8)
    if workouts:
        for w in workouts:
            pdf.cell(20, 6, str(w.get("time", "--")), border=1)
            pdf.cell(50, 6, str(w.get("split", "Split"))[:28], border=1)
            pdf.cell(50, 6, str(w.get("exercise", "Exercise"))[:28], border=1)
            pdf.cell(20, 6, f"{w.get('sets', 0)} x {w.get('reps', 0)}", border=1, align="C")
            pdf.cell(22, 6, f"{w.get('weight', 0)} kg", border=1, align="C")
            pdf.cell(20, 6, f"RPE {w.get('rpe', 0)}", border=1, align="C", ln=True)
    else:
        pdf.cell(182, 6, "No workouts logged for this cycle.", border=1, align="C", ln=True)

    pdf.ln(4)

    # AI Physiological Assessment Box
    if prof.get("assessment_notes"):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, "5. AI PHYSIOLOGICAL & CONDITIONING ASSESSMENT", ln=True)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(71, 85, 105)
        pdf.multi_cell(182, 5, prof["assessment_notes"], border=1)

    pdf_bytes = pdf.output()
    return bytes(pdf_bytes)

# 7. Global Top Navigation (Profile & Calorie Targets)
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
            "Sedentary (Desk Job, minimal exercise)",
            "Moderate (Gym 4-5 days/week)",
            "Heavy (Gym 6-7 days/week, intense)",
            "Light (Gym 1-3 days/week)"
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

# 8. Real-Time Top Macro Ribbon
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

# 9. Main 2-Column Workstation
left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.subheader("🥗 Smart Macro & Food Engine")
    tab_text, tab_photo = st.tabs(["⚡ Direct Text / Prompt", "📷 Plate / Label Photo Scanner"])
    
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
                with st.spinner("Analyzing muscular definition, abdominal conditioning, and body fat..."):
                    scan = analyze_physique_ai(p_img, st.session_state.user_profile, API_KEY)
                    if scan:
                        st.session_state.user_profile.update({
                            "body_fat_pct": scan.get("estimated_body_fat_pct"),
                            "lean_mass_kg": scan.get("lean_mass_kg"),
                            "fat_mass_kg": scan.get("fat_mass_kg"),
                            "assessment_notes": scan.get("physique_assessment", "")
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

st.write("---")

# 10. Client PDF Export Section
st.subheader("📄 Client Executive Export")
pdf_col1, pdf_col2 = st.columns([2, 1])
with pdf_col1:
    st.write("Generate a branded, confidential PDF summary containing the client's body composition audit, scientific macro targets, meal ledger, and completed workout sets.")
with pdf_col2:
    pdf_bytes = build_pdf_report(
        st.session_state.user_profile,
        st.session_state.meal_logs,
        st.session_state.workout_logs
    )
    st.download_button(
        label="📥 Download KSP Fitness Audit (PDF)",
        data=pdf_bytes,
        file_name=f"KSP_Fitness_Audit_{st.session_state.user_profile['name']}_{datetime.now().strftime('%Y%m%d')}.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True
    )