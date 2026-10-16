"""Design layer: light and dark palettes plus CSS overrides for Streamlit's widgets."""

from __future__ import annotations

import html
import zlib

PALETTES = {
    "dark": {
        "bg": "#0a0c13", "bg2": "#0e111b", "surface": "#131724", "surface2": "#1a1f2f",
        "border": "#262c40", "text": "#e8eaf3", "muted": "#8d95ab", "accent": "#8b7bff",
        "accent2": "#d36bff", "accent_soft": "rgba(139,123,255,.14)", "bubble": "#171c2c",
        "bubble_me": "linear-gradient(135deg,#5b46e8,#9b4fe8)", "bubble_me_text": "#ffffff",
        "shadow": "0 10px 30px rgba(0,0,0,.45)", "scheme": "dark", "glow": "rgba(139,123,255,.18)",
    },
    "light": {
        "bg": "#f4f5fb", "bg2": "#eceef8", "surface": "#ffffff", "surface2": "#f1f3fa",
        "border": "#e2e5f0", "text": "#161a2e", "muted": "#677086", "accent": "#6a4cff",
        "accent2": "#b44cf0", "accent_soft": "rgba(106,76,255,.10)", "bubble": "#ffffff",
        "bubble_me": "linear-gradient(135deg,#6a4cff,#a84cf0)", "bubble_me_text": "#ffffff",
        "shadow": "0 8px 24px rgba(30,40,90,.08)", "scheme": "light", "glow": "rgba(106,76,255,.12)",
    },
}

CHAR_COLORS = ["#ff7a90", "#ffb454", "#5bd6a0", "#4cc3ff", "#a78bfa", "#f472d0", "#9be15d", "#ff9f6b"]


def color_for(name: str) -> str:
    """A stable colour per character name."""
    return CHAR_COLORS[zlib.crc32(name.encode()) % len(CHAR_COLORS)]


def avatar_html(name: str, size: int = 34) -> str:
    initial = html.escape((name.strip()[:1] or "?").upper())
    return (f'<span class="av" style="--c:{color_for(name)};width:{size}px;height:{size}px;'
            f'font-size:{int(size * .44)}px">{initial}</span>')


def css(mode: str) -> str:
    p = PALETTES[mode]
    return f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&display=swap');
:root {{
  --bg:{p['bg']}; --bg2:{p['bg2']}; --surface:{p['surface']}; --surface2:{p['surface2']};
  --border:{p['border']}; --text:{p['text']}; --muted:{p['muted']}; --accent:{p['accent']};
  --accent2:{p['accent2']}; --accent-soft:{p['accent_soft']}; --bubble:{p['bubble']};
  --bubble-me:{p['bubble_me']}; --bubble-me-text:{p['bubble_me_text']}; --shadow:{p['shadow']};
  --glow:{p['glow']}; --radius:16px;
}}
html {{ color-scheme: {p['scheme']}; }}
html, body, .stApp, button, input, textarea, select {{
  font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif !important;
}}

/* ---- canvas ---- */
.stApp {{
  background: radial-gradient(1100px 520px at 12% -8%, var(--glow), transparent 60%),
              radial-gradient(900px 480px at 100% 0%, var(--accent-soft), transparent 55%), var(--bg) !important;
  color: var(--text);
}}
[data-testid="stHeader"] {{ background: transparent !important; pointer-events: none; }}  /* the invisible header must not swallow clicks */
[data-testid="stToolbar"], [data-testid="stDecoration"], footer {{ visibility: hidden; }}
.block-container {{ max-width: 1360px; padding: 2.2rem 2rem 2rem !important; }}
.stApp, .stApp p, .stApp li, .stApp label, .stApp span, .stApp div,
[data-testid="stMarkdownContainer"], [data-testid="stWidgetLabel"] p {{ color: var(--text); }}
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5 {{ color: var(--text) !important; letter-spacing: -.01em; }}
[data-testid="stCaptionContainer"], [data-testid="stCaptionContainer"] p, .stCaption, small {{ color: var(--muted) !important; }}
hr {{ border-color: var(--border) !important; }}

