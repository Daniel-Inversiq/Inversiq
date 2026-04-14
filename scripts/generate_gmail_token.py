# scripts/generate_gmail_token.py
#
# One-time script to generate gmail_token.json for the Gmail API.
#
# Prerequisites:
#   pip install google-auth-oauthlib
#
# Usage:
#   python scripts/generate_gmail_token.py
#
# Reads:  credentials.json  (OAuth client secret — download from Google Cloud Console)
# Writes: gmail_token.json  (access + refresh token — used by GmailProvider at runtime)

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",
]
CREDENTIALS_FILE = "credentials.json"
TOKEN_FILE = "gmail_token.json"


def main():
    flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_FILE, SCOPES)
    creds = flow.run_local_server(port=0)

    with open(TOKEN_FILE, "w") as f:
        f.write(creds.to_json())

    print(f"Token saved to {TOKEN_FILE}")


if __name__ == "__main__":
    main()
