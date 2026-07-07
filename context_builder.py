def format_thread_history(thread):
    """
    Formats an email thread into plain text for the LLM.
    """
    lines = [f"Subject: {thread['subject']}", ""]

    for msg in thread["messages"]:
        lines.append(f"From: {msg['from']}")
        lines.append(f"Date: {msg['date']}")
        lines.append(f"Body:\n{msg['body']}")
        lines.append("---")

    return "\n".join(lines)


def assemble_context(thread):
    """
    Returns the formatted email thread.
    The complete prompt is assembled in draft_machine.py.
    """
    return {
        "system": "",
        "user": (
            "Draft a reply to the email thread below.\n\n"
            f"{format_thread_history(thread)}\n\n"
            "Reply:"
        ),
    }


if __name__ == "__main__":
    sample_thread = {
        "subject": "Launch timeline for v2.5",
        "messages": [
            {
                "from": "Meera (Design Lead)",
                "date": "2026-06-20",
                "body": (
                    "Hey team,\n\n"
                    "I've wrapped up the final mockups for v2.5. "
                    "The new dashboard layout is ready for dev handoff. "
                    "Let me know if there are any questions before we lock it in.\n\n"
                    "Cheers,\nMeera"
                ),
            },
            {
                "from": "Arjun (Engineering)",
                "date": "2026-06-21",
                "body": (
                    "Thanks Meera! The designs look solid. "
                    "I have a question about the analytics widget — "
                    "should it auto-refresh or require a manual click?\n\n"
                    "Also, what's the target launch date for v2.5?\n\n"
                    "- Arjun"
                ),
            },
        ],
    }

    context = assemble_context(sample_thread)

    print("=" * 72)
    print("SYSTEM PROMPT")
    print("=" * 72)
    print(context["system"])

    print()
    print("=" * 72)
    print("USER PROMPT")
    print("=" * 72)
    print(context["user"])
    
    
    
# context_builder.py
#         ↓
# formats thread

# draft_machine.py
#         ↓
# loads tone profile
# adds drafting rules
# creates final prompt
# calls Gemini/Groq