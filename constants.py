
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/calendar",
]

# ==========================
# Sources
# ==========================

SOURCE_SAMPLE = "Sample threads"
SOURCE_GMAIL = "Gmail via engine.py"

# ==========================
# Priorities
# ==========================

PRIORITY_URGENT = "urgent"
PRIORITY_NEEDS_REPLY = "needs-reply"
PRIORITY_FYI = "fyi"
PRIORITY_IGNORE = "ignore"
PRIORITY_UNKNOWN = "unknown"

# ==========================
# Workflow Phases
# ==========================

PHASE_INBOX = "inbox"
PHASE_DRAFT = "draft"
PHASE_APPROVAL = "approval"
PHASE_EXPORT = "export"

# ==========================
# File Prefixes
# ==========================

FILE_PREFIX_SAMPLE = "sample_threads"
FILE_PREFIX_GMAIL = "gmail_threads"

STATUS_REJECTED = "rejected"
STATUS_SENT = "sent"
STATUS_APPROVED = "approved"
STATUS_DRAFT = "draft"
STATUS_NONE = "none"