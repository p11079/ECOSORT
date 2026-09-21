"""EcoSort AI v1.0.0 - lightweight waste segregation assistant."""
from __future__ import annotations

import io
import json
from datetime import datetime
from pathlib import Path

import pandas as pd
import streamlit as st
from PIL import Image

APP_DIR = Path(__file__).parent
HISTORY_FILE = APP_DIR / "classification_history.csv"

WASTE_RULES = {
    "Organic": {"color": "#9bbf58", "examples": "food scraps, leaves, fruit peels", "advice": "Place it in the wet/compost bin. Keep plastic and stickers out."},
    "Paper": {"color": "#e5bd65", "examples": "newspaper, cardboard, notebooks", "advice": "Keep it dry and flatten boxes before placing it with paper recyclables."},
    "Plastic": {"color": "#56a6a2", "examples": "bottles, containers, wrappers", "advice": "Empty and rinse rigid plastic. Check your local recycling rules for wrappers."},
    "Glass": {"color": "#7c9bc9", "examples": "jars, bottles, glass containers", "advice": "Rinse it and place it with glass recycling. Do not include broken ceramics."},
    "Metal": {"color": "#b8a8c7", "examples": "cans, tins, foil", "advice": "Empty and rinse it. Fold sharp foil safely before disposal."},
    "E-waste": {"color": "#d47d63", "examples": "chargers, batteries, electronics", "advice": "Never place it in regular bins. Use an authorised e-waste collection point."},
}

st.set_page_config(page_title="EcoSort AI", page_icon="♻", layout="wide", initial_sidebar_state="expanded")

