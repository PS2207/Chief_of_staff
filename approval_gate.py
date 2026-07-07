"""
approval_gate.py — Human in the Loop approval gate for the AI email ghostwriter.

Lets the user select a thread, generate a draft, and approve / edit / reject it.
NEVER auto-sends without human approval.
"""

import json
import os
import sys
from datetime import datetime

import streamlit as st

from context_builder import assemble_context, format_thread_history
from draft_machine import SAMPLE_THREADS, draft_reply_groq, DRAFTING_RULES
from approval_utils import save_approved_draft, load_approved_drafts

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------
st.set_page_config(page_title="Approval Gate — Email Ghostwriter", layout="wide")

# ---------------------------------------------------------------------------
# Styles
# ---------------------------------------------------------------------------
st.markdown(
    """
<style>
    /* Dark theme base */
    .stApp {
        background-color: #1a1a2e;
        color: #e0e0e0;
    }
    .stApp h1, .stApp h2, .stApp h3, .stApp h4 {
        color: #e0e0e0;
    }
    .stApp .stTextArea textarea, .stApp .stSelectbox,
    .stApp .stButton button, .stApp .stTextInput input {
        background-color: #16213e;
        color: #e0e0e0;
        border-color: #0f3460;
    }
    .stApp .stButton button {
        border-radius: 6px;
        font-weight: 600;
        padding: 0.35rem 1.2rem;
    }
    /* Thread message box */
    .thread-box {
        background-color: #16213e;
        border-left: 3px solid #0f3460;
        border-radius: 6px;
        padding: 12px 16px;
        margin-bottom: 12px;
    }
    .thread-box .sender {
        font-weight: 600;
        color: #e94560;
        font-size: 0.9rem;
    }
    .thread-box .date {
        color: #888;
        font-size: 0.75rem;
        margin-bottom: 6px;
    }
    .thread-box .body {
        color: #ccc;
        font-size: 0.85rem;
        white-space: pre-wrap;
    }
    /* Draft display */
    .draft-box {
        background-color: #16213e;
        border: 1px solid #0f3460;
        border-radius: 8px;
        padding: 16px 20px;
        margin-top: 8px;
        min-height: 180px;
        white-space: pre-wrap;
        color: #e0e0e0;
        font-size: 0.9rem;
        line-height: 1.5;
    }
    /* Status indicators */
    .status-approved {
        background-color: #1b5e20;
        color: #a5d6a7;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: 600;
        text-align: center;
    }
    .status-rejected {
        background-color: #b71c1c;
        color: #ef9a9a;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: 600;
        text-align: center;
    }
    .status-none {
        background-color: #333;
        color: #999;
        padding: 8px 16px;
        border-radius: 6px;
        font-weight: 600;
        text-align: center;
    }
    .section-header {
        color: #e94560;
        font-weight: 700;
        font-size: 1.1rem;
        margin-bottom: 10px;
        border-bottom: 1px solid #0f3460;
        padding-bottom: 4px;
    }
    .stButton button,
    .stSelectbox *,
    button,
    a {
    cursor: pointer !important;
     }
</style>
""",
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# State initialisation
# ---------------------------------------------------------------------------
DEFAULT_STATE = {
    "draft": None,
    "status": "none",        # none | approved | editing | rejected
    # "selected_label": SAMPLE_THREADS[0]["label"],
     "selected_label": "-- Select Thread --",
    "generation_count": 0,
    "api_key": None,
    "custom_json": "",
    "draft_metadata": None,
}

for key, value in DEFAULT_STATE.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
def get_thread_by_label(label):
    """Return the thread dict matching the given label."""
    for t in SAMPLE_THREADS:
        if t["label"] == label:
            return t
    # return SAMPLE_THREADS[0]
    return None


# def load_approved_drafts():
#     """Load previously approved drafts from the JSON file."""
#     path = os.path.join(os.path.dirname(__file__), "approved_drafts.json")
#     if os.path.exists(path):
#         with open(path, "r", encoding="utf-8") as f:
#             return json.load(f)
#     return []


# def save_approved_draft(draft_text, subject, replying_to, model, edited=False):
#     """Append an approved draft to approved_drafts.json with a timestamp."""
#     path = os.path.join(os.path.dirname(__file__), "approved_drafts.json")
#     drafts = load_approved_drafts()
#     drafts.append(
#         {
#             "draft": draft_text,
#             "subject": subject,
#             "replying_to": replying_to,
#             "model": model,
#             "edited": edited,
#             "approved_at": datetime.now().isoformat(),
#         }
#     )
#     with open(path, "w", encoding="utf-8") as f:
#         json.dump(drafts, f, indent=2)


def resolve_api_key():
    """Return the API key from secrets, env, or session state."""
    # st.secrets for Streamlit Cloud
    try:
        return st.secrets["GROQ_API_KEY"]
    except (FileNotFoundError, KeyError):
        pass
    # Environment variable
    key = os.environ.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    if key:
        return key
    # Session state (password input)
    return st.session_state.get("api_key")


# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
st.title("📧 Approval Gate — AI Email Ghostwriter")
st.caption("Review, approve, edit, or reject AI-generated draft replies. Never auto-send without human approval.")

# --- Sidebar ---
with st.sidebar:
    st.header("📁 Thread Selection")

    # Dropdown for sample threads
    # labels = [t["label"] for t in SAMPLE_THREADS]
    labels = ["-- Select Thread --"] + [t["label"] for t in SAMPLE_THREADS]
    selected_label = st.selectbox(
        "Choose a sample thread:",
        labels,
        index=labels.index(st.session_state.selected_label)
        if st.session_state.selected_label in labels
        else 0,
        key="side_select",
    )

    # Custom JSON text area
    custom_json = st.text_area(
        "Or paste custom thread JSON:",
        value=st.session_state.custom_json,
        height=120,
        placeholder='{"subject": "...", "messages": [...]}',
        key="side_json",
    )

    # API key
    st.divider()
    st.header("🔑 API Key")
    resolved_key = resolve_api_key()
    if resolved_key:
        st.success("API key loaded", icon="✔️")
    else:
        api_key_input = st.text_input(
            "Enter GROQ_API_KEY:",
            type="password",
            placeholder="gsk_...",
            key="side_api_input",
        )
        if api_key_input:
            st.session_state.api_key = api_key_input

    # Generate button
    st.divider()
    gen_col1, gen_col2 = st.columns([3, 1])
    with gen_col1:
        generate_clicked = st.button("🚀 Generate Draft", type="primary", use_container_width=True)
    with gen_col2:
        st.metric("Generations", st.session_state.generation_count)

# Determine which thread to use
if custom_json.strip():
    try:
        active_thread = json.loads(custom_json.strip())
    except json.JSONDecodeError:
        st.sidebar.error("Invalid JSON in custom thread area")
        active_thread = get_thread_by_label(selected_label)
else:
    active_thread = get_thread_by_label(selected_label)
    # Update selected label
    st.session_state.selected_label = selected_label


# --- Draft generation ---
if generate_clicked:
    if active_thread is None:
        st.warning("Please select a thread first.")
    else:
        api_key = resolve_api_key()
        if not api_key:
           st.error("❌ No GROQ_API_KEY found. Enter a GROQ API key in the sidebar to generate drafts.")
        else:
          with st.spinner("✍️ Generating draft..."):
            try:
                result = draft_reply_groq(active_thread, api_key=api_key)
                st.session_state.draft = result
                st.session_state.status = "none"
                st.session_state.generation_count += 1
                st.session_state.draft_metadata = {
                    "model": "llama-3.3-70b-versatile",
                    "subject": active_thread["subject"],
                    "replying_to": active_thread["messages"][-1]["from"]
                    if active_thread["messages"]
                    else "unknown",
                    "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"), #add
}
                
                st.rerun()
            except Exception as e:
                st.error(f"❌ Generation failed: {e}")


