# load_approved_drafts()
# save_approved_draft()
# from approval_gate import save_approved_draft, load_approved_drafts
# to
# from approval_utils import save_approved_draft, load_approved_drafts
# import datetime
from datetime import datetime
import os

import json


def load_approved_drafts():
    """Load previously approved drafts from the JSON file."""
    path = os.path.join(os.path.dirname(__file__), "approved_drafts.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    return []

def save_approved_draft(draft_text, subject, replying_to, model, edited=False):
    """Append an approved draft to approved_drafts.json with a timestamp."""
    path = os.path.join(os.path.dirname(__file__), "approved_drafts.json")
    drafts = load_approved_drafts()
    drafts.append(
        {
            "draft": draft_text,
            "subject": subject,
            "replying_to": replying_to,
            "model": model,
            "edited": edited,
            "approved_at": datetime.now().isoformat(),
        }
    )
    with open(path, "w", encoding="utf-8") as f:
        json.dump(drafts, f, indent=2)
