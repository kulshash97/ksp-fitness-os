import streamlit as st
import pandas as pd
import json
import os
import hashlib
from datetime import datetime
from PIL import Image
import google.generativeai as genai
from google.generativeai.types import HarmCategory, HarmBlockThreshold
from fpdf import FPDF
from supabase import create_client, Client

# 1. Page Config & Dark Neon Aesthetics
st.set_page_config(
    page_title="KSP Fitness OS • Clinical Diagnostician & Diet Architect",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

st.markdown("""
<style>
    .stApp {
        background: radial-gradient(circle at top left, #0D1527, #070B14 80%);
        color: #F8FAFC;
    }
    .ksp-header {
        background: linear-gradient(135deg, #0F172A 0%, #1E293B 100%);
        padding: 20px 24px;
        border-radius: 14px;
        border: 1px solid #334155;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
        margin-bottom: 20px;
    }
    .ksp-brand {
        color: #3B82F6;
        font-size: 11px;
        font-weight: 800;
        letter-spacing: 2px;
        text-transform: uppercase;
    }
    .ksp-title {
        color: #FFFFFF;
        font-size: 24px;
        font-weight: 900;
        margin-top: 4px;
    }
    .ksp-tagline {
        color: #94A3B8;
        font-size: 12px;
        font-style: italic;
    }
    .diet-card {
        background: #0F172A;
        border: 1px solid #1E293B;
        border-radius: 12px;
        padding: 16px;
        margin-bottom: 12px;
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

# 2. Supabase Cloud Connection & API Keys
API_KEY = st.secrets.get("GEMINI_API_KEY", "")
SUPABASE_URL = st.secrets.get("SUPABASE_URL", "")
SUPABASE_KEY = st.secrets.get("SUPABASE_KEY", "")

@st.cache_resource
def init_supabase():
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            return create_client(SUPABASE_URL, SUPABASE_KEY)
        except Exception:
            return None
    return None

supabase: Client = init_supabase()

def hash_pw(password):
    return hashlib.sha256(password.encode()).hexdigest()

# 3. Clinical Metabolic Engine
def compute_clinical_metabolic_protocol(weight_kg, height_cm, age_yrs, gender, activity_str, goal_choice, body_fat_pct=None, lean_mass_kg=None):
    if lean_mass_kg is not None and lean_mass_kg > 0:
        bmr = 370.0 + (21.6 * lean_mass_kg)
    else:
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
        fat_mass = round(weight_kg * (body_fat_pct / 100.0), 2)
        lean_mass = round(weight_kg - fat_mass, 2) if lean_mass_kg is None else lean_mass_kg
    else:
        body_fat_pct = 22.0 if gender == "Male" else 28.0
        fat_mass = round(weight_kg * (body_fat_pct / 100.0), 2)
        lean_mass = round(weight_kg - fat_mass, 2)

    if "Pure Cutting" in goal_choice:
        target_calories = tdee - 700.0
        protein_g = weight_kg * 2.2
        fat_pct = 0.20
    elif "Recomposition" in goal_choice:
        target_calories = tdee - 250.0
        protein_g = weight_kg * 2.2
        fat_pct = 0.25
    elif "Lean Bulk" in goal_choice:
        target_calories = tdee + 275.0
        protein_g = weight_kg * 2.0
        fat_pct = 0.25
    elif "Aggressive Bulk" in goal_choice:
        target_calories = tdee + 500.0
        protein_g = weight_kg * 1.8
        fat_pct = 0.28
    else:
        target_calories = tdee
        protein_g = weight_kg * 2.0
        fat_pct = 0.25

    min_floor = 1350.0 if gender == "Male" else 1200.0
    target_calories = max(min_floor, target_calories)

    fat_calories = target_calories * fat_pct
    fat_g = fat_calories / 9.0
    protein_calories = protein_g * 4.0
    carb_calories = max(0.0, target_calories - (protein_calories + fat_calories))
    carb_g = carb_calories / 4.0

    return {
        "bmr": round(bmr, 1),
        "tdee": round(tdee, 1),
        "body_fat_pct": round(body_fat_pct, 1),
        "fat_mass_kg": fat_mass,
        "lean_mass_kg": lean_mass,
        "goal": goal_choice,
        "target_kcal": int(round(target_calories)),
        "target_p": int(round(protein_g)),
        "target_c": int(round(carb_g)),
        "target_f": int(round(fat_g))
    }

# 4. Multi-Diet Food Library (Pure Veg, Vegan, Eggetarian, Non-Veg, Flexitarian)
FOOD_LIBRARY = {
    "Pure Veg": {
        "Low Budget": [
            {"item": "Dry Soya Chunks (boiled/curry)", "portion": "70g dry", "p": 36.4, "c": 23.1, "f": 0.4, "kcal": 242, "cost": "₹12", "type": "High Protein Low Fat"},
            {"item": "Roasted Chana / Bhuna Chana", "portion": "60g", "p": 13.5, "c": 35.0, "f": 3.2, "kcal": 225, "cost": "₹15", "type": "High Protein High Carb"},
            {"item": "Sprouted Moong Salad", "portion": "100g", "p": 8.0, "c": 20.0, "f": 0.6, "kcal": 120, "cost": "₹10", "type": "Clean Plant Protein"},
            {"item": "Low-Fat Curd (Dahi)", "portion": "250g", "p": 10.5, "c": 12.0, "f": 3.0, "kcal": 120, "cost": "₹20", "type": "Dairy Protein"}
        ],
        "Medium Budget": [
            {"item": "Low-Fat Paneer (Fresh)", "portion": "150g", "p": 27.0, "c": 4.5, "f": 12.0, "kcal": 240, "cost": "₹60", "type": "Vegetarian Staple"},
            {"item": "Soy Milk / Tofu Block", "portion": "200g tofu", "p": 16.0, "c": 3.0, "f": 8.0, "kcal": 145, "cost": "₹45", "type": "Lactose Free"},
            {"item": "Whey Protein Concentrate", "portion": "1 scoop (33g)", "p": 24.0, "c": 2.5, "f": 1.5, "kcal": 120, "cost": "₹70", "type": "High Protein"}
        ],
        "Premium Budget": [
            {"item": "Whey Isolate + Greek Yogurt", "portion": "1 scoop + 100g", "p": 35.0, "c": 4.0, "f": 1.0, "kcal": 170, "cost": "₹150", "type": "Ultra Pure Protein"},
            {"item": "Almond Butter + Raw Seeds", "portion": "30g mix", "p": 18.0, "c": 12.0, "f": 26.0, "kcal": 350, "cost": "₹120", "type": "Healthy Fats"}
        ]
    },
    "Vegan": {
        "Low Budget": [
            {"item": "Boiled Soya Chunks with Rice", "portion": "75g soya", "p": 39.0, "c": 30.0, "f": 0.5, "kcal": 280, "cost": "₹14", "type": "100% Plant Protein"},
            {"item": "Sprouted Kala Chana + Peanuts", "portion": "100g mix", "p": 14.0, "c": 28.0, "f": 8.0, "kcal": 240, "cost": "₹12", "type": "Plant Whole Food"},
            {"item": "Roasted Chana Powder Sattu Drink", "portion": "50g sattu", "p": 11.5, "c": 32.0, "f": 2.5, "kcal": 195, "cost": "₹15", "type": "Digestive Fuel"}
        ],
        "Medium Budget": [
            {"item": "Firm Organic Tofu Stir Fry", "portion": "250g", "p": 20.0, "c": 4.0, "f": 10.0, "kcal": 185, "cost": "₹55", "type": "Soy Protein"},
            {"item": "Plant Pea & Brown Rice Protein Scoop", "portion": "33g scoop", "p": 25.0, "c": 2.0, "f": 1.2, "kcal": 120, "cost": "₹85", "type": "Vegan Isolate"}
        ],
        "Premium Budget": [
            {"item": "Chia Seeds + Quinoa + Hemp Hearts", "portion": "Bowl (150g)", "p": 22.0, "c": 40.0, "f": 14.0, "kcal": 370, "cost": "₹160", "type": "Superfood Complex"}
        ]
    },
    "Eggetarian": {
        "Low Budget": [
            {"item": "Boiled Whole Eggs (3) + 3 Whites", "portion": "6 eggs", "p": 30.0, "c": 1.5, "f": 15.0, "kcal": 260, "cost": "₹42", "type": "High Bioavailability"},
            {"item": "Egg White Bhurji with Soya Chunks", "portion": "5 whites + 40g soya", "p": 38.0, "c": 14.0, "f": 1.0, "kcal": 220, "cost": "₹45", "type": "Lean Muscle Builder"},
            {"item": "Roasted Chana with Boiled Eggs", "portion": "50g chana + 2 eggs", "p": 23.0, "c": 30.0, "f": 11.0, "kcal": 310, "cost": "₹28", "type": "Sustained Energy"}
        ],
        "Medium Budget": [
            {"item": "Whole Egg Omelette with Low-Fat Paneer", "portion": "3 eggs + 80g paneer", "p": 32.0, "c": 4.0, "f": 20.0, "kcal": 320, "cost": "₹65", "type": "Mid Fat High Protein"},
            {"item": "Whey Protein Shake + 4 Egg Whites", "portion": "1 scoop + 4 whites", "p": 38.0, "c": 3.0, "f": 1.5, "kcal": 180, "cost": "₹95", "type": "Rapid Absorption"}
        ],
        "Premium Budget": [
            {"item": "Free-Range Organic Eggs with Avocado", "portion": "4 whole + 1/2 avocado", "p": 26.0, "c": 6.0, "f": 28.0, "kcal": 380, "cost": "₹160", "type": "Hormone Optimization"}
        ]
    },
    "Non-Veg": {
        "Low Budget": [
            {"item": "Whole Eggs (4) + 2 Whites", "portion": "6 eggs total", "p": 32.0, "c": 2.0, "f": 20.0, "kcal": 320, "cost": "₹40", "type": "Complete Protein"},
            {"item": "Chicken Liver / Lean Value Cuts", "portion": "150g", "p": 26.0, "c": 1.0, "f": 6.0, "kcal": 170, "cost": "₹35", "type": "Micro-Nutrient Dense"}
        ],
        "Medium Budget": [
            {"item": "Chicken Breast (Pan Seared)", "portion": "200g raw", "p": 62.0, "c": 0.0, "f": 5.0, "kcal": 310, "cost": "₹70", "type": "Pure Lean Protein"},
            {"item": "Local Rohu/Katla or White Fish", "portion": "180g", "p": 36.0, "c": 0.0, "f": 3.0, "kcal": 175, "cost": "₹90", "type": "Lean Fish"}
        ],
        "Premium Budget": [
            {"item": "Atlantic Salmon Fillet / Mutton Lean Cut", "portion": "200g", "p": 44.0, "c": 0.0, "f": 22.0, "kcal": 380, "cost": "₹350", "type": "Omega-3 Rich"}
        ]
    }
}
FOOD_LIBRARY["Both / Flexitarian"] = FOOD_LIBRARY["Non-Veg"]

# 5. Gemini AI Engine with InBody OCR
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

    candidate_models = ['gemini-2.5-flash', 'gemini-1.5-flash-latest']
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

def analyze_inbody_sheet_ai(pil_img: Image.Image, key: str):
    system_prompt = """
    You are an expert clinical diagnostician and OCR system specialized in InBody/DEXA body composition sheets.
    Accurately extract all printed biometric values from the provided image.
    
    OUTPUT STRICT JSON ONLY:
    {
      "weight_kg": float,
      "height_cm": float,
      "age": integer,
      "gender": "Male" or "Female",
      "smm_kg": float,
      "body_fat_mass_kg": float,
      "body_fat_pct": float,
      "bmi": float,
      "fat_free_mass_kg": float,
      "bmr_kcal": integer,
      "inbody_score": integer,
      "visceral_fat_level": integer,
      "diagnostic_summary": "1-2 sentence clinical summary of the report metrics"
    }
    """
    img_resized = pil_img.copy()
    img_resized.thumbnail((1500, 1500))
    raw_resp = run_gemini_query([system_prompt, img_resized], key)
    if not raw_resp:
        return None
    try:
        clean_json = raw_resp.replace("```json", "").replace("```", "").strip()
        return json.loads(clean_json)
    except Exception:
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

# 6. PDF Audit Document Generator
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
    pdf.cell(0, 6, f"1. CLIENT BIOMETRIC & CLINICAL AUDIT ({prof['name'].upper()})", ln=True)
    pdf.set_draw_color(59, 130, 246)
    pdf.set_line_width(0.4)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(30, 41, 59)
    col_w = 45.5
    
    pdf.cell(col_w, 6, f" Age: {prof.get('age', 25)} yrs", border=1)
    pdf.cell(col_w, 6, f" Gender: {prof.get('gender', 'Male')}", border=1)
    pdf.cell(col_w, 6, f" Height: {prof.get('height_cm', 170.0)} cm", border=1)
    pdf.cell(col_w, 6, f" Weight: {prof.get('weight_kg', 70.0)} kg", border=1, ln=True)

    bf_text = f"{prof.get('body_fat_pct', '--')}%"
    lean_text = f"{prof.get('lean_mass_kg', '--')} kg"
    fat_text = f"{prof.get('fat_mass_kg', '--')} kg"
    smm_text = f"{prof.get('smm_kg', '--')} kg" if prof.get('smm_kg') else "--"

    pdf.cell(col_w, 6, f" Body Fat: {bf_text}", border=1)
    pdf.cell(col_w, 6, f" Lean Mass: {lean_text}", border=1)
    pdf.cell(col_w, 6, f" Fat Mass: {fat_text}", border=1)
    pdf.cell(col_w, 6, f" Muscle (SMM): {smm_text}", border=1, ln=True)

    if prof.get("visceral_fat_level") or prof.get("inbody_score"):
        v_level = f"Level {prof.get('visceral_fat_level')}" if prof.get('visceral_fat_level') else "--"
        score_val = f"{prof.get('inbody_score')}/100" if prof.get('inbody_score') else "--"
        bmr_val = f"{prof.get('bmr')} kcal"
        pdf.cell(col_w, 6, f" InBody Score: {score_val}", border=1)
        pdf.cell(col_w, 6, f" Visceral Fat: {v_level}", border=1)
        pdf.cell(col_w, 6, f" Clinical BMR: {bmr_val}", border=1)
        pdf.cell(col_w, 6, f" Method: Clinical Scan", border=1, ln=True)

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
    pdf.cell(col_w, 6, f"{prof.get('target_kcal', 2000)} kcal", border=1, align="C")
    pdf.cell(col_w, 6, f"{prof.get('target_p', 140)} g", border=1, align="C")
    pdf.cell(col_w, 6, f"{prof.get('target_c', 220)} g", border=1, align="C")
    pdf.cell(col_w, 6, f"{prof.get('target_f', 55)} g", border=1, align="C", ln=True)
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
        pdf.cell(0, 6, "5. AI CLINICAL & POSTURAL ASSESSMENT", ln=True)
        pdf.set_font("Helvetica", "I", 8)
        pdf.set_text_color(51, 65, 85)
        clean_notes = prof["assessment_notes"].replace("-29.", "29.").replace("-", "~")
        pdf.multi_cell(182, 5, clean_notes, border=1)

    return bytes(pdf.output())

# 7. Database Operations
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
    clean_name = name.strip().title()
    init_proto = compute_clinical_metabolic_protocol(70.0, 170.0, 25, "Male", "Moderate Active (Gym 3-5 days/week)", "Body Recomposition (Build Muscle & Burn Fat)")
    new_user_profile = {
        "name": clean_name,
        "age": 25,
        "gender": "Male",
        "weight_kg": 70.0,
        "height_cm": 170.0,
        "activity": "Moderate Active (Gym 3-5 days/week)",
        "goal": "Body Recomposition (Build Muscle & Burn Fat)",
        "smm_kg": None,
        "inbody_score": None,
        "visceral_fat_level": None,
        "assessment_notes": "Profile initialized. Upload your InBody scan or mirror photo to calibrate clinical targets.",
        **init_proto
    }
    if supabase:
        try:
            supabase.table("users").insert({
                "email": email,
                "name": clean_name,
                "password_hash": pw_hash,
                "subscription_status": "Free Beta",
                "profile": new_user_profile,
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

# 8. User Authentication State & Sidebar
if "auth_user" not in st.session_state:
    st.session_state.auth_user = None

with st.sidebar:
    st.markdown("### ⚡ KSP Cloud SaaS Platform")
    if not st.session_state.auth_user:
        auth_mode = st.radio("Access:", ["Log In", "Sign Up (Free Beta)"], key="auth_mode_select")
        u_email = st.text_input("Email / Mobile:", placeholder="athlete@gmail.com", key="auth_email_in").strip().lower()
        u_pass = st.text_input("Password:", type="password", key="auth_pass_in")
        
        if auth_mode == "Sign Up (Free Beta)":
            u_fullname = st.text_input("Full Name:", placeholder="Your Name", key="auth_name_in")
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

# 9. Main Application Workspace
st.markdown("""
<div class="ksp-header">
    <div class="ksp-brand">KSP Consulting & Solutions</div>
    <div class="ksp-title">Fitness OS • Clinical Metabolic & Diet Engine</div>
    <div class="ksp-tagline">Strategy amplified, complexity simplified. Precision Indian macros & clinical diagnostics.</div>
</div>
""", unsafe_allow_html=True)

if not st.session_state.auth_user:
    st.info("👋 Welcome to **KSP Fitness OS**. Please **Sign Up** or **Log In** from the sidebar to access your private athlete profile, InBody scanner, and customized diet planner.")
    st.stop()

user_record = fetch_user(st.session_state.auth_user)
if not user_record:
    st.error("Session expired. Please log in again.")
    st.stop()

prof = user_record["profile"]
meal_logs = user_record.get("meals", [])
workout_logs = user_record.get("workouts", [])
u_id = st.session_state.auth_user

# 10. Profile & Target Goal Customization (Scoped strictly by user session)
with st.expander("👤 Athlete Biometrics & Clinical Target Protocols", expanded=False):
    col_u1, col_u2, col_u3 = st.columns(3)
    with col_u1:
        u_name = st.text_input("Full Name:", value=str(prof.get("name", "")), key=f"prof_name_{u_id}")
        u_gender = st.selectbox("Gender:", ["Male", "Female"], index=0 if prof.get("gender") == "Male" else 1, key=f"prof_gender_{u_id}")
        u_age = st.number_input("Age (years):", min_value=12, max_value=90, value=int(prof.get("age", 25)), key=f"prof_age_{u_id}")
    with col_u2:
        u_weight = st.number_input("Weight (kg):", min_value=30.0, max_value=250.0, value=float(prof.get("weight_kg", 70.0)), step=0.1, key=f"prof_wt_{u_id}")
        u_height = st.number_input("Height (cm):", min_value=100.0, max_value=240.0, value=float(prof.get("height_cm", 170.0)), step=0.1, key=f"prof_ht_{u_id}")
        
        act_opts = [
            "Moderate Active (Gym 3-5 days/week)",
            "Heavy Active (Gym 6-7 days intense gym + cardio)",
            "Light Active (Gym 1-3 days/week)",
            "Sedentary (Desk Job, minimal exercise)"
        ]
        curr_act = prof.get("activity", act_opts[0])
        act_idx = act_opts.index(curr_act) if curr_act in act_opts else 0
        u_activity = st.selectbox("Activity Level:", act_opts, index=act_idx, key=f"prof_act_{u_id}")
    with col_u3:
        goal_opts = [
            "Pure Cutting (Aggressive Fat Loss)",
            "Body Recomposition (Build Muscle & Burn Fat)",
            "Lean Bulk (Clean Hypertrophy)",
            "Aggressive Bulk (Heavy Mass Gain)",
            "Maintenance & Peak Performance"
        ]
        curr_goal = prof.get("goal", goal_opts[1])
        goal_idx = 0
        for i, g in enumerate(goal_opts):
            if g.split()[0] in curr_goal:
                goal_idx = i
                break
        u_goal = st.selectbox("Target Goal:", goal_opts, index=goal_idx, key=f"prof_goal_{u_id}")
        
        bf_disp = f"{prof.get('body_fat_pct', 20.0)}%" if prof.get('body_fat_pct') else "--"
        lean_disp = f"{prof.get('lean_mass_kg', 55.0)}kg" if prof.get('lean_mass_kg') else "--"
        st.markdown(f"**Body Fat:** `{bf_disp}` | **Lean Mass:** `{lean_disp}`")
        
        if st.button("⚡ Apply Scientific Goal Protocol", type="primary", use_container_width=True, key=f"btn_calc_{u_id}"):
            new_proto = compute_clinical_metabolic_protocol(
                u_weight, u_height, u_age, u_gender, u_activity, u_goal, prof.get("body_fat_pct"), prof.get("lean_mass_kg")
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
            st.success(f"Updated: {new_proto['goal']} | {new_proto['target_kcal']} kcal | {new_proto['target_p']}g Protein")
            st.rerun()

# 11. Top Real-Time Macro Tracker
df_meals = pd.DataFrame(meal_logs)
curr_kcal = int(df_meals["kcal"].sum()) if not df_meals.empty else 0
curr_p = round(float(df_meals["p"].sum()), 1) if not df_meals.empty else 0.0
curr_c = round(float(df_meals["c"].sum()), 1) if not df_meals.empty else 0.0
curr_f = round(float(df_meals["f"].sum()), 1) if not df_meals.empty else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Calories", f"{curr_kcal} kcal", f"{prof.get('target_kcal', 2000) - curr_kcal} remaining", delta_color="inverse")
col2.metric("Protein", f"{curr_p} g", f"{round(prof.get('target_p', 140) - curr_p, 1)}g to goal")
col3.metric("Carbs", f"{curr_c} g", f"Target: {prof.get('target_c', 220)}g")
col4.metric("Fats", f"{curr_f} g", f"Target: {prof.get('target_f', 55)}g")

# Interactive Progress Bars
p_target = max(1, prof.get('target_p', 140))
k_target = max(1, prof.get('target_kcal', 2000))
p_prog = min(1.0, max(0.0, curr_p / p_target))
k_prog = min(1.0, max(0.0, curr_kcal / k_target))

c_prog1, c_prog2 = st.columns(2)
with c_prog1:
    st.caption(f"Protein Progress: {int(p_prog*100)}% ({curr_p}g / {p_target}g)")
    st.progress(p_prog)
with c_prog2:
    st.caption(f"Calorie Burn/Budget: {int(k_prog*100)}% ({curr_kcal} / {k_target} kcal)")
    st.progress(k_prog)

st.write("---")

# 12. Smart Diet Recommendation Engine (Veg, Vegan, Eggetarian, Non-Veg)
st.subheader("🥗 Smart Indian Diet & Budget Recommendation Engine")
st.markdown("*Select your exact diet philosophy and budget tier to load tailored Indian meal options that match your daily protein needs.*")

col_d1, col_d2, col_d3 = st.columns(3)
with col_d1:
    sel_diet = st.selectbox("Diet Type:", ["Pure Veg", "Vegan", "Eggetarian", "Non-Veg", "Both / Flexitarian"], key=f"rec_diet_{u_id}")
with col_d2:
    sel_budget = st.selectbox("Budget Tier:", ["Low Budget", "Medium Budget", "Premium Budget"], key=f"rec_budget_{u_id}")
with col_d3:
    sel_allergy = st.selectbox("Dairy / Allergies:", ["Regular (Dairy OK)", "Lactose-Free (No Milk/Paneer)", "Nut-Free"], key=f"rec_allergy_{u_id}")

suggested_items = FOOD_LIBRARY.get(sel_diet, FOOD_LIBRARY["Pure Veg"]).get(sel_budget, [])
if sel_allergy == "Lactose-Free (No Milk/Paneer)":
    suggested_items = [item for item in suggested_items if "Paneer" not in item["item"] and "Curd" not in item["item"]]

cols_rec = st.columns(len(suggested_items) if suggested_items else 1)
for idx, food in enumerate(suggested_items):
    with cols_rec[idx]:
        st.markdown(f"""
        <div class="diet-card">
            <span style="color: #3B82F6; font-size: 11px; font-weight: bold; text-transform: uppercase;">{food['type']}</span>
            <div style="font-weight: 800; font-size: 14px; margin-top: 4px; color: #FFFFFF;">{food['item']}</div>
            <div style="color: #94A3B8; font-size: 12px; margin-bottom: 8px;">Portion: <b>{food['portion']}</b> | Est. Cost: <b style="color: #10B981;">{food['cost']}</b></div>
            <div style="font-size: 13px; color: #E2E8F0;">
                🥩 <b>{food['p']}g</b> Protein<br>
                🍚 <b>{food['c']}g</b> Carbs<br>
                🥑 <b>{food['f']}g</b> Fats<br>
                ⚡ <b>{food['kcal']}</b> kcal
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button("+ Log This Meal", key=f"quick_log_{u_id}_{idx}", use_container_width=True):
            meal_logs.insert(0, {
                "item": f"{food['item']} ({food['portion']})",
                "grams": 150,
                "kcal": food['kcal'],
                "p": food['p'],
                "c": food['c'],
                "f": food['f'],
                "source": f"{sel_diet} Budget Recommendation",
                "time": datetime.now().strftime("%I:%M %p")
            })
            sync_user_data(st.session_state.auth_user, prof, meal_logs, workout_logs)
            st.success(f"Logged {food['item']}!")
            st.rerun()

st.write("---")

# 13. Dual Workstation (Food Scanner & Clinical OCR Scanner)
left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.subheader("📸 Smart Meal AI Vision & Prompt")
    tab_text, tab_photo = st.tabs(["⚡ Direct Text Prompt", "📷 Plate / Label Scanner"])
    
    with tab_text:
        meal_input = st.text_input("Enter meal with quantities:", placeholder="e.g., 70g dry soya chunks with 100g curd, 4 boiled eggs", key=f"text_meal_{u_id}")
        if st.button("Log Food Entry", type="primary", use_container_width=True, key=f"btn_log_meal_{u_id}"):
            if meal_input:
                with st.spinner("Calculating macros..."):
                    result = analyze_nutrition_ai(user_text=meal_input, key=API_KEY)
                    if result:
                        meal_logs.insert(0, result)
                        sync_user_data(st.session_state.auth_user, prof, meal_logs, workout_logs)
                        st.success(f"✅ Logged: {result['item']} ({result['p']}g Protein, {result['kcal']} kcal)")
                        st.rerun()

    with tab_photo:
        uploaded_food = st.file_uploader("Upload meal plate or packaged label:", type=["jpg", "png", "jpeg"], key=f"food_uploader_{u_id}")
        if uploaded_food:
            f_img = Image.open(uploaded_food)
            st.image(f_img, caption="Meal Preview", use_container_width=True)
            if st.button("⚡ Scan Meal Macros", type="primary", use_container_width=True, key=f"btn_scan_food_{u_id}"):
                with st.spinner("Analyzing portion scale & ingredients..."):
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
        if st.button("Clear Meal Log", key=f"clear_meals_{u_id}"):
            sync_user_data(st.session_state.auth_user, prof, [], workout_logs)
            st.rerun()
    else:
        st.info("No meals logged yet today.")

with right_col:
    st.subheader("🏋️ Clinical Body Composition & Training OS")
    tab_inbody, tab_workout = st.tabs(["📄 Scan InBody Printout", "📝 Workout Log"])
    
    with tab_inbody:
        st.markdown("#### Upload Gym InBody / DEXA Sheet")
        inbody_file = st.file_uploader("Upload high-res photo of your InBody report:", type=["jpg", "png", "jpeg"], key=f"inbody_uploader_{u_id}")
        if inbody_file:
            in_img = Image.open(inbody_file)
            st.image(in_img, caption="InBody Report Preview", width=260)
            if st.button("⚡ Run InBody Clinical OCR Scan", type="primary", use_container_width=True, key=f"btn_ocr_{u_id}"):
                with st.spinner("AI OCR reading clinical printout metrics..."):
                    in_data = analyze_inbody_sheet_ai(in_img, API_KEY)
                    if in_data:
                        # Extract clinical parameters
                        w_val = in_data.get("weight_kg", prof.get("weight_kg", 70.0))
                        h_val = in_data.get("height_cm", prof.get("height_cm", 170.0))
                        age_val = in_data.get("age", prof.get("age", 25))
                        gender_val = in_data.get("gender", prof.get("gender", "Male"))
                        pbf_val = in_data.get("body_fat_pct", prof.get("body_fat_pct", 20.0))
                        ffm_val = in_data.get("fat_free_mass_kg", prof.get("lean_mass_kg"))
                        smm_val = in_data.get("smm_kg", 30.0)
                        v_fat = in_data.get("visceral_fat_level", 8)
                        score_val = in_data.get("inbody_score", 70)
                        
                        # Recompute metabolic targets with updated profile
                        updated_proto = compute_clinical_metabolic_protocol(
                            w_val, h_val, age_val, gender_val, prof.get("activity", "Moderate Active (Gym 3-5 days/week)"), prof.get("goal", "Body Recomposition (Build Muscle & Burn Fat)"), pbf_val, ffm_val
                        )
                        
                        # Overwrite athlete profile with extracted values
                        prof.update({
                            "weight_kg": w_val,
                            "height_cm": h_val,
                            "age": age_val,
                            "gender": gender_val,
                            "smm_kg": smm_val,
                            "visceral_fat_level": v_fat,
                            "inbody_score": score_val,
                            "assessment_notes": in_data.get("diagnostic_summary", "Clinical InBody report synchronized."),
                            **updated_proto
                        })
                        
                        sync_user_data(st.session_state.auth_user, prof, meal_logs, workout_logs)
                        st.success("✅ Profile & Clinical Targets Synchronized with InBody Printout!")
                        st.rerun()

        if prof.get("inbody_score"):
            st.markdown(f"> **InBody Score:** `{prof.get('inbody_score')}/100` | **Visceral Fat:** `Level {prof.get('visceral_fat_level')}` | **SMM:** `{prof.get('smm_kg')}kg`")

    with tab_workout:
        st.markdown("#### Log Training Set")
        w_split = st.selectbox("Split:", ["Push (Chest/Delts/Triceps)", "Pull (Back/Biceps)", "Legs (Quads/Hamstrings)", "Upper / Lower", "Full Body"], key=f"w_split_{u_id}")
        c_w1, c_w2 = st.columns(2)
        with c_w1:
            ex_name = st.text_input("Exercise Name:", placeholder="e.g., Incline DB Press", key=f"w_ex_{u_id}")
            sets_val = st.number_input("Sets:", min_value=1, max_value=20, value=3, key=f"w_sets_{u_id}")
        with c_w2:
            weight_val = st.number_input("Weight (kg):", min_value=0.0, max_value=500.0, value=20.0, step=2.5, key=f"w_wt_{u_id}")
            reps_val = st.number_input("Reps:", min_value=1, max_value=100, value=10, key=f"w_reps_{u_id}")
            
        rpe_val = st.slider("Intensity (RPE Scale 1-10):", min_value=5.0, max_value=10.0, value=8.5, step=0.5, key=f"w_rpe_{u_id}")
        
        if st.button("⚡ Save Workout Log", type="primary", use_container_width=True, key=f"btn_save_w_{u_id}"):
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
            if st.button("Clear Workout Logs", key=f"clear_w_{u_id}"):
                sync_user_data(st.session_state.auth_user, prof, meal_logs, [])
                st.rerun()
        else:
            st.info("No workout sets logged yet today.")

st.write("---")

# 14. Executive Client Export
st.subheader("📄 Client Executive Export")
pdf_col1, pdf_col2 = st.columns([2, 1])
with pdf_col1:
    st.write("Download your official, confidential KSP Metabolic Audit PDF containing your exact calorie target, clinical InBody metrics, logged meals, and workout performance.")
with pdf_col2:
    pdf_bytes = build_pdf_report(prof, meal_logs, workout_logs)
    st.download_button(
        label="📥 Download My Fitness Audit (PDF)",
        data=pdf_bytes,
        file_name=f"KSP_Fitness_Audit_{prof.get('name', 'Athlete')}_{datetime.now().strftime('%Y%m%d')}.pdf",
        mime="application/pdf",
        type="primary",
        use_container_width=True,
        key=f"btn_dl_pdf_{u_id}"
    )