/* ---- brand header ---- */
.brand {{ display:flex; align-items:center; gap:14px; }}
.brand .logo {{ width:46px; height:46px; border-radius:14px; display:grid; place-items:center; font-size:24px;
  background: linear-gradient(135deg, var(--accent), var(--accent2)); box-shadow: 0 8px 22px var(--glow); }}
.brand h1 {{ margin:0; font-size:1.65rem; font-weight:700; line-height:1.1;
  background: linear-gradient(90deg, var(--text), var(--accent)); -webkit-background-clip:text;
  background-clip:text; -webkit-text-fill-color: transparent; }}
.brand p {{ margin:2px 0 0; color:var(--muted) !important; font-size:.86rem; }}

/* ---- tabs as pills ---- */
[role="tablist"] {{ gap:6px; background: var(--surface); border:1px solid var(--border);
  padding:5px; border-radius:14px; width:fit-content; box-shadow: var(--shadow); }}
.react-aria-SelectionIndicator {{ display:none !important; }}
[data-testid="stTab"] {{ border-radius:10px !important; padding:8px 18px !important; height:auto !important;
  background: transparent !important; transition: all .18s; cursor:pointer; }}
[data-testid="stTab"] p {{ color: var(--muted) !important; font-weight:600; font-size:.9rem; }}
[data-testid="stTab"]:hover p {{ color: var(--text) !important; }}
[data-testid="stTab"][aria-selected="true"] {{ background: linear-gradient(135deg, var(--accent), var(--accent2)) !important;
  box-shadow: 0 6px 16px var(--glow); }}
