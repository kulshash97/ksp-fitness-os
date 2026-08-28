import streamlit as st
import pandas as pd
import json
import hashlib
from datetime import datetime
from PIL import Image
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from fpdf import FPDF
from supabase import create_client, Client

# 1. Page Config & Dark Slate Styling
st.set_page_config(
    page_title="KSP Fitness OS • Cloud SaaS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
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

# 2. Key Extraction & Supabase Cloud Connection
API_KEY = st.secrets.get("GEMINI_API_KEY", "")
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

@st.cache_resource
def init_supabase():
    if SUPABASE_URL and SUPABASE_KEY:
        return create_client(SUPABASE_URL, SUPABASE_KEY)
    return None

supabase: Client = init_supabase()

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

# 3. Clinical Protocol Engine
def compute_clinical_metabolic_protocol(weight_kg, height_cm, age_yrs, gender, activity_str, body_fat_pct=None):
    if gender == "Male":
        bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age_yrs) + 5.0
    else:
        bmr = (10.0 * weight_kg) + (6.25 * height_cm) - (5.0 * age_yrs) - 161.0

    act_multipliers = {
        "Sedentary (Desk Job, minimal exercise)": 1.2,
        "Light Active (Gym 1-3 days/week)": 1.375,
        "Moderate Active (Gym 3-5 days/week)": 1.55,
        "Heavy Active (Gym 6-7 days intense gym + cardio)": 1.725
    }
    multiplier = act_multipliers.get(activity_str, 1.55)
    tdee = bmr * multiplier

    if body_fat_pct is not None and body_fat_pct > 0:
        fat_mass_kg = round(weight_kg * (body_fat_pct / 100.0), 2)
        lean_mass_kg = round(weight_kg - fat_mass_kg, 2)
    else:
        body_fat_pct = 24.0 if gender == "Male" else 30.0
        fat_mass_kg = round(weight_kg * (body_fat_pct / 100.0), 2)
        lean_mass_kg = round(weight_kg - fat_mass_kg, 2)

    if (gender == "Male" and body_fat_pct > 20.0) or (gender == "Female" and body_fat_pct > 28.0):
        prescribed_goal = "Targeted Fat Loss & Muscle Preservation"
        target_calories = tdee - 700.0
        min_floor = 1350.0 if gender == "Male" else 1200.0
        target_calories = max(min_floor, target_calories)
        protein_g = weight_kg * 2.0
    elif (gender == "Male" and 15.0 <= body_fat_pct <= 20.0) or (gender == "Female" and 23.0 <= body_fat_pct <= 28.0):
        prescribed_goal = "Body Recomposition"
        target_calories = tdee - 250.0
        protein_g = weight_kg * 2.2
    else:
        prescribed_goal = "Lean Bulk / Hypertrophy Phase"
        target_calories = tdee + 275.0
        protein_g = weight_kg * 2.0

    fat_calories = target_calories * 0.25
    fat_g = fat_calories / 9.0
    protein_calories = protein_g * 4.0
    carb_calories = max(0.0, target_calories - (protein_calories + fat_calories))
    carb_g = carb_calories / 4.0

    return {
        "bmr": round(bmr, 1),
        "tdee": round(tdee, 1),
        "body_fat_pct": round(body_fat_pct, 1),
        "fat_mass_kg": fat_mass_kg,
        "lean_mass_kg": lean_mass_kg,
        "goal": prescribed_goal,
        "target_kcal": int(round(target_calories)),
        "target_p": int(round(protein_g)),
        "target_c": int(round(carb_g)),
        "target_f": int(round(fat_g))
    }

