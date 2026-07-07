import subprocess
import json
import sys
import os
import csv
import base64
import traceback
import sqlite3
import time

from datetime import datetime
import google.generativeai as genai

from triage import triage_inbox
from email.mime.text import MIMEText

from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from constants import SCOPES

# SCOPES = [
#     "https://www.googleapis.com/auth/gmail.readonly",
#     "https://www.googleapis.com/auth/gmail.send",
#     "https://www.googleapis.com/auth/calendar",#for schedule meeting
# ]

   
# *****************************************************************************************
def get_gmail_service():
    print("Inside get_gmail_service()")
    creds = None
# -----------------------------
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json",
                SCOPES,
            )
            creds = flow.run_local_server(port=0)

        with open("token.json", "w") as token:
            token.write(creds.to_json())

    print("get_gmail_service called")
    return build("gmail", "v1", credentials=creds)
# ***************For calendar************************************************


# ******************************************************************************
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
        api_key = os.getenv("GEMINI_API_KEY")

        if not api_key:
            return {
                "parsing_error": "GEMINI_API_KEY not found.",
                "raw": ""
            }

        genai.configure(api_key=api_key)

        model = genai.GenerativeModel("gemini-2.5-flash")

        # ----------------------------------------------------
        # Build thread text
        # ----------------------------------------------------
        messages = thread.get("messages", [])

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

        response = model.generate_content(prompt)

        raw = response.text.strip()

        # Remove markdown code fences
        if raw.startswith("```"):
            raw = raw.replace("```json", "")
            raw = raw.replace("```", "")
            raw = raw.strip()

        data = json.loads(raw)

        return {
            "proposed_times": data.get("proposed_times", []),
            "attendees": data.get("attendees", []),
            "topic": data.get("topic", ""),
            "duration_minutes": int(data.get("duration_minutes", 30)),
        }

    except Exception as e:
        return {
            "parsing_error": str(e),
            "raw": raw if "raw" in locals() else ""
        }
# *********************************************************************************
# def get_calendar_service():
#     creds = None

#     if os.path.exists("token.json"):
#         creds = Credentials.from_authorized_user_file(
#             "token.json",
#             SCOPES,
#         )

#     if not creds or not creds.valid:
#         if creds and creds.expired and creds.refresh_token:
#             creds.refresh(Request())
#         else:
#             flow = InstalledAppFlow.from_client_secrets_file(
#                 "credentials.json",
#                 SCOPES,
#             )
#             creds = flow.run_local_server(port=0)

#         with open("token.json", "w") as token:
#             token.write(creds.to_json())

#     return build("calendar", "v3", credentials=creds)
# --------------------------------------------------------------

# -------------Adding function to create meeting----------------------------------------------------
# from datetime import datetime, timedelta

# def schedule_meeting(
#     summary,
#     description,
#     attendee_email,
#     start_time,
#     duration_minutes=30,
# ):
#     service = get_calendar_service()

#     end_time = start_time + timedelta(minutes=duration_minutes)

#     event = {
#         "summary": summary,
#         "description": description,
#         "start": {
#             "dateTime": start_time.isoformat(),
#             "timeZone": "Asia/Kolkata",
#         },
#         "end": {
#             "dateTime": end_time.isoformat(),
#             "timeZone": "Asia/Kolkata",
#         },
#         "attendees": [
#             {"email": attendee_email},1
#         ],
#     }

#     event = (
#         service.events()
#         .insert(
#             calendarId="primary",
#             body=event,
#             sendUpdates="all",
#         )
#         .execute()
#     )

#     return event
# ----------------------------------------------------------------------------

def send_reply(thread_id: str, to: str, subject: str, body: str, message_id: str | None = None) -> dict:

    # if not subject.startswith("Re: "):
    if not subject.lower().startswith("re:"):    
        subject = f"Re: {subject}"

    message = MIMEText(body)
    message["to"] = to
    message["subject"] = subject

    if message_id:
        message["In-Reply-To"] = message_id
        message["References"] = message_id

    raw_message = base64.urlsafe_b64encode(message.as_bytes()).decode("utf-8")

    service = get_gmail_service()

    try:
        sent_message = service.users().messages().send(
            userId="me",
            body={
                "raw": raw_message,
                "threadId": thread_id,
            },
        ).execute()

        return {
            "message_id": sent_message["id"],
            "thread_id": thread_id,
            "status": "sent",
        }

    except Exception:
        # traceback.print_exc()   # Debug: prints full traceback in terminal
        # st.exception(e)         # Debug: shows full traceback in Streamlit UI
        raise
