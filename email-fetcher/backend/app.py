import imaplib
import email
from email.header import decode_header
from flask import Flask, request, jsonify
from flask_cors import CORS
from dotenv import load_dotenv
import os
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import Flow
from googleapiclient.discovery import build

load_dotenv()

app = Flask(__name__)
CORS(app)

IMAP_SERVERS = {
    "gmail": "imap.gmail.com",
    "outlook": "outlook.office365.com",
    "yahoo": "imap.mail.yahoo.com",
}

GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def get_gmail_service(access_token, refresh_token, client_id, client_secret):
    creds = Credentials(
        token=access_token,
        refresh_token=refresh_token,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=client_id,
        client_secret=client_secret,
    )
    return build("gmail", "v1", credentials=creds)


def decode_str(s):
    if s is None:
        return ""
    decoded = decode_header(s)
    result = []
    for part, charset in decoded:
        if isinstance(part, bytes):
            result.append(part.decode(charset or "utf-8", errors="replace"))
        else:
            result.append(part)
    return " ".join(result)


def get_body_gmail(payload):
    if "parts" in payload:
        for part in payload["parts"]:
            if part["mimeType"] == "text/plain":
                data = part["body"].get("data", "")
                return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
            elif "parts" in part:
                result = get_body_gmail(part)
                if result:
                    return result
    elif payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")
    return ""


def search_gmail(access_token, refresh_token, client_id, client_secret, recipient=None, keywords=None):
    try:
        service = get_gmail_service(access_token, refresh_token, client_id, client_secret)

        query_parts = []
        if recipient:
            query_parts.append(f"to:{recipient} OR from:{recipient}")
        if keywords:
            for keyword in keywords.split(","):
                keyword = keyword.strip()
                if keyword:
                    query_parts.append(f"subject:{keyword}")

        query = " ".join(query_parts) if query_parts else "in:inbox"

        results = service.users().messages().list(
            userId="me", q=query, maxResults=50
        ).execute()

        messages = results.get("messages", [])
        emails = []

        for msg_ref in messages:
            msg = service.users().messages().get(
                userId="me", id=msg_ref["id"], format="full"
            ).execute()

            headers = msg.get("payload", {}).get("headers", [])
            from_addr = next((h["value"] for h in headers if h["name"] == "From"), "")
            to_addr = next((h["value"] for h in headers if h["name"] == "To"), "")
            subject = next((h["value"] for h in headers if h["name"] == "Subject"), "")
            date = next((h["value"] for h in headers if h["name"] == "Date"), "")
            body = get_body_gmail(msg.get("payload", {}))

            emails.append({
                "id": msg["id"],
                "from": from_addr,
                "to": to_addr,
                "subject": subject,
                "date": date,
                "body": body[:500] if body else "",
            })

        return {"emails": emails, "count": len(emails)}

    except Exception as e:
        return {"error": str(e)}


def search_imap(provider, email_addr, password, recipient=None, keywords=None):
    if provider not in IMAP_SERVERS:
        return {"error": f"Unsupported provider: {provider}"}

    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVERS[provider])
        mail.login(email_addr, password)
        mail.select("INBOX")

        search_criteria = []
        if recipient:
            search_criteria.append(f'(OR TO "{recipient}" FROM "{recipient}")')
        if keywords:
            for keyword in keywords.split(","):
                keyword = keyword.strip()
                if keyword:
                    search_criteria.append(f'(SUBJECT "{keyword}")')
        if not search_criteria:
            search_criteria.append('ALL')

        criteria = " ".join(search_criteria) if len(search_criteria) > 1 else search_criteria[0]
        status, messages = mail.search(None, criteria)

        if status != "OK":
            return {"error": "Search failed"}

        email_ids = messages[0].split()
        emails = []

        for eid in email_ids[-50:]:
            status, msg_data = mail.fetch(eid, "(RFC822)")
            if status != "OK":
                continue

            msg = email.message_from_bytes(msg_data[0][1])
            from_addr = decode_str(msg.get("From", ""))
            to_addr = decode_str(msg.get("To", ""))
            subject = decode_str(msg.get("Subject", ""))
            date = msg.get("Date", "")

            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    ct = part.get_content_type()
                    if ct == "text/plain":
                        payload = part.get_payload(decode=True)
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="replace")
                        break
            else:
                payload = msg.get_payload(decode=True)
                if payload:
                    charset = msg.get_content_charset() or "utf-8"
                    body = payload.decode(charset, errors="replace")

            emails.append({
                "id": eid.decode(),
                "from": from_addr,
                "to": to_addr,
                "subject": subject,
                "date": date,
                "body": body[:500] if body else "",
            })

        mail.logout()
        return {"emails": emails, "count": len(emails)}

    except Exception as e:
        return {"error": str(e)}


@app.route("/api/auth/gmail", methods=["POST"])
def gmail_auth():
    data = request.json
    redirect_uri = data.get("redirect_uri", "http://localhost:5000/api/auth/callback")

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.getenv("GMAIL_CLIENT_ID"),
                "client_secret": os.getenv("GMAIL_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=GMAIL_SCOPES,
    )
    flow.redirect_uri = redirect_uri

    authorization_url, state = flow.authorization_url(
        access_type="offline", include_granted_scopes="true", prompt="consent"
    )

    return jsonify({"authorization_url": authorization_url, "state": state})


@app.route("/api/auth/callback", methods=["POST"])
def gmail_callback():
    data = request.json
    authorization_code = data.get("code")
    redirect_uri = data.get("redirect_uri", "http://localhost:5000/api/auth/callback")

    if not authorization_code:
        return jsonify({"error": "Authorization code required"}), 400

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": os.getenv("GMAIL_CLIENT_ID"),
                "client_secret": os.getenv("GMAIL_CLIENT_SECRET"),
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [redirect_uri],
            }
        },
        scopes=GMAIL_SCOPES,
    )
    flow.redirect_uri = redirect_uri

    try:
        flow.fetch_token(code=authorization_code)
        credentials = flow.credentials

        return jsonify({
            "access_token": credentials.token,
            "refresh_token": credentials.refresh_token,
            "client_id": os.getenv("GMAIL_CLIENT_ID"),
            "client_secret": os.getenv("GMAIL_CLIENT_SECRET"),
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/api/search", methods=["POST"])
def search():
    data = request.json
    if not data:
        return jsonify({"error": "No data provided"}), 400

    server = data.get("server", "gmail")
    recipient = data.get("recipient")
    keywords = data.get("keywords")

    if server == "gmail":
        access_token = data.get("access_token")
        refresh_token = data.get("refresh_token")
        client_id = data.get("client_id")
        client_secret = data.get("client_secret")

        if not access_token or not refresh_token:
            return jsonify({"error": "Gmail OAuth2 tokens required"}), 400

        result = search_gmail(
            access_token, refresh_token, client_id, client_secret, recipient, keywords
        )
    else:
        email_addr = data.get("email")
        password = data.get("password")
        if not email_addr or not password:
            return jsonify({"error": "Email and password are required"}), 400
        result = search_imap(server, email_addr, password, recipient, keywords)

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)


@app.route("/api/health", methods=["GET"])
def health():
    return jsonify({"status": "ok"})


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
