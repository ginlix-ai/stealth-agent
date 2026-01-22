"""
Gmail API Test Script

This script demonstrates how to authenticate and use the Gmail API.
It lists the user's Gmail labels.

Prerequisites:
1. Create a Gmail API project in Google Cloud Console
2. Download credentials.json and place it in the project root
3. Run this script and authorize access in the browser

Usage:
    python example/test_gmail_api.py
"""

import os
import os.path
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# If modifying these scopes, delete the file token.json.
# Available scopes:
# - gmail.readonly: Read emails and labels
# - gmail.send: Send emails
# - gmail.modify: Read, send, delete, and modify emails
# - gmail: Full access to Gmail (readonly + send + modify)
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
]


def main():
    """Shows basic usage of the Gmail API.
    
    Lists the user's Gmail labels.
    """
    # Get project root directory
    project_root = Path(__file__).parent.parent
    credentials_path = project_root / "credentials.json"
    token_path = project_root / "token.json"

    creds = None
    
    # The file token.json stores the user's access and refresh tokens, and is
    # created automatically when the authorization flow completes for the first time.
    if os.path.exists(token_path):
        creds = Credentials.from_authorized_user_file(str(token_path), SCOPES)
    
    # If there are no (valid) credentials available, let the user log in.
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Check if credentials.json exists
            if not os.path.exists(credentials_path):
                print(f"❌ Error: credentials.json not found at {credentials_path}")
                print("\nPlease:")
                print("1. Go to https://console.cloud.google.com/")
                print("2. Create a project and enable Gmail API")
                print("3. Create OAuth 2.0 credentials")
                print("4. Download credentials.json to the project root")
                return
            
            print(f"Using credentials from: {credentials_path}")
            try:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(credentials_path), SCOPES
                )
                creds = flow.run_local_server(port=0)
            except Exception as e:
                error_msg = str(e).lower()
                if "access_denied" in error_msg or "403" in error_msg or "verification" in error_msg:
                    print("\n" + "="*70)
                    print("❌ ACCESS BLOCKED: OAuth App in Testing Mode")
                    print("="*70)
                    print("\nYour OAuth app is in testing mode and needs test users.")
                    print("\n🔧 Quick Fix:")
                    print("1. Go to: https://console.cloud.google.com/apis/credentials/consent")
                    print("   (Or search: OAuth consent screen in Google Cloud Console)")
                    print("2. Select project: hackathon-483913")
                    print("3. Scroll to 'Test users' section")
                    print("4. Click '+ ADD USERS'")
                    print("5. Add your email: zhizhu0730@gmail.com")
                    print("6. Click 'ADD' and 'SAVE'")
                    print("7. Wait 1-2 minutes for changes to propagate")
                    print("8. Run this script again")
                    print("\n📖 For detailed instructions, see: example/GMAIL_OAUTH_SETUP.md")
                    print("="*70 + "\n")
                raise
        
        # Save the credentials for the next run
        with open(token_path, "w") as token:
            token.write(creds.to_json())
        print(f"✅ Credentials saved to: {token_path}")

    try:
        # Call the Gmail API
        print("\n📧 Connecting to Gmail API...")
        service = build("gmail", "v1", credentials=creds)
        results = service.users().labels().list(userId="me").execute()
        labels = results.get("labels", [])

        if not labels:
            print("No labels found.")
            return
        
        print(f"\n✅ Success! Found {len(labels)} Gmail labels:\n")
        for label in labels:
            print(f"  • {label['name']}")
        
    except HttpError as error:
        # TODO(developer) - Handle errors from gmail API.
        print(f"❌ An error occurred: {error}")


if __name__ == "__main__":
    main()