# 4. Gemini AI Engine
def run_gemini_query(payload, key):
    if not key:
        st.error("❌ Gemini API Key missing.")
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
        live_models = [m.name.replace('models/', '') for m in genai.list_models() if 'generateContent' in m.supported_generation_methods]
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
    You are the Lead Sports Nutritionist for KSP Consulting.
    Analyze the meal input (image or text) and calculate exact portion grams and macronutrients.
    OUTPUT STRICT JSON ONLY:
    {
      "food_title": "Descriptive food name and portion",
      "portion_grams": integer,
      "calories": integer,
      "protein_grams": float,
      "carbs_grams": float,
      "fats_grams": float,
      "ai_observation": "1-line diagnostic observation"
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
    except Exception:
        return None

def analyze_physique_ai(pil_img: Image.Image, user_prof: dict, key: str):
    system_prompt = f"""
    You are the Lead Metabolic Diagnostician and Fitness Physiologist for KSP Consulting.
    Analyze this user's physique photo solely for medical, postural, and athletic body composition assessment.
    User Profile Context:
    - Gender: {user_prof['gender']}, Weight: {user_prof['weight_kg']} kg, Height: {user_prof['height_cm']} cm, Age: {user_prof['age']} years
    
    CLOTHING & OCCLUSION INSTRUCTIONS:
    - If the subject is wearing loose clothing covering the torso/waist, recognize that abdominal fat is obscured.
    - Apply a conservative correction (+3% to +5%) to the visual estimate rather than basing body fat solely on exposed arms and shoulders.
    - If shirtless/clear, estimate visual body fat directly from abdominal definition and waistline tightness.
    
    OUTPUT STRICT JSON ONLY:
    {{
      "estimated_body_fat_pct": float,
      "physique_assessment": "1-2 sentence clinical and motivating breakdown of muscle structure and conditioning focal points"
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
        est_bf = max(10.0, min(est_bf, 36.0))
        return {
            "estimated_body_fat_pct": est_bf,
            "physique_assessment": f"Biometric analysis reflects a structural frame (BMI: {round(bmi,1)}) with central abdominal adiposity as the primary target."
        }

    try:
        clean_json = raw_resp.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception:
        return {
            "estimated_body_fat_pct": 26.5,
            "physique_assessment": "The subject displays a solid foundation of clavicular width and deltoid fullness, accompanied by moderate central midsection adiposity."
        }

# 5. PDF Generation Class
class KSPFitnessPDF(FPDF):
    def header(self):
        self.set_fill_color(15, 23, 42)
        self.rect(0, 0, 210, 28, 'F')
        self.set_text_color(59, 130, 246)
        self.set_font("Helvetica", "B", 10)
        self.set_xy(14, 6)
        self.cell(0, 5, "KSP CONSULTING & SOLUTIONS", ln=True)
        self.set_text_color(255, 255, 255)
        self.set_font("Helvetica", "B", 13)
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
    pdf.set_auto_page_break(auto=True, margin=15)

    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, f"1. CLIENT BIOMETRIC & METABOLIC PROFILE ({prof['name'].upper()})", ln=True)
    pdf.set_draw_color(59, 130, 246)
    pdf.set_line_width(0.4)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(30, 41, 59)
    col_w = 45.5
    
    pdf.cell(col_w, 6, f" Age: {prof['age']} yrs", border=1)
    pdf.cell(col_w, 6, f" Gender: {prof['gender']}", border=1)
    pdf.cell(col_w, 6, f" Height: {prof['height_cm']} cm", border=1)
    pdf.cell(col_w, 6, f" Weight: {prof['weight_kg']} kg", border=1, ln=True)

    bf_text = f"{prof.get('body_fat_pct', '--')}%"
    lean_text = f"{prof.get('lean_mass_kg', '--')} kg"
    fat_text = f"{prof.get('fat_mass_kg', '--')} kg"
    act_clean = prof['activity'].split('(')[0].strip()

    pdf.cell(col_w, 6, f" Body Fat: {bf_text}", border=1)
    pdf.cell(col_w, 6, f" Lean Mass: {lean_text}", border=1)
    pdf.cell(col_w, 6, f" Fat Mass: {fat_text}", border=1)
    pdf.cell(col_w, 6, f" Activity: {act_clean}", border=1, ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, f"2. SCIENTIFIC DAILY MACRONUTRIENT TARGETS -- {prof['goal'].upper()}", ln=True)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(2)

    pdf.set_fill_color(241, 245, 249)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(col_w, 6, "Target Calories", border=1, fill=True, align="C")
    pdf.cell(col_w, 6, "Protein (g)", border=1, fill=True, align="C")
    pdf.cell(col_w, 6, "Carbohydrates (g)", border=1, fill=True, align="C")
    pdf.cell(col_w, 6, "Fats (g)", border=1, fill=True, align="C", ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(col_w, 6, f"{prof['target_kcal']} kcal", border=1, align="C")
    pdf.cell(col_w, 6, f"{prof['target_p']} g", border=1, align="C")
    pdf.cell(col_w, 6, f"{prof['target_c']} g", border=1, align="C")
    pdf.cell(col_w, 6, f"{prof['target_f']} g", border=1, align="C", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, "3. DAILY MEAL & NUTRITION LEDGER", ln=True)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(2)

    valid_meals = [m for m in meals if m.get('kcal', 0) > 0 and "no food" not in m.get('item', '').lower()]

    pdf.set_fill_color(241, 245, 249)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(20, 6, "Time", border=1, fill=True)
    pdf.cell(78, 6, "Food Item / Portion", border=1, fill=True)
    pdf.cell(21, 6, "Protein", border=1, fill=True, align="C")
    pdf.cell(21, 6, "Carbs", border=1, fill=True, align="C")
    pdf.cell(21, 6, "Fats", border=1, fill=True, align="C")
    pdf.cell(21, 6, "Calories", border=1, fill=True, align="C", ln=True)

    pdf.set_font("Helvetica", "", 8)
    if valid_meals:
        for m in valid_meals:
            pdf.cell(20, 6, str(m.get("time", "--")), border=1)
            pdf.cell(78, 6, str(m.get("item", "Item"))[:45], border=1)
            pdf.cell(21, 6, f"{m.get('p', 0)}g", border=1, align="C")
            pdf.cell(21, 6, f"{m.get('c', 0)}g", border=1, align="C")
            pdf.cell(21, 6, f"{m.get('f', 0)}g", border=1, align="C")
            pdf.cell(21, 6, f"{m.get('kcal', 0)} kcal", border=1, align="C", ln=True)
    else:
        pdf.cell(182, 6, "No meals submitted for this 24-hr cycle.", border=1, align="C", ln=True)
    pdf.ln(4)

    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, "4. STRENGTH & TRAINING PERFORMANCE LOG", ln=True)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(2)

    pdf.set_fill_color(241, 245, 249)
    pdf.set_font("Helvetica", "B", 8)
    pdf.cell(20, 6, "Time", border=1, fill=True)
    pdf.cell(48, 6, "Split Target", border=1, fill=True)
    pdf.cell(50, 6, "Exercise Name", border=1, fill=True)
    pdf.cell(22, 6, "Sets x Reps", border=1, fill=True, align="C")
    pdf.cell(22, 6, "Weight (kg)", border=1, fill=True, align="C")
    pdf.cell(20, 6, "RPE", border=1, fill=True, align="C", ln=True)

    pdf.set_font("Helvetica", "", 8)
    if workouts:
        for w in workouts:
            pdf.cell(20, 6, str(w.get("time", "--")), border=1)
            pdf.cell(48, 6, str(w.get("split", "Split"))[:26], border=1)
            pdf.cell(50, 6, str(w.get("exercise", "Exercise"))[:28], border=1)
            pdf.cell(22, 6, f"{w.get('sets', 0)} x {w.get('reps', 0)}", border=1, align="C")
            pdf.cell(22, 6, f"{w.get('weight', 0)} kg", border=1, align="C")
            pdf.cell(20, 6, f"RPE {w.get('rpe', 0)}", border=1, align="C", ln=True)
    else:
        pdf.cell(182, 6, "No workouts submitted for this 24-hr cycle.", border=1, align="C", ln=True)
    pdf.ln(4)

    if prof.get("assessment_notes"):
        pdf.set_font("Helvetica", "B", 10)
        pdf.set_text_color(15, 23, 42)
        pdf.cell(0, 6, "5. AI PHYSIOLOGICAL & CONDITIONING ASSESSMENT", ln=True)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(51, 65, 85)
        clean_notes = prof["assessment_notes"].replace("-29.", "29.").replace("-", "~")
        pdf.multi_cell(182, 5, clean_notes, border=1)

    return bytes(pdf.output())

# 6. Database Operations (Supabase Cloud with Local Fallback)
def fetch_user(email):
    if supabase:
        try:
            res = supabase.table("users").select("*").eq("email", email).execute()
            if res.data and len(res.data) > 0:
                return res.data[0]
        except Exception:
            pass
    return None

def create_user(email, name, pw_hash):
    init_proto = compute_clinical_metabolic_protocol(75.0, 158.0, 28, "Male", "Moderate Active (Gym 3-5 days/week)", 26.5)
    default_profile = {
        "name": name,
        "age": 28,
        "gender": "Male",
        "weight_kg": 75.0,
        "height_cm": 158.0,
        "activity": "Moderate Active (Gym 3-5 days/week)",
        "assessment_notes": "The subject displays a solid foundation of clavicular width, deltoid fullness, and upper back thickness, accompanied by elevated central abdominal adiposity.",
        **init_proto
    }
    if supabase:
        try:
            supabase.table("users").insert({
                "email": email,
                "name": name,
                "password_hash": pw_hash,
                "subscription_status": "Free Beta",
                "profile": default_profile,
                "meals": [],
                "workouts": []
            }).execute()
            return True
        except Exception as e:
            st.error(f"Cloud DB Error: {e}")
            return False
    return False

def sync_user_data(email, profile, meals, workouts):
    if supabase:
        try:
            supabase.table("users").update({
                "profile": profile,
                "meals": meals,
                "workouts": workouts
            }).eq("email", email).execute()
        except Exception:
            pass

# 7. Session State & Sidebar Auth
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

with st.sidebar:
    st.markdown("### ⚡ KSP Cloud SaaS Platform")
    if not st.session_state.auth_user:
        auth_mode = st.radio("Access:", ["Log In", "Sign Up (Free Beta)"])
        u_email = st.text_input("Email / Mobile:", placeholder="athlete@gmail.com")
        u_pass = st.text_input("Password:", type="password")
        
        if auth_mode == "Sign Up (Free Beta)":
            u_fullname = st.text_input("Full Name:", placeholder="Shashank Kulkarni")
            if st.button("🚀 Create Account", type="primary", use_container_width=True):
                if u_email and u_pass and u_fullname:
                    existing = fetch_user(u_email)
                    if existing:
                        st.error("Account already exists. Please Log In.")
                    else:
                        if create_user(u_email, u_fullname, hash_pw(u_pass)):
                            st.session_state.auth_user = u_email
                            st.rerun()
                else:
                    st.warning("Please fill in all fields.")
        else:
            if st.button("🔑 Log In", type="primary", use_container_width=True):
                user_db = fetch_user(u_email)
                if user_db and user_db["password_hash"] == hash_pw(u_pass):
                    st.session_state.auth_user = u_email
                    st.rerun()
                else:
                    st.error("Invalid credentials.")
    else:
        user_record = fetch_user(st.session_state.auth_user)
        st.markdown(f"**Athlete:** `{user_record['name'] if user_record else 'User'}`")
        st.markdown(f"**Plan:** :green[{user_record.get('subscription_status', 'Free Beta') if user_record else 'Free'}]")
        if st.button("Logout", use_container_width=True):
            st.session_state.auth_user = None
            st.rerun()

# 8. Main App Gate
st.markdown("""
<div class="ksp-header">
    <div class="ksp-brand">KSP Consulting & Solutions</div>
    <div class="ksp-title">Fitness OS • Cloud SaaS Platform</div>
    <div class="ksp-tagline">Strategy amplified, complexity simplified.</div>
</div>
""", unsafe_allow_html=True)

if not st.session_state.auth_user:
    st.info("👋 Welcome to **KSP Fitness OS**. Please **Sign Up** or **Log In** from the sidebar to access your persistent cloud profile, AI vision scanner, and workout logs.")
    st.stop()

# Retrieve user profile from Supabase
user_record = fetch_user(st.session_state.auth_user)
if not user_record:
    st.error("Session expired or user not found. Please log in again.")
    st.stop()

prof = user_record["profile"]
meal_logs = user_record.get("meals", [])
workout_logs = user_record.get("workouts", [])

# 9. Profile & Auto-Routing Expander
with st.expander("👤 User Profile & Strict Clinical Protocol Routing", expanded=False):
    col_u1, col_u2, col_u3 = st.columns(3)
    with col_u1:
        u_name = st.text_input("Full Name:", value=prof["name"])
        u_gender = st.selectbox("Gender:", ["Male", "Female"], index=0 if prof["gender"] == "Male" else 1)
        u_age = st.number_input("Age (years):", min_value=12, max_value=90, value=int(prof["age"]))
    with col_u2:
        u_weight = st.number_input("Weight (kg):", min_value=30.0, max_value=250.0, value=float(prof["weight_kg"]), step=0.5)
        u_height = st.number_input("Height (cm):", min_value=100.0, max_value=240.0, value=float(prof["height_cm"]), step=0.5)
        u_activity = st.selectbox("Activity Level:", [
            "Moderate Active (Gym 3-5 days/week)",
            "Heavy Active (Gym 6-7 days intense gym + cardio)",
            "Light Active (Gym 1-3 days/week)",
            "Sedentary (Desk Job, minimal exercise)"
        ])
    with col_u3:
        st.markdown(f"**Prescribed Phase:** :orange[{prof.get('goal', 'Targeted Fat Loss')}]")
        st.markdown(f"**Body Fat:** `{prof.get('body_fat_pct', 24.0)}%` | **Lean Mass:** `{prof.get('lean_mass_kg', 55.0)}kg`")
        if st.button("⚡ Recalculate Clinical Protocol", type="primary", use_container_width=True):
            new_proto = compute_clinical_metabolic_protocol(
                u_weight, u_height, u_age, u_gender, u_activity, prof.get("body_fat_pct")
            )
            prof.update({
                "name": u_name,
                "gender": u_gender,
                "age": u_age,
                "weight_kg": u_weight,
                "height_cm": u_height,
                "activity": u_activity,
                **new_proto
            })
            sync_user_data(st.session_state.auth_user, prof, meal_logs, workout_logs)
            st.success(f"Protocol Applied: {new_proto['goal']} | {new_proto['target_kcal']} kcal | {new_proto['target_p']}g Protein")
            st.rerun()

# 10. Real-Time Top Macro Dashboard
df_meals = pd.DataFrame(meal_logs)
curr_kcal = int(df_meals["kcal"].sum()) if not df_meals.empty else 0
curr_p = round(float(df_meals["p"].sum()), 1) if not df_meals.empty else 0.0
curr_c = round(float(df_meals["c"].sum()), 1) if not df_meals.empty else 0.0
curr_f = round(float(df_meals["f"].sum()), 1) if not df_meals.empty else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Calories", f"{curr_kcal} kcal", f"{prof['target_kcal'] - curr_kcal} remaining", delta_color="inverse")
col2.metric("Protein", f"{curr_p} g", f"{round(prof['target_p'] - curr_p, 1)}g to goal")
col3.metric("Carbs", f"{curr_c} g", f"Target: {prof['target_c']}g")
col4.metric("Fats", f"{curr_f} g", f"Target: {prof['target_f']}g")

st.write("---")

# 11. Two-Column Workstation
left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.subheader("🥗 Smart Macro & Food Engine")
    tab_text, tab_photo = st.tabs(["⚡ Direct Text Prompt", "📷 Plate / Label Photo Scanner"])
    
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
                        meal_logs.insert(0, result)
                        sync_user_data(st.session_state.auth_user, prof, meal_logs, workout_logs)
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
                        meal_logs.insert(0, result)
                        sync_user_data(st.session_state.auth_user, prof, meal_logs, workout_logs)
                        st.success(f"✅ Identified: {result['item']} ({result['p']}g Protein, {result['kcal']} kcal)")
                        st.rerun()

    st.markdown("#### Today's Meal Log")
    if meal_logs:
        df_meal_disp = pd.DataFrame(meal_logs)[["time", "item", "p", "c", "f", "kcal", "source"]]
        df_meal_disp.columns = ["Time", "Food Item", "Protein (g)", "Carbs (g)", "Fats (g)", "Calories (kcal)", "AI Insight"]
        st.dataframe(df_meal_disp, use_container_width=True, hide_index=True)
        if st.button("Clear Meal Log"):
            sync_user_data(st.session_state.auth_user, prof, [], workout_logs)
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
                    scan = analyze_physique_ai(p_img, prof, API_KEY)
                    if scan:
                        new_bf = scan.get("estimated_body_fat_pct", 24.0)
                        updated_proto = compute_clinical_metabolic_protocol(
                            prof["weight_kg"], prof["height_cm"], prof["age"], prof["gender"], prof["activity"], new_bf
                        )
                        prof.update({
                            "assessment_notes": scan.get("physique_assessment", ""),
                            **updated_proto
                        })
                        sync_user_data(st.session_state.auth_user, prof, meal_logs, workout_logs)
                        st.success(f"Body Fat: {new_bf}% -> Auto-Routed to: {updated_proto['goal']}")
                        c_bf1, c_bf2, c_bf3 = st.columns(3)
                        c_bf1.metric("Body Fat %", f"{new_bf}%")
                        c_bf2.metric("Lean Muscle", f"{updated_proto['lean_mass_kg']} kg")
                        c_bf3.metric("Fat Mass", f"{updated_proto['fat_mass_kg']} kg")
                        st.info(f"**Clinical Assessment:** {scan.get('physique_assessment')}")
                        st.rerun()

        if prof.get("body_fat_pct") is not None:
            st.markdown(f"> **Stored Metabolic Scan:** **{prof['body_fat_pct']}% Body Fat** | **{prof['lean_mass_kg']}kg Lean Mass** | **Phase: {prof['goal']}**")

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
                workout_logs.insert(0, w_entry)
                sync_user_data(st.session_state.auth_user, prof, meal_logs, workout_logs)
                st.success(f"Logged: {ex_name.title()} ({sets_val}x{reps_val} @ {weight_val}kg)")
                st.rerun()

        st.markdown("#### Today's Completed Sets")
        if workout_logs:
            df_w_disp = pd.DataFrame(workout_logs)[["time", "split", "exercise", "sets", "reps", "weight", "rpe"]]
            df_w_disp.columns = ["Time", "Split", "Exercise", "Sets", "Reps", "Weight (kg)", "RPE"]
            st.dataframe(df_w_disp, use_container_width=True, hide_index=True)
            if st.button("Clear Workout Logs"):
                sync_user_data(st.session_state.auth_user, prof, meal_logs, [])
                st.rerun()
        else:
            st.info("No workout sets logged yet today.")

st.write("---")

# 12. Client Executive PDF Export
st.subheader("📄 Client Executive Export")
pdf_col1, pdf_col2 = st.columns([2, 1])
with pdf_col1:
    st.write("Generate a branded, confidential PDF summary containing your clinical body composition audit, strict macro targets, meal ledger, and workout sets.")
with pdf_col2:
    pdf_bytes = build_pdf_report(prof, meal_logs, workout_logs)
    st.download_button(
        label="📥 Download KSP Fitness Audit (PDF)",
        data=pdf_bytes,
        file_name=f"KSP_Fitness_Audit_{prof['name']}_{datetime.now().strftime('%Y%m%d')}.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True
    )