# --------------------------------------------------------------

def fetch_threads(max_results: int = 5) -> list[dict]:
    print("fetch_threads() called")
    get_gmail_service()
    server_script = os.path.join(
        os.path.dirname(__file__),
        "gmail-mcp-server", "dist", "index.js"
    )

    proc = subprocess.Popen(
        ["node", server_script],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding="utf-8",
        errors="replace"
    )

    next_id = 1
    # print(json.dumps(threads[0], indent=2)) #adding for debugging
    def send_request(method: str, params: dict = None) -> dict:
        nonlocal next_id

        req_id = next_id
        next_id += 1

        request = {
            "jsonrpc": "2.0",
            "id": req_id,
            "method": method,
        }

        if params:
            request["params"] = params

        proc.stdin.write(json.dumps(request) + "\n")
        proc.stdin.flush()

        start = time.time()

        while True:
            if time.time() - start > 30:
                raise TimeoutError("MCP request timeout")

            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("MCP server closed")

            try:
                response = json.loads(line.strip())
            except json.JSONDecodeError:
                continue

            if "id" not in response:
                continue

            if response["id"] != req_id:
                continue

            if "error" in response:
                raise RuntimeError(response["error"])

            return response.get("result", {})

    try:
        send_request("initialize", {
            "protocolVersion": "2024-11-05",
            "capabilities": {},
            "clientInfo": {
                "name": "engine.py",
                "version": "1.0.0",
            },
        })

        proc.stdin.write(json.dumps({
            "jsonrpc": "2.0",
            "method": "notifications/initialized",
        }) + "\n")
        proc.stdin.flush()

        result = send_request("tools/call", {
            "name": "fetch_threads",
            "arguments": {
                "maxResults": max_results,
            },
        })

        content_list = result.get("content", [])
#-----------------------------------------------------
    
    # -------------------------------------------------------------
        threads = None
        for item in content_list:
            if item.get("type") != "text":
              continue
            text = item.get("text", "").strip()
            print("MCP returned:")
            print(repr(text))

            if text.startswith("Error:"):
             raise RuntimeError(text)
            try:              
              parsed  = json.loads(text)
              if isinstance(parsed,list):
                  threads = parsed
                  break  #This exits the loop once valid JSON has been found.
            #   return threads
            except json.JSONDecodeError:
                continue
            # outside for loop
            #    raise RuntimeError(f"MCP returned invalid JSON:\n{text}")
        if threads is None:
         raise RuntimeError("No valid MCP thread JSON found")

        print("FINAL THREADS COUNT:", len(threads))

        print("FIRST THREAD:")
        print(json.dumps(threads[0], indent=2))

        return threads
        # raise RuntimeError("No valid MCP response found")
    finally:
        proc.terminate()
        try:
           proc.wait(timeout=3)
        except subprocess.TimeoutExpired:
           proc.kill()

def save_threads_to_json(threads, filename="gmail_threads_triaged.json"):
    """
    Save fetched + triaged threads to JSON.

    Works for:
    - Gmail threads
    - Sample threads
    """

    if not threads:
        print("No threads to save.")
        return

    with open(filename, "w", encoding="utf-8") as file:
        json.dump(
            threads,
            file,
            indent=4,
            ensure_ascii=False,
        )

    print(f"Threads saved to {filename}")

def save_threads_to_csv(threads, filename="gmail_threads_triaged.csv"):
    if not threads:
        print("No threads to save.")
        return

    with open(filename, "w", newline="", encoding="utf-8") as file:

        fieldnames = [
            "thread_id",
            "sender",
            "subject",
            "snippet",
            "date",
            "priority",
            "category",
            "reason",
        ]

        writer = csv.DictWriter(file, fieldnames=fieldnames)
        writer.writeheader()

        for t in threads:

            if "messages" in t:
                msg = t["messages"][-1] if t["messages"] else {}

                row = {
                    "thread_id": t.get("gmail_thread_id", t.get("id")),
                    "sender": msg.get("from", ""),
                    "subject": t.get("subject", ""),
                    # "snippet": msg.get("body", ""),
                    "snippet" : msg.get("body","")[:300],
                    "date": msg.get("date", ""),
                    "priority": t.get("priority", ""),
                    "category": t.get("category", ""),
                    "reason": t.get("reason", ""),
                }

            else:
                row = {
                    "thread_id": t.get("thread_id"),
                    "sender": t.get("sender", ""),
                    "subject": t.get("subject", ""),
                    "snippet": t.get("snippet", ""),
                    "date": t.get("date", ""),
                    "priority": t.get("priority", ""),
                    "category": t.get("category", ""),
                    "reason": t.get("reason", ""),
                }

            writer.writerow(row)

    print(f"Threads saved to {filename}")