# --- Two-column layout ---
col_left, col_right = st.columns(2)

# --- LEFT COLUMN: Thread history ---
# with col_left:
#     st.markdown('<div class="section-header">💬 Email Thread</div>', unsafe_allow_html=True)
#     st.markdown(f"**Subject:** {active_thread['subject']}")

#     for msg in active_thread["messages"]:
#         st.markdown(
#             f"""
#             <div class="thread-box">
#                 <div class="sender">{msg['from']}</div>
#                 <div class="date">{msg['date']}</div>
#                 <div class="body">{msg['body']}</div>
#             </div>
#             """,
#             unsafe_allow_html=True,
#         )
with col_left:
    st.markdown('<div class="section-header">💬 Email Thread</div>', unsafe_allow_html=True)

    if active_thread is None:
        # st.info("👈 Pick a thread in the sidebar.")
        st.info("Select a sample thread from the sidebar or paste custom thread JSON.")
    else:
        st.markdown(f"**Subject:** {active_thread['subject']}")

        for msg in active_thread["messages"]:
            st.markdown(
                f"""
                <div class="thread-box">
                    <div class="sender">{msg['from']}</div>
                    <div class="date">{msg['date']}</div>
                    <div class="body">{msg['body']}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
# --- RIGHT COLUMN: Draft ---
with col_right:
    st.markdown('<div class="section-header">✍️ Draft Reply</div>', unsafe_allow_html=True)
    if active_thread is None:
       st.info("👈 Pick a thread in the sidebar.")
    elif st.session_state.draft is None:
        st.markdown(
            '<div class="draft-box" style="color: #666; display: flex; align-items: center; justify-content: center;">'
            "Select a thread and click <strong>Generate Draft</strong> to see the AI's reply here."
            "</div>",
            unsafe_allow_html=True,
        )
    else:
        # --- Status indicator ---
        status = st.session_state.status
        if status == "approved":
            st.markdown(
                '<div class="status-approved">✅ APPROVED — Ready to send</div>',
                unsafe_allow_html=True,
            )
        elif status == "rejected":
            st.markdown(
                '<div class="status-rejected">❌ REJECTED — Draft discarded. Click Generate to try again.</div>',
                unsafe_allow_html=True,
            )
        elif status == "editing":
            st.markdown(
                '<div class="status-none">✏️ EDITING — Modify the draft below</div>',
                unsafe_allow_html=True,
            )
        else:
            st.markdown(
                '<div class="status-none">⏳ PENDING REVIEW</div>',
                unsafe_allow_html=True,
            )

        # --- Draft content or edit text area ---
        if status == "editing":
            edited_text = st.text_area(
                "Edit the draft:",
                value=st.session_state.draft,
                height=220,
                key="edit_area",
            )

            # Approve edited version button
            if st.button("✅ Approve Edited Version", type="primary", use_container_width=True):
                meta = st.session_state.draft_metadata or {}
                save_approved_draft(
                    draft_text=edited_text,
                    subject=meta.get("subject", active_thread["subject"]),
                    replying_to=meta.get("replying_to", "unknown"),
                    model=meta.get("model", "llama-3.3-70b-versatile"),
                    edited=True,
                )
                st.session_state.draft = edited_text
                st.session_state.status = "approved"
                st.rerun()

        else:
            st.markdown(
                f'<div class="draft-box">{st.session_state.draft}</div>',
                unsafe_allow_html=True,
            )

        # --- Metadata line ---
        if st.session_state.draft_metadata:
            meta = st.session_state.draft_metadata
            st.caption(
                f"Model: {meta['model']}  ·  "
                f"Subject: {meta['subject']}  ·  "
                f"Replying to: {meta['replying_to']}  ·  "
                f"Generated: {meta['generated_at']}"
            )

        # --- Action buttons (only when NOT editing) ---
        # if status != "editing":
        if status not in ["editing", "approved"]:    
            btn_col1, btn_col2, btn_col3 = st.columns(3)

            with btn_col1:
                if st.button("✅ Approve", use_container_width=True, type="primary"):
                    meta = st.session_state.draft_metadata or {}
                    save_approved_draft(
                        draft_text=st.session_state.draft,
                        subject=meta.get("subject", active_thread["subject"]),
                        replying_to=meta.get("replying_to", "unknown"),
                        model=meta.get("model", "llama-3.3-70b-versatile"),
                        edited=False,
                    )
                    st.session_state.status = "approved"
                    st.rerun()

            with btn_col2:
                if st.button("✏️ Edit", use_container_width=True):
                    st.session_state.status = "editing"
                    st.rerun()

            with btn_col3:
                if st.button("🗑️ Reject", use_container_width=True):
                    st.session_state.status = "rejected"
                    st.rerun()


# ---------------------------------------------------------------------------
# Footer: show approved drafts log
# ---------------------------------------------------------------------------
st.divider()
with st.expander("📋 Approved Drafts Log"):
    drafts = load_approved_drafts()
    if drafts:
        for i, d in enumerate(reversed(drafts[-10:]), 1):
            edited_flag = "✏️ (edited)" if d.get("edited") else ""
            st.markdown(
                f"**{i}. [{d['approved_at']}]** {d['subject']} → {d['replying_to']} {edited_flag}"
            )
            st.code(d["draft"], language="text")
    else:
        st.info("No approved drafts yet. Approve one to see it here.")
  
if st.button("🔄 Reset Session"):
    st.session_state.draft = None
    st.session_state.status = "none"
    st.session_state.draft_metadata = None
    st.session_state.selected_label = "-- Select Thread --"
    st.session_state.custom_json = ""
    st.rerun()
    
# if st.button("🔄 Reset Session"):
#     st.session_state.draft = None
#     st.session_state.status = "none"
#     st.session_state.draft_metadata = None
#     st.session_state.selected_label = "-- Select Thread --"
#     st.session_state.custom_json = ""

#     path = os.path.join(
#         os.path.dirname(__file__),
#         "approved_drafts.json"
#     )

#     if os.path.exists(path):
#         os.remove(path)

#     st.rerun()           