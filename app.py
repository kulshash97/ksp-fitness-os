import streamlit as st
import pandas as pd
import re
import json
from datetime import datetime
from PIL import Image
from google import genai
from google.genai import types

# 1. Page Configuration & Custom Theme
st.set_page_config(
    page_title="KSP Fitness OS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
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
    <div class="ksp-title">Fitness OS</div>
    <div class="ksp-tagline">Strategy amplified, complexity simplified.</div>
</div>
""", unsafe_allow_html=True)

# 2. Comprehensive Fallback Macro Database (Exact Indian Diet & Fitness Profile)
FOOD_DB = {
    # Beverages & Everyday Items
    "tea": {"kcal": 75, "p": 2.0, "c": 10.0, "f": 2.5, "unit": "1 Cup Indian Chai", "g": 150},
    "chai": {"kcal": 75, "p": 2.0, "c": 10.0, "f": 2.5, "unit": "1 Cup Indian Chai", "g": 150},
    "coffee": {"kcal": 80, "p": 2.2, "c": 11.0, "f": 2.8, "unit": "1 Cup Milk Coffee", "g": 150},
    "black coffee": {"kcal": 5, "p": 0.3, "c": 0.5, "f": 0.0, "unit": "1 Cup Black Coffee", "g": 150},
    "green tea": {"kcal": 2, "p": 0.0, "c": 0.5, "f": 0.0, "unit": "1 Cup Green Tea", "g": 150},
    
    # High Protein Vegetarian Sources
    "pea protein": {"kcal": 135, "p": 26.0, "c": 2.5, "f": 2.0, "unit": "1 Scoop Pea Protein (33g)", "g": 33},
    "whey": {"kcal": 130, "p": 25.0, "c": 3.0, "f": 1.5, "unit": "1 Scoop Whey Protein (33g)", "g": 33},
    "soya chunks": {"kcal": 345, "p": 52.0, "c": 33.0, "f": 0.5, "unit": "Raw Soya Chunks (100g)", "g": 100},
    "soya": {"kcal": 345, "p": 52.0, "c": 33.0, "f": 0.5, "unit": "Raw Soya Chunks (100g)", "g": 100},
    "paneer": {"kcal": 280, "p": 18.0, "c": 4.0, "f": 22.0, "unit": "Standard Paneer (100g)", "g": 100},
    "tofu": {"kcal": 83, "p": 10.0, "c": 2.0, "f": 4.5, "unit": "Soy Tofu (100g)", "g": 100},
    
    # Dals & Legumes (Raw/Dry Basis per 100g)
    "moong dal": {"kcal": 347, "p": 24.0, "c": 59.0, "f": 1.2, "unit": "Raw Moong Dal (100g)", "g": 100},
    "moogdal": {"kcal": 347, "p": 24.0, "c": 59.0, "f": 1.2, "unit": "Raw Moong Dal (100g)", "g": 100},
    "chana": {"kcal": 360, "p": 19.0, "c": 60.0, "f": 5.0, "unit": "Raw Chana / Chickpeas (100g)", "g": 100},
    "rajma": {"kcal": 340, "p": 22.0, "c": 60.0, "f": 1.5, "unit": "Raw Rajma (100g)", "g": 100},
    
    # Dairy & Staples
    "curd": {"kcal": 70, "p": 4.0, "c": 5.0, "f": 4.0, "unit": "Plain Curd / Dahi (100g)", "g": 100},
    "dahi": {"kcal": 70, "p": 4.0, "c": 5.0, "f": 4.0, "unit": "Plain Curd / Dahi (100g)", "g": 100},
    "milk": {"kcal": 65, "p": 3.3, "c": 5.0, "f": 3.8, "unit": "Toned Milk (100ml)", "g": 100},
    "roti": {"kcal": 115, "p": 3.5, "c": 22.0, "f": 1.5, "unit": "1 Whole Wheat Roti", "g": 40},
    "chapati": {"kcal": 115, "p": 3.5, "c": 22.0, "f": 1.5, "unit": "1 Chapati", "g": 40},
    "rice": {"kcal": 350, "p": 7.0, "c": 78.0, "f": 0.6, "unit": "Raw Rice (100g)", "g": 100},
    "oats": {"kcal": 389, "p": 13.5, "c": 66.0, "f": 6.9, "unit": "Rolled Oats (100g)", "g": 100},
}

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

# 3. Sidebar API Key & Goal Settings
with st.sidebar:
    st.markdown("### 🔑 Live AI Parser")
    api_key = st.text_input(
        "Gemini API Key (Recommended):",
        type="password",
        help="Paste a free Google AI Studio key to handle any food spelling, voice transcripts, or meal photos."
    )
    st.markdown("---")
    st.markdown("**Daily Targets:**")
    target_kcal = st.number_input("Daily Kcal Goal", value=2200, step=50)
    target_p = st.number_input("Daily Protein Goal (g)", value=140, step=5)

# 4. Universal Macro Solver (Gemini AI + Smart Local Rulebook)
def calculate_macros(user_text: str, image: Image.Image = None, user_api_key: str = ""):
    # Priority 1: Use Gemini 2.5 Flash if API key is provided
    if user_api_key:
        try:
            client = genai.Client(api_key=user_api_key)
            prompt = """
            You are a precision sports nutrition analyzer specialized in Indian & global diets.
            Analyze the meal input (text or photo) and return STRICT JSON with exact macro estimations.
            
            JSON format:
            {
              "item_name": "Clear clean item name",
              "grams": integer,
              "calories": integer,
              "protein": float,
              "carbs": float,
              "fats": float
            }
            """
            contents = [prompt]
            if user_text:
                contents.append(f"Input description: {user_text}")
            if image:
                contents.append(image)

            response = client.models.generate_content(
                model='gemini-2.5-flash',
                contents=contents,
                config=types.GenerateContentConfig(
                    response_mime_type="application/json"
                )
            )
            data = json.loads(response.text)
            return {
                "item": data.get("item_name", user_text or "Scanned Meal"),
                "grams": int(data.get("grams", 150)),
                "kcal": int(data.get("calories", 100)),
                "p": round(float(data.get("protein", 2.0)), 1),
                "c": round(float(data.get("carbs", 10.0)), 1),
                "f": round(float(data.get("fats", 2.0)), 1),
                "time": datetime.now().strftime("%I:%M %p")
            }
        except Exception as e:
            st.warning(f"AI live scan notice: {str(e)}. Falling back to precision rulebook.")

    # Priority 2: Precision Rulebook for Offline / Direct Text
    clean = (user_text or "custom meal").lower().strip()
    
    # Check count words (e.g., "one", "two", "2", "3")
    count = 1.0
    count_words = {"one": 1, "two": 2, "three": 3, "four": 4, "half": 0.5, "1": 1, "2": 2, "3": 3, "4": 4}
    for word, val in count_words.items():
        if re.search(rf'\b{word}\b', clean):
            count = float(val)
            break

    # Check explicit gram quantities (e.g., "200gm", "100g")
    explicit_grams = None
    g_match = re.search(r'(\d+)\s*(g|gm|gms|gram|grams)', clean)
    if g_match:
        explicit_grams = float(g_match.group(1))

    # Match against food database
    for key, data in FOOD_DB.items():
        if key in clean:
            if explicit_grams:
                mult = explicit_grams / 100.0
                return {
                    "item": f"{int(explicit_grams)}g {data['unit']}",
                    "grams": int(explicit_grams),
                    "kcal": round(data["kcal"] * mult),
                    "p": round(data["p"] * mult, 1),
                    "c": round(data["c"] * mult, 1),
                    "f": round(data["f"] * mult, 1),
                    "time": datetime.now().strftime("%I:%M %p")
                }
            else:
                return {
                    "item": f"{int(count) if count == int(count) else count}x {data['unit']}",
                    "grams": int(data["g"] * count),
                    "kcal": int(data["kcal"] * count),
                    "p": round(data["p"] * count, 1),
                    "c": round(data["c"] * count, 1),
                    "f": round(data["f"] * count, 1),
                    "time": datetime.now().strftime("%I:%M %p")
                }

    # Safe conversational fallback (e.g. snack, beverage, vegetable)
    return {
        "item": user_text.title() if user_text else "Light Snack / Beverage",
        "grams": int(100 * count),
        "kcal": int(90 * count),
        "p": round(2.0 * count, 1),
        "c": round(12.0 * count, 1),
        "f": round(2.5 * count, 1),
        "time": datetime.now().strftime("%I:%M %p")
    }

# 5. Session State
if "logs" not in st.session_state:
    st.session_state.logs = [
        {"item": "100g Plain Curd", "grams": 100, "kcal": 70, "p": 4.0, "c": 5.0, "f": 4.0, "time": "01:15 PM"},
        {"item": "70g Raw Soya Chunks", "grams": 70, "kcal": 242, "p": 36.4, "c": 23.1, "f": 0.4, "time": "01:15 PM"},
    ]

# 6. Dashboard Metrics
df_logs = pd.DataFrame(st.session_state.logs)
curr_kcal = int(df_logs["kcal"].sum()) if not df_logs.empty else 0
curr_p = round(float(df_logs["p"].sum()), 1) if not df_logs.empty else 0.0
curr_c = round(float(df_logs["c"].sum()), 1) if not df_logs.empty else 0.0
curr_f = round(float(df_logs["f"].sum()), 1) if not df_logs.empty else 0.0

col1, col2, col3, col4 = st.columns(4)
col1.metric("Calories", f"{curr_kcal} kcal", f"{target_kcal - curr_kcal} remaining", delta_color="inverse")
col2.metric("Protein", f"{curr_p} g", f"{round(target_p - curr_p, 1)}g to goal")
col3.metric("Carbs", f"{curr_c} g")
col4.metric("Fats", f"{curr_f} g")

st.write("---")

# 7. Two Column Layout
left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.subheader("🥗 Smart Macro & Meal Tracker")
    tab_text, tab_photo = st.tabs(["⚡ Text / Voice / Grams", "📷 Live Photo Scan"])
    
    with tab_text:
        meal_input = st.text_input(
            "Describe meal with quantities:",
            placeholder="e.g., one medium cup of tea, one scoop of pea protein, 200gm moong dal"
        )
        if st.button("Log & Calculate Macros", type="primary", use_container_width=True):
            if meal_input:
                entry = calculate_macros(user_text=meal_input, user_api_key=api_key)
                st.session_state.logs.insert(0, entry)
                st.success(f"Logged: {entry['item']} ({entry['p']}g Protein, {entry['kcal']} kcal)")
                st.rerun()

    with tab_photo:
        uploaded_file = st.file_uploader("Upload or take meal photo:", type=["jpg", "png", "jpeg"])
        if uploaded_file:
            img = Image.open(uploaded_file)
            st.image(img, caption="Meal Preview", width=260)
            if st.button("Analyze & Scan Photo with AI", use_container_width=True):
                with st.spinner("Analyzing portion & macronutrients..."):
                    photo_entry = calculate_macros(user_text="", image=img, user_api_key=api_key)
                    st.session_state.logs.insert(0, photo_entry)
                    st.success(f"Scanned: {photo_entry['item']} ({photo_entry['p']}g Protein, {photo_entry['kcal']} kcal)")
                    st.rerun()

    st.markdown("#### Logged Meals Today")
    if st.session_state.logs:
        df_display = pd.DataFrame(st.session_state.logs)[["time", "item", "p", "c", "f", "kcal"]]
        df_display.columns = ["Time", "Food Item", "Protein (g)", "Carbs (g)", "Fats (g)", "Calories (kcal)"]
        st.dataframe(df_display, use_container_width=True, hide_index=True)
        if st.button("Clear Log History"):
            st.session_state.logs = []
            st.rerun()
    else:
        st.info("No meals logged yet today.")

with right_col:
    st.subheader("🏋️ Workout Splits & Form Micro-Videos")
    split_choice = st.selectbox(
        "Select Active Workout Split:",
        ["Push • Pull • Legs (6-Day)", "Arnold Split (Chest/Back, Arms, Legs)", "Upper / Lower (4-Day)"]
    )
    muscle_choice = st.radio(
        "Target Muscle Group:",
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
            st.markdown("**Form Checklist:**")
            for cue in ex["cues"]:
                st.markdown(f"- {cue}")