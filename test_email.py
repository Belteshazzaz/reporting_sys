#!/usr/bin/env python3
# test_email.py
# Test script to verify email configuration and send test email

import sys
import os
from pathlib import Path

# Add project directory to path
project_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(project_dir))

from email_config import validate_config, SMTP_EMAIL, TEST_EMAIL
from send_reminders import send_email, get_email_template

def test_configuration():
    """Test email configuration"""
    print("\n" + "=" * 60)
    print("EMAIL CONFIGURATION TEST")
    print("=" * 60)
    
    is_valid, message = validate_config()
    
    if is_valid:
        print(f"✅ {message}")
        print(f"\nSMTP Email: {SMTP_EMAIL}")
        print(f"Test Recipient: {TEST_EMAIL}")
        return True
    else:
        print(f"❌ {message}")
        return False

def send_test_email():
    """Send a test email"""
    print("\n" + "=" * 60)
    print("SENDING TEST EMAIL")
    print("=" * 60)
    
    # Generate test email content
    html_content = get_email_template("Test User", reminder_type='first')
    subject = "🧪 TEST EMAIL - FCCPC Portal Reminder System"
    
    print(f"\nSending test email to: {TEST_EMAIL}")
    print("Please wait...")
    
    # Send email
    success, error = send_email(
        to_email=TEST_EMAIL,
        to_name="Test User",
        subject=subject,
        html_content=html_content
    )
    
    print("\n" + "=" * 60)
    
    if success:
        print("✅ TEST EMAIL SENT SUCCESSFULLY!")
        print(f"\nCheck inbox at: {TEST_EMAIL}")
        print("\nWhat to check:")
        print("  1. Email arrives in inbox (check spam folder too)")
        print("  2. FCCPC branding displays correctly")
        print("  3. 'Login to Portal' button works")
        print("  4. Email formatting looks professional")
        return True
    else:
        print("❌ TEST EMAIL FAILED")
        print(f"\nError: {error}")
        print("\nTroubleshooting:")
        print("  1. Check email credentials in .env file")
        print("  2. Verify SMTP settings (smtp.office365.com:587)")
        print("  3. Check if 2FA is enabled (use App Password)")
        print("  4. Ensure account is not locked")
        return False

def main():
    """Run email tests"""
    print("\n🚀 FCCPC PORTAL - EMAIL SYSTEM TEST")
    print("=" * 60)
    
    # Step 1: Test configuration
    if not test_configuration():
        print("\n❌ Configuration test failed. Please fix errors above.")
        sys.exit(1)
    
    # Step 2: Ask user to proceed
    print("\n" + "=" * 60)
    response = input("\nProceed with test email? (yes/no): ").strip().lower()
    
    if response not in ['yes', 'y']:
        print("\nTest cancelled.")
        sys.exit(0)
    
    # Step 3: Send test email
    if send_test_email():
        print("\n✅ ALL TESTS PASSED!")
        print("\nNext steps:")
        print("  1. Check your email inbox")
        print("  2. If email looks good, proceed with cron job setup")
        print("  3. If no email, check spam folder")
        sys.exit(0)
    else:
        print("\n❌ TEST FAILED")
        print("\nPlease fix the errors above before proceeding.")
        sys.exit(1)

if __name__ == "__main__":
    main()
