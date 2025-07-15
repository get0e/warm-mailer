from fastapi import FastAPI, UploadFile, Form, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from email.mime.text import MIMEText
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request as GoogleRequest

import csv, io, time, base64, json, os, requests

from backend.gmail_auth import get_authorization_url, fetch_token

app = FastAPI()

# --- FIXED: Correct base path to root project directory ---
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
FRONTEND_DIR = os.path.join(BASE_DIR, "frontend")
TOKEN_DIR = os.path.join(BASE_DIR, "backend", "tokens")
os.makedirs(TOKEN_DIR, exist_ok=True)

# --- CORS ---
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # tighten for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- Serve static files ---
app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")

@app.get("/")
def serve_index():
    return FileResponse(os.path.join(FRONTEND_DIR, "index.html"))

@app.get("/authorize")
def authorize():
    return RedirectResponse(get_authorization_url())

@app.get("/auth/callback")
def callback(request: Request):
    code = request.query_params.get("code")
    state = request.query_params.get("state")
    if not code:
        print(" No code in callback")
        return {"error": "No code received from Google"}

    try:
        creds = fetch_token(code, state)
        print("Token fetched from Google")
    except Exception as e:
        print(" Token fetch failed:", e)
        return {"error": f"Token fetch failed: {e}"}

    try:
        profile_resp = requests.get(
            "https://gmail.googleapis.com/gmail/v1/users/me/profile",
            headers={"Authorization": f"Bearer {creds.token}"}
        )
        profile_json = profile_resp.json()
        user_email = profile_json.get("emailAddress")
        if not user_email:
            print(" Email fetch failed: no email returned")
            raise Exception("Could not get email address")
        print("Got user email:", user_email)
    except Exception as e:
        print("Failed to fetch user profile:", e)
        return {"error": f"Failed to fetch user profile: {e}"}

    try:
        token_path = os.path.join(TOKEN_DIR, f"{user_email}.json")
        print(" Writing token to:", token_path)

        token_data = {
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": creds.scopes
        }

        with open(token_path, "w") as f:
            json.dump(token_data, f, indent=2)

        print("Token file created successfully")

    except Exception as e:
        print(" Failed to write token file:", e)
        return {"error": f"Token write failed: {e}"}

    return RedirectResponse(f"http://localhost:8000/?email={user_email}")

@app.get("/check-auth")
def check_auth(email: str = None):
    print(f" /check-auth called with email: {email}")
    if not email:
        return {"authenticated": False, "error": "Missing email in query"}

    token_path = os.path.join(TOKEN_DIR, f"{email}.json")
    print(" Looking for token at:", token_path)

    if not os.path.exists(token_path):
        print(" Token file not found")
        return {"authenticated": False, "error": "Token not found for this email"}

    try:
        with open(token_path, "r") as f:
            token_data = json.load(f)

        creds = Credentials.from_authorized_user_info(token_data)
        print(" Loaded credentials object")

        if not creds.valid:
            print(" Token not valid")
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                with open(token_path, "w") as f:
                    f.write(creds.to_json())
                print(" Token refreshed")
            else:
                return {"authenticated": False, "error": "Token expired or invalid"}

        return {"authenticated": True, "email": email}

    except Exception as e:
        print(" Token error:", e)
        return {"authenticated": False, "error": f"Token error: {e}"}

@app.post("/send-emails")
async def send_emails(
    csv_file: UploadFile,
    sender: str = Form(...),
    subject: str = Form(...),
    body: str = Form(...)
):
    token_path = os.path.join(TOKEN_DIR, f"{sender}.json")
    if not os.path.exists(token_path):
        return {"error": f"No token found for {sender}. Please /authorize."}

    try:
        with open(token_path, "r") as f:
            token_data = json.load(f)
        creds = Credentials.from_authorized_user_info(token_data)

        if not creds.valid:
            if creds.expired and creds.refresh_token:
                creds.refresh(GoogleRequest())
                with open(token_path, "w") as f:
                    f.write(creds.to_json())
            else:
                return {"error": "Token expired or invalid for sender."}

        access_token = creds.token
    except Exception as e:
        return {"error": f"Failed to load token for {sender}: {e}"}

    contents = await csv_file.read()
    text = contents.decode("utf-8")
    reader = csv.reader(io.StringIO(text))
    recipients = [row[0].strip() for row in reader if row]

    sent, failed = 0, 0

    for recipient in recipients:
        try:
            name_part = recipient.split("@")[0].split(".")[0].capitalize()
            personalized = body.replace("{{name}}", name_part)

            msg = MIMEText(personalized)
            msg["to"] = recipient
            msg["from"] = sender
            msg["subject"] = subject

            raw = base64.urlsafe_b64encode(msg.as_bytes()).decode()
            headers = {
                "Authorization": f"Bearer {access_token}",
                "Content-Type": "application/json"
            }

            url = "https://gmail.googleapis.com/gmail/v1/users/me/messages/send"
            resp = requests.post(url, headers=headers, json={"raw": raw})

            if resp.status_code == 200:
                sent += 1
            else:
                failed += 1
                print(f"Failed for {recipient}: {resp.status_code} - {resp.text}")

            time.sleep(1)

        except Exception as e:
            failed += 1
            print(f" Exception for {recipient}: {e}")

    return {"status": "Emails processed", "sent": sent, "failed": failed}
