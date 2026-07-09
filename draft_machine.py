# 6 functions in this file:

import os
import sys
import json
from urllib import response
from dotenv import load_dotenv

from context_builder import assemble_context


load_dotenv()
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

def load_tone_profile():
    path = os.path.join(os.path.dirname(__file__), "tone_profile.json")

    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

# --- Sample threads for the approval gate ---

SAMPLE_THREADS = [
    # {
    #     "label": "--Select a s sampe thread--",
    # },
    {
        "label": "Q3 Budget Review",
        "subject": "Q3 Budget Review",
        "messages": [
            {
                "from": "Meera (Finance)",
                "date": "2026-06-21",
                "body": "Hi team,\n\nWe're starting Q3 budget reviews next week. Please send across your projected spends by Friday so I can consolidate before the leadership meeting.\n\nEach team lead should include:\n1. Headcount costs\n2. Vendor/contractor expenses\n3. Any new tooling requests\n\nThanks,\nMeera",
            },
            {
                "from": "Arjun (Engineering)",
                "date": "2026-06-22",
                "body": "Hey Meera,\n\nQuick question — should we include the cloud infrastructure scaling costs under headcount or vendor expenses? We're expecting a 2x cost increase in Q3 due to the new regions we're launching in.\n\n- Arjun",
            },
        ],
    },
    {
        "label": "Sprint Demo Feedback",
        "subject": "Re: Sprint demo feedback",
        "messages": [
            {
                "from": "Anika (Design)",
                "date": "2026-06-19",
                "body": "Hey Rahul,\n\nI've compiled the feedback from yesterday's sprint demo. The onboarding flow got a lot of comments — mostly positive but a few UX friction points.\n\nI've documented everything here: [link to doc]\n\nLet me know if you want to walk through it together.\n\nCheers,\nAnika",
            },
            {
                "from": "Rahul (Product)",
                "date": "2026-06-19",
                "body": "Thanks Anika! Let's sync tomorrow. I'd like to prioritize the fixes before the next release.\n\n- Rahul",
            },
            {
                "from": "Anika (Design)",
                "date": "2026-06-20",
                "body": "Hey Rahul,\n\nQuick update — I added a few more notes based on the post-demo survey responses. The main theme is that the loading states feel sluggish.\n\nWould you like me to run a quick prototype with skeleton screens for the next standup?\n\nCheers,\nAnika",
            },
        ],
    },
    {
        "label": "Vendor Contract Renewal",
        "subject": "Contract renewal — Analytics Suite",
        "messages": [
            {
                "from": "Priya (Procurement)",
                "date": "2026-06-18",
                "body": "Hi team,\n\nOur annual contract with DataPulse Analytics is up for renewal next month. We're currently on the Enterprise plan at $48k/yr.\n\nThey've offered a 15% discount if we renew before July 1. The sales rep (David) is also pushing for a 2-year lock-in at $82k total.\n\nI'd recommend the 1-year renewal given we're evaluating other tools. Thoughts?\n\nBest,\nPriya",
            },
            {
                "from": "Rahul (Product)",
                "date": "2026-06-18",
                "body": "Thanks Priya. Agreed — 1-year at $48k with the discount makes sense. Let's not lock in for 2 years since we might switch to a cheaper alternative post-Q3.\n\nCan you send over the proposal for signature?\n\nBest, Rahul",
            },
        ],
    },
]


# --- Drafting rules appended to the user prompt ---

DRAFTING_RULES = """
=== Drafting Constraints ===
a. ONE-ASK RULE: every email has exactly ONE clear question or ONE clear response
b. LENGTH CONTROL: match thread energy, max 5 sentences, use numbered points if needed
c. NO AI FILLER: never say "I hope this finds you well", "Thank you for reaching out", etc.
d. STRUCTURE: acknowledge briefly -> give response -> ONE clear next step"""


# def _build_prompt(thread):
#     """Build the full combined prompt from context + drafting rules."""
#     context = assemble_context(thread)
#     full_user_prompt = context["user"] + DRAFTING_RULES
#     combined = context["system"] + "\n\n" + full_user_prompt
#     return combined
def _build_prompt(thread):
    context = assemble_context(thread)
    profile = load_tone_profile()
    system_prompt = f"""
You are writing emails exactly like this person.
Name: {profile["name"]}
Role: {profile["role"]}
Company: {profile["company"]}

Tone:
{profile["tone"]}

Voice:
{profile["voice_description"]}

Traits:
{chr(10).join("- " + t for t in profile["traits"])}

Always Do:
{chr(10).join("- " + t for t in profile["do"])}

Never Do:
{chr(10).join("- " + t for t in profile["dont"])}

Greeting Options:
{", ".join(profile["preferred_greetings"])}

Signoffs:
{", ".join(profile["preferred_signoffs"])}

Signature:
{profile["signature"]}

Never mention AI.
Never invent information.
Follow the email thread exactly.
"""
    prompt = (
        system_prompt
        + "\n\n"
        + context["system"]
        + "\n\n"
        + context["user"]
        + "\n\n"
        + DRAFTING_RULES
    )
    return prompt

