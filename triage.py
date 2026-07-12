# 3 functions in this file:-
# 1) triage_thread(sender: str, subject: str, snippet: str)
# 2)parse_triage_response(text: str) 
# 3)triage_inbox(threads: list) 


import os
import time

from dotenv import load_dotenv
from groq import Groq

# Load environment variables
load_dotenv()

# Initialize Groq client
# client = Groq(api_key=os.environ["GROQ_API_KEY"])
api_key = os.getenv("GROQ_API_KEY")

if not api_key:
    raise RuntimeError("GROQ_API_KEY not found in .env")

client = Groq(api_key=api_key)

# This function makes a call to the LLM
def triage_thread(sender: str, subject: str, snippet: str) -> dict:
    # Normalize inputs safely
    sender = (sender or "").lower()
    subject = (subject or "").lower()
    snippet = (snippet or "").lower()

    # -------------------------------
    # Fast rule-based classification
    # -------------------------------

    security_keywords = [
        "security alert",
        "security advisory",
        "vulnerability",
        "dependabot",
        "critical",
        "high severity",
        "cve",
        "account access",
        "new sign-in",
        "password",
        "authentication",
        "login",
        "verification",
        "verify account",
        "unusual activity",
        "suspicious",
        "2fa",
        "two-factor",
        "mfa",
    ]

    combined = f"{subject} {snippet}"
  
    # -------------------------------
    # Newsletter detection
    # -------------------------------
    
    newsletter_keywords = [
        "introducing",
        "newsletter",
        "weekly digest",
        "release notes",
        "product update",
        "announcement",
        "new feature",
        "blog",
        "launch",
        "product launch",
        "monthly update",
       "changelog",
       "developer update",
       "feature update",
        "new in",
       "what's new",
       "available now",
       "now available",
       "download",
       "learn more",
       "try now",
       "get started",
    
    ]
    promotion_keywords = [
    "premium",
    "reward",
    "claim your reward",
    "save your streak",
    "upgrade",
    "upgrade now",
    "complete your room",
    "keep my streak",
    "25% off",
    "discount",
    "offer",
    "limited time",
    "limited-time",
    "sale",
    "subscribe",
    "unlock",
    "unlock premium",
    "start now",
    "come back",
    "don't miss",
]
    if any(word in combined for word in security_keywords):
        return {
            "priority": "urgent",
            "category": "security",
            "reason": "Security-related email requiring attention.",
        }
    if any(word in combined for word in promotion_keywords):
        return {
        "priority": "ignore",
        "category": "promotion",
        "reason": "Promotional or re-engagement email.",
    }
    if any(word in combined for word in newsletter_keywords):
        return {
            "priority": "fyi",
            "category": "newsletter",
            "reason": "Detected newsletter/product announcement.",
        }
    
    # -------------------------------
    # Automated emails
    # -------------------------------

    # if "noreply" in sender or "no-reply" in sender:
    if any(x in sender for x in [
    "noreply",
    "no-reply",
    "donotreply",
    "do-not-reply",
    ]):    
        return {
            "priority": "ignore",
            "category": "automated",
            "reason": "Automated email.",
        }

    # -------------------------------
    # Otherwise use the LLM
    # -------------------------------

    prompt = f"""
You are an intelligent email assistant helping triage an inbox.

Classify the email using these rules.

Priority rules

urgent
- Requires immediate action.
- Security alerts.
- Payment failures.
- Meeting today.
- Production issues.
- Deadlines.

needs-reply
- Someone asked a question.
- Someone expects a response.
- Customer emails.
- Interview scheduling.
- Requests for approval.

fyi
- Newsletters.
- Product announcements.
- Marketing emails.
- Blog posts.
- Release notes.
- Informational updates.
- Marketing newsletters and product updates from companies you subscribe to.
- No response expected.

ignore
- Spam.
- Advertisements.
- Promotions.
- Promotional emails whose main purpose is:
  - selling a product
  - discounts
  - upgrade reminders
  - reward offers
  - encouraging you to return to a service
- Automated notifications with no value.

Important

- Marketing newsletters and product updates are FYI.
- Product launches and release announcements are FYI.
- Promotional or re-engagement emails ("Come back", "Complete your profile", "Claim your reward", "Upgrade now", "Save your streak", "Limited-time offer") are IGNORE.
- Do NOT classify newsletters as urgent because they contain words like:
  today
  introducing
  launch
  important
- Only choose urgent if immediate user action is required.

Examples

Example 1
Sender: Cognition
Subject: Introducing Devin Fusion
Preview: Today we're introducing Devin Fusion...
Priority: fyi
Category: newsletter
Reason: Product announcement.

Example 2
Sender: GitHub
Subject: Security alert
Preview: We detected a login from a new device.
Priority: urgent
Category: security
Reason: Immediate review required.

Example 3
Sender: HR
Subject: Can you interview tomorrow?
Preview: Please let us know if 2 PM works.
Priority: needs-reply
Category: interview
Reason: Sender expects a reply.

Example 4
Sender: Amazon
Subject: Prime Day starts now!
Preview: Huge discounts available.
Priority: ignore
Category: promotion
Reason: Promotional advertisement.

Email

Sender:
{sender}

Subject:
{subject}

Preview:
{snippet}

Respond ONLY in this format.

Priority: <urgent | needs-reply | fyi | ignore>
Category: <one short tag>
Reason: <one sentence>
"""

    try:
      response = client.chat.completions.create(
        model="llama-3.3-70b-versatile",
        temperature=0,
        messages=[
            {
                "role": "user",
                "content": prompt,
            }
        ],
      )

      text = response.choices[0].message.content
      return parse_triage_response(text)

    except Exception as e:
    #   print(f"Groq API error: {e}")
      return {
        "priority": "unknown",
        "category": "error",
        "reason": "Failed to classify email.",
      }

