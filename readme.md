.venv, app.py, approval_gate.py, approved_drafts.json, 
context_builder.py, credentials.json, draft_machine.py, engine.py, 
original_5_emails.json, past_replies.json
sample_threads.josn, token.json, tone_profile.json, triage.py
--------------------------------------------------------------------------

Project Overview:
This is the architecture I'd recommend for this project
This project is an AI-powered email assistant (called The Draft Desk / Chief of Staff) 
that helps a user process Gmail with an AI workflow instead of manually reading and replying to emails.
                  AI Email Assistant

               Choose Data Source

          ┌─────────────────────────┐
          │ Sample Threads (Demo)   │
          │ Gmail Inbox (Live)      │
          └────────────┬────────────┘
                       │
         ┌─────────────┴─────────────┐
         │                           │
         ▼                           ▼
 sample_threads.json            Gmail API
         │                           │
         └──────────┬────────────────┘
                    ▼
               AI Triage
                    ▼
            Draft Generation
                    ▼
                 Approve
                    ▼
          Save JSON + Save DB
                    ▼
        Gmail Mode? ── Yes ──► Send Reply
              │
              No
              ▼
            Finished
--------------------------------------
The pipeline looks like this:

Gmail
   │
   ▼
Fetch Emails
(engine.py)
   │
   ▼
AI Triage
(triage.py)
   │
   ▼
Priority Groups
(Urgent / Needs Reply / FYI / Ignore)
   │
   ▼
Generate Reply Drafts
(draft_machine.py)
   │
   ▼
Human Review
(Approval Gate)
   │
   ▼
Send Email
(Gmail API)
   │
   ▼
Export Proof


******************************************************
1. engine.py

This is Gmail integration layer.
It performs several jobs.

Authentication
Uses OAuth.

credentials.json
        │
        ▼
token.json

The first time:

Opens Google login
User grants permission
Creates token.json

Later:

Uses token.json
Refreshes automatically
******************************************
(i)Fetch Emails-

It starts the Gmail MCP Server

Node.js Gmail MCP Server
        │
        ▼
fetch_threads()

Then retrieves emails like

Sender
Subject
Snippet
Date
Thread ID
**********************************************************
(ii)Save Results-

This also save everything into
1.gmail_threads.json
2.gmail_threads.csv
3.gmail_threads.db

So your project has persistence.
************************************************
(iii)Send Replies

Later, after approval,
send_reply()

Uses Gmail API
users().messages().send()

to send replies inside the original Gmail thread.

***********************************************************************
3. app.py

This is the Streamlit frontend.
Everything the user sees is here.

Phase 1-
Inbox & Triage
User clicks:
Pull & Triage

↓

Loads:
Sample Threads
or
Real Gmail

↓

Calls:
triage_inbox()

↓

Shows:
Urgent
Needs Reply
FYI
Ignore
***********************************************
Which email sends the reply?

Suppose your inbox is yourprojectdemo@gmail.com
Client sends:
client@gmail.com
        │
        ▼
yourprojectdemo@gmail.com

Your project generates a draft.
When you click Approve your code calls: send_reply(...)

The Gmail API sends the email from:
yourprojectdemo@gmail.com
to
client@gmail.com

Exactly as if you had clicked Reply in Gmail yourself.
*************************************************************
What this project actually is

This roject is an AI Email Chief of Staff.
It is not using Gmail's built-in categories.
It is using an LLM (Gemini/Groq) to read every email and make a decision, just like a human assistant would.

The flow is:
Gmail
   │
   ▼
engine.py
   │
Fetch latest emails
   │
   ▼
triage.py
   │
LLM reads each email
   │
   ▼
Priority
Category
Reason
   │
   ▼
app.py
Displays grouped inbox
   │
   ▼
Generate reply
   │
   ▼
Human approves
   │
   ▼
Send email
*********************************************
1. Boss:
"Need the report by 5 PM."

2. HR:
"Interview tomorrow at 10."

3. Amazon:
"Your order shipped."

4. Spotify:
"Upgrade Premium."

5. Friend:
"Are we meeting today?"

6. GitHub:
"Security alert."

7. Canva:
"New AI feature."

8. Google:
"Terms updated."

9. Client:
"Can you send the quotation?"

10. Newsletter

This project downloads these emails.

Nothing is classified yet.
It just receives raw emails.

Like
[
 {
   sender:"boss@company.com",
   subject:"Need report",
   snippet:"Need before 5 PM"
 },

 {
   sender:"spotify.com",
   subject:"Premium"
 },

 ...
]
**********************
Then what happens?

This is the important step.

For EVERY email

your code runs

triage_thread(sender, subject, snippet)

Suppose

Boss

Subject:
Need report today

Snippet:
Please send before 5 PM.

Your code creates this prompt

You are an intelligent email assistant.

Sender:
boss@company.com

Subject:
Need report today

Preview:
Please send before 5 PM.

Classify it.

Priority:
Category:
Reason:

This prompt is sent to

Gemini

or

Groq

NOT to Gmail.

Then Llama or Gemini thinks.

Exactly like ChatGPT.