def save_threads_to_db(threads, filename="gmail_threads_triaged.db"):
    conn = sqlite3.connect(filename)
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS email_threads (
            thread_id TEXT PRIMARY KEY,
            sender TEXT,
            subject TEXT,
            snippet TEXT,
            date TEXT,
            priority TEXT,
            category TEXT,
            reason TEXT
        )
    """)

    for thread in threads:

        if "messages" in thread and thread["messages"]:
            msg = thread["messages"][-1]

            thread_id = thread.get("gmail_thread_id") or thread.get("id")
            sender = msg.get("from", "")
            subject = thread.get("subject", "")
            snippet = msg.get("body", "")
            date = msg.get("date", "")
            priority = thread.get("priority", "")
            category = thread.get("category", "")
            reason = thread.get("reason", "")

        else:
            thread_id = thread.get("thread_id") or thread.get("id")
            sender = thread.get("sender", "")
            subject = thread.get("subject", "")
            snippet = thread.get("snippet", "")
            date = thread.get("date", "")
            priority = thread.get("priority", "")
            category = thread.get("category", "")
            reason = thread.get("reason", "")

        if not thread_id:
            continue

        cursor.execute("""
            INSERT OR REPLACE INTO email_threads
            (thread_id, sender, subject, snippet, date, priority, category, reason)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            thread_id,
            sender,
            subject,
            snippet,
            date,
            priority,
            category,
            reason
        ))

    conn.commit()
    conn.close()

    print(f"Threads saved to {filename}")


if __name__ == "__main__":

    try:
        threads = fetch_threads()
        print("Fetched threads")

        try:
            temp_flat = []

            for t in threads:
                last = t["messages"][-1] if t.get("messages") else {}
                print("LAST MESSAGE:")
                print(last) #for debugging
                raw_headers = last.get("headers", [])
                print(raw_headers)
             
                header_map = {
                    h.get("name", ""): h.get("value", "")
                    for h in raw_headers
                    if isinstance(h, dict)
                }
                print("HEADER MAP:")
                print(header_map)  
                print("SUBJECT:", header_map.get("Subject"))
                print("FROM:", header_map.get("From"))  #for debugging      
                temp_flat.append({
                    "thread_id": t.get("id", ""),
                    "sender": header_map.get("From", ""),
                    "subject": header_map.get("Subject", ""),
                    "snippet": last.get("body", ""),
                    "body": last.get("body", ""),
             })
            # The break is only for debugging. It prints information for the first email only, so terminal isn't flooded with output.
                # break #adding
            print("SAMPLE FLATTENED EMAIL:")
            if temp_flat:
                print(temp_flat[0])

            classified = triage_inbox(temp_flat)
            print("Threads fetched:", len(threads))
            print("Flattened:", len(temp_flat))
            print("Classified:", len(classified))
            for original, label in zip(threads, classified):
                original["priority"] = label.get("priority", "unknown")
                original["category"] = label.get("category", "")
                original["reason"] = label.get("reason", "")

            classified_threads = threads

        except Exception as e:
            print("Classification failed, using fallback")
            print(e)

            reason = str(e)
            classified_threads = []

            for thread in threads:
                classified_threads.append({
                    **thread,
                    "priority": "unknown",
                    "category": "unclassified",
                    "reason": reason,
                })

        print("Finished classification")
        print(f"Retrieved {len(threads)} threads\n")

        # for t in classified_threads:
        #     print(
        #         f"[{t['priority'].upper()}] "
        #         f"[{t['category']}] "
        #         f"{t.get('subject', '')} - {t['reason']}"
        #     )
        # for i, t in enumerate(classified_threads):
        #  if "priority" not in t:
        #    print(f"\nMissing priority in thread {i}")
        #    print(json.dumps(t, indent=2))
        #    continue
        # ------------Replace with single loop in place og 2 loop above---
        for i, t in enumerate(classified_threads):

            if "priority" not in t:
              print(f"\nMissing priority in thread {i}")
              print(json.dumps(t, indent=2))
              continue

            print(
              f"[{t.get('priority', 'unknown').upper()}] "
              f"[{t.get('category', '')}] "
              f"{t.get('subject', '')} - {t.get('reason', '')}"
            )
    
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)