st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;600;700;800&display=swap');
:root { --ink:#18231f; --muted:#64736b; --paper:#f4f1e8; --leaf:#23483c; --lime:#d6e88a; --line:#d9ded4; }
.stApp { background:var(--paper); color:var(--ink); }
[data-testid="stSidebar"] { background:#18382f; }
[data-testid="stSidebar"] * { color:#f4f1e8 !important; }
h1,h2,h3,p,span,div,button { font-family:'Manrope', sans-serif; }
.hero { padding:2.6rem 0 1.6rem; border-bottom:1px solid var(--line); }
.eyebrow { font-family:'DM Mono', monospace; color:#9ab86b; letter-spacing:.12em; font-size:.72rem; text-transform:uppercase; }
.hero h1 { font-size:clamp(2.5rem,5vw,5.7rem); line-height:.95; letter-spacing:-.07em; margin:.7rem 0 1rem; color:var(--leaf); }
.hero p { max-width:650px; color:var(--muted); font-size:1.05rem; }
.card { background:#fbfaf5; border:1px solid var(--line); border-radius:18px; padding:1.25rem; box-shadow:0 10px 28px rgba(24,35,31,.05); }
.label { font-family:'DM Mono',monospace; font-size:.7rem; text-transform:uppercase; letter-spacing:.08em; color:var(--muted); }
.result { border-left:8px solid #56a6a2; background:#e8f0dd; border-radius:14px; padding:1.4rem; }
.result h2 { margin:.25rem 0; color:var(--leaf); }
.tip { background:#e8e1cc; border-radius:12px; padding:1rem; color:var(--ink); }
.small { color:var(--muted); font-size:.88rem; }
div[data-testid="stMetric"] { background:#fbfaf5; border:1px solid var(--line); padding:1rem; border-radius:14px; }
/* Make Streamlit's native upload trigger clearly visible on the warm paper surface. */
div[data-testid="stFileUploader"] button {
    background:#23483c !important;
    color:#f8f7f0 !important;
    border:1px solid #23483c !important;
    border-radius:10px !important;
    font-weight:800 !important;
    box-shadow:0 4px 0 #142d25 !important;
    transition:transform .15s ease, box-shadow .15s ease, background .15s ease !important;
}
div[data-testid="stFileUploader"] button:hover {
    background:#2f6250 !important;
    color:#ffffff !important;
    transform:translateY(-1px);
    box-shadow:0 5px 0 #142d25 !important;
}
div[data-testid="stFileUploader"] button:focus-visible {
    outline:3px solid #d6e88a !important;
    outline-offset:3px !important;
}
div[data-testid="stCheckbox"] label,
div[data-testid="stCheckbox"] label p {
    color:var(--ink) !important;
    font-weight:600 !important;
}
div[data-testid="stSelectbox"] label,
div[data-testid="stSelectbox"] label p {
    color:var(--ink) !important;
    font-weight:700 !important;
}
div[data-testid="stFileUploader"] {
    margin-top:1rem !important;
}
</style>
""", unsafe_allow_html=True)

def load_history() -> pd.DataFrame:
    if HISTORY_FILE.exists():
        return pd.read_csv(HISTORY_FILE)
    return pd.DataFrame(columns=["time", "item", "category", "confidence", "method"])

def save_result(item: str, category: str, confidence: int | None, method: str) -> None:
    row = pd.DataFrame([{"time": datetime.now().isoformat(timespec="seconds"), "item": item, "category": category, "confidence": confidence, "method": method}])
    history = pd.concat([load_history(), row], ignore_index=True)
    history.to_csv(HISTORY_FILE, index=False)

def guess_from_name(name: str) -> tuple[str, int, str]:
    value = name.lower()
    # Put specific material terms before generic object terms such as "bottle".
    keywords = {"E-waste":["battery","charger","phone","electronic","laptop"], "Organic":["food","banana","leaf","fruit","apple"], "Paper":["paper","card","book","newspaper"], "Glass":["glass","jar"], "Metal":["metal","can","tin","foil"], "Plastic":["plastic","bottle","wrapper","bag"]}
    for category, terms in keywords.items():
        if any(term in value for term in terms):
            return category, None, "filename demo mode"
    return "Plastic", None, "demo fallback"

def analyze_with_gemini(image_bytes: bytes) -> tuple[str, int, str] | None:
    try:
        import google.generativeai as genai
        api_key = st.secrets.get("GEMINI_API_KEY", "")
        if not api_key:
            return None
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel("gemini-1.5-flash")
        prompt = "Classify this waste item into exactly one of Organic, Paper, Plastic, Glass, Metal, E-waste. Return JSON only with keys category, confidence, item."
        response = model.generate_content([prompt, {"mime_type":"image/jpeg", "data":image_bytes}])
        data = json.loads(response.text.replace("```json", "").replace("```", "").strip())
        category = data.get("category", "Plastic")
        if category not in WASTE_RULES:
            category = "Plastic"
        return category, int(data.get("confidence", 80)), f"Gemini Vision: {data.get('item', 'item')}"
    except Exception:
        return None

st.sidebar.markdown("## EcoSort AI")
st.sidebar.caption("Waste decisions, made clearer.")
page = st.sidebar.radio("Navigate", ["Sort an item", "Impact dashboard", "About the project"])
st.sidebar.markdown("---")
st.sidebar.caption("v1.0.0 · SDG 12 + SDG 13")

if page == "Sort an item":
    st.markdown('<div class="hero"><div class="eyebrow">Everyday sustainability · 01</div><h1>Give waste<br>the right next step.</h1><p>Upload an item and EcoSort will suggest where it belongs, why it matters, and what to do next.</p></div>', unsafe_allow_html=True)
    left, right = st.columns([1.1, .9], gap="large")
    with left:
        st.markdown('<div class="card"><div class="label">Step 01 / Add an item</div>', unsafe_allow_html=True)
        uploaded = st.file_uploader("Upload a clear photo", type=["jpg", "jpeg", "png"], label_visibility="collapsed")
        if uploaded:
            image = Image.open(uploaded)
            st.image(image, use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
    with right:
        st.markdown('<div class="card"><div class="label">Step 02 / Confirm context</div>', unsafe_allow_html=True)
        category_options = ["Select category…"] + list(WASTE_RULES)
        fallback_category = st.selectbox("Demo category", category_options, index=0, help="Used when no image or Gemini API key is configured.")
        use_ai = st.checkbox("Use AI image analysis", value=True)
        analyze = st.button("Analyze item →", type="primary", use_container_width=True)
        st.markdown('</div>', unsafe_allow_html=True)
        if analyze:
            if uploaded:
                result = analyze_with_gemini(uploaded.getvalue()) if use_ai else None
                category, confidence, method = result or guess_from_name(uploaded.name)
                item = uploaded.name.rsplit('.', 1)[0].replace('_', ' ').replace('-', ' ')
            elif fallback_category == "Select category…":
                st.warning("Upload an image or select a waste category before analyzing.")
                st.stop()
            else:
                category, confidence, method, item = fallback_category, 100, "manual demo mode", fallback_category
            st.session_state["result"] = {"category":category, "confidence":confidence, "method":method, "item":item}
            save_result(item, category, confidence, method)
    if "result" in st.session_state:
        result = st.session_state["result"]
        category = result["category"]
        rule = WASTE_RULES[category]
        st.markdown("### Result")
        confidence = result["confidence"]
        confidence_text = f"Confidence: {confidence}%" if confidence is not None else "Demo mode · confidence not measured"
        st.markdown(f'<div class="result" style="border-color:{rule["color"]}"><div class="label">Recommended category</div><h2>{category}</h2><p>{rule["advice"]}</p><div class="small">{confidence_text} · {result["method"]}</div></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="tip"><b>Why this matters:</b> Correct sorting keeps useful materials in circulation and reduces contamination at collection and recycling points.</div>', unsafe_allow_html=True)

elif page == "Impact dashboard":
    st.markdown('<div class="hero"><div class="eyebrow">Impact log · 02</div><h1>Small choices.<br>Visible progress.</h1><p>A lightweight record of classification decisions made in the prototype.</p></div>', unsafe_allow_html=True)
    history = load_history()
    a,b,c = st.columns(3)
    a.metric("Items checked", len(history))
    b.metric("Categories used", history["category"].nunique() if not history.empty else 0)
    c.metric("Recyclable / reusable", int(history["category"].isin(["Paper","Plastic","Glass","Metal"]).sum()) if not history.empty else 0)
    if not history.empty:
        st.bar_chart(history["category"].value_counts())
        st.dataframe(history.sort_values("time", ascending=False), use_container_width=True, hide_index=True)
    else:
        st.info("Classify an item to start the impact log.")

else:
    st.markdown('<div class="hero"><div class="eyebrow">Project note · 03</div><h1>Useful before<br>it is ambitious.</h1><p>EcoSort AI focuses on one persistent sustainability gap: people often want to dispose of items responsibly but are unsure what to do.</p></div>', unsafe_allow_html=True)
    st.markdown("""
    ### What this prototype demonstrates

    - AI-assisted image classification
    - Human-readable disposal guidance
    - A transparent fallback mode for demos without an API key
    - A simple impact log for measuring usage

    ### Honest limitation

    Waste rules vary by city, packaging can contain multiple materials, and computer vision can be uncertain. EcoSort is a decision aid, not a replacement for local waste authorities.
    """)
