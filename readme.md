# Chief of Staff – AI Email Assistant

An AI-powered email assistant built with **Python** and **Streamlit** that helps professionals manage their inbox more efficiently. The application retrieves email threads from Gmail (or uses sample threads for demonstration), classifies emails using a Large Language Model (LLM), generates professional reply drafts, supports human approval before sending, and integrates with Google Calendar for meeting scheduling.

---

## Project Overview

Managing a busy inbox can be time-consuming. This project automates repetitive email tasks while keeping the user in control.

The application:

- Fetches email conversations
- Uses AI to understand each email
- Prioritizes emails by urgency
- Generates professional reply drafts
- Requires human approval before sending
- Supports Google Calendar meeting scheduling
- Exports processed data for record keeping

The project follows a **Human-in-the-Loop** workflow, ensuring AI never sends emails without user approval.

---

# Features

### AI Email Triage

The application automatically classifies emails into:

- 🚨 Urgent
- 💬 Needs Reply
- 📌 FYI
- 🗑 Ignore

Each classification includes AI-generated reasoning.


### Configurable Email Fetch Limit

The application allows users to specify how many email threads should be retrieved from Gmail before running the AI workflow.

Benefits include:

- Faster processing
- Reduced API usage
- Flexible inbox analysis
- Improved performance for large inboxes

Users can configure the number of email threads directly from the Streamlit interface before starting the pipeline.



### Robust Exception Handling

The application includes comprehensive error handling to ensure a reliable user experience.

Handled scenarios include:

- Gmail authentication failures
- Missing or invalid OAuth credentials
- Expired OAuth tokens
- API rate limit or quota exceeded
- Internet connectivity issues
- Empty inbox or no matching emails
- AI model response failures
- Calendar authorization errors
- Invalid user input
- Unexpected runtime exceptions

Meaningful error messages are displayed in the interface so users can understand and resolve issues easily.


### Interactive Streamlit Dashboard

The application provides an intuitive user interface with:

- Data source selection (Sample Threads or Gmail)
- Configurable email fetch limit
- AI pipeline progress tracking
- Email categorization dashboard
- Draft generation interface
- Human approval workflow
- Meeting scheduling support
- Export options

---

### AI Draft Generation

For actionable emails, the application generates professional reply drafts using a Large Language Model.

Features include:

- Generate Draft
- Regenerate Draft
- Edit Draft
- Save Draft

---

### Human Approval Workflow

Every AI-generated response must be reviewed before sending.

Users can:

- Approve
- Reject
- Edit

This Human-in-the-Loop approach prevents accidental AI-generated responses.

---

### Gmail Integration

Using the Gmail API, the application can:

- Fetch inbox threads
- Read email conversations
- Send replies inside the original Gmail thread

---

### Google Calendar Integration

The assistant can detect meeting requests inside emails and:

- Extract meeting information
- Check calendar availability
- Book meetings
- Avoid scheduling conflicts

---

### Export Support

Processed data can be exported for auditing and record keeping.

Supported formats include:

- JSON
- CSV
- SQLite Database

---

# Workflow

```
Choose Data Source
        │
        ▼
Sample Threads / Gmail Inbox
        │
        ▼
Fetch Email Threads
        │
        ▼
AI Email Triage
        │
        ▼
Priority Classification
(Urgent / Needs Reply / FYI / Ignore)
        │
        ▼
Generate AI Draft Replies
        │
        ▼
Human Approval
        │
        ▼
Send Reply (Gmail Mode)
        │
        ▼
Export Results
```

---

# Project Architecture

```
                Streamlit UI
                     │
                     ▼
                app.py
                     │
      ┌──────────────┴──────────────┐
      ▼                             ▼
 Sample Threads              Gmail API
      │                             │
      └──────────────┬──────────────┘
                     ▼
                 engine.py
                     ▼
                triage.py
                     ▼
          AI Priority Classification
                     ▼
            draft_machine.py
                     ▼
            approval_gate.py
                     ▼
          Gmail API / Export Files
```

---

# Tech Stack

| Technology | Purpose |
|------------|----------|
| Python | Backend |
| Streamlit | Web Interface |
| Gmail API | Email Integration |
| Google Calendar API | Meeting Scheduling |
| Google OAuth 2.0 | Authentication |
| Gemini / Groq LLM | AI Email Analysis |
| SQLite | Local Database |
| JSON | Data Storage |
| CSV | Data Export |

---

# Project Structure

