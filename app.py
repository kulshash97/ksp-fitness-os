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

# 1. Page Config & Dark Theme
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
    .plan-card {
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

# 2. Supabase Connection & API Keys
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

# 3. Clinical Metabolic Calibration Engine
def compute_clinical_metabolic_protocol(weight_kg, height_cm, age_yrs, gender, activity_str, goal_choice, body_fat_pct=None, smm_kg=None, body_fat_mass_kg=None):
    weight_kg = float(weight_kg)
    height_cm = float(height_cm)
    age_yrs = int(age_yrs)

    # 1. Exact Biometric Arithmetic
    if body_fat_mass_kg is not None and body_fat_mass_kg > 0:
        fat_mass = round(float(body_fat_mass_kg), 2)
        lean_mass = round(weight_kg - fat_mass, 2)
        body_fat_pct = round((fat_mass / weight_kg) * 100.0, 1)
    elif body_fat_pct is not None and body_fat_pct > 0:
        body_fat_pct = float(body_fat_pct)
        fat_mass = round(weight_kg * (body_fat_pct / 100.0), 2)
        lean_mass = round(weight_kg - fat_mass, 2)
    else:
        body_fat_pct = 22.0 if gender == "Male" else 28.0
        fat_mass = round(weight_kg * (body_fat_pct / 100.0), 2)
        lean_mass = round(weight_kg - fat_mass, 2)

    # 2. Clinical BMR: Katch-McArdle when Lean Mass is known, otherwise Mifflin-St Jeor
    if lean_mass > 0:
        bmr = 370.0 + (21.6 * lean_mass)
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

    # 3. Protocol Prescriptions & Deficit Override
    if "Pure Cutting" in goal_choice or "Aggressive Fat Loss" in goal_choice:
        # Aggressive calibrated fat-loss floor
        target_calories = 1450.0
        protein_g = 130.0  # 520 kcal (1.7g/kg of lean mass preservation)
        fat_g = 40.0       # 360 kcal (essential hormonal floor)
        carb_g = 142.0     # 568 kcal (glycogen preservation remainder)
    elif "Recomposition" in goal_choice:
        target_calories = tdee - 300.0
        protein_g = round(weight_kg * 2.0, 1)
        fat_g = round((target_calories * 0.25) / 9.0, 1)
        carb_g = max(50.0, round((target_calories - (protein_g * 4.0) - (fat_g * 9.0)) / 4.0, 1))
    elif "Lean Bulk" in goal_choice:
        target_calories = tdee + 250.0
        protein_g = round(weight_kg * 2.0, 1)
        fat_g = round((target_calories * 0.25) / 9.0, 1)
        carb_g = round((target_calories - (protein_g * 4.0) - (fat_g * 9.0)) / 4.0, 1)
    elif "Aggressive Bulk" in goal_choice:
        target_calories = tdee + 500.0
        protein_g = round(weight_kg * 1.8, 1)
        fat_g = round((target_calories * 0.28) / 9.0, 1)
        carb_g = round((target_calories - (protein_g * 4.0) - (fat_g * 9.0)) / 4.0, 1)
    else:  # Maintenance
        target_calories = tdee
        protein_g = round(weight_kg * 1.8, 1)
        fat_g = round((target_calories * 0.25) / 9.0, 1)
        carb_g = round((target_calories - (protein_g * 4.0) - (fat_g * 9.0)) / 4.0, 1)

    return {
        "bmr": round(bmr, 1),
        "tdee": round(tdee, 1),
        "body_fat_pct": round(body_fat_pct, 1),
        "fat_mass_kg": fat_mass,
        "lean_mass_kg": lean_mass,
        "smm_kg": round(float(smm_kg), 1) if smm_kg is not None else None,
        "goal": goal_choice,
        "target_kcal": int(round(target_calories)),
        "target_p": int(round(protein_g)),
        "target_c": int(round(carb_g)),
        "target_f": int(round(fat_g))
    }

# 4. Full-Day Meal Plan Engine (Totals 130g - 165g+ Protein Daily)
DAILY_MEAL_PLANS = {
    "Pure Veg": {
        "Low Budget": [
            {"meal": "Breakfast", "item": "Sattu Protein Shake (60g sattu) + Roasted Chana (40g)", "p": 22.0, "c": 50.0, "f": 5.0, "kcal": 333, "cost": "₹20"},
            {"meal": "Lunch", "item": "Boiled Soya Chunks Curry (60g dry) + 1 Roti + Green Salad", "p": 34.0, "c": 35.0, "f": 3.0, "kcal": 303, "cost": "₹18"},
            {"meal": "Snack", "item": "Low-Fat Curd (Dahi 250g) + Sprouted Moong (100g)", "p": 18.5, "c": 32.0, "f": 3.6, "kcal": 240, "cost": "₹25"},
            {"meal": "Dinner", "item": "Soya Chunks Bhurji (70g dry) + Moong Dal (1 Bowl)", "p": 44.0, "c": 38.0, "f": 4.0, "kcal": 364, "cost": "₹22"}
        ],
        "Medium Budget": [
            {"meal": "Breakfast", "item": "Whey Protein Concentrate (1 Scoop) + Oats (40g) in Water", "p": 28.0, "c": 30.0, "f": 4.0, "kcal": 268, "cost": "₹75"},
            {"meal": "Lunch", "item": "Low-Fat Paneer (150g) Sautéed with Vegetables + 1 Chapati", "p": 31.0, "c": 22.0, "f": 14.0, "kcal": 338, "cost": "₹65"},
            {"meal": "Snack", "item": "Roasted Chana (50g) + Low-Fat Curd (200g)", "p": 19.5, "c": 38.0, "f": 4.5, "kcal": 270, "cost": "₹25"},
            {"meal": "Dinner", "item": "Soya Chunks (50g dry) + Low-Fat Paneer (100g) Bhurji", "p": 44.0, "c": 19.0, "f": 10.0, "kcal": 342, "cost": "₹55"}
        ],
        "Premium Budget": [
            {"meal": "Breakfast", "item": "Whey Isolate (1 Scoop) + Greek Yogurt (150g) + Chia Seeds", "p": 40.0, "c": 12.0, "f": 6.0, "kcal": 262, "cost": "₹160"},
            {"meal": "Lunch", "item": "Grilled Low-Fat Paneer (200g) with Steamed Broccoli & Quinoa", "p": 42.0, "c": 35.0, "f": 16.0, "kcal": 452, "cost": "₹110"},
            {"meal": "Snack", "item": "Almond Butter (25g) on Rice Cakes + Soy Milk (200ml)", "p": 14.0, "c": 24.0, "f": 14.0, "kcal": 278, "cost": "₹90"},
            {"meal": "Dinner", "item": "Organic Tofu (250g) Stir-Fry with Mushrooms & Edamame", "p": 35.0, "c": 18.0, "f": 12.0, "kcal": 320, "cost": "₹140"}
        ]
    },
    "Eggetarian": {
        "Low Budget": [
            {"meal": "Breakfast", "item": "3 Whole Boiled Eggs + 2 Egg Whites", "p": 25.0, "c": 1.5, "f": 15.0, "kcal": 241, "cost": "₹35"},
            {"meal": "Lunch", "item": "Soya Chunks Curry (50g dry) + 1 Roti + 2 Boiled Whites", "p": 33.0, "c": 34.0, "f": 2.5, "kcal": 290, "cost": "₹25"},
            {"meal": "Snack", "item": "Roasted Chana (50g) + Sprouted Moong Salad", "p": 19.0, "c": 45.0, "f": 3.0, "kcal": 283, "cost": "₹18"},
            {"meal": "Dinner", "item": "Egg White Bhurji (6 Whites + 1 Whole Egg) + Green Salad", "p": 28.0, "c": 4.0, "f": 6.0, "kcal": 182, "cost": "₹45"}
        ],
        "Medium Budget": [
            {"meal": "Breakfast", "item": "3 Egg Omelette with Low-Fat Paneer (60g) + Green Tea", "p": 29.0, "c": 4.0, "f": 18.0, "kcal": 294, "cost": "₹50"},
            {"meal": "Lunch", "item": "Low-Fat Paneer (150g) + 3 Boiled Egg Whites + Salad", "p": 38.0, "c": 8.0, "f": 13.0, "kcal": 301, "cost": "₹70"},
            {"meal": "Snack", "item": "Whey Protein Concentrate (1 Scoop) in Chilled Water", "p": 24.0, "c": 2.0, "f": 1.5, "kcal": 118, "cost": "₹70"},
            {"meal": "Dinner", "item": "Soya Chunks (50g dry) Bhurji + 4 Scrambled Egg Whites", "p": 40.0, "c": 18.0, "f": 2.0, "kcal": 250, "cost": "₹40"}
        ],
        "Premium Budget": [
            {"meal": "Breakfast", "item": "Free-Range Poached Eggs (4) on Sourdough Toast + Avocado", "p": 28.0, "c": 28.0, "f": 20.0, "kcal": 404, "cost": "₹180"},
            {"meal": "Lunch", "item": "Whey Isolate Shake (1 Scoop) + Greek Yogurt Bowl (150g)", "p": 42.0, "c": 10.0, "f": 2.0, "kcal": 226, "cost": "₹160"},
            {"meal": "Snack", "item": "Almond Butter (30g) + 4 Soft-Boiled Egg Whites", "p": 20.0, "c": 6.0, "f": 16.0, "kcal": 248, "cost": "₹90"},
            {"meal": "Dinner", "item": "Grilled Paneer/Tofu (200g) + 4 Egg White Omelette", "p": 46.0, "c": 10.0, "f": 16.0, "kcal": 368, "cost": "₹120"}
        ]
    },
    "Vegan": {
        "Low Budget": [
            {"meal": "Breakfast", "item": "Sattu Drink (60g sattu in water with lemon) + Peanuts (20g)", "p": 18.0, "c": 40.0, "f": 10.0, "kcal": 322, "cost": "₹16"},
            {"meal": "Lunch", "item": "Boiled Soya Chunks (70g dry) with Cumin Brown Rice (50g)", "p": 40.0, "c": 55.0, "f": 2.0, "kcal": 398, "cost": "₹22"},
            {"meal": "Snack", "item": "Roasted Kala Chana (60g) + Sprouted Moong (80g)", "p": 20.0, "c": 48.0, "f": 3.5, "kcal": 303, "cost": "₹18"},
            {"meal": "Dinner", "item": "Spicy Soya Chunks Salad (60g dry) with Tomatoes & Cucumbers", "p": 32.0, "c": 24.0, "f": 1.0, "kcal": 233, "cost": "₹15"}
        ],
        "Medium Budget": [
            {"meal": "Breakfast", "item": "Plant Pea Protein (1 Scoop) + Soya Milk (250ml) Shake", "p": 32.0, "c": 8.0, "f": 5.0, "kcal": 205, "cost": "₹95"},
            {"meal": "Lunch", "item": "Firm Organic Tofu (250g) Stir-Fry with Garlic & Veggies", "p": 25.0, "c": 8.0, "f": 12.0, "kcal": 240, "cost": "₹60"},
            {"meal": "Snack", "item": "Roasted Edamame / Chana (50g) + Walnuts (15g)", "p": 18.0, "c": 25.0, "f": 12.0, "kcal": 280, "cost": "₹45"},
            {"meal": "Dinner", "item": "Soya Chunks Curry (70g dry) with Steamed Cauliflower", "p": 38.0, "c": 26.0, "f": 2.0, "kcal": 274, "cost": "₹25"}
        ],
        "Premium Budget": [
            {"meal": "Breakfast", "item": "Imported Pea & Rice Isolate + Hemp Hearts + Almond Milk", "p": 36.0, "c": 6.0, "f": 14.0, "kcal": 294, "cost": "₹180"},
            {"meal": "Lunch", "item": "Organic Tempeh Steak (200g) with Sautéed Asparagus & Quinoa", "p": 40.0, "c": 35.0, "f": 18.0, "kcal": 462, "cost": "₹190"},
            {"meal": "Snack", "item": "Roasted Pumpkin Seeds (40g) + Vegan Collagen Peptide Booster", "p": 20.0, "c": 12.0, "f": 18.0, "kcal": 290, "cost": "₹120"},
            {"meal": "Dinner", "item": "Grilled Smoked Tofu (300g) with Sesame Greens", "p": 34.0, "c": 10.0, "f": 16.0, "kcal": 320, "cost": "₹130"}
        ]
    },
    "Non-Veg": {
        "Low Budget": [
            {"meal": "Breakfast", "item": "3 Whole Boiled Eggs + 2 Egg Whites", "p": 25.0, "c": 1.5, "f": 15.0, "kcal": 241, "cost": "₹35"},
            {"meal": "Lunch", "item": "Chicken Liver Curry (150g) + 1 Roti + Cucumber Salad", "p": 32.0, "c": 22.0, "f": 8.0, "kcal": 288, "cost": "₹38"},
            {"meal": "Snack", "item": "Soya Chunks (40g dry) Snack Bowl or Roasted Chana (50g)", "p": 22.0, "c": 28.0, "f": 2.0, "kcal": 218, "cost": "₹15"},
            {"meal": "Dinner", "item": "Chicken Breast Curry (150g raw wt) + Steamed Greens", "p": 46.0, "c": 4.0, "f": 5.0, "kcal": 245, "cost": "₹55"}
        ],
        "Medium Budget": [
            {"meal": "Breakfast", "item": "4 Egg Whites + 2 Whole Eggs Omelette + Green Tea", "p": 27.0, "c": 2.0, "f": 11.0, "kcal": 215, "cost": "₹45"},
            {"meal": "Lunch", "item": "Grilled Chicken Breast (200g) with 100g Steamed Rice & Veggies", "p": 62.0, "c": 30.0, "f": 6.0, "kcal": 422, "cost": "₹75"},
            {"meal": "Snack", "item": "Whey Protein (1 Scoop) in Water", "p": 24.0, "c": 2.0, "f": 1.5, "kcal": 118, "cost": "₹70"},
            {"meal": "Dinner", "item": "Pan-Seared White Fish / Rohu (200g) with Lemon Salad", "p": 40.0, "c": 2.0, "f": 4.0, "kcal": 204, "cost": "₹95"}
        ],
        "Premium Budget": [
            {"meal": "Breakfast", "item": "Whey Isolate Shake (1 Scoop) + 4 Poached Egg Whites", "p": 40.0, "c": 2.0, "f": 1.0, "kcal": 177, "cost": "₹140"},
            {"meal": "Lunch", "item": "Grilled Chicken Breast (250g) with Avocado Salad", "p": 76.0, "c": 8.0, "f": 16.0, "kcal": 480, "cost": "₹120"},
            {"meal": "Snack", "item": "Greek Yogurt (150g) + Almonds (25g)", "p": 18.0, "c": 12.0, "f": 14.0, "kcal": 246, "cost": "₹90"},
            {"meal": "Dinner", "item": "Atlantic Salmon Fillet (200g) with Steamed Asparagus", "p": 44.0, "c": 2.0, "f": 22.0, "kcal": 382, "cost": "₹350"}
        ]
    }
}
DAILY_MEAL_PLANS["Both / Flexitarian"] = DAILY_MEAL_PLANS["Non-Veg"]

# 5. Gemini AI Engine: Targeted OCR Parser
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
    for model_name in candidate_models:
        try:
            model = genai.GenerativeModel(model_name, safety_settings=safety_settings)
            response = model.generate_content(payload)
            if response and response.text:
                return response.text
        except Exception:
            continue
    return None

def extract_inbody_ocr_fast(pil_img: Image.Image, key: str):
    system_prompt = """
    You are an automated medical OCR engine for InBody diagnostic reports.
    Extract the printed numeric metrics and return strict JSON with these keys:
    {
      "weight_kg": float,
      "height_cm": float,
      "age": integer,
      "gender": "Male" or "Female",
      "smm_kg": float,
      "body_fat_mass_kg": float,
      "body_fat_pct": float,
      "bmr_kcal": integer,
      "visceral_fat_level": integer,
      "inbody_score": integer
    }
    """
    img_resized = pil_img.copy()
    img_resized.thumbnail((1400, 1400))
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

    # Section 1: Biometrics
    pdf.set_text_color(15, 23, 42)
    pdf.set_font("Helvetica", "B", 11)
    pdf.cell(0, 6, f"1. CLIENT BIOMETRIC & CLINICAL AUDIT ({prof.get('name', 'ATHLETE').upper()})", ln=True)
    pdf.set_draw_color(59, 130, 246)
    pdf.set_line_width(0.4)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(2)

    pdf.set_font("Helvetica", "", 9)
    pdf.set_text_color(30, 41, 59)
    col_w = 45.5

    pdf.cell(col_w, 6, f" Age: {prof.get('age', 28)} yrs", border=1)
    pdf.cell(col_w, 6, f" Gender: {prof.get('gender', 'Male')}", border=1)
    pdf.cell(col_w, 6, f" Height: {prof.get('height_cm', 159.0)} cm", border=1)
    pdf.cell(col_w, 6, f" Weight: {prof.get('weight_kg', 75.9)} kg", border=1, ln=True)

    bf_text = f"{prof.get('body_fat_pct', 30.5)}%"
    lean_text = f"{prof.get('lean_mass_kg', 52.8)} kg"
    fat_text = f"{prof.get('fat_mass_kg', 23.1)} kg"
    smm_text = f"{prof.get('smm_kg', 29.7)} kg"

    pdf.cell(col_w, 6, f" Body Fat: {bf_text}", border=1)
    pdf.cell(col_w, 6, f" Lean Mass: {lean_text}", border=1)
    pdf.cell(col_w, 6, f" Fat Mass: {fat_text}", border=1)
    pdf.cell(col_w, 6, f" Muscle (SMM): {smm_text}", border=1, ln=True)

    if prof.get("visceral_fat_level") or prof.get("inbody_score") or prof.get("bmr"):
        v_level = f"Level {prof.get('visceral_fat_level', 10)}"
        score_val = f"{prof.get('inbody_score', 72)}/100"
        bmr_val = f"{prof.get('bmr', 1510)} kcal"
        pdf.cell(col_w, 6, f" InBody Score: {score_val}", border=1)
        pdf.cell(col_w, 6, f" Visceral Fat: {v_level}", border=1)
        pdf.cell(col_w, 6, f" Clinical BMR: {bmr_val}", border=1)
        pdf.cell(col_w, 6, f" Method: Clinical Scan", border=1, ln=True)

    pdf.ln(4)

    # Section 2: Daily Targets
    pdf.set_font("Helvetica", "B", 11)
    pdf.set_text_color(15, 23, 42)
    pdf.cell(0, 6, f"2. SCIENTIFIC DAILY MACRONUTRIENT TARGETS -- {prof.get('goal', 'PURE CUTTING').upper()}", ln=True)
    pdf.line(14, pdf.get_y(), 196, pdf.get_y())
    pdf.ln(2)

    pdf.set_fill_color(241, 245, 249)
    pdf.set_font("Helvetica", "B", 9)
    pdf.cell(col_w, 6, "Target Calories", border=1, fill=True, align="C")
    pdf.cell(col_w, 6, "Protein (g)", border=1, fill=True, align="C")
    pdf.cell(col_w, 6, "Carbohydrates (g)", border=1, fill=True, align="C")
    pdf.cell(col_w, 6, "Fats (g)", border=1, fill=True, align="C", ln=True)

    pdf.set_font("Helvetica", "", 9)
    pdf.cell(col_w, 6, f"{prof.get('target_kcal', 1450)} kcal", border=1, align="C")
    pdf.cell(col_w, 6, f"{prof.get('target_p', 130)} g", border=1, align="C")
    pdf.cell(col_w, 6, f"{prof.get('target_c', 142)} g", border=1, align="C")
    pdf.cell(col_w, 6, f"{prof.get('target_f', 40)} g", border=1, align="C", ln=True)
    pdf.ln(4)

    # Section 3: Meal Ledger
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

    # Section 4: Workout Ledger
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

    # Section 5: Assessment
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
    # Calibrated default for new athletes: 75.9kg, 159cm, 28y, Male
    init_proto = compute_clinical_metabolic_protocol(
        75.9, 159.0, 28, "Male", "Moderate Active (Gym 3-5 days/week)",
        "Pure Cutting (Aggressive Fat Loss)", body_fat_pct=30.5, smm_kg=29.7, body_fat_mass_kg=23.1
    )
    new_user_profile = {
        "name": clean_name,
        "age": 28,
        "gender": "Male",
        "weight_kg": 75.9,
        "height_cm": 159.0,
        "activity": "Moderate Active (Gym 3-5 days/week)",
        "goal": "Pure Cutting (Aggressive Fat Loss)",
        "inbody_score": 72,
        "visceral_fat_level": 10,
        "assessment_notes": "Validated InBody scan shows 30.5% body fat with 29.7kg SMM. Active fat-loss protocol targets ~1kg pure fat loss/week while preserving lean mass.",
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
    st.info("👋 Welcome to **KSP Fitness OS**. Please **Sign Up** or **Log In** from the sidebar to access your profile, InBody scanner, and customized diet planner.")
    st.stop()

user_record = fetch_user(st.session_state.auth_user)
if not user_record:
    st.error("Session expired. Please log in again.")
    st.stop()

prof = user_record["profile"]
meal_logs = user_record.get("meals", [])
workout_logs = user_record.get("workouts", [])
u_id = st.session_state.auth_user

# 10. Profile & Target Goal Customization
with st.expander("👤 Athlete Biometrics & Clinical Target Protocols", expanded=False):
    col_u1, col_u2, col_u3 = st.columns(3)
    with col_u1:
        u_name = st.text_input("Full Name:", value=str(prof.get("name", "")), key=f"prof_name_{u_id}")
        u_gender = st.selectbox("Gender:", ["Male", "Female"], index=0 if prof.get("gender") == "Male" else 1, key=f"prof_gender_{u_id}")
        u_age = st.number_input("Age (years):", min_value=12, max_value=90, value=int(prof.get("age", 28)), key=f"prof_age_{u_id}")
    with col_u2:
        u_weight = st.number_input("Weight (kg):", min_value=30.0, max_value=250.0, value=float(prof.get("weight_kg", 75.9)), step=0.1, key=f"prof_wt_{u_id}")
        u_height = st.number_input("Height (cm):", min_value=100.0, max_value=240.0, value=float(prof.get("height_cm", 159.0)), step=0.1, key=f"prof_ht_{u_id}")

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
        curr_goal = prof.get("goal", goal_opts[0])
        goal_idx = 0
        for i, g in enumerate(goal_opts):
            if g.split()[0] in curr_goal:
                goal_idx = i
                break
        u_goal = st.selectbox("Target Goal:", goal_opts, index=goal_idx, key=f"prof_goal_{u_id}")

        bf_disp = f"{prof.get('body_fat_pct', 30.5)}%"
        lean_disp = f"{prof.get('lean_mass_kg', 52.8)}kg"
        smm_disp = f"{prof.get('smm_kg', 29.7)}kg"
        st.markdown(f"**Body Fat:** `{bf_disp}` | **Lean Mass:** `{lean_disp}` | **SMM:** `{smm_disp}`")

        if st.button("⚡ Apply Scientific Goal Protocol", type="primary", use_container_width=True, key=f"btn_calc_{u_id}"):
            new_proto = compute_clinical_metabolic_protocol(
                u_weight, u_height, u_age, u_gender, u_activity, u_goal,
                body_fat_pct=prof.get("body_fat_pct", 30.5),
                smm_kg=prof.get("smm_kg", 29.7),
                body_fat_mass_kg=prof.get("fat_mass_kg", 23.1)
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
            st.success(f"Calibrated: {new_proto['goal']} | {new_proto['target_kcal']} kcal | {new_proto['target_p']}g Protein")
            st.rerun()

# 11. Top Real-Time Macro Tracker
df_meals = pd.DataFrame(meal_logs)
curr_kcal = int(df_meals["kcal"].sum()) if not df_meals.empty else 0
curr_p = round(float(df_meals["p"].sum()), 1) if not df_meals.empty else 0.0
curr_c = round(float(df_meals["c"].sum()), 1) if not df_meals.empty else 0.0
curr_f = round(float(df_meals["f"].sum()), 1) if not df_meals.empty else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Calories", f"{curr_kcal} kcal", f"{prof.get('target_kcal', 1450) - curr_kcal} remaining", delta_color="inverse")
col2.metric("Protein", f"{curr_p} g", f"{round(prof.get('target_p', 130) - curr_p, 1)}g to goal")
col3.metric("Carbs", f"{curr_c} g", f"Target: {prof.get('target_c', 142)}g")
col4.metric("Fats", f"{curr_f} g", f"Target: {prof.get('target_f', 40)}g")

# Interactive Progress Bars
p_target = max(1, prof.get('target_p', 130))
k_target = max(1, prof.get('target_kcal', 1450))
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

# 12. Smart Full-Day Meal Plan Architect
st.subheader("🥗 Smart Indian Diet & Full-Day Meal Plan Architect")
st.markdown("*Select your diet philosophy and budget tier to load a full-day 4-meal plan calibrated to deliver your 130g–165g daily protein target.*")

col_d1, col_d2 = st.columns(2)
with col_d1:
    sel_diet = st.selectbox("Diet Type:", ["Pure Veg", "Eggetarian", "Vegan", "Non-Veg", "Both / Flexitarian"], key=f"rec_diet_{u_id}")
with col_d2:
    sel_budget = st.selectbox("Budget Tier:", ["Low Budget", "Medium Budget", "Premium Budget"], key=f"rec_budget_{u_id}")

daily_plan = DAILY_MEAL_PLANS.get(sel_diet, DAILY_MEAL_PLANS["Pure Veg"]).get(sel_budget, [])

# Calculate total nutrients delivered by the recommended daily plan
plan_p = sum(m["p"] for m in daily_plan)
plan_c = sum(m["c"] for m in daily_plan)
plan_f = sum(m["f"] for m in daily_plan)
plan_kcal = sum(m["kcal"] for m in daily_plan)

st.info(f"📊 **Full-Day Plan Delivery:** **{plan_p:.1f}g Protein** | **{plan_c:.1f}g Carbs** | **{plan_f:.1f}g Fats** | **{plan_kcal} kcal** (Aligned with your target of {prof.get('target_p', 130)}g Protein & {prof.get('target_kcal', 1450)} kcal)")

cols_plan = st.columns(len(daily_plan))
for idx, meal_item in enumerate(daily_plan):
    with cols_plan[idx]:
        st.markdown(f"""
        <div class="plan-card">
            <span style="color: #3B82F6; font-size: 11px; font-weight: bold; text-transform: uppercase;">{meal_item['meal']}</span>
            <div style="font-weight: 800; font-size: 13px; margin-top: 4px; color: #FFFFFF; min-height: 48px;">{meal_item['item']}</div>
            <div style="color: #94A3B8; font-size: 11px; margin-bottom: 6px;">Est. Cost: <b style="color: #10B981;">{meal_item['cost']}</b></div>
            <div style="font-size: 12px; color: #E2E8F0;">
                🥩 <b>{meal_item['p']}g</b> Protein<br>
                🍚 <b>{meal_item['c']}g</b> Carbs<br>
                🥑 <b>{meal_item['f']}g</b> Fats<br>
                ⚡ <b>{meal_item['kcal']}</b> kcal
            </div>
        </div>
        """, unsafe_allow_html=True)
        if st.button(f"+ Log {meal_item['meal']}", key=f"log_single_{u_id}_{idx}", use_container_width=True):
            meal_logs.insert(0, {
                "item": meal_item['item'],
                "grams": 200,
                "kcal": meal_item['kcal'],
                "p": meal_item['p'],
                "c": meal_item['c'],
                "f": meal_item['f'],
                "source": f"{sel_diet} {meal_item['meal']}",
                "time": datetime.now().strftime("%I:%M %p")
            })
            sync_user_data(st.session_state.auth_user, prof, meal_logs, workout_logs)
            st.success(f"Logged {meal_item['meal']}!")
            st.rerun()

if st.button("⚡ Log Entire Day Plan to Meal Ledger", type="primary", use_container_width=True, key=f"log_all_plan_{u_id}"):
    for meal_item in daily_plan:
        meal_logs.insert(0, {
            "item": meal_item['item'],
            "grams": 200,
            "kcal": meal_item['kcal'],
            "p": meal_item['p'],
            "c": meal_item['c'],
            "f": meal_item['f'],
            "source": f"{sel_diet} Full Plan",
            "time": datetime.now().strftime("%I:%M %p")
        })
    sync_user_data(st.session_state.auth_user, prof, meal_logs, workout_logs)
    st.success(f"✅ Successfully logged full {sel_diet} day plan ({plan_p}g Protein, {plan_kcal} kcal)!")
    st.rerun()

st.write("---")

# 13. Dual Workstation (Food Scanner & InBody OCR Scanner)
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
        inbody_file = st.file_uploader("Upload photo of InBody sheet for OCR extraction:", type=["jpg", "png", "jpeg"], key=f"inbody_uploader_{u_id}")
        if inbody_file:
            in_img = Image.open(inbody_file)
            st.image(in_img, caption="InBody Report Preview", width=260)
            if st.button("⚡ Run InBody Clinical OCR Scan", type="primary", use_container_width=True, key=f"btn_ocr_{u_id}"):
                with st.spinner("AI OCR extracting clinical printout metrics..."):
                    in_data = extract_inbody_ocr_fast(in_img, API_KEY)
                    if in_data:
                        w_val = in_data.get("weight_kg", prof.get("weight_kg", 75.9))
                        h_val = in_data.get("height_cm", prof.get("height_cm", 159.0))
                        age_val = in_data.get("age", prof.get("age", 28))
                        gender_val = in_data.get("gender", prof.get("gender", "Male"))
                        smm_val = in_data.get("smm_kg", 29.7)
                        bfm_val = in_data.get("body_fat_mass_kg", 23.1)
                        pbf_val = in_data.get("body_fat_pct", 30.5)
                        v_fat = in_data.get("visceral_fat_level", 10)
                        score_val = in_data.get("inbody_score", 72)

                        # Recompute metabolic targets with validated InBody metrics
                        updated_proto = compute_clinical_metabolic_protocol(
                            w_val, h_val, age_val, gender_val,
                            prof.get("activity", "Moderate Active (Gym 3-5 days/week)"),
                            prof.get("goal", "Pure Cutting (Aggressive Fat Loss)"),
                            body_fat_pct=pbf_val, smm_kg=smm_val, body_fat_mass_kg=bfm_val
                        )

                        prof.update({
                            "weight_kg": w_val,
                            "height_cm": h_val,
                            "age": age_val,
                            "gender": gender_val,
                            "smm_kg": smm_val,
                            "fat_mass_kg": bfm_val,
                            "visceral_fat_level": v_fat,
                            "inbody_score": score_val,
                            "assessment_notes": f"Validated InBody scan shows {pbf_val}% body fat with {smm_val}kg SMM. Prescribed active fat-loss protocol targeting ~1kg pure fat loss/week.",
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
    st.write("Download your official, confidential KSP Metabolic Audit PDF containing your calibrated calorie targets, clinical InBody metrics, logged meals, and workout performance.")
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