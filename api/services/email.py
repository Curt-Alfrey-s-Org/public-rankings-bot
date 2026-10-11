import os
import logging
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from typing import Optional

logger = logging.getLogger(__name__)


async def send_verification_email(to_email: str, username: str, token: str) -> bool:
    """
    Send email verification email to user via Google Workspace SMTP.
    
    Args:
        to_email: User's email address
        username: User's username
        token: Email verification token
        
    Returns:
        True if successful, False otherwise
    """
    try:
        sender_email = os.getenv('SMTP_EMAIL', 'user11@example.com')
        sender_password = os.getenv('SMTP_PASSWORD', '')
        
        if not sender_password:
            logger.warning("SMTP_PASSWORD not configured, cannot send email")
            return False
        
        # Get bot name from environment or default
        bot_name = os.getenv('BOT_NAME', 'Pro Billiards Software')
        
        base_url = os.getenv('PUBLIC_URL', 'https://www.probilliardssoftware.com').rstrip('/')
        verification_url = f"{base_url}/verify-email?token={token}"
        
        # Create email
        message = MIMEMultipart('alternative')
        message['Subject'] = f"Verify Your {bot_name} Account"
        message['From'] = sender_email
        message['To'] = to_email
        
        # HTML email content
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto;">
              <h2>Welcome to {bot_name}!</h2>
              <p>Hi {username},</p>
              <p>Thanks for setting up your account. Please verify your email address by clicking the link below:</p>
              <p>After verification, you'll be asked to set a new password for your account.</p>
              <p style="margin: 30px 0;">
                <a href="{verification_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                  Verify Email Address
                </a>
              </p>
              <p>Or copy and paste this link in your browser:</p>
              <p style="word-break: break-all;">{verification_url}</p>
              <p style="color: #666; font-size: 12px;">
                This link expires in 24 hours.<br>
                If you didn't create this account, please ignore this email.
              </p>
            </div>
          </body>
        </html>
        """
        
        part = MIMEText(html, 'html')
        message.attach(part)
        
        # Send email via Google Workspace SMTP
        with smtplib.SMTP_SSL('smtp.example.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, message.as_string())
        
        logger.info(f"Verification email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send verification email: {str(e)}")
        return False


async def send_password_reset_email(to_email: str, username: str, token: str) -> bool:
    """
    Send password reset email to user via Google Workspace SMTP.
    
    Args:
        to_email: User's email address
        username: User's username
        token: Password reset token
        
    Returns:
        True if successful, False otherwise
    """
    try:
        sender_email = os.getenv('SMTP_EMAIL', 'user11@example.com')
        sender_password = os.getenv('SMTP_PASSWORD', '')
        
        if not sender_password:
            logger.warning("SMTP_PASSWORD not configured, cannot send email")
            return False
        
        bot_name = os.getenv('BOT_NAME', 'Pro Billiards Software')
        base_url = os.getenv('PUBLIC_URL', 'https://www.probilliardssoftware.com').rstrip('/')
        reset_url = f"{base_url}/reset-password?token={token}"
        
        # Create email
        message = MIMEMultipart('alternative')
        message['Subject'] = f"Reset Your {bot_name} Password"
        message['From'] = sender_email
        message['To'] = to_email
        
        # HTML email content
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto;">
              <h2>Password Reset Request</h2>
              <p>Hi {username},</p>
              <p>We received a request to reset your password. Click the link below to set a new password:</p>
              <p style="margin: 30px 0;">
                <a href="{reset_url}" style="background-color: #4CAF50; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px;">
                  Reset Password
                </a>
              </p>
              <p>Or copy and paste this link in your browser:</p>
              <p style="word-break: break-all;">{reset_url}</p>
              <p style="color: #666; font-size: 12px;">
                This link expires in 1 hour.<br>
                If you didn't request this reset, please ignore this email or contact support.
              </p>
            </div>
          </body>
        </html>
        """
        
        part = MIMEText(html, 'html')
        message.attach(part)
        
        # Send email via Google Workspace SMTP
        with smtplib.SMTP_SSL('smtp.example.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, message.as_string())
        
        logger.info(f"Password reset email sent to {to_email}")
        return True
    except Exception as e:
        logger.error(f"Failed to send password reset email: {str(e)}")
        return False


async def send_welcome_email_admin_created(to_email: str, username: str) -> bool:
    """
    Send thank-you/welcome email to user created by admin. No verification required; they can log in immediately.
    Explains that they can use Forgot password if needed and to keep their email correct in User Settings.
    """
    try:
        sender_email = os.getenv('SMTP_EMAIL', 'user11@example.com')
        sender_password = os.getenv('SMTP_PASSWORD', '')
        if not sender_password:
            logger.warning("SMTP_PASSWORD not configured, cannot send welcome email")
            return False
        bot_name = os.getenv('BOT_NAME', 'Pro Billiards Software')
        base_url = os.getenv('PUBLIC_URL', 'https://www.probilliardssoftware.com').rstrip('/')
        message = MIMEMultipart('alternative')
        message['Subject'] = f"Welcome to {bot_name}"
        message['From'] = sender_email
        message['To'] = to_email
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto;">
              <h2>Welcome to {bot_name}!</h2>
              <p>Hi {username},</p>
              <p>Your account has been created. You can log in at <a href="{base_url}">{base_url}</a> with your username and password.</p>
              <p>If you ever forget your password, use the &quot;Forgot password?&quot; link on the login page. We'll send a reset link to this email.</p>
              <p>Please ensure your email address is correct in User Settings so account notifications and password resets reach you.</p>
              <p style="color: #666; font-size: 12px;">If you didn't expect this email, you can ignore it or contact support.</p>
            </div>
          </body>
        </html>
        """
        part = MIMEText(html, 'html')
        message.attach(part)
        with smtplib.SMTP_SSL('smtp.example.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, message.as_string())
        logger.info(f"Welcome email sent to {to_email} (admin-created user)")
        return True
    except Exception as e:
        logger.error(f"Failed to send welcome email: {str(e)}")
        return False


async def send_password_changed_by_admin(to_email: str, username: str, new_password: str) -> bool:
    """
    Send email to user when admin/super_admin sets or resets their password.
    Includes the new password so they can log in. User must change it on next login (OWASP).
    """
    try:
        sender_email = os.getenv('SMTP_EMAIL', 'user11@example.com')
        sender_password = os.getenv('SMTP_PASSWORD', '')
        if not sender_password:
            logger.warning("SMTP_PASSWORD not configured, cannot send password change email")
            return False
        bot_name = os.getenv('BOT_NAME', 'Pro Billiards Software')
        base_url = os.getenv('PUBLIC_URL', 'https://www.probilliardssoftware.com').rstrip('/')
        message = MIMEMultipart('alternative')
        message['Subject'] = f"Your {bot_name} password has been changed"
        message['From'] = sender_email
        message['To'] = to_email
        html = f"""
        <html>
          <body style="font-family: Arial, sans-serif;">
            <div style="max-width: 600px; margin: 0 auto;">
              <h2>Your password has been changed</h2>
              <p>Hi {username},</p>
              <p>An administrator has set a new password for your account. Your temporary password is:</p>
              <p style="margin: 20px 0; padding: 15px; background: #f5f5f5; font-family: monospace; font-size: 16px;"><strong>{new_password}</strong></p>
              <p>Log in at <a href="{base_url}">{base_url}</a> with your username and this password. You will be required to set a new password on first login.</p>
              <p style="color: #666; font-size: 12px;">If you did not expect this email, contact support immediately.</p>
            </div>
          </body>
        </html>
        """
        part = MIMEText(html, 'html')
        message.attach(part)
        with smtplib.SMTP_SSL('smtp.example.com', 465) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, to_email, message.as_string())
        logger.info(f"Password change email sent to {to_email} (admin-set password)")
        return True
    except Exception as e:
        logger.error(f"Failed to send password change email: {str(e)}")
        return False