```
chief-of-staff/
│
├── .devcontainer/               # Development container configuration
├── .venv/                       # Python virtual environment (not committed)
├── gmail-mcp-server/            # Gmail MCP Server
│
├── app.py                       # Streamlit application entry point
├── engine.py                    # Gmail integration and email retrieval
├── triage.py                    # AI-powered email classification
├── draft_machine.py             # AI draft generation
├── calendar_engine.py           # Google Calendar integration
├── approval_utils.py            # Draft approval utilities
├── context_builder.py           # Builds email context for the LLM
├── helper.py                    # Shared helper functions
├── constants.py                 # Application constants
├── proof_export.py              # Export reports and proofs
├── task_logger.py               # Logs user actions
│
├── sample_threads.json          # Demo email conversations
├── tone_profile.json            # Writing tone configuration
├── past_replies.json            # Previous reply examples
├── approved_drafts.json         # Approved draft storage
├── action_log.json              # Action history
│
├── gmail_threads_triaged.json   # Gmail triage output (JSON)
├── gmail_threads_triaged.csv    # Gmail triage output (CSV)
├── gmail_threads_triaged.db     # Gmail triage output (SQLite)
│
├── sample_threads_triaged.json  # Sample triage output (JSON)
├── sample_threads_triaged.csv   # Sample triage output (CSV)
├── sample_threads_triaged.db    # Sample triage output (SQLite)
│
├── requirements.txt             # Python dependencies
├── .gitignore                   # Git ignore rules
├── README.md                    # Project documentation
│
├── credentials.json             # Google OAuth credentials (local only)
├── token.json                   # OAuth access token (local only)
└── .env                         # Environment variables (local only)

---

# Installation

Clone the repository:

```bash
git clone <repository-url>
cd Chief-of-Staff
```

Create a virtual environment:
```bash
python -m venv .venv
```

Activate the environment:
For Windows-
```bash
.venv\Scripts\activate
```

Install dependencies:
```bash
pip install -r requirements.txt
```

Run the application:
```bash
streamlit run app.py
```

---

# Google OAuth Setup

To use live Gmail integration:

1. Create a Google Cloud Project.
2. Enable the Gmail API.
3. Enable the Google Calendar API.
4. Configure the OAuth Consent Screen.
5. Download the `credentials.json` file.
6. Place `credentials.json` in the project root.
7. Run the application and authorize access.

The first authorization creates a `token.json` file, which stores the OAuth access token securely.

---

# Environment Variables

Create a `.env` file:

```
GROQ_API_KEY=your_api_key
GOOGLE_API_KEY=your_api_key
```

---

# Demo Mode vs Live Gmail Mode

## Demo Mode

Uses:

- sample_threads.json

Features:

- AI Email Triage
- Draft Generation
- Human Approval
- Export

No access to personal Gmail accounts.

---

## Live Gmail Mode

Uses:

- Gmail API
- OAuth Authentication

Features:

- Fetch Gmail Threads
- AI Triage
- Generate Drafts
- Send Replies
- Calendar Integration

---

# Human-in-the-Loop Design

The application never sends AI-generated emails automatically.

Every generated response must be reviewed and approved by the user before being sent.

This approach improves reliability, accuracy, and user trust.

---

# Security

Sensitive files are intentionally excluded from GitHub:

- credentials.json
- token.json
- .env

The deployed application runs in Demo Mode to protect personal Gmail credentials and OAuth tokens.

---

# Future Improvements

- Multi-account Gmail support
- Attachment summarization
- Voice-controlled email replies
- Email sentiment analysis
- RAG-based email search
- Multi-language reply generation
- AI-powered follow-up reminders
- Team inbox collaboration

---

# License

This project is intended for educational and portfolio purposes.

---

# Author

**Pragya Sinha**

AI-powered Email Assistant built using Python, Streamlit, Gmail API, Google Calendar API, and Large Language Models.


---------------------------------------------------------------------------------------------------------------------------

NOTE:-
Troubleshooting

If you encounter import errors (such as ModuleNotFoundError) or see red underlines under import statements in VS Code, follow these steps.

1. Check Your Python Version
python --version

Make sure you are using the Python version recommended for this project.

2. Create a Virtual Environment
python -m venv .venv
3. Activate the Virtual Environment

Windows:
.venv\Scripts\activate

macOS / Linux:
source .venv/bin/activate

If activated successfully, your terminal will show (.venv) at the beginning of the line.

4. Install the Project Dependencies
pip install -r requirements.txt
5. Select the Correct Python Interpreter in VS Code
Press Ctrl + Shift + P
Search for Python: Select Interpreter
Select Python (.venv) from the list.

If you don't see it immediately, wait a few seconds or reload the VS Code window.

6. Restart VS Code

After installing dependencies or changing the interpreter, restart VS Code.

7. If the Error Still Exists

Check whether the required package is installed:

pip show <package-name>

Example:

pip show streamlit

If the package is not installed, install it using:

pip install <package-name>


Example:

pip install streamlit
Common Reasons for Import Errors
The virtual environment is not activated.
Project dependencies have not been installed.
VS Code is using the wrong Python interpreter.
The required package is missing.
The installed Python version is not compatible with the project.













"Why doesn't Gmail work on the deployed version?"

Answer:
"The application uses Google OAuth. The OAuth credentials and user tokens are confidential and are never committed to GitHub. To avoid exposing my personal Gmail account, the deployed version runs in Demo Mode with sample threads, while the local version demonstrates the complete Gmail and Calendar workflow."


"For security reasons, the public deployment runs in Demo Mode using sample email threads. This allows anyone to test the complete AI workflow without access to my personal Gmail account."

Then demonstrate:

✅ Pull & Triage
✅ Draft Generation
✅ Approval
✅ Edit
✅ Reject
✅ Export Proof

This shows the entire product workflow.

Run the project on your laptop:

"Locally, the same application connects to Gmail using OAuth. I don't expose my Google credentials publicly, so this feature is demonstrated only in my local environment."

Then demonstrate:

Fetch Gmail
Triage real emails
Generate AI drafts
Send email
Book meeting

This proves the integration works.

3. Mention why it's not on the public deployment

Say something like:

"Google OAuth credentials (credentials.json, token.json) and API keys are private and are intentionally excluded from GitHub. Therefore, the public deployment runs in Demo Mode while the local version demonstrates the full Gmail and Google Calendar integration."