# This function parses the LLM response
def parse_triage_response(text: str) -> dict:
    result = {
        "priority": "unknown",
        "category": "other",
        "reason": "",
    }

    for line in text.splitlines():
        line = line.strip()

        if line.lower().startswith("priority:"):
            result["priority"] = line.split(":", 1)[1].strip().lower()

        elif line.lower().startswith("category:"):
            result["category"] = line.split(":", 1)[1].strip().lower()

        elif line.lower().startswith("reason:"):
            result["reason"] = line.split(":", 1)[1].strip()

    return result


def triage_inbox(threads: list) -> list:
    triaged = []

    for i, thread in enumerate(threads, start=1):
        print(f"Triage {i}/{len(threads)}")
        print("=" * 80)
        print("SUBJECT:", thread.get("subject"))
        print("SENDER :", thread.get("sender"))
        print("BODY   :", thread.get("body"))
        print("SNIPPET:", thread.get("snippet"))
        print("=" * 80)
        label = triage_thread(
            sender=thread.get("sender", ""),
            subject=thread.get("subject", ""),
            # snippet=thread.get("body", thread.get("snippet", ""))[:1000],
            snippet=thread.get("body") or thread.get("snippet", "")
        )

        triaged.append({**thread, **label})

        # Optional: helps avoid hitting API rate limits
        time.sleep(0.2)

    # priority_order = {
    #     "urgent": 0,
    #     "needs-reply": 1,
    #     "fyi": 2,
    #     "ignore": 3,
    #     "unknown": 4,
    # }

    # triaged.sort(
    #     key=lambda x: priority_order.get(x["priority"], 4)
    # )
    # for sample_thread hard coded
    # --------------------------------
#     sample_priority = {
#     "CRITICAL: Customer Payments Failing After Latest Deployment": "urgent",
#     "URGENT: Suspicious Login Activity Detected": "urgent",
#     "Q4 Product Roadmap Feedback Needed": "needs-reply",
#     "Vendor Renewal Decision Required": "needs-reply",
#     "Meeting Request: AI Dashboard Prototype Review": "needs-reply",
#     "Monthly Infrastructure Health Report": "fyi",
#     "Enterprise Contract Successfully Signed": "fyi",
#     "Customer Training Session Completed": "fyi",
#     "Marketing Campaign Performance Update": "fyi",
#     "Engineering Capacity Planning Documents": "fyi",
# }
    return triaged


sample_threads = [
    {
        "sender": "john.doe@example.com",
        "subject": "Urgent: Project Deadline Approaching",
        "snippet": (
            "Hi team, just wanted to remind everyone "
            "about the upcoming project deadline..."
        ),
    },
    {
        "sender": "notifications@github.com",
        "subject": "Pull Request Approved",
        "snippet": (
            "Your pull request has been reviewed and "
            "approved. You may proceed with merging "
            "the changes."
        ),
    },
    {
        "sender": "finance@acmecorp.com",
        "subject": "Invoice Payment Confirmation",
        "snippet": (
            "We have successfully processed your "
            "payment. The transaction receipt is "
            "attached for your records."
        ),
    },
]


if __name__ == "__main__":
    results = triage_inbox(sample_threads)

    # for r in results:
    #     print(
    #         f"[{r['priority'].upper()}] "
    #         f"[{r['category']}] "
    #         f"{r['subject']} - {r['reason']}"
    #     )