[data-testid="stTab"][aria-selected="true"] p {{ color:#fff !important; }}
[data-testid="stTabPanel"] {{ padding-top: 1.1rem; }}

/* ---- cards ---- */
div[class*="st-key-card"], div[class*="st-key-scene"], div[class*="st-key-manifestbox"] {{
  background: var(--surface); border:1px solid var(--border); border-radius: var(--radius);
  padding: 1rem 1.1rem; box-shadow: var(--shadow);
}}
[data-testid="stExpander"] details {{ background: var(--surface) !important; border:1px solid var(--border) !important;
  border-radius: 14px !important; }}
[data-testid="stExpander"] summary, [data-testid="stExpander"] details[open] > summary {{
  border-radius: 14px; background: transparent !important; color: var(--text) !important; }}
[data-testid="stExpander"] summary:hover, [data-testid="stExpander"] details[open] > summary:hover,
[data-testid="stExpander"] summary:focus-visible {{ background: var(--accent-soft) !important; }}
[data-testid="stExpander"] summary:active {{ background: var(--accent-soft) !important; }}
[data-testid="stExpander"] summary p {{ font-weight:600; }}

/* ---- inputs: every field surface is dark/light according to the theme ---- */
[data-testid="stSelectbox"] [role="group"], [data-testid="stMultiSelect"] [role="group"],
[data-testid="stTextInputRootElement"], [data-testid="stTextAreaRootElement"],
[data-testid="stNumberInputContainer"] {{
  background: var(--surface2) !important; border:1px solid var(--border) !important; border-radius: 12px !important;
  box-shadow:none !important; }}
[data-testid="stSelectbox"] [role="group"] *, [data-testid="stMultiSelect"] [role="group"] *,
[data-testid="stTextInputRootElement"] *, [data-testid="stTextAreaRootElement"] * {{ background-color: transparent; }}
[data-testid="stSelectbox"] input, [data-testid="stMultiSelect"] input, [data-testid="stTextInput"] input,
[data-testid="stTextArea"] textarea {{ color: var(--text) !important; -webkit-text-fill-color: var(--text) !important;
  caret-color: var(--accent); background: transparent !important; }}
[data-testid="stSelectbox"] input::placeholder, [data-testid="stTextInput"] input::placeholder,
[data-testid="stTextArea"] textarea::placeholder {{ color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important; }}
[data-testid="stSelectbox"] [role="group"]:focus-within, [data-testid="stMultiSelect"] [role="group"]:focus-within,
[data-testid="stTextInputRootElement"]:focus-within, [data-testid="stTextAreaRootElement"]:focus-within {{
  border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-soft) !important; }}
[data-testid="stSelectbox"] svg, [data-testid="stMultiSelect"] svg {{ color: var(--muted); fill: var(--muted); }}
[data-testid="stMultiSelect"] [role="group"] [data-tag] {{ background: var(--accent-soft) !important; border:1px solid var(--accent) !important;
  border-radius: 999px !important; padding: 2px 10px !important; }}
[data-testid="stMultiSelect"] [role="group"] [data-tag] span {{ color: var(--text) !important; font-weight:600; font-size:.82rem; }}
[data-testid="stMultiSelect"] [role="group"] [data-tag] svg {{ fill: var(--muted); }}

/* ---- checkbox (unchecked box) and toggle ---- */
[data-testid="stCheckbox"]:not(:has(input[role="switch"])) label > div:first-of-type {{
  background: var(--surface2) !important; border:1.5px solid var(--border) !important; border-radius: 7px !important; }}
[data-testid="stCheckbox"]:not(:has(input[role="switch"])) label[data-selected="true"] > div:first-of-type {{
  background: linear-gradient(135deg, var(--accent), var(--accent2)) !important; border-color: transparent !important; }}
[data-testid="stCheckbox"]:has(input[role="switch"]) label:not([data-selected="true"]) > div:first-of-type {{
  background: var(--border) !important; }}
[data-testid="stCheckbox"] p {{ font-size:.9rem; }}

/* ---- dropdown menus (selectbox / multiselect) and popovers ---- */
[data-testid$="Dropdown"], [data-testid="stPopoverBody"], [data-testid="portal"] [role="dialog"] {{
  background: var(--surface) !important; color: var(--text) !important; border:1px solid var(--border);
  border-radius:14px !important; box-shadow: var(--shadow); }}
[data-testid$="Dropdown"] *, [data-testid="stPopoverBody"] p, [data-testid="stPopoverBody"] label {{ color: var(--text); }}
[data-testid$="Dropdown"] [role="listbox"], [data-testid$="Dropdown"] ul {{ background: transparent !important; }}
[role="option"] {{ background: transparent !important; color: var(--text) !important; border-radius:8px; cursor:pointer; }}
[role="option"]:hover, [role="option"][data-hovered="true"], [role="option"][data-focused="true"],
[role="option"][data-focus-visible="true"] {{ background: var(--accent-soft) !important; }}
[role="option"][aria-selected="true"], [role="option"][data-selected="true"] {{
  background: var(--accent-soft) !important; color: var(--accent) !important; font-weight:600; }}

/* ---- buttons ---- */
button[data-testid^="stBaseButton"], button[data-testid="stPopoverButton"] {{
  border-radius: 12px !important; font-weight:600; transition: all .15s; }}
button[data-testid="stBaseButton-secondary"], button[data-testid="stBaseButton-secondaryFormSubmit"],
button[data-testid="stPopoverButton"] {{
  background: var(--surface2) !important; color: var(--text) !important; border:1px solid var(--border) !important; }}
button[data-testid="stBaseButton-secondary"]:hover:not(:disabled), button[data-testid="stPopoverButton"]:hover {{
  border-color: var(--accent) !important; color: var(--accent) !important; transform: translateY(-1px);
  box-shadow: 0 6px 18px var(--glow); }}
button[data-testid="stBaseButton-primary"], button[data-testid="stBaseButton-primaryFormSubmit"] {{
  background: linear-gradient(135deg, var(--accent), var(--accent2)) !important; color:#fff !important; border:none !important; }}
button[data-testid="stBaseButton-primary"] *, button[data-testid="stBaseButton-primaryFormSubmit"] * {{ color:#fff !important; }}
button[data-testid="stBaseButton-primary"]:hover:not(:disabled) {{ transform: translateY(-1px); box-shadow: 0 8px 22px var(--glow); }}
button:disabled {{ opacity:.45 !important; }}

/* ---- chat window ---- */
div[class*="st-key-chatbox"] {{ padding: 10px 14px; background: linear-gradient(180deg, var(--bg2), var(--surface)); border:1px solid var(--border) !important;
  border-radius: 20px; box-shadow: var(--shadow); }}
[data-testid="stChatMessage"] {{ background: transparent !important; padding: .25rem .2rem; gap:.7rem; align-items:flex-start; }}
[data-testid="stChatMessageAvatarUser"], [data-testid="stChatMessageAvatarAssistant"] {{ display:none !important; }}
[data-testid="stChatMessageContent"] {{ background: var(--bubble); border:1px solid var(--border); border-radius: 4px 18px 18px 18px;
  padding: .7rem 1rem .75rem; box-shadow: 0 2px 10px rgba(0,0,0,.08); animation: pop .25s ease-out;
  flex: 0 1 auto !important; width: fit-content !important; min-width: 260px; max-width: 80%; margin: 0 auto 0 0 !important; }}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) {{ flex-direction: row-reverse; }}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] {{
  background: var(--bubble-me); border: none; border-radius: 18px 4px 18px 18px; margin: 0 0 0 auto !important; }}
[data-testid="stChatMessage"]:has([data-testid="stChatMessageAvatarUser"]) [data-testid="stChatMessageContent"] * {{
  color: var(--bubble-me-text) !important; }}
@keyframes pop {{ from {{ opacity:0; transform: translateY(6px) scale(.99); }} to {{ opacity:1; transform:none; }} }}
.msg-head {{ display:flex; align-items:center; gap:8px; margin-bottom:4px; font-weight:600; font-size:.84rem; }}
.msg-head .nm {{ color: var(--c); }}
.av, .stApp .av {{ color:#fff !important; }}
.av {{ display:inline-grid; place-items:center; border-radius:50%; font-weight:700; color:#fff;
  background: linear-gradient(135deg, var(--c), color-mix(in srgb, var(--c) 55%, #000)); flex:none;
  box-shadow: 0 3px 10px color-mix(in srgb, var(--c) 40%, transparent); }}
[data-testid="stChatMessageContent"] p {{ margin:.15rem 0; line-height:1.55; }}
[data-testid="stChatMessageContent"] audio {{ height:34px; width:100%; margin-top:.4rem; }}

/* ---- chat input ---- */
[data-testid="stChatInput"] {{ background: var(--surface) !important; border:1px solid var(--border) !important;
  border-radius: 16px !important; box-shadow: var(--shadow); }}
[data-testid="stChatInput"] div, [data-testid="stChatInput"] textarea {{ background: transparent !important; }}
[data-testid="stChatInput"] textarea {{ color: var(--text) !important; -webkit-text-fill-color: var(--text) !important; }}
[data-testid="stChatInput"] textarea::placeholder {{ color: var(--muted) !important; -webkit-text-fill-color: var(--muted) !important; }}
[data-testid="stChatInput"] svg {{ fill: var(--muted); }}
[data-testid="stChatInput"]:focus-within {{ border-color: var(--accent) !important; box-shadow: 0 0 0 3px var(--accent-soft) !important; }}
[data-testid="stChatInputSubmitButton"]:not(:disabled) {{ background: linear-gradient(135deg, var(--accent), var(--accent2)) !important; }}
[data-testid="stChatInputSubmitButton"]:not(:disabled) svg {{ fill:#fff; }}
[data-testid="stBottom"] > div, [data-testid="stBottomBlockContainer"] {{ background: transparent !important; }}

/* ---- misc widgets ---- */
[data-testid="stAlert"] {{ border-radius: 14px; border:1px solid var(--border); }}
[data-testid="stToast"] {{ background: var(--surface) !important; border:1px solid var(--border); border-radius:14px; }}
[data-testid="stSlider"] [role="slider"] {{ background: var(--accent) !important; }}
[data-testid="stTooltipContent"] {{ background: var(--surface) !important; color: var(--text) !important; }}
::-webkit-scrollbar {{ width:10px; height:10px; }}
::-webkit-scrollbar-thumb {{ background: var(--border); border-radius:10px; border:2px solid transparent; background-clip:content-box; }}

/* ---- world events (manifestations) ---- */
.world {{ margin: .9rem auto; max-width: 82%; text-align:center; padding: .8rem 1.2rem; border-radius: 16px; position:relative;
  background: linear-gradient(var(--surface), var(--surface)) padding-box, linear-gradient(135deg, var(--accent), var(--accent2), #ffb454) border-box;
  border: 1.5px solid transparent; box-shadow: 0 0 28px var(--glow); animation: pop .5s ease-out; }}
.world .w-label {{ font-size:.68rem; font-weight:700; letter-spacing:.14em; text-transform:uppercase;
  background: linear-gradient(90deg, var(--accent), var(--accent2)); -webkit-background-clip:text; background-clip:text;
  -webkit-text-fill-color: transparent; }}
.world .w-label::before {{ content:"\\2726  "; }}
.world .w-name {{ font-size:1.12rem; font-weight:700; margin-top:2px; color: var(--text) !important; }}
.world .w-desc {{ font-size:.88rem; color: var(--muted) !important; margin-top:3px; line-height:1.45; }}
.world.banish {{ background: var(--surface2); border:1px dashed var(--border); box-shadow:none; opacity:.85; }}
.world.banish .w-label {{ background:none; -webkit-text-fill-color: var(--muted); color: var(--muted); }}
.world.banish .w-label::before {{ content:"\\2727  "; }}
.world.banish .w-name {{ text-decoration: line-through; color: var(--muted) !important; }}

/* ---- app-specific bits ---- */
.chip {{ display:inline-flex; align-items:center; gap:6px; padding:4px 10px; border-radius:999px; font-size:.78rem;
  font-weight:600; background: var(--accent-soft); color: var(--accent) !important; border:1px solid transparent; margin-right:6px; }}
.chip.muted {{ background: var(--surface2); color: var(--muted) !important; border-color: var(--border); }}
.scene-card {{ background: var(--surface2); border:1px dashed var(--border); border-radius:12px; padding:.7rem .9rem;
  font-size:.86rem; color: var(--muted) !important; line-height:1.5; font-style: italic; }}
.card-head {{ display:flex; align-items:center; gap:12px; margin-bottom:.45rem; }}
.card-head .t {{ font-weight:700; font-size:1.02rem; }}
.card-head .s {{ font-size:.76rem; color: var(--muted) !important; }}
.persona {{ font-size:.86rem; color: var(--muted) !important; line-height:1.5; min-height: 2.6em; }}
.room-title {{ display:flex; align-items:center; gap:10px; margin: 0 0 .5rem; }}
.room-title .t {{ font-size:1.15rem; font-weight:700; }}
.section-label {{ font-size:.72rem; font-weight:700; letter-spacing:.09em; text-transform:uppercase; color: var(--muted) !important; margin:.2rem 0 .5rem; }}
#ar-dev {{ display:flex; flex-direction:column; gap:.7rem; }}
#ar-dev .ar-field label {{ display:block; font-size:.85rem; margin-bottom:4px; color: var(--text); }}
#ar-dev select {{ width:100%; padding:9px 10px; border-radius:12px; border:1px solid var(--border);
  background: var(--surface2); color: var(--text); font: inherit; font-size:.9rem; }}
#ar-dev select:focus {{ outline:none; border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-soft); }}
#ar-dev select:disabled {{ opacity:.5; }}
#ar-dev .ar-btn {{ padding:9px 12px; border-radius:12px; border:1px solid var(--border); background: var(--surface2);
  color: var(--text); font: inherit; font-weight:600; font-size:.88rem; cursor:pointer; transition: all .15s; }}
#ar-dev .ar-btn:hover {{ border-color: var(--accent); color: var(--accent); }}
#ar-dev .ar-note {{ font-size:.8rem; color: var(--muted); line-height:1.4; }}
.st-key-player {{ height:0; overflow:hidden; margin:0 !important; }}
</style>
"""
