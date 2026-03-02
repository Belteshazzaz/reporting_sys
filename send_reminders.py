#!/usr/bin/env python3
# send_reminders.py
# Email Reminder System for FCCPC Portal
# Sends automated reminders to users for monthly report submissions

import sys
import os
import smtplib
import logging
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from pathlib import Path

# Add project directory to path
project_dir = Path(__file__).resolve().parent
sys.path.insert(0, str(project_dir))

from email_config import (
    SMTP_SERVER, SMTP_PORT, SMTP_USE_TLS, SMTP_EMAIL, SMTP_PASSWORD,
    FROM_NAME, REPLY_TO, PORTAL_URL, SUBMISSION_DEADLINE,
    MAX_RETRIES, RETRY_DELAY, TIMEOUT, LOG_FILE, ENABLE_LOGGING,
    TEST_MODE, TEST_EMAIL, validate_config
)

# Setup logging
if ENABLE_LOGGING:
    log_dir = os.path.dirname(LOG_FILE)
    if not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)
    
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(LOG_FILE),
            logging.StreamHandler()
        ]
    )
else:
    logging.basicConfig(level=logging.INFO)

logger = logging.getLogger(__name__)


def get_email_template(user_name, reminder_type='first'):
    """
    Generate HTML email template
    
    Args:
        user_name (str): Name of the recipient
        reminder_type (str): 'first' or 'final'
    
    Returns:
        str: HTML email content
    """
    current_month = datetime.now().strftime('%B %Y')
    next_month = (datetime.now().replace(day=1).replace(month=datetime.now().month % 12 + 1)).strftime('%B %Y')
    
    if reminder_type == 'final':
        urgency_badge = '<span style="background: #dc3545; color: white; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: 600;">URGENT REMINDER</span>'
        urgency_text = 'This is your <strong>final reminder</strong>.'
    else:
        urgency_badge = '<span style="background: #ffc107; color: #212529; padding: 4px 12px; border-radius: 4px; font-size: 12px; font-weight: 600;">REMINDER</span>'
        urgency_text = 'This is a friendly reminder.'
    
    html = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>Monthly Report Reminder</title>
    </head>
    <body style="margin: 0; padding: 0; font-family: Arial, sans-serif; background-color: #f4f4f4;">
        <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #f4f4f4; padding: 20px;">
            <tr>
                <td align="center">
                    <!-- Main Container -->
                    <table width="600" cellpadding="0" cellspacing="0" style="background-color: #ffffff; border-radius: 8px; overflow: hidden; box-shadow: 0 2px 8px rgba(0,0,0,0.1);">
                        
                        <!-- Header with FCCPC Branding -->
                        <tr>
                            <td style="background: linear-gradient(135deg, #006837 0%, #004d28 100%); padding: 30px 40px; text-align: center;">
                                <h1 style="margin: 0; color: #ffffff; font-size: 24px; font-weight: 700;">
                                    Federal Competition & Consumer Protection Commission
                                </h1>
                                <p style="margin: 10px 0 0 0; color: #ffffff; opacity: 0.9; font-size: 14px;">
                                    Program Status Reporter Portal
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Urgency Badge -->
                        <tr>
                            <td style="padding: 20px 40px 0 40px; text-align: center;">
                                {urgency_badge}
                            </td>
                        </tr>
                        
                        <!-- Main Content -->
                        <tr>
                            <td style="padding: 20px 40px;">
                                <h2 style="color: #006837; margin: 0 0 20px 0; font-size: 20px;">
                                    Monthly Report Submission Reminder
                                </h2>
                                
                                <p style="color: #333; line-height: 1.6; margin: 0 0 15px 0;">
                                    Dear <strong>{user_name}</strong>,
                                </p>
                                
                                <p style="color: #333; line-height: 1.6; margin: 0 0 15px 0;">
                                    {urgency_text} Please ensure that you submit your monthly Program Status Reports for <strong>{current_month}</strong>.
                                </p>
                                
                                <!-- Deadline Box -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="background-color: #fff3cd; border-left: 4px solid #ffc107; margin: 20px 0; border-radius: 4px;">
                                    <tr>
                                        <td style="padding: 15px;">
                                            <p style="margin: 0; color: #856404; font-size: 14px;">
                                                <strong>⏰ Submission Deadline:</strong><br>
                                                <span style="font-size: 18px; font-weight: 700; color: #006837;">
                                                    {SUBMISSION_DEADLINE.upper()}
                                                </span>
                                            </p>
                                        </td>
                                    </tr>
                                </table>
                                
                                <p style="color: #333; line-height: 1.6; margin: 0 0 15px 0;">
                                    All reports must be submitted through the online portal before the deadline to ensure timely processing.
                                </p>
                                
                                <!-- Action Button -->
                                <table width="100%" cellpadding="0" cellspacing="0" style="margin: 25px 0;">
                                    <tr>
                                        <td align="center">
                                            <a href="{PORTAL_URL}" style="display: inline-block; background-color: #006837; color: #ffffff; padding: 14px 40px; text-decoration: none; border-radius: 6px; font-weight: 600; font-size: 16px;">
                                                Login to Portal
                                            </a>
                                        </td>
                                    </tr>
                                </table>
                                
                                <p style="color: #666; line-height: 1.6; margin: 20px 0 0 0; font-size: 14px;">
                                    If you have already submitted your reports, please disregard this message.
                                </p>
                                
                                <p style="color: #666; line-height: 1.6; margin: 15px 0 0 0; font-size: 14px;">
                                    For technical support or assistance, please contact the IT Administrator.
                                </p>
                            </td>
                        </tr>
                        
                        <!-- Footer -->
                        <tr>
                            <td style="background-color: #f8f9fa; padding: 20px 40px; text-align: center; border-top: 1px solid #dee2e6;">
                                <p style="margin: 0; color: #6c757d; font-size: 12px; line-height: 1.6;">
                                    This is an automated message from the FCCPC Portal System.<br>
                                    Please do not reply to this email.
                                </p>
                                <p style="margin: 10px 0 0 0; color: #6c757d; font-size: 12px;">
                                    © {datetime.now().year} Federal Competition & Consumer Protection Commission
                                </p>
                            </td>
                        </tr>
                        
                    </table>
                </td>
            </tr>
        </table>
    </body>
    </html>
    """
    
    return html


def send_email(to_email, to_name, subject, html_content):
    """
    Send email via M365/Outlook SMTP
    
    Args:
        to_email (str): Recipient email address
        to_name (str): Recipient name
        subject (str): Email subject
        html_content (str): HTML email body
    
    Returns:
        tuple: (success, error_message)
    """
    try:
        # Create message
        msg = MIMEMultipart('alternative')
        msg['From'] = f"{FROM_NAME} <{SMTP_EMAIL}>"
        msg['To'] = f"{to_name} <{to_email}>"
        msg['Subject'] = subject
        msg['Reply-To'] = REPLY_TO
        
        # Attach HTML content
        html_part = MIMEText(html_content, 'html')
        msg.attach(html_part)
        
        # Connect to SMTP server with retry logic
        for attempt in range(MAX_RETRIES):
            try:
                logger.info(f"Connecting to {SMTP_SERVER}:{SMTP_PORT} (Attempt {attempt + 1}/{MAX_RETRIES})")
                
                with smtplib.SMTP(SMTP_SERVER, SMTP_PORT, timeout=TIMEOUT) as server:
                    server.ehlo()
                    
                    if SMTP_USE_TLS:
                        server.starttls()
                        server.ehlo()
                    
                    # Login
                    logger.info(f"Authenticating as {SMTP_EMAIL}")
                    server.login(SMTP_EMAIL, SMTP_PASSWORD)
                    
                    # Send email
                    logger.info(f"Sending email to {to_email}")
                    server.send_message(msg)
                    
                    logger.info(f"✅ Email sent successfully to {to_email}")
                    return True, None
                    
            except smtplib.SMTPException as smtp_err:
                logger.warning(f"SMTP error on attempt {attempt + 1}: {str(smtp_err)}")
                
                if attempt < MAX_RETRIES - 1:
                    import time
                    time.sleep(RETRY_DELAY)
                else:
                    return False, f"SMTP error after {MAX_RETRIES} attempts: {str(smtp_err)}"
            
            except Exception as conn_err:
                logger.warning(f"Connection error on attempt {attempt + 1}: {str(conn_err)}")
                
                if attempt < MAX_RETRIES - 1:
                    import time
                    time.sleep(RETRY_DELAY)
                else:
                    return False, f"Connection error after {MAX_RETRIES} attempts: {str(conn_err)}"
        
        return False, "Max retries exceeded"
        
    except Exception as e:
        error_msg = f"Unexpected error: {str(e)}"
        logger.error(error_msg)
        return False, error_msg


def send_reminders(reminder_type='first'):
    """
    Send reminder emails to all active users
    
    Args:
        reminder_type (str): 'first' (25th) or 'final' (28th)
    
    Returns:
        dict: Statistics about sent emails
    """
    logger.info(f"=" * 60)
    logger.info(f"Starting {reminder_type.upper()} reminder email batch")
    logger.info(f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    logger.info(f"=" * 60)
    
    # Validate configuration
    is_valid, error_msg = validate_config()
    if not is_valid:
        logger.error(f"Configuration error: {error_msg}")
        return {'success': 0, 'failed': 0, 'error': error_msg}
    
    # Import Flask app and models
    try:
        from app import app, User
        
        with app.app_context():
            # Get all active users
            if TEST_MODE:
                logger.warning("🧪 TEST MODE ENABLED - Sending only to test email")
                users = [{'email': TEST_EMAIL, 'name': 'Test User'}]
            else:
                query = User.query.filter_by(is_enabled=True).all()
                users = [{'email': user.email, 'name': user.name} for user in query]
            
            logger.info(f"Found {len(users)} active user(s)")
            
            # Determine subject based on reminder type
            if reminder_type == 'final':
                from email_config import SUBJECT_FINAL_REMINDER
                subject = SUBJECT_FINAL_REMINDER
            else:
                from email_config import SUBJECT_FIRST_REMINDER
                subject = SUBJECT_FIRST_REMINDER
            
            # Send emails
            stats = {'success': 0, 'failed': 0, 'errors': []}
            
            for user in users:
                logger.info(f"\nProcessing: {user['name']} ({user['email']})")
                
                # Generate email content
                html_content = get_email_template(user['name'], reminder_type)
                
                # Send email
                success, error = send_email(user['email'], user['name'], subject, html_content)
                
                if success:
                    stats['success'] += 1
                else:
                    stats['failed'] += 1
                    stats['errors'].append({
                        'email': user['email'],
                        'error': error
                    })
                    logger.error(f"❌ Failed to send to {user['email']}: {error}")
            
            # Log summary
            logger.info(f"\n" + "=" * 60)
            logger.info(f"EMAIL BATCH SUMMARY")
            logger.info(f"=" * 60)
            logger.info(f"Total users: {len(users)}")
            logger.info(f"✅ Successfully sent: {stats['success']}")
            logger.info(f"❌ Failed: {stats['failed']}")
            
            if stats['errors']:
                logger.error(f"\nFailed emails:")
                for err in stats['errors']:
                    logger.error(f"  - {err['email']}: {err['error']}")
            
            logger.info(f"=" * 60)
            
            return stats
            
    except Exception as e:
        error_msg = f"Error accessing database: {str(e)}"
        logger.error(error_msg)
        return {'success': 0, 'failed': 0, 'error': error_msg}


if __name__ == "__main__":
    # Parse command line arguments
    reminder_type = 'first'  # Default
    
    if len(sys.argv) > 1:
        if sys.argv[1] in ['first', 'final']:
            reminder_type = sys.argv[1]
        else:
            print("Usage: python send_reminders.py [first|final]")
            print("  first - Send first reminder (25th of month)")
            print("  final - Send final reminder (28th of month)")
            sys.exit(1)
    
    # Send reminders
    stats = send_reminders(reminder_type)
    
    # Exit with appropriate code
    if 'error' in stats:
        sys.exit(1)
    elif stats['failed'] > 0:
        sys.exit(2)
    else:
        sys.exit(0)
