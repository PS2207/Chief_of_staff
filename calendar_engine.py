"""
in this file, have 5 functions :-
1) _build_calendar_service(), 
2) parse_meeting_request(thread), 
3) check_availability(service, time_min: str, time_max: str)
4) find_free_slot( proposed_times,duration_minutes)
5_ def create_event(summary, start_time, duration_minutes,attendees, description="")

"""

import uuid #for link send
import os
import json
from datetime import datetime, timedelta
from xml.parsers.expat import model

import google.generativeai as genai

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from constants import SCOPES
# import tzlocal
# timezone = tzlocal.get_localzone_name()
import re

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if GEMINI_API_KEY:
    genai.configure(api_key=GEMINI_API_KEY)
    MEETING_MODEL = genai.GenerativeModel("gemini-2.5-flash")
else:
    MEETING_MODEL = None


def _build_calendar_service():
    
    here = os.path.dirname(os.path.abspath(__file__))
    creds_path = os.path.join(here, "credentials.json")
    token_path = os.path.join(here, "token.json")
    
    print(f"[DEBUG] credentials path = {creds_path}")
    print(f"[DEBUG] token path = {token_path}")
    
    creds: Credentials | None = None
    if os.path.exists(token_path):
        print("[DEBUG] loading token.json exists")
        try:
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)
            print("[DEBUG] token.json loaded")
        except ValueError as e:
            print(f"[DEBUG] error token invalid: {e}")
            creds = None
    
    if not creds or not creds.valid:
        print("[DEBUG] need authentication")
        if creds and creds.expired and creds.refresh_token:
            print("[DEBUG] refereshing token")
            creds.refresh(Request())
            print("[DEBUG] token refreshed")
        else:
            print("[DEBUG] starting OAuth flow")
            if not os.path.exists(creds_path):
                raise FileNotFoundError(f"Google OAuth client secrets not found at {creds_path}")
            flow = InstalledAppFlow.from_client_secrets_file(
                creds_path,
                SCOPES,
            )
            creds = flow.run_local_server(
                host="localhost",
                port=8080,
            open_browser=True
            )
            print("[DEBUG] OAuth flow completed")
        print("[DEBUG] writing token.json")
        with open(token_path, "w", encoding="utf-8") as f:
            f.write(creds.to_json())
        print("[DEBUG] token.json written")
        
    print("[DEBUG] building calendar service")  
    
    service = build(
        "calendar",
        "v3",
        credentials=creds,
        cache_discovery=False
    )   
    print("[DEBUG] Calendar service built")  
    return service

# ---------------------------------------------------------
def parse_meeting_request(thread):
    """
    Uses Gemini to extract meeting information from an email thread.

    Returns:
        {
            "proposed_times": [...],
            "attendees": [...],
            "topic": "...",
            "duration_minutes": 30
        }

    or

        {
            "parsing_error": "...",
            "raw": "..."
        }
    """

    try:
        # api_key = os.getenv("GEMINI_API_KEY")

        # if not api_key:
        #     return {
        #         "parsing_error": "GEMINI_API_KEY not found.",
        #         "raw": ""
        #     }

        # genai.configure(api_key=api_key)

        # model = genai.GenerativeModel("gemini-2.5-flash")

        # ----------------------------------------------------
        # Build thread text
        # ----------------------------------------------------
        messages = thread.get("messages", [])
        if not messages:
         return {
         "parsing_error": "Thread contains no messages.",
         "raw": ""
        }
        conversation = []

        for msg in messages:
            conversation.append(
                f"""
From: {msg.get("from","")}
Date: {msg.get("date","")}

{msg.get("body","")}
"""
            )

        conversation_text = "\n\n".join(conversation)

        today = datetime.now().strftime("%Y-%m-%d")

        prompt = f"""
You are an assistant that extracts meeting requests from email threads.

Today's date is {today}.

Resolve relative dates such as:
- today
- tomorrow
- next Monday
- Friday afternoon

into ISO-8601 datetime strings whenever possible.

Return ONLY valid JSON.

Schema:

{{
    "proposed_times":[
        "2026-07-05T14:00:00"
    ],
    "attendees":[
        "alice@example.com",
        "bob@example.com"
    ],
    "topic":"One line meeting summary",
    "duration_minutes":30
}}

Rules:

- proposed_times must be a JSON array.
- attendees must contain email addresses only.
- topic must be short.
- duration_minutes must be an integer.
- If duration is missing, use 30.
- If no meeting is discussed, return empty arrays and empty topic.
- DO NOT include markdown.
- DO NOT explain anything.
- Output JSON only.

Email Thread:

{conversation_text}
"""
        if MEETING_MODEL is None:
          return {
           "parsing_error": "GEMINI_API_KEY not found.",
           "raw": ""
      }

        response = MEETING_MODEL.generate_content(prompt)
        if not response.text:
          return {
            "parsing_error": "Gemini returned an empty response.",
            "raw": ""
          }
        # response = model.generate_content(prompt)

        raw = response.text.strip()

        if raw.startswith("```"):
         raw = raw.replace("```json", "")
         raw = raw.replace("```", "")
         raw = raw.strip()
  

        data = json.loads(raw)
            # "duration_minutes": int(data.get("duration_minutes", 30)),
        try:
               duration = int(data.get("duration_minutes", 30))
        except (TypeError, ValueError):
               duration = 30
        
        return {
           "proposed_times": data.get("proposed_times", []),
           "attendees": data.get("attendees", []),
           "topic": data.get("topic", ""),
           "duration_minutes": duration,
}
    except Exception as e:
        print("Gemini meeting parser error:", e)
        return {
            "parsing_error": (
              "Meeting scheduling is currently unavailable. " 
              "because the AI API quota has been exhausted. " 
              "Please try again later or use a different API key."
        ),
        "raw": raw if "raw" in locals() else ""
        }
        
