# auth_service.py
import pandas as pd
import hashlib
import secrets
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import json

class VoterAuthService:
    def __init__(self, excel_path, secret_key):
        self.voter_db = pd.read_excel(excel_path)
        self.cipher = Fernet(secret_key)
        self.active_sessions = {}
        self.pending_otp_verifications = {}  # Store voter info pending OTP verification
        
    def validate_voter(self, voter_id, dob, email):
        """
        Validate voter credentials (Step 1 - Before OTP)
        Returns: (success, temp_token, voter_info)
        """
        # Query Excel data
        voter = self.voter_db[
            (self.voter_db['VoterID'] == voter_id) &
            (self.voter_db['DOB'] == dob) &
            (self.voter_db['Email'] == email)
        ]
        
        if voter.empty:
            return False, None, None
        
        # Check if already voted
        if voter.iloc[0].get('HasVoted', False):
            return False, None, {'error': 'Already voted'}
        
        # Generate temporary token for OTP verification
        temp_token = secrets.token_urlsafe(32)
        voter_info = {
            'voter_id': voter_id,
            'name': voter.iloc[0]['Name'],
            'email': email,
            'temp_token': temp_token
        }
        
        # Store pending verification
        self.pending_otp_verifications[temp_token] = {
            'voter_info': voter_info,
            'created': datetime.utcnow(),
            'expires': datetime.utcnow() + timedelta(minutes=10)
        }
        
        return True, temp_token, voter_info
    
    def complete_login_after_otp(self, temp_token):
        """
        Complete login after OTP verification (Step 2)
        Returns: (success, session_token, voter_info)
        """
        if temp_token not in self.pending_otp_verifications:
            return False, None, {'error': 'Invalid or expired verification token'}
        
        pending = self.pending_otp_verifications[temp_token]
        
        # Check expiration
        if datetime.utcnow() > pending['expires']:
            del self.pending_otp_verifications[temp_token]
            return False, None, {'error': 'Verification timeout. Please login again.'}
        
        voter_info = pending['voter_info']
        
        # Generate secure session token
        session_token = secrets.token_urlsafe(32)
        session_data = {
            'voter_id': voter_info['voter_id'],
            'name': voter_info['name'],
            'created': datetime.utcnow().isoformat(),
            'expires': (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }
        
        # Encrypt session data
        encrypted_session = self.cipher.encrypt(
            json.dumps(session_data).encode()
        )
        self.active_sessions[session_token] = encrypted_session
        
        # Clean up pending verification
        del self.pending_otp_verifications[temp_token]
        
        return True, session_token, session_data
    
    def verify_session(self, session_token):
        """Verify active session and return voter info"""
        if session_token not in self.active_sessions:
            return None
        
        encrypted_data = self.active_sessions[session_token]
        session_data = json.loads(
            self.cipher.decrypt(encrypted_data).decode()
        )
        
        # Check expiration
        if datetime.fromisoformat(session_data['expires']) < datetime.utcnow():
            del self.active_sessions[session_token]
            return None
        
        return session_data