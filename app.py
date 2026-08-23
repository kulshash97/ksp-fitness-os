import streamlit as st
import pandas as pd
import re
import json
from datetime import datetime
from PIL import Image
import google.generativeai as genai

# 1. Page Config & Branding
st.set_page_config(
    page_title="KSP Fitness OS",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Dark Slate Theme Styling
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

# 2. Master Indian & Fitness Nutrition Rulebook (Fallback Engine)
NUTRITION_DB = {
    "moong dal": {"kcal": 347, "p": 24.0, "c": 59.0, "f": 1.2, "name": "Raw Moong Dal"},
    "moogdal": {"kcal": 347, "p": 24.0, "c": 59.0, "f": 1.2, "name": "Raw Moong Dal"},
    "paneer": {"kcal": 280, "p": 18.0, "c": 4.0, "f": 22.0, "name": "Standard Paneer"},
    "panner": {"kcal": 280, "p": 18.0, "c": 4.0, "f": 22.0, "name": "Standard Paneer"},
    "soya chunks": {"kcal": 345, "p": 52.0, "c": 33.0, "f": 0.5, "name": "Raw Soya Chunks"},
    "soya": {"kcal": 345, "p": 52.0, "c": 33.0, "f": 0.5, "name": "Raw Soya Chunks"},
    "pea protein": {"kcal": 135, "p": 26.0, "c": 2.5, "f": 2.0, "name": "Pea Protein Scoop (33g)", "fixed_grams": 33},
    "pea protine": {"kcal": 135, "p": 26.0, "c": 2.5, "f": 2.0, "name": "Pea Protein Scoop (33g)", "fixed_grams": 33},
    "whey": {"kcal": 130, "p": 25.0, "c": 3.0, "f": 1.5, "name": "Whey Protein Scoop (33g)", "fixed_grams": 33},
    "curd": {"kcal": 70, "p": 4.0, "c": 5.0, "f": 4.0, "name": "Plain Curd / Dahi"},
    "dahi": {"kcal": 70, "p": 4.0, "c": 5.0, "f": 4.0, "name": "Plain Curd / Dahi"},
    "chana": {"kcal": 360, "p": 19.0, "c": 60.0, "f": 5.0, "name": "Raw Chana / Chickpeas"},
    "rajma": {"kcal": 340, "p": 22.0, "c": 60.0, "f": 1.5, "name": "Raw Rajma"},
    "tofu": {"kcal": 83, "p": 10.0, "c": 2.0, "f": 4.5, "name": "Soy Tofu"},
    "oats": {"kcal": 389, "p": 13.5, "c": 66.0, "f": 6.9, "name": "Rolled Oats"},
    "rice": {"kcal": 360, "p": 7.0, "c": 80.0, "f": 0.6, "name": "Raw Rice"},
    "roti": {"kcal": 120, "p": 3.5, "c": 22.0, "f": 1.5, "name": "Whole Wheat Roti (1 pc / 40g)"},
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

# 3. Sidebar API Key Config
with st.sidebar:
    st.markdown("### 🔑 AI Vision Setup")
    api_key = st.text_input("Gemini API Key (Optional):", type="password", help="Get a free key from Google AI Studio to unlock live image recognition.")
    st.markdown("---")
    st.markdown("**Targets:**")
    target_kcal = st.number_input("Daily Kcal Goal", value=2200, step=50)
    target_p = st.number_input("Daily Protein Goal (g)", value=140, step=5)

# 4. Parsing Functions
def parse_text_macros(text):
    clean = text.lower().strip()
    
    # Scoop detector (e.g. "one scope", "1 scoop", "2 scoops")
    scoop_match = re.search(r'(\d+|one|two|three)\s*(scope|scoop|scoops)', clean)
    num_scoops = 1
    if scoop_match:
        val = scoop_match.group(1)
        word_map = {"one": 1, "two": 2, "three": 3}
        num_scoops = word_map.get(val, int(val) if val.isdigit() else 1)

    # Gram detector
    grams = None
    g_match = re.search(r'(\d+)\s*(g|gm|gms|gram|grams)', clean)
    if g_match:
        grams = float(g_match.group(1))
    else:
        num_match = re.match(r'^(\d+)', clean)
        if num_match:
            grams = float(num_match.group(1))

    matched_profile = None
    for key, profile in NUTRITION_DB.items():
        if key in clean:
            matched_profile = profile
            break

    if matched_profile:
        if "fixed_grams" in matched_profile:
            actual_grams = matched_profile["fixed_grams"] * num_scoops
            return {
                "item": f"{num_scoops} Scoop(s) {matched_profile['name']}",
                "grams": int(actual_grams),
                "kcal": int(matched_profile["kcal"] * num_scoops),
                "p": round(matched_profile["p"] * num_scoops, 1),
                "c": round(matched_profile["c"] * num_scoops, 1),
                "f": round(matched_profile["f"] * num_scoops, 1),
                "time": datetime.now().strftime("%I:%M %p")
            }
        else:
            final_grams = grams if grams else 100
            mult = final_grams / 100.0
            return {
                "item": f"{int(final_grams)}g {matched_profile['name']}",
                "grams": int(final_grams),
                "kcal": round(matched_profile["kcal"] * mult),
                "p": round(matched_profile["p"] * mult, 1),
                "c": round(matched_profile["c"] * mult, 1),
                "f": round(matched_profile["f"] * mult, 1),
                "time": datetime.now().strftime("%I:%M %p")
            }

    # Fallback heuristic
    final_grams = grams if grams else 150
    return {
        "item": text.title(),
        "grams": int(final_grams),
        "kcal": int(final_grams * 1.5),
        "p": round(final_grams * 0.12, 1),
        "c": round(final_grams * 0.20, 1),
        "f": round(final_grams * 0.04, 1),
        "time": datetime.now().strftime("%I:%M %p")
    }

def analyze_photo_with_ai(image: Image.Image, key: str):
    if not key:
        return {
            "item": "Visual Scan (Estimated Bowl)",
            "grams": 250,
            "kcal": 360,
            "p": 24.0,
            "c": 42.0,
            "f": 11.0,
            "time": datetime.now().strftime("%I:%M %p")
        }
    try:
        genai.configure(api_key=key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = """
        Analyze this meal picture. Identify the food item and estimate portion weight in grams and macronutrients.
        Output MUST be strict JSON only with this schema:
        {
          "food_name": "string",
          "grams": integer,
          "calories": integer,
          "protein": float,
          "carbs": float,
          "fats": float
        }
        """
        response = model.generate_content([prompt, image])
        clean_text = response.text.replace("```json", "").replace("```", "").strip()
        data = json.loads(clean_text)
        return {
            "item": f"📷 {data.get('food_name', 'Meal')}",
            "grams": int(data.get('grams', 200)),
            "kcal": int(data.get('calories', 300)),
            "p": round(float(data.get('protein', 20.0)), 1),
            "c": round(float(data.get('carbs', 30.0)), 1),
            "f": round(float(data.get('fats', 10.0)), 1),
            "time": datetime.now().strftime("%I:%M %p")
        }
    except Exception as e:
        st.warning(f"AI API error ({str(e)}). Using heuristic estimation.")
        return {
            "item": "📷 Scanned Food Item",
            "grams": 200,
            "kcal": 320,
            "p": 22.0,
            "c": 35.0,
            "f": 9.0,
            "time": datetime.now().strftime("%I:%M %p")
        }

# 5. Session State
if "logs" not in st.session_state:
    st.session_state.logs = [
        {"item": "70g Raw Soya Chunks", "grams": 70, "kcal": 242, "p": 36.4, "c": 23.1, "f": 0.4, "time": "01:15 PM"},
        {"item": "100g Plain Curd", "grams": 100, "kcal": 70, "p": 4.0, "c": 5.0, "f": 4.0, "time": "01:15 PM"},
    ]

# 6. Calculations & Metric Display
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

# 7. Dashboard 2-Column Split
left_col, right_col = st.columns([1, 1], gap="large")

with left_col:
    st.subheader("🥗 Smart Macro & Meal Tracker")
    tab_text, tab_photo = st.tabs(["⚡ Text / Voice / Grams", "📷 Live Photo Scan"])
    
    with tab_text:
        meal_input = st.text_input(
            "Describe meal with quantities:",
            placeholder="e.g., one scope of pea protine, 200gm dry moogdal, 100g paneer"
        )
        if st.button("Log & Calculate Macros", type="primary", use_container_width=True):
            if meal_input:
                new_entry = parse_text_macros(meal_input)
                st.session_state.logs.insert(0, new_entry)
                st.success(f"Logged: {new_entry['item']} ({new_entry['p']}g Protein, {new_entry['kcal']} kcal)")
                st.rerun()

    with tab_photo:
        uploaded_file = st.file_uploader("Upload or take meal photo:", type=["jpg", "png", "jpeg"])
        if uploaded_file:
            img = Image.open(uploaded_file)
            st.image(img, caption="Meal Preview", width=260)
            if st.button("Analyze & Scan Photo with AI", use_container_width=True):
                with st.spinner("AI Vision is calculating portion & macros..."):
                    photo_entry = analyze_photo_with_ai(img, api_key)
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