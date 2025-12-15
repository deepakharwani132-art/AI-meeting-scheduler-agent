# ---------------------------------------------------------
# MEETING SCHEDULER AGENT – FULL VERSION (Login first)
# Python + Streamlit + Google Calendar + Email
# ---------------------------------------------------------

import os, csv, uuid
import streamlit as st
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
import smtplib
from email.mime.text import MIMEText

# ---------------- CONFIG ----------------
st.set_page_config("Meeting Scheduler", "📅", layout="wide")
DATA_DIR = "data"
CSV_FILE = f"{DATA_DIR}/meetings.csv"
SERVICE_ACCOUNT_FILE = f"google_service_account.json"
TZ = ZoneInfo("Asia/Karachi")
HOST_EMAIL = os.environ.get("SMTP_USER")
os.makedirs(DATA_DIR, exist_ok=True)

# ---------------- GOOGLE CALENDAR ----------------
from google.oauth2 import service_account
from googleapiclient.discovery import build

@st.cache_resource
def get_calendar_service():
    creds = service_account.Credentials.from_service_account_file(
        SERVICE_ACCOUNT_FILE,
        scopes=["https://www.googleapis.com/auth/calendar"]
    )
    return build("calendar", "v3", credentials=creds)

calendar_service = get_calendar_service()

# ---------------- EMAIL ----------------
def send_email(to_email, subject, body):
    try:
        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = HOST_EMAIL
        msg["To"] = to_email
        with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
            server.login(HOST_EMAIL, os.environ.get("SMTP_PASS"))
            server.send_message(msg)
    except Exception as e:
        st.warning(f"Email failed: {e}")

# ---------------- CSV STORAGE ----------------
def load_meetings():
    if os.path.exists(CSV_FILE):
        with open(CSV_FILE, newline='', encoding='utf-8') as f:
            return list(csv.DictReader(f))
    return []

def save_meetings(meetings):
    if meetings:
        with open(CSV_FILE, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=meetings[0].keys())
            writer.writeheader()
            writer.writerows(meetings)

# ---------------- CONFLICT CHECK ----------------
def has_conflict(start, end, exclude_id=None):
    meetings = load_meetings()
    for m in meetings:
        if exclude_id and m['id'] == exclude_id:
            continue
        m_start = datetime.combine(datetime.fromisoformat(m['date']),
                                   datetime.strptime(m['time'], "%H:%M").time()).replace(tzinfo=TZ)
        m_end = m_start + timedelta(minutes=int(m.get("duration", 60)))
        if start < m_end and end > m_start:
            return True
    if start < datetime.now(TZ):
        return True
    return False

# ---------------- LOGIN ----------------
if 'logged_in' not in st.session_state:
    st.session_state.logged_in = False

# Sidebar logout button
if st.session_state.get('logged_in', False):
    with st.sidebar:
        if st.button("Logout 🚪"):
            # Reset login-related session state
            st.session_state.logged_in = False
            st.session_state.groq_api_key = ""
            st.session_state.pop("edit_id", None)
            st.session_state.pop("edit_mode", None)
            st.stop()  # Stop and show login page

# Login form
if not st.session_state.logged_in:
    st.header("🔒 Login Required")
    with st.form("login_form"):
        username = st.text_input("Username")
        password = st.text_input("Password", type="password")
        groq_api_key = st.text_input("Groq API Key", type="password")
        login_submit = st.form_submit_button("Login")
    if login_submit:
        if username == "deepak" and password == "12345" and groq_api_key.strip() != "":
            st.session_state.logged_in = True
            st.session_state.groq_api_key = groq_api_key
            st.toast("✅ Logged in successfully")
            st.stop()  # Stop to refresh and show main app
        else:
            st.error("❌ Invalid credentials")

