def normalize_thread_id(t):#for calender changed
    tid = t.get("id") or t.get("threadId") or t.get("gmail_thread_id")
    if not tid:
        tid = f"missing_{hash(str(t))}"
    return str(tid) 

def get_thread_by_id(thread_id, threads):
    """Return the thread matching the given normalized thread id."""
    for thread in threads:
        if normalize_thread_id(thread) == thread_id:
            return thread
    return None

def get_draft_error_message(error: Exception) -> str:
    error_text = str(error).lower()

    if "quota" in error_text or "429" in error_text:
        return "AI service usage limit reached."

    elif "rate limit" in error_text:
        return "AI service rate limit exceeded."

    elif "api key" in error_text or "authentication" in error_text:
        return "Invalid AI API key."

    elif "timeout" in error_text:
        return "The AI service timed out."

    elif "connection" in error_text or "network" in error_text:
        return "Network connection to the AI service failed."

    elif "json" in error_text or "decode" in error_text:
        return "Received an invalid response from the AI service."

    elif "model" in error_text:
        return "Requested AI model is unavailable."

    else:
        return "The AI service returned an unexpected error."