# ----------------------------------------------------------------
def check_availability(service, time_min: str, time_max: str) -> bool:
    """
    Checks whether the user's primary Google Calendar is free.

    Args:
        service: Google Calendar service returned by _build_calendar_service().
        time_min: ISO-8601 start datetime.
        time_max: ISO-8601 end datetime.

    Returns:
        True if calendar is free.
        False if busy or an error occurs.
    """

    try:
        start = datetime.fromisoformat(time_min.replace("Z", ""))
        # start = datetime.fromisoformat(start_time.replace("Z", "+00:00"))
        end = datetime.fromisoformat(time_max.replace("Z", ""))

        if start.tzinfo is None:
            time_min = start.isoformat(timespec="seconds") + "Z"
        else:
            time_min = start.isoformat(timespec="seconds")

        if end.tzinfo is None:
            time_max = end.isoformat(timespec="seconds") + "Z"
        else:
            time_max = end.isoformat(timespec="seconds")

        body = {
            "timeMin": time_min,
            "timeMax": time_max,
            "items": [
                {"id": "primary"}
            ]
        }

        result = (
            service.freebusy()
            .query(body=body)
            .execute()
        )

        busy = (
            result
            .get("calendars", {})
            .get("primary", {})
            .get("busy", [])
        )

        return len(busy) == 0

    except Exception as e:
        print(f"[Calendar] FreeBusy check failed: {e}")
        return False


def find_free_slot(
    proposed_times,
    duration_minutes,
):
    """
    Finds the first available meeting slot.

    Args:
        proposed_times:
            List of ISO datetime strings returned by Gemini.

        duration_minutes:
            Meeting duration.

    Returns:
        ISO datetime string if available.
        None otherwise.
    """
    
    print("1. Entered find_free_slot")
    try:
        duration = max(1, int(duration_minutes))
    except (TypeError, ValueError):
        duration = 30

    if not proposed_times:
        print("2. No proposed times")
        return None
    
    print("3. Before _build_calendar_service")
    try:
        service = _build_calendar_service()
    except Exception as e:
        print(f"[Calendar] Could not initialize Calendar service: {e}")
        return None

    print("4. After _build_calendar_service")
    
    for proposed in proposed_times:
        print("5. Proposed:", proposed)
        try:
            start = datetime.fromisoformat(
                proposed.replace("Z", "")
            )

            end = start + timedelta(minutes=duration)

            start_iso = start.isoformat(timespec="seconds")
            end_iso = end.isoformat(timespec="seconds")
            print("6. Before check_availability") 

            if check_availability(
                service,
                start_iso,
                end_iso,
            ):
                
             
             
                print("7. Slot available")
                return start_iso
            
            print("8. Slot busy")     

        except Exception as e:
            print(
                f"[Calendar] Skipping invalid proposed time "
                f"'{proposed}': {e}"
            )
            continue

    return None

# -------------------------------------------------
def create_event(
    summary,
    start_time,
    duration_minutes,
    attendees,
    description="",
):
    """
    Creates a Google Calendar event.

    Args:
        summary (str):
            Event title.

        start_time (str | datetime):
            ISO-8601 datetime string or datetime object.

        duration_minutes (int):
            Meeting duration.

        attendees (list[str]):
            List of attendee email addresses.

        description (str):
            Optional event description.

    Returns:
        dict:
            Full Google Calendar API response.
    """

    service = _build_calendar_service()

    # -----------------------------------------------------
    # Validate duration
    # -----------------------------------------------------
    try:
        duration = max(1, int(duration_minutes))
    except (TypeError, ValueError):
        duration = 30

    # -----------------------------------------------------
    # Parse start time
    # -----------------------------------------------------
    if isinstance(start_time, str):
        start = datetime.fromisoformat(
            start_time.replace("Z", "")
        )
    elif isinstance(start_time, datetime):
        start = start_time
    else:
        raise ValueError("start_time must be an ISO string or datetime.")

    end = start + timedelta(minutes=duration)

    # -----------------------------------------------------
    # Build attendee list
    # -----------------------------------------------------
    valid_attendees = []

    if attendees:
        for email in attendees:
            if isinstance(email, str):
                email = email.strip()

                if "@" in email:
                    valid_attendees.append(
                        {"email": email}
                    )

    # -----------------------------------------------------
    # Build event payload
    # -----------------------------------------------------
    event_body = {
        "summary": summary or "Meeting",
        "description": description,
        "start": {
            "dateTime": start.isoformat(timespec="seconds"),
            # "timeZone": "UTC",
            "timeZone": "Asia/Kolkata"
        },
        "end": {
            "dateTime": end.isoformat(timespec="seconds"),
            # "timeZone": "UTC",  # if both attendies in different country then use  this
            "timeZone": "Asia/Kolkata" # if both attendies in india then use 
        },
        "conferenceData": { #for sending link for meeting 
          "createRequest": {
            "requestId": str(uuid.uuid4()),
            "conferenceSolutionKey": {
              "type": "hangoutsMeet"
            }
           }
        }
    }

    if valid_attendees:
        event_body["attendees"] = valid_attendees

    # -----------------------------------------------------
    # Create Calendar event
    # -----------------------------------------------------
    created_event = (
        service.events()
        .insert(
            calendarId="primary",
            body=event_body,
            conferenceDataVersion=1, #adding for link
            sendUpdates="all",
        )
        .execute()
    )
    # for debuging link
    print("HTML:", created_event.get("htmlLink"))
    print("Meet:", created_event.get("hangoutLink"))
    print("Conference:", created_event.get("conferenceData"))

    return created_event        