# ---------------- MAIN APP ----------------
else:
    st.header("📅 Schedule a Meeting with Deepak Harwani")

    # --- Create meeting form ---
    with st.form("meeting_form"):
        col1, col2 = st.columns(2)
        with col1:
            date = st.date_input("Meeting Date")
            time = st.time_input("Meeting Time")
        with col2:
            topic = st.text_input("Meeting Topic")
            duration = st.selectbox("Duration (minutes)", [30, 60, 90])

        email = st.text_input("Your Email")
        phone = st.text_input("Phone / WhatsApp Number")
        reminder = st.selectbox("Email Reminder", ["15 minutes before", "30 minutes before"])

        submit = st.form_submit_button("Create Meeting")

    if submit:
        start_dt = datetime.combine(date, time).replace(tzinfo=TZ)
        end_dt = start_dt + timedelta(minutes=duration)

        if has_conflict(start_dt, end_dt):
            st.error("❌ Time slot already booked or in the past")
        else:
            event_body = {
                "summary": topic,
                "start": {"dateTime": start_dt.isoformat(), "timeZone": str(TZ)},
                "end": {"dateTime": end_dt.isoformat(), "timeZone": str(TZ)}
            }

            created_event = calendar_service.events().insert(
                calendarId="deepakharwani132@gmail.com", body=event_body
            ).execute()

            meetings = load_meetings()
            meeting_data = {
                "id": str(uuid.uuid4()),
                "topic": topic,
                "date": date.isoformat(),
                "time": time.strftime("%H:%M"),
                "duration": duration,
                "email": email,
                "phone": phone,
                "calendar_event_id": created_event["id"],
                "created_at": datetime.now(TZ).isoformat()
            }
            meetings.append(meeting_data)
            save_meetings(meetings)

            send_email(email, "Meeting Confirmed",
                       f"Your meeting '{topic}' is scheduled on {date} at {time}.")
            send_email(HOST_EMAIL, "Meeting Scheduled",
                       f"You scheduled a meeting '{topic}' on {date} at {time} with {email}.")
            st.success("✅ Meeting created, email sent, calendar updated")

    # --- Meetings on selected date with Edit/Delete ---
    st.header("📅 Meetings on Selected Date")
    meetings = load_meetings()
    selected_date = st.date_input("Select a date to view meetings", key="view_date")
    meetings_on_date = [m for m in meetings if m['date'] == selected_date.isoformat()]

    if meetings_on_date:
        for m in meetings_on_date:
            st.markdown(f"**{m['time']} - {m['topic']} (Attendee: {m['email']})**")
            col1, col2 = st.columns([1, 1])
            with col1:
                if st.button(f"✏️ Edit {m['topic']}", key=f"edit_{m['id']}"):
                    st.session_state.edit_id = m['id']
                    st.session_state.edit_mode = True
                    st.stop()
            with col2:
                if st.button(f"🗑️ Delete {m['topic']}", key=f"delete_{m['id']}"):
                    try:
                        calendar_service.events().delete(
                            calendarId="deepakharwani132@gmail.com",
                            eventId=m['calendar_event_id']
                        ).execute()
                    except:
                        pass
                    meetings = [x for x in meetings if x['id'] != m['id']]
                    save_meetings(meetings)
                    send_email(m['email'], "Meeting Cancelled",
                               f"Your meeting '{m['topic']}' on {m['date']} at {m['time']} has been cancelled.")
                    send_email(HOST_EMAIL, "Meeting Cancelled",
                               f"Your meeting '{m['topic']}' on {m['date']} at {m['time']} with {m['email']} has been cancelled.")
                    st.success("✅ Meeting deleted successfully")
                    st.stop()

    # --- Edit Meeting Form ---
    if st.session_state.get('edit_mode', False) and 'edit_id' in st.session_state:
        edit_meeting = next((x for x in meetings if x['id'] == st.session_state.edit_id), None)
        if edit_meeting:
            st.subheader(f"✏️ Edit Meeting: {edit_meeting['topic']}")
            with st.form("edit_form"):
                new_date = st.date_input("Date", datetime.fromisoformat(edit_meeting['date']))
                new_time = st.time_input("Time", datetime.strptime(edit_meeting['time'], '%H:%M').time())
                new_topic = st.text_input("Topic", edit_meeting['topic'])
                new_email = st.text_input("Attendee Email", edit_meeting['email'])
                new_phone = st.text_input("Phone", edit_meeting['phone'])
                new_duration = st.selectbox("Duration (minutes)", [30, 60, 90],
                                            index=[30,60,90].index(edit_meeting['duration']))

                if st.form_submit_button("Save Changes"):
                    start_dt = datetime.combine(new_date, new_time).replace(tzinfo=TZ)
                    end_dt = start_dt + timedelta(minutes=new_duration)

                    if has_conflict(start_dt, end_dt, exclude_id=edit_meeting['id']):
                        st.error("❌ Time slot already booked or in the past")
                    else:
                        calendar_service.events().update(
                            calendarId="deepakharwani132@gmail.com",
                            eventId=edit_meeting['calendar_event_id'],
                            body={
                                "summary": new_topic,
                                "start": {"dateTime": start_dt.isoformat(), "timeZone": str(TZ)},
                                "end": {"dateTime": end_dt.isoformat(), "timeZone": str(TZ)}
                            }
                        ).execute()

                        edit_meeting.update({
                            'date': new_date.isoformat(),
                            'time': new_time.strftime('%H:%M'),
                            'duration': new_duration,
                            'topic': new_topic,
                            'email': new_email,
                            'phone': new_phone
                        })
                        save_meetings(meetings)

                        send_email(new_email, "Meeting Updated",
                                   f"Your meeting '{new_topic}' has been updated to {new_date} at {new_time}.")
                        send_email(HOST_EMAIL, "Meeting Updated",
                                   f"Your meeting '{new_topic}' has been updated to {new_date} at {new_time} with {new_email}.")

                        st.success("✅ Meeting updated successfully")
                        st.session_state.edit_mode = False
                        st.session_state.pop('edit_id', None)
                        st.stop()

