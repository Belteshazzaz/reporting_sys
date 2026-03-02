# email_config.py
# M365/Outlook Email Configuration for FCCPC Portal
# Phase 2: Email Notifications System

import os
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# M365/Outlook SMTP Configuration
SMTP_SERVER = 'smtp.office365.com'
SMTP_PORT = 587
SMTP_USE_TLS = True

# Email Credentials (from .env file for security)
SMTP_EMAIL = os.environ.get('SMTP_EMAIL', 'itadmin@fccpc.gov.ng')
SMTP_PASSWORD = os.environ.get('SMTP_PASSWORD', '')

# Email Settings
FROM_EMAIL = SMTP_EMAIL
FROM_NAME = 'FCCPC Portal System'
REPLY_TO = SMTP_EMAIL

# Email Templates
SUBJECT_FIRST_REMINDER = 'Monthly Report Submission Reminder - Deadline Approaching'
SUBJECT_FINAL_REMINDER = 'URGENT: Final Reminder - Monthly Report Submission Due Soon'

# Report Submission Details
SUBMISSION_DEADLINE = '2nd of next month'
PORTAL_URL = 'http://72.61.102.87'

# Email Sending Settings
MAX_RETRIES = 3
RETRY_DELAY = 5  # seconds
TIMEOUT = 30  # seconds

# Logging
LOG_FILE = '/var/log/fccpc/email_reminders.log'
ENABLE_LOGGING = True

# Test Mode (set to False in production)
TEST_MODE = False
TEST_EMAIL = 'gabrieladekola3@gmail.com'  # Only send to this email when testing

def get_smtp_config():
    """
    Get SMTP configuration dictionary
    
    Returns:
        dict: SMTP configuration
    """
    return {
        'server': SMTP_SERVER,
        'port': SMTP_PORT,
        'use_tls': SMTP_USE_TLS,
        'email': SMTP_EMAIL,
        'password': SMTP_PASSWORD,
        'from_name': FROM_NAME,
        'reply_to': REPLY_TO
    }

def validate_config():
    """
    Validate email configuration
    
    Returns:
        tuple: (is_valid, error_message)
    """
    if not SMTP_EMAIL:
        return False, "SMTP_EMAIL not configured"
    
    if not SMTP_PASSWORD:
        return False, "SMTP_PASSWORD not configured in .env file"
    
    if not PORTAL_URL:
        return False, "PORTAL_URL not configured"
    
    return True, "Configuration valid"

if __name__ == "__main__":
    # Test configuration
    is_valid, message = validate_config()
    print(f"Configuration Status: {message}")
    
    if is_valid:
        print("\n✅ Email Configuration Valid!")
        print(f"SMTP Server: {SMTP_SERVER}:{SMTP_PORT}")
        print(f"From Email: {SMTP_EMAIL}")
        print(f"Portal URL: {PORTAL_URL}")
    else:
        print(f"\n❌ Configuration Error: {message}")