def draft_reply(thread):
    """Generates an email reply draft using Gemini."""
    import google.generativeai as genai

    if not GEMINI_API_KEY:
        raise RuntimeError(
            "GEMINI_API_KEY not found. Make sure it's set in the .env file."
        )

    genai.configure(api_key=GEMINI_API_KEY)
    model = genai.GenerativeModel("gemini-2.5-flash")

    prompt = _build_prompt(thread)
    # response = model.generate_content(prompt)
    # return response.text.strip()
    try:
     response = model.generate_content(prompt)

     print("========== GEMINI RESPONSE ==========")
     print(response)
     print("=====================================")

     return response.text.strip()

    except Exception as e:
      import traceback
      traceback.print_exc()
      raise
    return response.text.strip()


def draft_reply_groq(thread, api_key=None):
    """Generates an email reply draft using Groq (llama-3.3-70b-versatile)."""
    from groq import Groq

    key = api_key or GROQ_API_KEY
    if not key:
        raise RuntimeError(
            "GROQ_API_KEY not found. Pass it directly or set it in the .env file."
        )

    client = Groq(api_key=key)
    prompt = _build_prompt(thread)

    completion = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        messages=[{"role": "user", "content": prompt}],
    )
    return completion.choices[0].message.content.strip()
# -----------------------------------------------------------------------------------------------
def generate_sample_draft(thread):
    """
    Generates fixed demo drafts without calling any AI API.
    Used only for sample threads.
    """

    subject = thread.get("subject", "")

    sample_drafts = {
        "CRITICAL: Customer Payments Failing After Latest Deployment":
            """Hi Emma,

Please proceed with the rollback immediately.

Customer payments are our top priority. Once the issue has been resolved, please share a root cause analysis along with any preventive actions.

Thanks,
Jordan""",

        "URGENT: Suspicious Login Activity Detected":
            """Hi Daniel,

Please proceed with the full incident response process.

Rotate any affected credentials, continue monitoring for suspicious activity, and keep me informed of any customer impact. Send me the incident report once the investigation is complete.

Thanks,
Jordan""",

        "Q4 Product Roadmap Feedback Needed":
            """Hi Sophia,

Thanks for reaching out.

I'll prepare my top three platform priorities, including major feature work, technical improvements, and staffing requirements, and send them before Thursday.

Thanks,
Jordan""",

        "Vendor Renewal Decision Required":
            """Hi Olivia,

Let's proceed with the one-year renewal option.

Please send me the final agreement for review before we complete the renewal.

Thanks,
Jordan""",

        "Meeting Request: AI Dashboard Prototype Review":
            """Hi Lucas,

Thursday afternoon works well for me.

Please send the prototype materials beforehand so I can review them prior to the meeting.

Looking forward to it.

Thanks,
Jordan"""
    }

    return sample_drafts.get(subject, "")
# ----------------------------------------------------------------------------------------------------------

def draft_reply_with_metadata(thread):
    """Like draft_reply but returns a dict with: draft, model, subject, replying_to."""
    draft = draft_reply(thread)
    last_msg = thread["messages"][-1] if thread["messages"] else {"from": "unknown"}
    return {
        "draft": draft,
        "model": "gemini-2.5-flash",
        "subject": thread["subject"],
        "replying_to": last_msg["from"],
    }


def draft_reply_with_metadata_groq(thread, api_key=None):
    """Like draft_reply_groq but returns a dict with: draft, model, subject, replying_to."""
    draft = draft_reply_groq(thread, api_key=api_key)
    last_msg = thread["messages"][-1] if thread["messages"] else {"from": "unknown"}
    return {
        "draft": draft,
        "model": "llama-3.3-70b-versatile",
        "subject": thread["subject"],
        "replying_to": last_msg["from"],
    }


# ---------------------------------------------------------------------------
# Demo
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    if not GEMINI_API_KEY:
        print(
            "ERROR: GEMINI_API_KEY is missing.\n"
            "Make sure your .env file contains:\n"
            "  GEMINI_API_KEY=your_key_here"
        )
        sys.exit(1)

    thread = SAMPLE_THREADS[0]
    print("=" * 72)
    print(f"DRAFT MACHINE — {thread['subject']}")
    print("=" * 72)

    result = draft_reply_with_metadata(thread)

    print(f"\nModel:               {result['model']}")
    print(f"Thread Subject:      {result['subject']}")
    print(f"Replying To:         {result['replying_to']}")
    print("\n--- Generated Draft ---")
    print(result["draft"])