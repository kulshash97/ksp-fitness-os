import streamlit as st
import pandas as pd
import re
import json
from datetime import datetime
from PIL import Image
from google import genai
from google.genai import types

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
    .badge-macro {
        background-color: #1E293B;
        padding: 4px 8px;
        border-radius: 6px;
        font-size: 12px;
        font-weight: bold;
    }
</style>
""", unsafe_allow_html=True)

st.markdown("""
<div class="ksp-header">
    <div class="ksp-brand">KSP Consulting & Solutions</div>
    <div class="ksp-title">Fitness OS • Pro</div>
    <div class="ksp-tagline">Strategy amplified, complexity simplified.</div>
</div>
""", unsafe_allow_html=True)

# 2. Secure API Key Management
SERVER_API_KEY = ""
if "GEMINI_API_KEY" in st.secrets:
    SERVER_API_KEY = st.secrets["GEMINI_API_KEY"]

with st.sidebar:
    st.markdown("### ⚙️ System Settings")
    if not SERVER_API_KEY:
        SERVER_API_KEY = st.text_input("Enter Gemini API Key:", type="password", help="Add GEMINI_API_KEY to Streamlit Cloud secrets to bypass this.")
    st.markdown("---")
    target_kcal = st.number_input("Daily Caloric Target", value=2200, step=50)
    target_p = st.number_input("Daily Protein Target (g)", value=140, step=5)

# 3. Master Offline Rulebook
FOOD_DB = {
    "tea": {"kcal": 75, "p": 2.0, "c": 10.0, "f": 2.5, "unit": "1 Cup Indian Chai", "g": 150},
    "chai": {"kcal": 75, "p": 2.0, "c": 10.0, "f": 2.5, "unit": "1 Cup Indian Chai", "g": 150},
    "coffee": {"kcal": 80, "p": 2.2, "c": 11.0, "f": 2.8, "unit": "1 Cup Coffee", "g": 150},
    "pea protein": {"kcal": 135, "p": 26.0, "c": 2.5, "f": 2.0, "unit": "1 Scoop Pea Protein (33g)", "g": 33},
    "whey": {"kcal": 130, "p": 25.0, "c": 3.0, "f": 1.5, "unit": "1 Scoop Whey Protein (33g)", "g": 33},
    "soya chunks": {"kcal": 345, "p": 52.0, "c": 33.0, "f": 0.5, "unit": "Raw Soya Chunks (100g)", "g": 100},
    "soya": {"kcal": 345, "p": 52.0, "c": 33.0, "f": 0.5, "unit": "Raw Soya Chunks (100g)", "g": 100},
    "paneer": {"kcal": 280, "p": 18.0, "c": 4.0, "f": 22.0, "unit": "Paneer (100g)", "g": 100},
    "panner": {"kcal": 280, "p": 18.0, "c": 4.0, "f": 22.0, "unit": "Paneer (100g)", "g": 100},
    "moong dal": {"kcal": 347, "p": 24.0, "c": 59.0, "f": 1.2, "unit": "Raw Moong Dal (100g)", "g": 100},
    "moogdal": {"kcal": 347, "p": 24.0, "c": 59.0, "f": 1.2, "unit": "Raw Moong Dal (100g)", "g": 100},
    "curd": {"kcal": 70, "p": 4.0, "c": 5.0, "f": 4.0, "unit": "Plain Curd / Dahi (100g)", "g": 100},
    "dahi": {"kcal": 70, "p": 4.0, "c": 5.0, "f": 4.0, "unit": "Plain Curd / Dahi (100g)", "g": 100},
    "roti": {"kcal": 115, "p": 3.5, "c": 22.0, "f": 1.5, "unit": "1 Roti", "g": 40},
    "chapati": {"kcal": 115, "p": 3.5, "c": 22.0, "f": 1.5, "unit": "1 Chapati", "g": 40},
    "rice": {"kcal": 350, "p": 7.0, "c": 78.0, "f": 0.6, "unit": "Raw Rice (100g)", "g": 100},
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

# 4. Pro AI Vision & Macro Engine
def calculate_macros(user_text: str = "", image: Image.Image = None):
    if SERVER_API_KEY:
        try:
            client = genai.Client(api_key=SERVER_API_KEY)
            prompt = """
            You are a world-class precision sports nutritionist and computer vision nutrition analyzer.
            
            TASK:
            1. If an image is provided:
               - Determine if it is a PACKAGED food (read nutrition table, serving size, net weight) or UNPACKAGED/COOKED meal (estimate ingredients, portion volume, and raw weight equivalents).
               - Calculate exact total macros for the visible portion.
            2. If text is provided:
               - Extract quantities, handle colloquial terms (e.g. 'one cup tea', '2 scoops whey', '200gm moong dal', '70g soya chunks').
            
            Return STRICT JSON matching this schema:
            {
              "item_name": "Clear descriptive name of item/portion",
              "grams": integer,
              "calories": integer,
              "protein": float,
              "carbs": float,
              "fats": float,
              "confidence_notes": "Short 1-line breakdown (e.g. Packaged Label Read / Estimated 200g portion)"
            }
            """
            contents = [prompt]
            if user_text:
                contents.append(f"User Description: {user_text}")
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
                "item": data.get("item_name", user_text or "Scanned Food"),
                "grams": int(data.get("grams", 150)),
                "kcal": int(data.get("calories", 100)),
                "p": round(float(data.get("protein", 2.0)), 1),
                "c": round(float(data.get("carbs", 10.0)), 1),
                "f": round(float(data.get("fats", 2.0)), 1),
                "note": data.get("confidence_notes", "AI Verified"),
                "time": datetime.now().strftime("%I:%M %p")
            }
        except Exception as e:
            st.error(f"AI Vision Error: {e}")

    # Fallback Rulebook
    clean = (user_text or "snack").lower().strip()
    count = 1.0
    count_words = {"one": 1, "two": 2, "three": 3, "four": 4, "half": 0.5, "1": 1, "2": 2, "3": 3, "4": 4}
    for word, val in count_words.items():
        if re.search(rf'\b{word}\b', clean):
            count = float(val)
            break

    explicit_grams = None
    g_match = re.search(r'(\d+)\s*(g|gm|gms|gram|grams)', clean)
    if g_match:
        explicit_grams = float(g_match.group(1))

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
                    "note": "Rulebook Exact Match",
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
                    "note": "Standard Portion Rule",
                    "time": datetime.now().strftime("%I:%M %p")
                }

    return {
        "item": user_text.title() if user_text else "Custom Item",
        "grams": int(120 * count),
        "kcal": int(85 * count),
        "p": round(2.0 * count, 1),
        "c": round(12.0 * count, 1),
        "f": round(2.5 * count, 1),
        "note": "Heuristic Estimate",
        "time": datetime.now().strftime("%I:%M %p")
    }

# 5. Session State Initializers
if "meal_logs" not in st.session_state:
    st.session_state.meal_logs = [
        {"item": "70g Raw Soya Chunks", "grams": 70, "kcal": 242, "p": 36.4, "c": 23.1, "f": 0.4, "note": "Verified", "time": "01:15 PM"},
        {"item": "100g Plain Curd", "grams": 100, "kcal": 70, "p": 4.0, "c": 5.0, "f": 4.0, "note": "Verified", "time": "01:15 PM"},
    ]

if "workout_logs" not in st.session_state:
    st.session_state.workout_logs = [
        {"time": "07:30 AM", "split": "Push (Chest/Shoulders/Triceps)", "exercise": "Incline Dumbbell Press", "sets": 4, "reps": 10, "weight": 24.0, "rpe": 8.5},
        {"time": "07:45 AM", "split": "Push (Chest/Shoulders/Triceps)", "exercise": "Flat Barbell Bench Press", "sets": 3, "reps": 8, "weight": 60.0, "rpe": 9.0},
    ]

# 6. Global Top Metric Ribbon
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

# 7. Main Dashboard Grid
left_col, right_col = st.columns([1, 1], gap="large")

# LEFT PANEL: Nutrition Engine
with left_col:
    st.subheader("🥗 Smart Macro & Meal Tracker")
    tab_photo, tab_text = st.tabs(["📷 AI Live Photo Scan (Packaged & Cooked)", "⚡ Text & Gram Input"])
    
    with tab_photo:
        uploaded_file = st.file_uploader("Snap or upload meal photo / nutrition label:", type=["jpg", "png", "jpeg"])
        if uploaded_file:
            img = Image.open(uploaded_file)
            st.image(img, caption="Loaded Meal Preview", use_container_width=True)
            if st.button("⚡ Scan & Calculate All Macros", type="primary", use_container_width=True):
                with st.spinner("AI Vision is inspecting packaging, ingredients, and portion volume..."):
                    photo_entry = calculate_macros(image=img)
                    st.session_state.meal_logs.insert(0, photo_entry)
                    st.success(f"Identified: {photo_entry['item']} ({photo_entry['p']}g Protein, {photo_entry['kcal']} kcal)")
                    st.rerun()

    with tab_text:
        meal_input = st.text_input(
            "Describe meal with quantities:",
            placeholder="e.g., one medium cup of tea, 200gm moong dal, 1 scoop pea protein"
        )
        if st.button("Log Food Entry", type="primary", use_container_width=True):
            if meal_input:
                entry = calculate_macros(user_text=meal_input)
                st.session_state.meal_logs.insert(0, entry)
                st.success(f"Logged: {entry['item']} ({entry['p']}g Protein, {entry['kcal']} kcal)")
                st.rerun()

    st.markdown("#### Today's Meal Log")
    if st.session_state.meal_logs:
        df_meal_disp = pd.DataFrame(st.session_state.meal_logs)[["time", "item", "p", "c", "f", "kcal", "note"]]
        df_meal_disp.columns = ["Time", "Food Item", "Protein (g)", "Carbs (g)", "Fats (g)", "Calories (kcal)", "Source"]
        st.dataframe(df_meal_disp, use_container_width=True, hide_index=True)
        if st.button("Clear Meals"):
            st.session_state.meal_logs = []
            st.rerun()
    else:
        st.info("No meals logged yet today.")

# RIGHT PANEL: Workout Split Engine & Daily Logger
with right_col:
    st.subheader("🏋️ Workout OS & Split Tracker")
    
    workout_tab1, workout_tab2 = st.tabs(["📝 Daily Workout Logger", "🎥 Form Guides & Splits"])
    
    with workout_tab1:
        st.markdown("#### Log Active Training Session")
        w_split = st.selectbox(
            "Training Split:",
            ["Push (Chest / Shoulders / Triceps)", "Pull (Back / Rear Delts / Biceps)", "Legs (Quads / Hamstrings / Calves)", "Full Body / Core"]
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

        st.markdown("#### Completed Sets Today")
        if st.session_state.workout_logs:
            df_w_disp = pd.DataFrame(st.session_state.workout_logs)[["time", "split", "exercise", "sets", "reps", "weight", "rpe"]]
            df_w_disp.columns = ["Time", "Split", "Exercise", "Sets", "Reps", "Weight (kg)", "RPE"]
            st.dataframe(df_w_disp, use_container_width=True, hide_index=True)
            if st.button("Clear Workout Logs"):
                st.session_state.workout_logs = []
                st.rerun()
        else:
            st.info("No workout logged yet today.")

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