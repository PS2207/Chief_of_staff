"""
task_logger.py

Maintains a persistent log of completed actions for the
AI Email Ghostwriter project.

Each log entry contains:
- timestamp
- action_type
- thread_subject
- detail
- id
"""


import json
import os
from datetime import datetime
from typing import Any

LOG_FILE = "action_log.json"

_HERE = os.path.dirname(os.path.abspath(__file__))
LOG_PATH = os.path.join(_HERE, LOG_FILE)

def _load_log():
    """
    Internal helper.

    Returns:
        list: Existing log records.
    """

    if not os.path.exists(LOG_FILE):
        return []

    try:
        with open(LOG_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)

            if isinstance(data, list):
                return data

            return []

    except (json.JSONDecodeError, OSError):
        return []


def _save_log(records):
    """
    Internal helper.

    Saves the complete log list.
    """

    try:
        with open(LOG_FILE, "w", encoding="utf-8") as file:
            json.dump(records, file, indent=2, ensure_ascii=False)

    except OSError:
        # Logging should never crash the application
        pass


def log_action(
    action_type: str,
    thread_subject: str, 
    detail: str, 
    action_id: str,)->dict[str, Any]:
    """
    Append a completed action to action_log.json.
    
    Args:
        action_type (str):
            "sent" or "booked"

        thread_subject (str):
            Email subject.

        detail (str):
            Recipient email (sent)
            OR
            Meeting title (booked)

        action_id (str):
            Gmail message_id
            OR
            Google Calendar event_id.
    """

    record: dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "action_type": action_type,
        "thread_subject": thread_subject,
        "detail": detail,
        "id": action_id,
    }
    existing = get_action_log()
    existing.append(record)
    
    with open(LOG_PATH, "w",encoding="utf-8") as f:
        json.dump(existing, f, indent=2, ensure_ascii=False)
        
    return record

    # records.append(record)
    # _save_log(records)


def get_action_log():
    """
    Return the complete action log.

    Returns:
        list
    """
    if not os.path.exists(LOG_PATH):
        return []
    
    try:
        with open(LOG_PATH, "r",encoding="utf-8") as f:
            data = json.load(f)
        if isinstance(data, list):
           return data  
        return []
    except (json.JSONDecodeError,OSError): 
        return [] 
     
    # return _load_log()


def clear_log():
    """
    Remove all log entries.
    """
    with open(LOG_PATH, "w",encoding="utf-8") as f:
        json.dump([], f)
    # _save_log([])
    
    
# after adding this code:
# run on terminal : python 
# then run:
# from task_logger import log_action, get_action_log, clear_log
# log_action('sent', 'Q3 Roadmap Review', 'alice@gmail.com', 'bob@gmail.com')
# log_action('booked', 'Q3 Roadmap Review', '30-min sync', 'evt_xyz789')
# log = get_action_log()
# print(f'Log has {len(log)} entries')
# for entry in log:
#     print(entry)
# clear_log()
# print("After clear:", get_action_log()) 
# it will create action_log.json with:
#     [
#   {
#     "timestamp": "2026-07-06T22:03:46.201492",
#     "action_type": "sent",
#     "thread_subject": "Q3 Roadmap Review",
#     "detail": "alice@gmail.com",
#     "id": "bob@gmail.com"
#   },
#   {
#     "timestamp": "2026-07-06T22:03:46.208548",
#     "action_type": "booked",
#     "thread_subject": "Q3 Roadmap Review",
#     "detail": "30-min sync",
#     "id": "evt_xyz789"
#   }
# ]
# Topic: Important meeting to discuss about revenue
# Duration:30min
# Proposed times:2026-06-28T14:00:00
# Attendees:-----