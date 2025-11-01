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
        
    def validate_voter(self, voter_id, dob, email):
        """
        Validate voter against Excel registry
        Returns: (success, session_token, voter_info)
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
        
        # Generate secure session token
        session_token = secrets.token_urlsafe(32)
        session_data = {
            'voter_id': voter_id,
            'name': voter.iloc[0]['Name'],
            'created': datetime.utcnow().isoformat(),
            'expires': (datetime.utcnow() + timedelta(hours=1)).isoformat()
        }
        
        # Encrypt session data
        encrypted_session = self.cipher.encrypt(
            json.dumps(session_data).encode()
        )
        self.active_sessions[session_token] = encrypted_session
        
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