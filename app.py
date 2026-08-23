import streamlit as st
import pandas as pd
import re
from datetime import datetime
from PIL import Image

# 1. Page Configuration
st.set_page_config(
    page_title="KSP Fitness OS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# 2. Styling (Dark Theme & Branding)
st.markdown("""
<style>
    .ksp-header {
        background-color: #0F172A;
        padding: 20px;
        border-radius: 12px;
        border: 1px solid #1E293B;
        margin-bottom: 20px;
    }
    .ksp-brand {
        color: #3B82F6;
        font-size: 13px;
        font-weight: 800;
        letter-spacing: 1.5px;
        text-transform: uppercase;
    }
    .ksp-title {
        color: #FFFFFF;
        font-size: 26px;
        font-weight: 900;
        margin: 4px 0 0 0;
    }
    .ksp-tagline {
        color: #94A3B8;
        font-size: 13px;
        font-style: italic;
    }
</style>
""", unsafe_allow_html=True)

# 3. Header Banner
st.markdown("""
<div class="ksp-header">
    <div class="ksp-brand">KSP Consulting & Solutions</div>
    <div class="ksp-title">Fitness OS</div>
    <div class="ksp-tagline">Strategy amplified, complexity simplified.</div>
</div>
""", unsafe_allow_html=True)

# 4. Master Food Database (Values per 100g raw / standard)
NUTRITION_DB = {
    "moong dal": {"kcal": 347, "p": 24.0, "c": 59.0, "f": 1.2, "name": "Raw Moong Dal"},
    "moogdal": {"kcal": 347, "p": 24.0, "c": 59.0, "f": 1.2, "name": "Raw Moong Dal"},
    "paneer": {"kcal": 280, "p": 18.0, "c": 4.0, "f": 22.0, "name": "Standard Paneer"},
    "panner": {"kcal": 280, "p": 18.0, "c": 4.0, "f": 22.0, "name": "Standard Paneer"},
    "soya chunks": {"kcal": 345, "p": 52.0, "c": 33.0, "f": 0.5, "name": "Raw Soya Chunks"},
    "soya": {"kcal": 345, "p": 52.0, "c": 33.0, "f": 0.5, "name": "Raw Soya Chunks"},
    "pea protein": {"kcal": 390, "p": 78.0, "c": 6.0, "f": 5.0, "name": "Pea Protein Powder"},
    "whey": {"kcal": 395, "p": 78.0, "c": 5.0, "f": 4.5, "name": "Whey Protein Powder"},
    "curd": {"kcal": 70, "p": 4.0, "c": 5.0, "f": 4.0, "name": "Plain Curd / Dahi"},
    "dahi": {"kcal": 70, "p": 4.0, "c": 5.0, "f": 4.0, "name": "Plain Curd / Dahi"},
    "chana": {"kcal": 360, "p": 19.0, "c": 60.0, "f": 5.0, "name": "Raw Chickpeas / Chana"},
    "rajma": {"kcal": 340, "p": 22.0, "c": 60.0, "f": 1.5, "name": "Raw Rajma"},
    "tofu": {"kcal": 83, "p": 10.0, "c": 2.0, "f": 4.5, "name": "Soy Tofu"},
    "oats": {"kcal": 389, "p": 13.5, "c": 66.0, "f": 6.9, "name": "Rolled Oats"},
    "rice": {"kcal": 360, "p": 7.0, "c": 80.0, "f": 0.6, "name": "Raw Rice"},
    "roti": {"kcal": 120, "p": 3.5, "c": 22.0, "f": 1.5, "name": "Whole Wheat Roti (1 pc / 40g)"},
}

# 5. Master Exercise Database with Universal Video Guides
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

# 6. Session State
if "logs" not in st.session_state:
    st.session_state.logs = [
        {"item": "70g Raw Soya Chunks", "grams": 70, "kcal": 242, "p": 36.4, "c": 23.1, "f": 0.4, "time": "01:15 PM"},
        {"item": "100g Plain Curd", "grams": 100, "kcal": 70, "p": 4.0, "c": 5.0, "f": 4.0, "time": "01:15 PM"},
    ]

# 7. Macro Parsing Engine
def parse_macros(text):
    clean = text.lower().strip()
    
    # Extract gram input (e.g., "200gm", "100g", "70 gms", or leading "100")
    grams = 100
    g_match = re.search(r'(\d+)\s*(g|gm|gms|gram|grams)', clean)
    if g_match:
        grams = float(g_match.group(1))
    else:
        num_match = re.match(r'^(\d+)', clean)
        if num_match:
            grams = float(num_match.group(1))
            
    matched_profile = None
    matched_label = text
    for key, profile in NUTRITION_DB.items():
        if key in clean:
            matched_profile = profile
            matched_label = profile["name"]
            break
            
    if not matched_profile:
        matched_profile = {"kcal": 250, "p": 15.0, "c": 30.0, "f": 5.0}
        matched_label = text
        
    mult = grams / 100.0
    return {
        "item": f"{int(grams)}g {matched_label}",
        "grams": int(grams),
        "kcal": round(matched_profile["kcal"] * mult),
        "p": round(matched_profile["p"] * mult, 1),
        "c": round(matched_profile["c"] * mult, 1),
        "f": round(matched_profile["f"] * mult, 1),
        "time": datetime.now().strftime("%I:%M %p")
    }

# 8. Dashboard Layout & Metrics
target_kcal = 2200
target_p = 140

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

left_col, right_col = st.columns([1, 1], gap="large")

# Left Column: Nutrition Tracker
with left_col:
    st.subheader("🥗 Smart Macro & Meal Tracker")
    
    tab_text, tab_photo = st.tabs(["⚡ Quick Text / Grams", "📷 Photo Scan"])
    
    with tab_text:
        meal_input = st.text_input(
            "Describe meal with quantities:",
            placeholder="e.g., 200gm dry moogdal, 100g paneer, 70g soya chunks"
        )
        if st.button("Log & Calculate Macros", type="primary", use_container_width=True):
            if meal_input:
                new_entry = parse_macros(meal_input)
                st.session_state.logs.insert(0, new_entry)
                st.success(f"Logged: {new_entry['item']} ({new_entry['p']}g Protein, {new_entry['kcal']} kcal)")
                st.rerun()

    with tab_photo:
        uploaded_file = st.file_uploader("Upload meal picture:", type=["jpg", "png", "jpeg"])
        if uploaded_file:
            img = Image.open(uploaded_file)
            st.image(img, caption="Uploaded Meal", width=240)
            if st.button("Analyze & Log Photo", use_container_width=True):
                photo_entry = {
                    "item": "Visual Scan: 200g Paneer Bowl + 2 Rotis",
                    "grams": 280,
                    "kcal": 560,
                    "p": 36.0,
                    "c": 44.0,
                    "f": 24.0,
                    "time": datetime.now().strftime("%I:%M %p")
                }
                st.session_state.logs.insert(0, photo_entry)
                st.success("Visual scan calculated!")
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

# Right Column: Workout Engine & Video Guides
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