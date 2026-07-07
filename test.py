from cmath import log
from turtle import st

# venv\Scripts\activate bck-i-search: venv_

def run_full_pipeline()-> list[str]:
    log: list[str]= []
    source = st.session_state.source
# -------------------------------------------
# Step 1: Fetch Threads
#--------------------------------------------
    log.append(f"[OK] Source: {source}")
    try:
        if source == "Sample threads":
            threads = load_sample_threads()
            if not threads:
               log.append(f"[ERROR] No threads found at {SAMPLE_THREADS_PATH}: {exc}")
            return log
        else:
            threads = fetch_threads_via_engine()
            if not threads:
                log.append("[WARN] Gmail returned 0 threads.")
                return log
        log.append(f"[OK] Fetched {len(threads)} threads(s).") 
    except Exception as exc:
        log.append(f"[ERROR] Failed to fetch threads: {exc}")
        return log
    st.session_state.threads = threads
# -------------------------------------------------------------------
# Step 2: Triage
#----------------------------------------------------------------------    
    try:
        grouped = triage_threads(threads)
        st.session_state.triaged = grouped
        urgent_n = len(grouped.get("urgent", []))
        needs_reply_n = len(grouped.get("needs-reply", []))
        total_n = sum(len(v) for v in grouped.values())
        log.append(
            f"[OK] Triaged {total_n} threads(s): "
            f"{urgent_n} urgent, {needs_reply_n} need reply."
        )
    except Exception as exc:
        log.append(f"[ERROR] Failed to triage threads: {exc}")
        return log    
# -------------------------------------------------------------------
# Step 2: Reset downstream state
#----------------------------------------------------------------------          
    st.session_state.drafts = ()
    st.session_state.approved = {}
    st.session_state.rejected = {}
    st.session_state.sent = set()
    st.session_state.booked= {}
    log.append(f"[OK] Downstream state reset.")
# -------------------------------------------------------------------
# Step 2: Draft actioanble threads
#----------------------------------------------------------------------           
    actionable=(
        grouped.get("urgent", []) + grouped.get("needs-reply", [])
    ) 
    
    if not actionable:
        log.append("[WARN] No urgent or needs-reply threads found.")
    else:
        log.append(f"[OK] Drafting {len(actionable)} thread(s)...")  
        try: 
            draft_reply = _get_draft_reply()           
        except Exception as exc:
            log.append(f"[ERROR] Failed to draft threads: {exc}")
            return log
        
        ok_count = 0
        for i, thread in enumerate(actionable):
            thread_id = thread.get("id", f"thread_{i}")
            subject = thread.get("subject", "(no subject)")
            
            try:
               draft = draft_reply(thread)
               st.session_drafts[thread_id] = draft
               log.sppend(f"[OK] draft {i+1}/{len(actionable)}:
               
            except Exception as exc:    
              log.append(
                f"[ERROR] Draft {i+1}/{len(actionable)} failed"
                f"({subject[:50]}): {exc}"
               )
            return log            
        log.append(
             f"[OK] Drafting complete: {ok_count}/{len(actionable)}"
         )           
# -------------------------------------------------------------------
# Step 2: Advance phase
#----------------------------------------------------------------------            
   st.session_state.current_phase = "Approval Gate"
   log.append("[OK] Phase -> Approval Gate.")
   return log
# Before ihave:
# Click  Pull &Triage
# wait..
# Click Draft Generation
# wait..
# Click Approval Gate
# Review drafts
# Click send/Book


# After i want: 
# Click Run Full Pipeline
# ...sip coffee...
# Review drafts at Approval Gate
# Click Send/Book           
    
    
    
    
