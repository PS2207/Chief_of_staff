"""
app.py — 'The Draft Desk' Streamlit UI for the AI Email Ghostwriter.

Combines triage, draft generation, approval gate, and export into one dashboard.
"""
import pandas as pd
import json
import os
import sys
from datetime import datetime
import time
import traceback
import streamlit as st

from engine import (
    fetch_threads,
    # fetch_gmail_threads,
    send_reply,
    save_threads_to_json,
    save_threads_to_csv,
    save_threads_to_db,
)
# ── Imports from the Chief-of-Staff modules ──────────────────────────────
sys.path.insert(0, os.path.dirname(__file__))

from triage import triage_inbox
from context_builder import assemble_context, format_thread_history
from draft_machine import draft_reply, generate_sample_draft,  draft_reply_with_metadata, draft_reply_with_metadata_groq
from email.utils import parseaddr
from approval_utils import save_approved_draft, load_approved_drafts

from constants import (
    FILE_PREFIX_GMAIL,
    FILE_PREFIX_SAMPLE,
    PRIORITY_UNKNOWN,
    SOURCE_SAMPLE,
    SOURCE_GMAIL,
    PRIORITY_URGENT,
    PRIORITY_NEEDS_REPLY,
    PRIORITY_FYI,
    PRIORITY_IGNORE,
    PHASE_INBOX,
    PHASE_DRAFT,
    PHASE_APPROVAL,
    PHASE_EXPORT,
    STATUS_APPROVED,
    STATUS_DRAFT,
    STATUS_NONE,
    STATUS_REJECTED,
    STATUS_SENT

)

DEFAULT_EMAIL_FETCH_LIMIT = int(os.getenv("EMAIL_FETCH_LIMIT", "5"))

# in this file, has 10 functions:-
# 1) _get_calendar_engine()
# 2) normalize_thread_id(t)
# 3) load_sample_threads(limit=None)
# 4) navigate_to(phase: str)  
# 5) get_thread_by_id(thread_id: str) 
# 6) get_draft_status(thread_id: str)  
# 7) get_file_prefix(source) get_actionable_threads()
# 8) run_full_pipeline(email_limit, status)
# 9) generate_proof_markdown() 
# 10) generate_proof_html()

@st.cache_resource
def _get_calendar_engine():
    import calendar_engine
    return calendar_engine

from task_logger import log_action, get_action_log #action_log.json file 
# from helper import get_draft_error_message
from helper import (
    normalize_thread_id,
    get_thread_by_id,
    get_draft_error_message,
)
from proof_export import (
    generate_proof_markdown,
    generate_proof_html,
)
   
