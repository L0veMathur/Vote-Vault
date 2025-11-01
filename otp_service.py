# otp_service.py
import random
import hashlib
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime, timedelta
import os

class OTPService:
    def __init__(self):
        self.otp_storage = {}  # {email: {'otp_hash', 'expires', 'attempts'}}
        self.otp_validity_minutes = 5
        self.max_attempts = 5
        self.rate_limit = {}  # {email: [timestamps]}
        
    def generate_otp(self):
        """Generate a 6-digit OTP"""
        return str(random.randint(100000, 999999))
    
    def hash_otp(self, otp):
        """Hash OTP for secure storage"""
        return hashlib.sha256(otp.encode()).hexdigest()
    
    def can_request_otp(self, email):
        """Check if user can request OTP (rate limiting)"""
        now = datetime.now()
        hour_ago = now - timedelta(hours=1)
        
        # Clean old timestamps
        if email in self.rate_limit:
            self.rate_limit[email] = [
                ts for ts in self.rate_limit[email] if ts > hour_ago
            ]
            
            # Check if exceeded rate limit (3 requests per hour)
            if len(self.rate_limit[email]) >= 3:
                return False, "Too many OTP requests. Please try again later."
        
        return True, None
    
    def store_otp(self, email, otp):
        """Store OTP with expiration"""
        otp_hash = self.hash_otp(otp)
        expires = datetime.now() + timedelta(minutes=self.otp_validity_minutes)
        
        self.otp_storage[email] = {
            'otp_hash': otp_hash,
            'expires': expires,
            'attempts': 0
        }
        
        # Track rate limiting
        if email not in self.rate_limit:
            self.rate_limit[email] = []
        self.rate_limit[email].append(datetime.now())
        
        return True
    
    def verify_otp(self, email, otp):
        """Verify OTP"""
        if email not in self.otp_storage:
            return False, "No OTP found. Please request a new one."
        
        stored = self.otp_storage[email]
        
        # Check expiration
        if datetime.now() > stored['expires']:
            del self.otp_storage[email]
            return False, "OTP has expired. Please request a new one."
        
        # Check attempts
        if stored['attempts'] >= self.max_attempts:
            del self.otp_storage[email]
            return False, "Too many failed attempts. Please request a new OTP."
        
        # Verify OTP
        otp_hash = self.hash_otp(otp)
        if otp_hash == stored['otp_hash']:
            del self.otp_storage[email]  # One-time use
            return True, "OTP verified successfully"
        else:
            stored['attempts'] += 1
            return False, f"Invalid OTP. {self.max_attempts - stored['attempts']} attempts remaining."
    
    def send_otp_email(self, email, voter_name, otp):
        """Send OTP via email"""
        try:
            # Email configuration
            smtp_server = os.getenv('SMTP_SERVER', 'smtp.gmail.com')
            smtp_port = int(os.getenv('SMTP_PORT', '587'))
            smtp_username = os.getenv('SMTP_USERNAME', '')
            smtp_password = os.getenv('SMTP_PASSWORD', '')
            
            # Check if email is configured
            if not smtp_username or not smtp_password:
                print("⚠️  Email not configured. OTP would be sent to:", email)
                print(f"🔐 OTP (for testing): {otp}")
                return True, otp  # Return OTP for testing
            
            # Create message
            message = MIMEMultipart('alternative')
            message['Subject'] = 'Your Voting OTP Code'
            message['From'] = smtp_username
            message['To'] = email
            
            # HTML content
            html_content = f"""
            <!DOCTYPE html>
            <html>
            <head>
                <style>
                    body {{ font-family: Arial, sans-serif; background: #f4f4f4; padding: 20px; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 30px; border-radius: 10px; }}
                    .header {{ text-align: center; color: #667eea; }}
                    .otp-box {{ 
                        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                        color: white; 
                        padding: 20px; 
                        text-align: center;
                        font-size: 36px;
                        letter-spacing: 8px;
                        border-radius: 10px;
                        margin: 20px 0;
                        font-weight: bold;
                    }}
                    .info {{ background: #f0f8ff; padding: 15px; border-radius: 5px; margin: 20px 0; }}
                    .footer {{ text-align: center; color: #666; font-size: 12px; margin-top: 20px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1 class="header">🗳️ Secure Voting Portal</h1>
                    <p>Hello <strong>{voter_name}</strong>,</p>
                    <p>Your One-Time Password (OTP) for voting authentication is:</p>
                    
                    <div class="otp-box">
                        {otp}
                    </div>
                    
                    <div class="info">
                        <strong>⏱️ Valid for {self.otp_validity_minutes} minutes</strong><br>
                        <small>Expires at: {(datetime.now() + timedelta(minutes=self.otp_validity_minutes)).strftime('%I:%M %p')}</small>
                    </div>
                    
                    <p>⚠️ <strong>Important Security Notes:</strong></p>
                    <ul>
                        <li>Never share this OTP with anyone</li>
                        <li>Our staff will never ask for your OTP</li>
                        <li>If you didn't request this, please ignore this email</li>
                    </ul>
                    
                    <div class="footer">
                        <hr>
                        <p>Secure Voting System | {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
                        <p>This is an automated message. Please do not reply.</p>
                    </div>
                </div>
            </body>
            </html>
            """
            
            # Attach HTML content
            html_part = MIMEText(html_content, 'html')
            message.attach(html_part)
            
            # Send email
            with smtplib.SMTP(smtp_server, smtp_port) as server:
                server.starttls()
                server.login(smtp_username, smtp_password)
                server.send_message(message)
            
            print(f"✅ OTP sent successfully to {email}")
            return True, None
            
        except Exception as e:
            print(f"❌ Error sending email: {e}")
            # For development: print OTP to console
            print(f"🔐 OTP (for testing): {otp}")
            return True, otp  # Return OTP for testing even if email fails
    
    def cleanup_expired_otps(self):
        """Clean up expired OTPs (optional maintenance)"""
        now = datetime.now()
        expired = [email for email, data in self.otp_storage.items() 
                   if data['expires'] < now]
        
        for email in expired:
            del self.otp_storage[email]
        
        return len(expired)