It reasons

Boss

Deadline

Need response

Time sensitive

→ Needs Reply

It replies

Priority: needs-reply

Category: work

Reason:
The sender is requesting action before a deadline.

Your parser converts this into

{
 priority:"needs-reply",
 category:"work",
 reason:"deadline"
}

Next email

Amazon

Your package shipped.

LLM thinks

No reply needed.

Only information.

FYI

Returns

Priority: fyi

Spotify

Upgrade Premium

LLM

Advertisement

Ignore

Client

Can you send quotation?

LLM

Needs reply.

Friend

Are we meeting today?

LLM

Needs reply.

Interview

Interview tomorrow.

LLM

Urgent

Time sensitive.

Finally

After classifying all 10 emails

your program has

[
 {
  subject:"Need report",
  priority:"needs-reply"
 },

 {
  subject:"Interview",
  priority:"urgent"
 },

 {
  subject:"Amazon",
  priority:"fyi"
 },

 {
  subject:"Spotify",
  priority:"ignore"
 }
]

Then app.py groups them.
Instead of showing
10 emails
it shows

🚨 Urgent (2)

Interview tomorrow
Server Down

------------------

💬 Needs Reply (4)

Boss
Client
Friend
University

------------------

🗒️ FYI (3)

Amazon
GitHub
Google

------------------

🗑 Ignore (1)
Spotify
This grouping is done in your code, not Gmail.
*********************************************************************
**********************************************************************
Then Draft Generation

Suppose

Client

Can you send quotation?

Again AI is called.

Now another prompt is sent.

Write a professional reply.

Thread history:

Client:
Can you send quotation?

Tone:
Professional

LLM replies

Hi,

Thank you for reaching out.

Please find the quotation attached.

Regards,
Pragya

Your UI displays it.

Approval

AI NEVER sends immediately.

Human checks.

Approve

Reject

Edit

This is called

Human-in-the-loop

Companies love this because AI doesn't automatically email customers.

Send

Only after approval

send_reply()

calls Gmail API.

Then Gmail sends it.

So how does AI know?

This is probably the question you're asking.

It doesn't use rules like

if subject contains "urgent"

then urgent

It uses reasoning.

Like ChatGPT.

Example:

Email

Our production server has crashed.

Need immediate assistance.

AI understands

Server crashed

Immediate assistance

High priority

→ Urgent

Another

Welcome to Spotify.

Enjoy Premium.

AI understands

Advertisement

Ignore

No if-else statements.

No keyword matching.

It is semantic understanding.

If someone asks in an interview:

How does your project determine which emails need replies?

A good answer is:

"The application fetches emails from Gmail using the Gmail API. For each email, it extracts the sender, subject, and a preview of the content, then sends that information to a large language model (Gemini or Groq Llama) with a structured prompt. The model semantically analyzes the email and returns a priority, category, and reasoning. The application groups emails by those AI-generated classifications, generates draft replies only for actionable emails, and requires human approval before sending through the Gmail API."

That's exactly what your current project is doing.

******************************************************************
{
    "id": "thread-005",
    "subject": "Meeting Request: AI Feature Review — New Concepts",
    "messages": [
      {
        "from": "Kavya (Data Science Lead)",
        "date": "2026-06-23 09:30",
        "body": "Hi Rahul,\n\nWe've wrapped up the initial research on two new AI-driven features we think could add significant value in the next quarter:\n\n1. **Smart Reply Suggestions** — ML model that suggests contextual replies for customer support tickets\n2. **Predictive Churn Scoring** — Flag at-risk accounts based on usage patterns\n\nI'd like to set up a 30-min review session with you to walk through the prototypes and get your input on prioritization.\n\nAre you free this Thursday or Friday afternoon?\n\nBest,\nKavya"
      },
      {
        "from": "Rahul (Product Manager)",
        "date": "2026-06-23 10:15",
        "body": "Hey Kavya,\n\nThese both sound exciting. I'm definitely interested.\n\nThursday at 3 PM works for me. Could you share a brief one-pager beforehand so I can come prepared with questions?\n\nAlso — is the churn scoring model dependent on any new data sources we'd need to integrate, or can it work with our existing usage data?\n\n- Rahul"
      },
      {
        "from": "Kavya (Data Science Lead)",
        "date": "2026-06-23 10:45",
        "body": "Thursday 3 PM works. I'll send over a one-pager by Wednesday evening.\n\nOn the churn model — it can work with our existing event data. No new integrations needed on day one. We might add CRM data later for improved accuracy but v1 is self-contained.\n\nSee you Thursday!\n\n- Kavya"
      }
    ]
  }
]
What is a Gmail Thread?
A thread is a conversation. Gmail groups all emails with the same subject into one thread.

Example:
Subject: Production Down

Arjun → Rahul        (Email 1)
Rahul → Arjun        (Reply 1)
Arjun → Rahul        (Reply 2)

Gmail displays these as one conversation, not three separate emails.
Imagine in gmail inbox:

Production Down (3)
Q3 Roadmap (3)
Weekly Standup (1)
Contract Renewal (3)
Meeting Request (3)