# ---------------------------------------------------------------------------
# Page configuration
# ---------------------------------------------------------------------------
st.set_page_config(
    page_title="The Draft Desk",
    page_icon="✍️",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Helper: load sample threads
# ---------------------------------------------------------------------------
def load_sample_threads(limit=None):
    print("load_sample_threads limit =", limit)
    """Load the 5 demo email threads from sample_threads.json."""
    path = os.path.join(os.path.dirname(__file__), "sample_threads.json")
    if not os.path.exists(path):
        st.error(f"sample_threads.json not found at {path}")
        return []
    with open(path, "r", encoding="utf-8") as f:
        threads = json.load(f)
    # adding
    if limit is not None:
        threads = threads[:limit]

    return threads


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------
defaults = {
    "threads": [],
    "triaged": {},          # dict by priority: {"urgent": [...], "needs-reply": [...], ...}
    "drafts": {},           # dict keyed by thread id -> draft text
    "approved": {},         # dict keyed by thread id -> approved draft text 
    "rejected": set(),
    "sent": set(),# add set of thread ids that were rejected
    "current_phase": PHASE_INBOX,
    "source": SOURCE_SAMPLE,
    "selected_thread_id": None,
    "triage_done": False,
    "api_key": None,
#   for calendar  
    "booked": {},
    
    # "pipeline_running": False,
    "run_pipeline": False,
    "pipeline_logs": [],
   
}

for key, value in defaults.items():
    if key not in st.session_state:
        st.session_state[key] = value


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------
def navigate_to(phase: str):
    """Set the current phase and trigger a rerun."""
    st.session_state.current_phase = phase



def get_draft_status(thread_id: str) -> str:
    """Return a status label for a thread: 'draft', 'approved', 'rejected', or 'none'."""
    if thread_id in st.session_state.rejected:
        return STATUS_REJECTED
    if thread_id in st.session_state.sent:
        return STATUS_SENT
    if thread_id in st.session_state.approved:
        return STATUS_APPROVED
    if thread_id in st.session_state.drafts:
        return STATUS_DRAFT
    return "none"
#----------------------------------------------------------------
def get_file_prefix(source):
    mapping = {
         SOURCE_SAMPLE : FILE_PREFIX_SAMPLE,
         SOURCE_GMAIL : FILE_PREFIX_GMAIL,
    }
    return mapping.get(source, "threads")
#------------------------------------------------------------------

def get_actionable_threads():
    """Return all urgent and needs-reply threads from triaged."""
    result = []
    for prio in (PRIORITY_URGENT, PRIORITY_NEEDS_REPLY):
        result.extend(st.session_state.triaged.get(prio, []))
    return result
# ---------------Adding for pipeline-----------------------------------------------------
def run_full_pipeline(email_limit, status):
    """
    Fetch -> Triage -> Generate Drafts -> Stop at Approval Gate.
    Returns a list of log strings.
    """
    print("parameter email_limit =", email_limit)
    print("session email_limit =", st.session_state.email_limit)
    print("=" * 60)
    print("email_limit received:", email_limit)
    print("=" * 60)
    logs = []

    # ----------------------------------------------------
    # Step 1: Fetch threads
    # ----------------------------------------------------
    try:
        status.update(
         label="Step 1/3 - Fetching threads...",
         state="running",
        )
        if st.session_state.source == SOURCE_SAMPLE:
            threads = load_sample_threads(email_limit)
            st.write("email_limit =", email_limit)#for debug 2 lines
            st.write("threads loaded =", len(threads))
            logs.append(f"✅ Loaded {len(threads)} sample thread(s).")

        else:
            threads = fetch_threads(max_results=email_limit)
            logs.append(f"✅ Loaded {len(threads)} Gmail thread(s).")

        st.session_state.threads = threads
        st.write("session threads =", len(st.session_state.threads))#for debug

        total = max(1, len(threads))

        status.update(
          label=f"Step 1/3 - Fetching threads ({len(threads)})",
          state="running",
        )

        # status.write(f"✅ Loaded {len(threads)} thread(s)")
        st.session_state.pipeline_logs.append(f"Fetched {len(threads)} threads")
    except Exception as e:
        logs.append(f"❌ Failed to load threads: {e}")
        return logs

    # ----------------------------------------------------
    # Step 2: Prepare triage input
    # ----------------------------------------------------
    try:

        temp_flat = []

        if st.session_state.source == SOURCE_SAMPLE:

            for t in threads:
                msgs = t.get("messages", [])
                first = msgs[0] if msgs else {}
                last = msgs[-1] if msgs else {}

                temp_flat.append({
                    "sender": first.get("from", ""),
                    "subject": t.get("subject", ""),
                    "snippet": last.get("body", "")[:200],
                })

        else:

            for ft in threads:
                last = ft["messages"][-1] if ft["messages"] else {}

                temp_flat.append({
                    "sender": last.get("from", ""),
                    "subject": last.get("subject", ""),
                    "snippet": last.get("body", ""),
                })

        # status.write("🧠 Triaging emails...")
        # classified = triage_inbox(temp_flat)
        # status.write("✅ Threads classified")
        status.update(
           label="Step 2/3 - Triaging threads...",
           state="running"
        )
        # ------------------------------
        if st.session_state.source == SOURCE_SAMPLE:
            sample_priorities = {
             "CRITICAL: Customer Payments Failing After Latest Deployment":
            {"priority": PRIORITY_URGENT, "category": "production", "reason": "Production outage."},

           "URGENT: Suspicious Login Activity Detected":
            {"priority": PRIORITY_URGENT, "category": "security", "reason": "Security incident."},

           "Q4 Product Roadmap Feedback Needed":
            {"priority": PRIORITY_NEEDS_REPLY, "category": "planning", "reason": "Reply requested."},

           "Vendor Renewal Decision Required":
            {"priority": PRIORITY_NEEDS_REPLY, "category": "procurement", "reason": "Approval required."},

           "Meeting Request: AI Dashboard Prototype Review":
            {"priority": PRIORITY_NEEDS_REPLY, "category": "meeting", "reason": "Meeting request."},
           }

            classified = []

            for t in threads:
               classified.append(
                  sample_priorities.get(
                    t["subject"],
                  {
                    "priority": PRIORITY_FYI,
                    "category": "information",
                    "reason": "Informational update."
                   }
            )
        )
        else:
       # -----------------------------------------         
           classified = triage_inbox(temp_flat)
        st.session_state.pipeline_logs.append(
           f"Triaged {len(threads)} threads"
        )

        triaged = {
            PRIORITY_URGENT: [],
            PRIORITY_NEEDS_REPLY: [],
            PRIORITY_FYI: [],
            PRIORITY_IGNORE: [],
            PRIORITY_UNKNOWN: [],
        }

        for i, t in enumerate(threads):
            t["priority"] = classified[i].get("priority", PRIORITY_UNKNOWN)
            t["category"] = classified[i].get("category", "")
            t["reason"] = classified[i].get("reason", "")

            triaged.setdefault(
                t["priority"],
                []
            ).append(t)

        st.session_state.triaged = triaged
        st.session_state.triage_done = True
        logs.append(
          f"Urgent={len(triaged[PRIORITY_URGENT])}, "
          f"Needs Reply={len(triaged[PRIORITY_NEEDS_REPLY])}, "
          f"FYI={len(triaged[PRIORITY_FYI])}, "
          f"Ignore={len(triaged[PRIORITY_IGNORE])}, "
          f"Unknown={len(triaged[PRIORITY_UNKNOWN])}"
         )
     

    except Exception as e:
        logs.append(f"❌ Triage failed: {e}")
        return logs

    # ----------------------------------------------------
    # Step 3: Reset downstream state
    # ----------------------------------------------------
    st.session_state.drafts = {}
    st.session_state.approved = {}
    st.session_state.rejected = set()
    st.session_state.sent = set()
    st.session_state.booked = {}

    logs.append("✅ Reset draft state.")

    # ----------------------------------------------------
    # Step 4: Draft generation
    # ----------------------------------------------------
    actionable = []

    actionable.extend(triaged.get(PRIORITY_URGENT, []))
    actionable.extend(triaged.get(PRIORITY_NEEDS_REPLY, []))
    success = 0
    failed = 0
    # logs.append(f"✍️ Generating {len(actionable)} draft(s)...")
    if actionable:
        logs.append(f"✍️ Generating {len(actionable)} draft(s)...")  
        print("Threads:", len(threads))
        print("Urgent:", len(triaged.get(PRIORITY_URGENT, [])))
        print("Needs Reply:", len(triaged.get(PRIORITY_NEEDS_REPLY, [])))
        print("Actionable:", len(actionable))
        
        for i, thread in enumerate(actionable, start=1):
            subject = thread.get("subject", "(No subject)")
            status.update(
              label=f"Step 3/3 - Drafting replies {i}/{len(actionable)}: {subject}",
              state="running",
            )

            logs.append(
              f"Draft {i}/{len(actionable)} : {thread.get('subject','No subject')}"
            )
       
            try:
            
                thread_id = normalize_thread_id(thread)
                
                if st.session_state.source == SOURCE_SAMPLE:
                    draft = generate_sample_draft(thread)
                else:
                   draft = draft_reply(thread)

                # draft = draft_reply(thread)

                if not draft or not str(draft).strip():
                   raise ValueError("Draft content is empty.")  
                    
                st.session_state.drafts[thread_id] = draft

                success += 1
                status.write(
                    f"✅ Draft {i}/{len(actionable)} completed"
                )
                logs.append(
                    f"   ✔ Draft {i}/{len(actionable)} : {thread.get('subject','(No subject)')}"
                )

            except Exception as e:
                failed += 1
                #aading for debuging for not draft gamil messg
                print("=" * 80)
                print("REAL ERROR")
                print(type(e))
                print(e)
                print("="*80)
                
            # print("Draft generation error:", e)  this is for terminal error
                logs.append(
                    # f"⚠️ Draft {i}/{len(actionable)} could not be generated. {get_draft_error_message(e)}"
                    f"⚠️ Draft {i}/{len(actionable)} could not be generated."
                )
                logs.append(str(e))
    else:
        logs.append("ℹ️ No actionable emails found. Draft generation skipped.")  
              

    # ----------------------------------------------------
    # Step 5: Move to Approval Gate
    # ----------------------------------------------------
    # st.session_state.current_phase = PHASE_APPROVAL

    if success:
      label = "Pipeline completed - drafts ready for review"
    else:
      label = "Pipeline completed"

    status.update(
      label=label,
      state="complete",
      expanded=False,
    )
    # show on UI after pipeline complete
    logs.append("")
    logs.append("────────────────────────")
    
    if success == len(actionable):
      logs.append("Pipeline completed successfully.")
    elif success > 0:
      logs.append("Pipeline completed with partial success.")
    else:
      logs.append("Pipeline completed.")
      
    logs.append(f"Drafts Generated: {success} of {len(actionable)}")

    if failed:
       logs.append(f"Failed Drafts: {failed}")
    
    if len(actionable) == 0:
       logs.append("ℹ️ No actionable emails were found.")
       logs.append("Nothing requires approval.")
       
    elif success > 0:
       logs.append(f"✅ {success} draft(s) ready for review.")
       if failed:
           logs.append(f"⚠️ {failed} draft(s) could not be generated.")
    else:
       logs.append("⚠️ Draft generation failed.")
       logs.append("No drafts were generated because the AI service could not complete the requests.")

    return logs
#---------------after pull triage code------------------------------------------------------------------------------------------
# ---------------------------------------------------------------------------
# UI — Sidebar
# ---------------------------------------------------------------------------
with st.sidebar:
        
    st.title("✍️ The Draft Desk")
    st.caption("AI-powered email copilot")
        # ==========================================================
    # Run Full Pipeline
    # ==========================================================
    email_limit = st.number_input(
        "Emails to fetch",
        min_value=1,
        max_value=50,
        value=DEFAULT_EMAIL_FETCH_LIMIT,
        step=1,
        key="email_limit"
    )

    st.divider()

    if st.button(
       "🚀 Run Full Pipeline",
       use_container_width=True,
       type="primary",
    ):
      
        st.session_state.run_pipeline = True
        
        st.session_state.current_phase = PHASE_INBOX
        st.rerun()

    st.caption(
      "Fetch emails, triage priorities, generate AI drafts, and review before sending."
    )
 
    st.divider()

    source = st.radio(
        "Source",
        options=[SOURCE_SAMPLE , SOURCE_GMAIL],
        index=0 if st.session_state.source == SOURCE_SAMPLE else 1,
        key="source_radio",
        on_change=lambda: setattr(
            st.session_state,
            "source",
            st.session_state.source_radio,
        ),
    )
    # email_limit = st.number_input(
    #     "Emails to fetch",
    #     min_value=1,
    #     max_value=50,
    #     value=DEFAULT_EMAIL_FETCH_LIMIT,
    #     step=1,
    #     key="email_limit"
    # )
    # st.write("Sidebar email_limit =", email_limit)
    # st.write("Session email_limit =", st.session_state.email_limit)
    st.divider()

    st.subheader("🧭 Navigation")

    phases = [
        (PHASE_INBOX, "📥 Inbox & Triage"),
        (PHASE_DRAFT, "✍️ Draft Generation"),
        (PHASE_APPROVAL, "✅ Approval Gate"),
        (PHASE_EXPORT, "📤 Export Proof"),
    ]

    for phase_key, phase_label in phases:
        if st.button(
            phase_label,
            key=f"nav_{phase_key}",
            use_container_width=True,
            type="primary" if st.session_state.current_phase == phase_key else "secondary",
        ):
            navigate_to(phase_key)
            st.rerun()

    st.divider()

    loaded = len(st.session_state.threads)
    triaged = sum(len(v) for v in st.session_state.triaged.values())
    drafts = len(st.session_state.drafts)
    approved = len(st.session_state.approved)
    rejected = len(st.session_state.rejected)

    # st.subheader("📊 Workflow Status")
    # st.write(f"Loaded: **{loaded}** thread(s)")
    # st.write(f"Triaged: **{triaged}**")
    # st.write(f"Drafts: **{drafts}**")
    # st.write(f"Approved: **{approved}**")
    # st.write(f"Rejected: **{rejected}**")
    
    col1, col2 = st.columns(2)

    col1.metric("Loaded", loaded)
    col2.metric("Triaged", triaged)

    col1, col2 = st.columns(2)

    col1.metric("Drafts", drafts)
    col2.metric("Approved", approved)

    st.metric("Rejected", rejected)

    st.divider()

    # KEEP YOUR EXISTING API KEY CODE HERE
    # KEEP YOUR RESET SESSION BUTTON HERE

# ---------------------------------------------------------------------------------------
    # API key input (only visible when source is Gmail or when generating drafts)
    st.markdown("**🔑 API Key**")
    resolved_key = os.environ.get("GROQ_API_KEY") or os.getenv("GROQ_API_KEY")
    if resolved_key:
        st.success("API key loaded from env", icon="✔️")
    else:
        api_key_input = st.text_input(
            "GROQ_API_KEY:",
            type="password",
            placeholder="gsk_...",
            key="sidebar_api_key",
            label_visibility="collapsed",
        )
        if api_key_input:
            st.session_state.api_key = api_key_input

    if st.button("🔄 Reset Session", use_container_width=True):
        for key in defaults:
            st.session_state[key] = defaults[key]     
        st.session_state.pop("flat_threads", None)    
        st.rerun()

    if st.session_state.pipeline_logs:
        st.divider()
        with st.expander( "⚙️ Pipeline Execution Log",   expanded=False,):
            for line in st.session_state.pipeline_logs:
                st.write(line)
# ---------------------------------------------------------------------------
# PHASE 1 — Inbox & Triage
# ---------------------------------------------------------------------------
if st.session_state.current_phase == PHASE_INBOX:
    st.title("📥 Inbox & Triage")
    st.caption("Pull emails from your source, then triage them by priority.")
    
    if st.session_state.run_pipeline:
        st.subheader("🚀 Full Pipeline")
        st.write(
            "Pull threads from the selected source, "
            "then triage them by priority. "
            "Once triaged, the highest-priority threads "
            "move to Draft Generation."
        )
        with st.status("🚀 Running Full Pipeline...", expanded=True) as status:
            st.session_state.pipeline_logs = run_full_pipeline(email_limit,status,)
            st.session_state.run_pipeline = False 
           
            
            navigate_to(PHASE_APPROVAL)   
            
            st.rerun()
            # status.update(
            #  label="✅ Pipeline Complete",
            #  state="complete",
            #  expanded=True,
            # )     

    st.divider()
    
    # ── Pull & Triage button ──────────────────────────────────────────
    col1, col2, col3 = st.columns([1, 1, 3])
    with col1:
        if st.button("🔍 Pull & Triage", type="primary", use_container_width=True):
            with st.spinner("Fetching email threads......"):

                if st.session_state.source == SOURCE_SAMPLE:
                    # print("email_limit received =", email_limit)
                    #for debug
                    threads = load_sample_threads(email_limit)
                    # print("threads loaded =", len(threads))
                    st.session_state.threads = threads
                    st.session_state.triage_done = False
                else:
                    # Gmail via engine.py
                    try:

                        flat_threads = fetch_threads(max_results=email_limit)
                        # st.write("Fetched from Gmail:", len(flat_threads))
                        # st.json(flat_threads[0])
                        st.session_state.flat_threads = flat_threads
                        # unify format for app usage
                        threads = flat_threads
                        st.session_state.threads = threads#for calender changed
                        # Convert flat Gmail format to unified thread format
                        temp_flat = []
                        for ft in flat_threads:
                          last = ft["messages"][-1] if ft["messages"] else {}

                          temp_flat.append({
                             "sender": last.get("from", ""),
                             "subject": last.get("subject", ""),
                             "snippet": last.get("body", ""),
                           })                      
                        # for ft in flat_threads:
                        # threads= st.session_state.flat_threads    
                        st.session_state.triage_input = temp_flat
                        st.session_state.triage_done = False
                        # st.session_state.threads = threads
                        # st.write("Threads stored:", len(st.session_state.threads))
                        
                    # except Exception as e:
                    #     st.error(f"Failed to fetch from Gmail: {e}")
                    #     st.stop() # <-- or st.rerun() / return
                   
                 #-------Adding exception after deploy on streamlit cloud---------------------------------
                    except Exception as e:
                        traceback.print_exc()

                        st.warning(
                            "⚠️ Gmail integration isn't configured for this deployment.\n\n"
                            "Please switch to **Sample Threads** to explore the app."
                        )

                        st.stop()    
                    #---------------------------------------------------------------      
            # st.write("Before triage:", len(st.session_state.threads))            
            # Auto-triage if we got threads
            if st.session_state.threads:
                with st.spinner("🧠 Triaging..."):
                    triaged_dict = {
                        PRIORITY_URGENT: [],
                        PRIORITY_NEEDS_REPLY: [],
                        PRIORITY_FYI: [],
                        PRIORITY_IGNORE: [],
                        PRIORITY_UNKNOWN: [],
                    }

                    # Build a flat list that triage_inbox() expects
                    if st.session_state.source == SOURCE_SAMPLE:
                        temp_flat = []
                        for t in st.session_state.threads:
                            msgs = t.get("messages", [])
                            first = msgs[0] if msgs else {}
                            last = msgs[-1] if msgs else {}
                            temp_flat.append({
                                "sender": first.get("from", ""),
                                "subject": t.get("subject", ""),
                                "snippet": last.get("body", "")[:200],
                            })
                    else:
                        # Reuse the original flat_threads we fetched earlier
                        temp_flat = []
                        for ft in flat_threads:
                           last = ft["messages"][-1] if ft["messages"] else {}
                           temp_flat.append({
                              "sender": last.get("from", ""),
                              "subject": last.get("subject", ""),
                              "snippet": last.get("body", "")
                            })

                    # Call the real triage engine
                    try:
                        classified = triage_inbox(temp_flat)
                        # st.write("Classified:", len(classified))
                        # Merge classification back into the unified threads
                        for i, t in enumerate(st.session_state.threads):
                            t["priority"] = classified[i].get("priority", PRIORITY_UNKNOWN)
                            t["category"] = classified[i].get("category", "")
                            t["reason"] = classified[i].get("reason", "")
                    except Exception as e:
                        st.warning(f"Triage API failed: {e}. Using uncategorized.")
                        for t in st.session_state.threads:
                            t["priority"] = PRIORITY_UNKNOWN

                    # Group by priority
                    for t in st.session_state.threads:
                        prio = t.get("priority", PRIORITY_UNKNOWN)
                        triaged_dict.setdefault(prio, []).append(t)

                    st.session_state.triaged = triaged_dict
                    # st.write("Urgent:", len(triaged_dict[PRIORITY_URGENT]))
                    # st.write("Needs Reply:", len(triaged_dict[PRIORITY_NEEDS_REPLY]))
                    # st.write("FYI:", len(triaged_dict[PRIORITY_FYI]))
                    # st.write("Ignore:", len(triaged_dict[PRIORITY_IGNORE]))
                    st.session_state.triage_done = True
                
                #---------------------------------------------------------------
                prefix = get_file_prefix(st.session_state.source)

                save_threads_to_json(st.session_state.threads, f"{prefix}_triaged.json")
                save_threads_to_csv(st.session_state.threads, f"{prefix}_triaged.csv")
                save_threads_to_db(st.session_state.threads, f"{prefix}_triaged.db")
                st.rerun()
                #----------------------------------------------------------------

    with col2:
        if not st.session_state.run_pipeline:
          thread_count = len(st.session_state.threads)
          st.metric("Threads loaded", thread_count)

    # ── Display triaged threads ───────────────────────────────────────
    # if st.session_state.triage_done and st.session_state.triaged:
    # Don't show inbox while pipeline is running
    if (
       not st.session_state.run_pipeline#add
       and st.session_state.triage_done
       and st.session_state.triaged
    ):    
        priority_order = [PRIORITY_URGENT, PRIORITY_NEEDS_REPLY, PRIORITY_FYI, PRIORITY_IGNORE, PRIORITY_UNKNOWN]
       
        priority_labels = {
            PRIORITY_URGENT: "🚨 Urgent",
            PRIORITY_NEEDS_REPLY: "💬 Needs Reply",
            PRIORITY_FYI: "🗒️ FYI",
            PRIORITY_IGNORE: "🗑️ Ignore",
            PRIORITY_UNKNOWN: "⚪ Unclassified",
        }
        priority_badges = {
            PRIORITY_URGENT: "🔴 URGENT",
            PRIORITY_NEEDS_REPLY: "🟡 NEEDS REPLY",
            PRIORITY_FYI: "🔵 FYI",
            PRIORITY_IGNORE: "⚫ IGNORE",
            PRIORITY_UNKNOWN: "⚪ UNCLASSIFIED",
        }

        with st.expander("📋 Triaged Inbox", expanded=True):
            for prio in priority_order:
                threads_in_bucket = st.session_state.triaged.get(prio, [])
                if not threads_in_bucket:
                    continue

                st.markdown(f"### {priority_labels.get(prio, prio)} ({len(threads_in_bucket)})")

                for t in threads_in_bucket:
                    subject = t.get("subject", "(No subject)")
                    # thread_id = t.get("id", "unknown")
                    # thread_id = t.get("id") or t.get("threadId") or f"missing_{hash(str(t))}"
                    thread_id = normalize_thread_id(t) #add
                    # thread_id = t.get("id") or t.get("threadId")
                    messages = t.get("messages", [])

                    status = get_draft_status(thread_id)
                  
                    # status_badge = {
                    #     "approved": " ✅",
                    #     "rejected": " ❌",
                    #     "draft": " ✍️",
                    #     "none": "",
                    # }.get(status, "")
                    status_badge = {
                       STATUS_DRAFT:"🟢",
                       STATUS_SENT:"📤",
                       STATUS_APPROVED:"✅",
                       STATUS_REJECTED:"❌",
                       STATUS_NONE:""
                    }.get(status, "")
                    badge = priority_badges.get(prio, "")

                    with st.expander(f"**{subject}**{status_badge}", expanded=False):
                        st.markdown(f"**Priority:** {badge}")
                        st.divider()
                        for msg in messages:
                            st.markdown(f"**From:** {msg.get('from', '')}")
                            st.markdown(f"**Date:** {msg.get('date', '')}")
                            st.markdown(f"{msg.get('body', '')}")
                            st.divider()
                        st.write(thread_id)
                        if st.button("Select", key=f"select_{thread_id}"):
                            st.session_state.selected_thread_id = thread_id
                            st.info(f"Selected: {subject}")
       #------------- ---------------------------------------------------------

        # ── Footer: count of threads needing replies ──────────────────
        needs_reply_count = len(st.session_state.triaged.get(PRIORITY_NEEDS_REPLY, []))
        if needs_reply_count > 0:
            st.markdown("---")
            col_a, col_b = st.columns([3, 1])
            with col_a:
                st.markdown(f"**{needs_reply_count} thread(s) need a reply → go to Draft Generation**")
            with col_b:
                if st.button("✍️ Draft Generation", type="primary", use_container_width=True):
                    navigate_to(PHASE_DRAFT)
                    st.rerun()
    else:
        if st.session_state.threads and not st.session_state.triage_done:
            st.info("👈 Click **Pull & Triage** to classify your inbox.")
        else:
            st.info("👈 Click **Pull & Triage** to load sample threads or fetch from Gmail.")

# ---------------------------------------------------------------------------
# PHASE 2 — Draft Generation
# ---------------------------------------------------------------------------
elif st.session_state.current_phase == PHASE_DRAFT:
    st.title("✍️ Draft Generation")
    st.caption("Generate AI drafts for threads that need a reply.")

    # ── Get all actionable threads (urgent + needs-reply) ────────────
    actionable = []
    for prio in (PRIORITY_URGENT, PRIORITY_NEEDS_REPLY):
        actionable.extend(st.session_state.triaged.get(prio, []))

    if not actionable:
        st.info("No threads need a reply. Go back to **Inbox & Triage** first.")
        if st.button("📥 Back to Inbox", type="primary"):
            navigate_to(PHASE_INBOX)
            st.rerun()
    else:
        st.markdown(f"**{len(actionable)} thread(s)** need a reply.")

        # ── Generate All Drafts button ───────────────────────────────
        col_gen1, col_gen2 = st.columns([1, 4])
        with col_gen1:
            if st.button("⚡ Generate All Drafts", type="primary", use_container_width=True):
                progress_bar = st.progress(0, text="Generating drafts...")
                status_text = st.empty()
                for idx, t in enumerate(actionable):
                    # thread_id = t.get("id", "unknown")
                    # thread_id = t.get("id") or t.get("threadId") or f"missing_{hash(str(t))}"
                    thread_id = normalize_thread_id(t)
                    status_text.info(f"✍️ Drafting reply for: **{t.get('subject', '(No subject)')}**")
                    try:
                        # draft_text = draft_reply(t)
                        # st.session_state.drafts[thread_id] = draft_text
                        # for debug
                        draft_text = draft_reply(t)

                        print("=" * 60)
                        # print("SUBJECT:", subject)
                        print("THREAD ID:", thread_id)
                        print("DRAFT:", repr(draft_text))
                        print("=" * 60)

                        st.session_state.drafts[thread_id] = draft_text
                        
                    except Exception as e:
                        print("Draft generation error:", e)
                        st.session_state.drafts[thread_id] = ( 
                                 "⚠️ Draft generation is temporarily unavailable because the AI service "
                                 "cannot be reached at the moment. Please try again later.")
                    progress_bar.progress((idx + 1) / len(actionable),
                                          text=f"Generating drafts... ({idx + 1}/{len(actionable)})")
                progress_bar.empty()
                status_text.success("✅ All drafts generated!")
                st.rerun()

        # ── Display generated drafts ─────────────────────────────────
        if st.session_state.drafts:
            with st.expander("📝 Generated Drafts", expanded=True):
                for t in actionable:
                    # thread_id = t.get("id", "unknown")
                    # thread_id = t.get("id") or t.get("threadId") or f"missing_{hash(str(t))}"
                    thread_id = normalize_thread_id(t)
                    subject = t.get("subject", "(No subject)")
                    print("SUBJECT:", subject)
                    messages = t.get("messages", [])
                    draft_text = st.session_state.drafts.get(thread_id, "")

                    latest_msg = messages[-1] if messages else {}

                    with st.expander(f"**{subject}**", expanded=False):
                        cols = st.columns(2)
                        # Left: latest message from original thread
                        with cols[0]:
                            st.markdown("**📨 Original (latest message)**")
                            st.markdown(f"**From:** {latest_msg.get('from', '')}")
                            st.markdown(f"**Date:** {latest_msg.get('date', '')}")
                            st.markdown(f"{latest_msg.get('body', '')}")
                        # Right: AI-generated draft
                        with cols[1]:
                            st.markdown("**🤖 AI Draft**")
                            if draft_text:
                                st.markdown(draft_text)
                            else:
                                st.caption("Click *Generate All Drafts* above to create drafts.")

        # ── Footer ───────────────────────────────────────────────────
        if st.session_state.drafts:
            st.markdown("---")
            col_f1, col_f2 = st.columns([3, 1])
            with col_f1:
                st.markdown(f"**Drafts ready → go to Approval Gate**")
            with col_f2:
                if st.button("✅ Approval Gate", type="primary", use_container_width=True):
                    navigate_to(PHASE_APPROVAL)
                    st.rerun()
                   
# ---------------------------------------------------------------------------
# PHASE 3 — Approval Gate
# ---------------------------------------------------------------------------
elif st.session_state.current_phase == PHASE_APPROVAL:
    st.title("✅ Approval Gate")
    st.caption("Review, edit, approve, or reject AI-generated drafts.")

    # ---------- ADD HERE ----------
    st.subheader("📜 Pipeline Execution Logs")

    if st.session_state.pipeline_logs:
        with st.expander("View Pipeline Logs", expanded=False):
          for line in st.session_state.pipeline_logs:
            st.write(line)
    else:
        st.info("No pipeline execution logs available.")

# ------------------------------
    actionable = get_actionable_threads()
    if not actionable or not st.session_state.drafts:
        st.info("No drafts to review. Go to **Inbox & Triage** → **Draft Generation** first.")
        if st.button("📥 Back to Inbox", type="primary"):
            navigate_to(PHASE_INBOX)
            st.rerun()
    else:
        # ── Running count ──────────────────────────────────────────
        total_drafts = len(actionable)#adding
        # approved_count = len(st.session_state.approved)
        approved_count = sum(
           1 for tid in st.session_state.approved
           if tid not in st.session_state.rejected
        )
        rejected_count = len(st.session_state.rejected)
        # pending_count = total_drafts - approved_count - rejected_count #adding
        pending_count = max(
                   0,
                   total_drafts - approved_count - rejected_count
        )
        reviewed_count = approved_count + rejected_count
        st.subheader("📊 Review Summary")
        # total_count = len(actionable)
        # reviewed_count = approved_count + rejected_count
       
        # col_meta1, col_meta2, col_meta3, _ = st.columns([1,1, 1, 4])
        col_meta1, col_meta2, col_meta3, col_meta4= st.columns(4)
        with col_meta1:
            st.metric("📝 Total Drafts", total_drafts)
            # st.metric("✅ Approved", approved_count)
        with col_meta2:
            # st.metric("❌ Rejected", rejected_count)
            st.metric("✅ Approved", approved_count)
        with col_meta3:
            # st.metric("📝 Remaining", total_count - reviewed_count)
            st.metric("❌ Rejected", rejected_count)
        with col_meta4:
            st.metric("⏳ Pending", pending_count)
            
        # ── Loop through each actionable thread ─────────────────────
        all_done = True
        for t in actionable:
            # thread_id = t.get("id", "unknown")
            # thread_id = t.get("id") or t.get("threadId") or f"missing_{hash(str(t))}"
            thread_id = normalize_thread_id(t)
            subject = t.get("subject", "(No subject)")
            messages = t.get("messages", [])

            # Skip if already approved or rejected
            # if thread_id in st.session_state.approved or thread_id in st.session_state.rejected:
            # if thread_id in st.session_state.sent or thread_id in st.session_state.rejected:    
            #     # Show a collapsed summary for already-reviewed threads
            #     with st.expander(f"**{subject}**" — 📤 Sent " if thread_id in st.session_state.sent else f"**{subject}** — ❌ Rejected", expanded=False):
            #         pass
            #     continue
            # Skip if already sent or rejected
            if thread_id in st.session_state.sent or thread_id in st.session_state.rejected:

                if thread_id in st.session_state.sent:
                    title = f"**{subject}** — 📤 Sent"
                else:
                    title = f"**{subject}** — 🔴 Rejected"

                with st.expander(title, expanded=False):
                   pass

                continue    

            all_done = False
            draft_text = st.session_state.drafts.get(thread_id, "")
            edit_key = f"edit_{thread_id}"
# ------------------------------------------------------------------------
            # Review status
            if thread_id in st.session_state.approved:
               status = "🟢 Approved"
            elif thread_id in st.session_state.rejected:
               status = "🔴 Rejected"
            else:
               status = "⏳ Pending Review"

            with st.expander(f"**{subject} — {status}**", expanded=True):
            # with st.expander(f"**{subject}**", expanded=True):
                col_left, col_right = st.columns(2)

                # ── Left: full thread history ──────────────────────
                with col_left:
                    st.markdown("**💬 Email Thread**")
                    for msg in messages:
                        st.markdown(f"**From:** {msg.get('from', '')}")
                        st.markdown(f"**Date:** {msg.get('date', '')}")
                        st.markdown(f"{msg.get('body', '')}")
                        st.divider()

                # ── Right: editable draft + buttons ────────────────
                with col_right:
                    st.markdown("**✍️ Draft**")
                    edited_draft = st.text_area(
                        "Edit draft:",
                        value=draft_text,
                        height=250,
                        key=edit_key,
                        label_visibility="collapsed",
                    )

                    btn_col1, btn_col2, btn_col3 = st.columns(3)
               
                    #---------------------------------------------------
                
                    with btn_col1:
                      if st.button(
                       "✅ Approve",
                       type="primary",
                       use_container_width=True,
                       key=f"approve_{thread_id}",
                      ):

                        st.session_state.approved[thread_id] = edited_draft

                        save_approved_draft(
                         draft_text=edited_draft,
                         subject=subject,
                         replying_to=messages[-1].get("from", "unknown"),
                         model="gemini-2.5-flash",
                         edited=(edited_draft != draft_text), 
                        )
                        st.success("✅ Draft approved. Ready to send.")
                        st.rerun()
                    # ------------------------------------------------------------------------------------------
                    with btn_col2:
                        if st.button("🔄 Regenerate", use_container_width=True, key=f"regen_{thread_id}"):
                            with st.spinner("Regenerating draft..."):
                                try:
                                    new_draft = draft_reply(t)
                                    st.session_state.drafts[thread_id] = new_draft
                                except Exception as e:
                                    st.session_state.drafts[thread_id] = f"*Regeneration failed: {e}*"
                                st.rerun()
                    # ---------------------------------------------------------------------------------------------            
                    with btn_col3:
                        if st.button("🗑️ Reject", use_container_width=True, key=f"reject_{thread_id}"):
                            st.session_state.rejected.add(thread_id)
                            st.rerun()
                    # ----------------------------------------------------------------------------------------------------------
                    
        # ------------------------------------------------------------------
        # Pipeline Execution Logs
        # ------------------------------------------------------------------
      
                    # Show Send button only after approval
                    if (
                        thread_id in st.session_state.approved
                        and thread_id not in st.session_state.sent
                    ):
                        st.success("✅ Draft approved. Ready to send or export.")
                    #    adding for calendar meeting
                        is_meeting = (
                          st.session_state.source == SOURCE_GMAIL
                        #   and t.get("category") == "meeting-request"
                          and "meeting" in t.get("category", "").lower()
                        ) 
                        # for debugging  adding these 4lines
                        # st.write("Category:", thread.get("category"))
                        # st.write("Priority:", thread.get("priority"))
                        # st.write("Source:", st.session_state.source)
                        # st.write("Is meeting:", is_meeting)
                        # ---------- Layout ----------
                        if is_meeting:
                          send_col, book_col = st.columns(2)
                        #   st.write("Creating meeting columns") #for debuggin on  ui after  draft on approved page   
                        else:
                          send_col = st.container()
                          book_col = None
                        with send_col:  
                        # if not is_meeting:   #Adding for calendar meeting 
                            if st.button(
                              "📤 Send Email",
                              key=f"send_{thread_id}",
                              type="primary",
                              use_container_width=True,
                            ):

                              try:  
                                 # ALWAYS define recipient first
                                recipient = parseaddr(messages[-1].get("from", ""))[1] if messages else "demo@local"      
                                if st.session_state.source == SOURCE_GMAIL:
                               
                                    with st.spinner(f"📤 Sending email to {recipient}..."):
                                        time.sleep(2)   # Demo delay so user sees the spinner
                                        
                                    #1. for action_log.json file :- using 'result ='
                                    result =send_reply(
                                        thread_id=thread_id,
                                        to=recipient,
                                        subject=subject,
                                        body=st.session_state.approved[thread_id],  
                                        message_id=t.get("gmail_message_id"),
                                    )
                                    st.success("✅ Email sent successfully!")
                                    if result.get("message_id"): #3. for json file
                                        log_action(
                                        action_type="sent",
                                        thread_subject=subject,
                                        detail=recipient,
                                        action_id=result["message_id"],
                                    )

                                else:
                                    with st.spinner(f"📤 Sending email to {recipient}..."):
                                        time.sleep(2)   # Demo delay so user sees the spinner  
                                    st.success("✅ Demo Mode: Draft marked as sent.")
                                st.session_state.sent.add(thread_id)   
                               #  time.sleep(2)   
                                st.rerun()
                             

                              except Exception as e:
                                st.error(f"Failed to send email: {e}")
                # ---------------------------------------------------------
                    # MEETING REQUEST
                # ----------------------------------------------------------
                        if is_meeting:
                            with book_col:
                                # st.write("Entering Book Meeting section")
                                if thread_id in st.session_state.booked:

                                    st.success("📅 Meeting already booked")

                                    st.link_button(
                                      "Open Calendar Event",
                                      st.session_state.booked[thread_id]["htmlLink"],
                                      use_container_width=True,
                                   )

                                else:
                                   
                                    if st.button(
                                      "📅 Book Meeting",
                                      key=f"book_{thread_id}",
                                      use_container_width=True,
                                    ):
                                        # import traceback
                                        # try:
                                            calendar = _get_calendar_engine()

                                            with st.spinner("Parsing meeting request..."):
                                                parsed = calendar.parse_meeting_request(t)
                                            # st.write("After parse") #for debug when send or book meeting buttin press AI limit exhausted
                                      
                                            if "parsing_error" in parsed:
                                               st.error(parsed["parsing_error"])
                                            #    st.warning( this is hardcoded so use in parsing_meeting_request in calendar_engine.py
                                            #      "Meeting scheduling is temporarily unavailable because the AI service has reached its usage limit."
                                            #     )
                                               st.stop()

                                            # st.info(parsed)
                                            # ----------------
                                            st.success("✅ Meeting request parsed successfully")

                                            st.markdown("### 📋 Meeting Details")

                                            st.write(f"**Topic:** {parsed.get('topic', 'N/A')}")

                                            st.write(f"**Duration:** {parsed.get('duration_minutes', 30)} min")

                                            times = parsed.get("proposed_times", [])
                                            if times:
                                              st.write("**Proposed Time(s):**")
                                              for proposed_time in times:
                                                    try:
                                                       dt = datetime.fromisoformat(proposed_time)
                                                       st.write(f"• {dt.strftime('%d %b %Y, %I:%M %p')}")
                                                    except ValueError:
                                                       st.write(f"• {proposed_time}")
                                            else:
                                                st.write("**Proposed Time(s):** None")

                                            attendees = parsed.get("attendees", [])
                                            if attendees:
                                               st.write("**Attendees:**")
                                               for attendee in attendees:
                                                   st.write(f"• {attendee}")
                                            else:
                                                st.write("**Attendees:** None")
                                    #    ----------------------------------------------         
                                            with st.spinner("Checking calendar availability..."):
                                                slot = calendar.find_free_slot(
                                                    parsed["proposed_times"],
                                                    parsed["duration_minutes"],
                                                )
                                            st.write("After find_free_slot")
                                      
                                            if slot is None:
                                                st.warning("No available time slot found.")
                                                st.stop()

                                            with st.spinner("Booking meeting..."):

                                                event = calendar.create_event(
                                                    summary=parsed["topic"],
                                                    start_time=slot,
                                                    duration_minutes=parsed["duration_minutes"],
                                                    attendees=parsed["attendees"],
                                                )
                                            st.write("After create_event")
                                      
                                            st.session_state.booked[thread_id] = event

                                            st.success("✅ Meeting booked successfully!")
                                            
                                            #4 for action_log
                                            if event.get("id"):
                                                log_action(
                                                    action_type="booked",
                                                    thread_subject=subject,
                                                    detail=parsed["topic"],
                                                    action_id=event["id"],                                             
                                                ) 
                                            st.link_button(
                                                "Open Calendar Event",
                                                event["htmlLink"],
                                                use_container_width=True,
                                            )

                                            st.rerun()   
                                             
                                        # except Exception:
                                        #     st.error(f"Exception: {type(e).__name__}")
                                        #     st.code(traceback.format_exc())
                                        #     st.stop()
 # ---------------------------------------------------------        
        # ── All reviewed → celebration + navigate ──────────────────
        if reviewed_count == total_drafts and total_drafts > 0:
            st.balloons()
            st.success("🎉 **All drafts reviewed!**")

            st.markdown("---")

            col_f1, col_f2 = st.columns([3, 1])

            with col_f1:
              st.markdown("**Go to Export Proof**")

            with col_f2:
              if st.button("📤 Export Proof", type="primary", use_container_width=True):
                 navigate_to("export")
                 st.rerun() 
# ---------------------------------------------------------------------------
# PHASE 4 — Export Proof
# ---------------------------------------------------------------------------
elif st.session_state.current_phase == PHASE_EXPORT:
    st.title("📤 Export Proof")
    st.caption("Export approved drafts as proof of human-in-the-loop review.")
    # If it expects proof of sent emails, then use
    # approved = {
    #  tid: st.session_state.approved[tid]
    #  for tid in st.session_state.sent
    #  if tid in st.session_state.approved
    # }
    # Export Proof shows approved drafts even if not sent
    approved = st.session_state.approved
    if not approved:
        st.info("No approved drafts yet. Approve a draft in the Approval Gate phase to see it here.")
        if st.button("✅ Go to Approval Gate", type="primary"):
            navigate_to(PHASE_APPROVAL)
            st.rerun()
    else:
        st.success(f"{len(approved)} approved draft(s) ready for export.")
        st.markdown("---")

        # ── Side-by-side preview ──────────────────────────────────
        with st.expander("📄 Preview Approved Drafts", expanded=True):
            for thread_id, draft_text in approved.items():
                t = get_thread_by_id(thread_id , st.session_state.threads,)
                subject = t.get("subject", "(No subject)") if t else "(Unknown thread)"
                messages = t.get("messages", []) if t else []

                st.markdown(f"### {subject}")
                cols = st.columns(2)
                with cols[0]:
                    st.markdown("**📨 Original Email**")
                    for msg in messages:
                        st.markdown(f"**From:** {msg.get('from', '')}")
                        st.markdown(f"**Date:** {msg.get('date', '')}")
                        st.markdown(f"{msg.get('body', '')}")
                        st.divider()
                with cols[1]:
                    st.markdown("**✅ Approved Draft**")
                    st.markdown(draft_text)
                 
        st.divider()
                
        st.subheader("📋 Action Log") #adding foe export proof logaction
        actions = get_action_log()
        # DEBUG - remove later
        # st.write("Actions loaded:", actions)
        if not actions:
            st.info("No actions logged yet.")
        else:
            # ------------for table in export page---------------
            rows = []
            for action in reversed(actions):
                if action["action_type"] == "sent":
                   action_name = "📤 SENT"
                else:
                   action_name = "📅 BOOKED"                 
                
                try:
                   ts = datetime.fromisoformat(action["timestamp"])
                   time_text = ts.strftime("%b %d %I:%M %p")
                except Exception:
                   time_text = action.get("timestamp", "")

                rows.append({
                    "Action": action_name,
                    "Subject": action.get("thread_subject", ""),
                    "Details": action.get("detail", ""),
                    "Time": time_text,
                })  
            df = pd.DataFrame(rows)

            st.dataframe(
                df,
                hide_index=True,
                use_container_width=True,
            ) 
            # st.write(df)    
            # --------------------------------------------------------
             

        # ── Download buttons ──────────────────────────────────────
        col_dl1, col_dl2, _ = st.columns([1, 1, 4])
        with col_dl1:
            md_content = generate_proof_markdown(
                st.session_state.approved,
                st.session_state.threads)
            st.download_button(
                label="📄 Download Proof (Markdown)",
                data=md_content,
                file_name=f"proof_of_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.md",
                mime="text/markdown",
                use_container_width=True,
                type="primary",
            )
        with col_dl2:
            html_content = generate_proof_html(    
                st.session_state.approved,
                st.session_state.threads,)
            st.download_button(
                label="📄 Download Proof (HTML)",
                data=html_content,
                file_name=f"proof_of_review_{datetime.now().strftime('%Y%m%d_%H%M%S')}.html",
                mime="text/html",
                use_container_width=True,
                type="primary",
            )

        st.markdown("---")
        st.info("📢 Share with **#MyChiefOfStaff** to earn your Ghostwriter badge!")
        
  
   
        
#  this page can be structred like below-
# app.py                  (~150 lines)

# constants.py

# engine.py

# calendar_engine.py

# approval_utils.py

# utils.py

# pages/
#     inbox.py
#     draft.py
#     approval.py
#     export.py

# templates/
#     proof_html.py

# services/
#     gmail_service.py
#     calendar_service.py

# models/
#     thread.py       

       