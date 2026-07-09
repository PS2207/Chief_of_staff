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

Thanks for the quick response and for resolving the issue promptly.

Please share the root cause analysis once it's ready, along with any preventive measures to reduce the risk of similar incidents in future deployments.

Thanks,
Jordan""",

        "URGENT: Suspicious Login Activity Detected":
            """Hi Daniel,

Thanks for acting quickly to secure the affected account.

Please continue monitoring the systems and send me the full incident report once your investigation is complete. Let me know immediately if any customer impact is identified.

Thanks,
Jordan""",

        "Q4 Product Roadmap Feedback Needed":
            """Hi Sophia,

Thanks for the clarification.

I'll prepare my Q4 priorities with infrastructure modernization included under technical debt and send the complete document before Thursday.

Thanks,
Jordan""",

        "Vendor Renewal Decision Required":
            """Hi Olivia,

Thanks for handling this.

Please send me the final agreement once it's ready. After I review it, you can proceed with the one-year renewal.

Thanks,
Jordan""",

        "Meeting Request: AI Dashboard Prototype Review":
            """Hi Lucas,

Thanks for confirming.

I'll review the design deck before Thursday's meeting. Looking forward to discussing the prototype and next steps.

Thanks,
Jordan""",

        "Production Database Storage Reaching Critical Capacity":
            """Hi Michael,

Thanks for the update.

I'm glad the storage expansion completed successfully. Please continue monitoring the database over the next 24 hours and share a brief summary once everything remains stable.

Thanks,
Jordan""",

        "Legal Review Required Before Enterprise Contract Signature":
            """Hi Rachel,

Thanks for taking this forward.

Please keep me informed of the customer's response and let me know if any executive involvement is needed during the negotiations.

Thanks,
Jordan""",

        "Customer Escalation: Major Feature Missing in Latest Release":
            """Hi Nathan,

Thanks for arranging the customer call and preparing the workaround.

Please keep me updated after the discussion and let me know if there are any additional commitments we need to make.

Thanks,
Jordan""",

        "Marketing Budget Approval for Product Launch Campaign":
            """Hi Emily,

Thanks for updating the proposal.

Once you've revised the budget allocation, please send me the final version for approval before we move ahead with the campaign.

Thanks,
Jordan""",

        "Meeting Request: Quarterly Engineering Capacity Planning":
            """Hi David,

Thanks for scheduling the meeting.

I'll review the planning documents before Tuesday so we can make the best use of our discussion.

Looking forward to it.

Thanks,
Jordan"""
    }

    return sample_drafts.get(
        subject,
        """Hi,

Thanks for the update. I'll review it and get back to you shortly.

Thanks,
Jordan"""
    )
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