Instead of showing : Email 1,Email 2... Email 13
Gmail groups them into 5 conversations.
That's why  AI project should think in terms of threads, because when people reply, Gmail keeps everything together.

These are dummy IDs for testing and demos. 
Real Gmail threadId values are long opaque strings or numbers generated by Gmail, such as: 197c8c1fd7d2c3a8
How  this project will typically work:
Gmail Inbox
     │
     ▼
List Threads
     │
     ▼
threadId = 197abc
     │
     ▼
Fetch Full Thread
     │
     ▼
Read every message
     │
     ▼
AI analyzes:
• Urgent?
• FYI?
• Need Reply?
• Ignore?
     │
     ▼
Generate reply (if needed)
     │
     ▼
Reply using the same threadId
*********************************
Case 1: Same thread ✅

Arjun sends an email:
Subject: Production Down
Hi Rahul,
The API is failing.

You click Reply:
Subject: Re: Production Down
I'll check it.

Arjun replies again:
Subject: Re: Production Down
Thanks.

This is one thread because everyone is replying within the same conversation.

Thread
├── Arjun → Rahul
├── Rahul → Arjun
└── Arjun → Rahul
**********************
Case 2: Different thread ❌

An hour later, Arjun sends a new email:
Subject: Team Lunch Tomorrow
Hi Rahul,
Are you joining?

Even though it's the same sender (Arjun), this is a new thread because it's a completely new conversation.

Thread 1
Subject: Production Down
├── Email 1
├── Email 2
└── Email 3

Thread 2
Subject: Team Lunch Tomorrow
└── Email 1
********************************
Rule to remember:
Reply to an existing email → Same threadId (same thread).
Compose a brand-new email → New threadId (new thread), even if it's from the same person and even if the subject is similar.
*****************************************************************************************************************************
Mode 1: Demo mode (using sample_threads.json)

sample_threads.json
        │
        ▼
AI triage
    ▼
Generate draft
    ▼
Approve
    ▼
Save to JSON/DB

✅ Good for demonstrating your AI logic.
❌ Cannot send emails through Gmail.
❌ thread-001, thread-002, etc. are fake IDs.
Mode 2: Real Gmail mod
-----------------------------------------------
Mode 2: Real Gmail mode
Gmail API
     │
     ▼
Fetch inbox
     ▼
Real threadId
     ▼
AI triage
     ▼
Generate draft
     ▼
Approve
     ▼
Reply via Gmail API

Now every email has something like:

threadId = 198f0d91a5cb8f4d

###################################################################################################################
Actual project requirements 
i have one Streamlit app (app.py) with two modes: 
Sample Threads
Gmail via engine.py

Phase 1:-

✅ Source selection

Sample Threads
Gmail via engine.py

✅ Pull emails
✅ AI Triage
✅ Show

Urgent
Needs Reply
FYI
Ignore

✅ Save after triage

For Sample:
sample_threads_saved.json
sample_threads.csv
sample_threads.db

For Gmail:
gmail_threads.json
gmail_threads.csv
gmail_threads.db

Total = 6 files

Sample Threads
Gmail via engine.py

After clicking Pull & Triage, regardless of which source is selected, the app should automatically:
Fetch threads
Run AI triage
Display them
Save locally

When source is Sample Threads, save:
✅ sample_threads_saved.json
✅ sample_threads.csv
✅ sample_threads.db

When source is Gmail via engine.py, save:
✅ gmail_threads.json
✅ gmail_threads.csv
✅ gmail_threads.db

Total generated files:

sample_threads_saved.json
sample_threads.csv
sample_threads.db

gmail_threads.json
gmail_threads.csv
gmail_threads.db

Exactly 6 files.
***************************************************
Phase 2

Generate drafts

Keep AI draft

Show original mail

Generate All Drafts

Regenerate
****************************************************
Phase 3

Approval

Edit

Approve

Reject

If Gmail

→ actually send email

If Sample

→ demo only

Save approved drafts
*****************************************
Phase 4

Export

Markdown

HTML

Preview

Proof

Everything stays.
******************************************

exports/
│
├── gmail_threads_triaged.json
├── gmail_threads_triaged.csv
├── gmail_threads_triaged.db
│
├── gmail_drafts.json
├── gmail_drafts.csv
├── gmail_drafts.db
│
├── gmail_reviewed.json
├── gmail_reviewed.csv
├── gmail_reviewed.db
│
└── gmail_sent.json

When we create a project in the Google Cloud Console, enable the Gmail API, and download credentials.json,
we're creating OAuth credentials. 
Those credentials are required regardless of whether you're using:

Google Python API
Google Java API
Google Node.js API
A Gmail MCP server

------------------------------------
5. One important point

If project already has a token.json that was created without the Calendar scope (for example, only Gmail scopes), 
Google will not automatically add the new Calendar permission.

After adding:
"https://www.googleapis.com/auth/calendar"

to SCOPES, must delete token.json and rerun the application 
so the OAuth consent screen appears again and requests Calendar access. 
Otherwise, you'll get authorization errors when calling the Calendar API.