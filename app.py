# app.py (Flask example)
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import hashlib
import json
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Import services
from auth_service import VoterAuthService
from kyc_service import KYCService
from blockchain_lite import TamperEvidenceChain
from vote_service import VoteProcessor
from excel_manager import ExcelManager
from anti_replay import AntiReplayProtection
from security_config import SecurityConfig
from otp_service import OTPService

app = Flask(__name__)
CORS(app, resources={r"/api/*": {"origins": "*"}})  # Enable CORS for frontend

# Initialize services
keys = SecurityConfig.load_keys()
auth_service = VoterAuthService('voter_registry.xlsx', keys['session_key'])
kyc_service = KYCService('kyc_storage', keys['pii_encryption_key'])
tamper_chain = TamperEvidenceChain('vote_chain.json')
vote_processor = VoteProcessor(auth_service, kyc_service, tamper_chain)
excel_manager = ExcelManager('voter_registry.xlsx', 'vote_records.xlsx', 'candidates.xlsx')
anti_replay = AntiReplayProtection()
otp_service = OTPService()

# Load voter registry and candidates at startup
excel_manager.load_voter_registry()
excel_manager.load_candidates()
excel_manager.load_vote_records()

# ========== HTML ROUTES ==========

@app.route('/')
def index():
    """Serve the login page"""
    return send_file('login.html')

@app.route('/vote')
def vote_page():
    """Serve the voting page"""
    return send_file('voting.html')

@app.route('/login')
def login_page():
    """Serve the login page"""
    return send_file('login.html')

@app.route('/<path:filename>')
def serve_static(filename):
    """Serve static files (CSS, JS, etc.)"""
    if os.path.exists(filename):
        return send_file(filename)
    return "File not found", 404

# ========== API ENDPOINTS ==========

@app.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({'status': 'ok', 'message': 'Server is running'}), 200

@app.route('/api/candidates', methods=['GET'])
def get_candidates():
    """Get list of candidates"""
    try:
        candidates = excel_manager.get_candidates()
        return jsonify({
            'success': True,
            'candidates': candidates
        }), 200
    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Voter authentication endpoint - Step 1: Validate credentials and send OTP"""
    try:
        data = request.json
        
        success, temp_token, voter_info = auth_service.validate_voter(
            data['voter_id'],
            data['dob'],
            data['email']
        )
        
        if success:
            # Check rate limiting
            can_request, error_msg = otp_service.can_request_otp(data['email'])
            if not can_request:
                return jsonify({
                    'success': False,
                    'error': error_msg
                }), 429
            
            # Generate and send OTP
            otp = otp_service.generate_otp()
            otp_service.store_otp(data['email'], otp)
            
            # Send OTP via email
            email_sent, test_otp = otp_service.send_otp_email(
                data['email'], 
                voter_info['name'], 
                otp
            )
            
            response_data = {
                'success': True,
                'requires_otp': True,
                'temp_token': temp_token,
                'message': f'OTP sent to {data["email"][:3]}***@{data["email"].split("@")[1]}'
            }
            
            # Include OTP in response for testing if email not configured
            if test_otp:
                response_data['test_otp'] = test_otp
                response_data['message'] += ' (Check console for OTP)'
            
            return jsonify(response_data), 200
        else:
            return jsonify({
                'success': False,
                'error': voter_info.get('error', 'Authentication failed') if voter_info else 'Invalid credentials'
            }), 401
    except Exception as e:
        print(f"Error in login: {e}")
        return jsonify({
            'success': False,
            'error': 'Server error'
        }), 500

@app.route('/api/auth/verify-otp', methods=['POST'])
def verify_otp():
    """Verify OTP and complete login - Step 2"""
    try:
        data = request.json
        email = data.get('email')
        otp = data.get('otp')
        temp_token = data.get('temp_token')
        
        # Verify OTP
        otp_valid, message = otp_service.verify_otp(email, otp)
        
        if otp_valid:
            # Complete login and create session
            success, session_token, voter_info = auth_service.complete_login_after_otp(temp_token)
            
            if success:
                return jsonify({
                    'success': True,
                    'session_token': session_token,
                    'voter_info': voter_info,
                    'message': 'Login successful'
                }), 200
            else:
                return jsonify({
                    'success': False,
                    'error': voter_info.get('error', 'Session creation failed')
                }), 401
        else:
            return jsonify({
                'success': False,
                'error': message
            }), 401
            
    except Exception as e:
        print(f"Error in verify_otp: {e}")
        return jsonify({
            'success': False,
            'error': 'Verification failed'
        }), 500

@app.route('/api/auth/resend-otp', methods=['POST'])
def resend_otp():
    """Resend OTP"""
    try:
        data = request.json
        email = data.get('email')
        temp_token = data.get('temp_token')
        
        # Verify temp_token is still valid
        if temp_token not in auth_service.pending_otp_verifications:
            return jsonify({
                'success': False,
                'error': 'Session expired. Please login again.'
            }), 401
        
        # Check rate limiting
        can_request, error_msg = otp_service.can_request_otp(email)
        if not can_request:
            return jsonify({
                'success': False,
                'error': error_msg
            }), 429
        
        # Get voter info
        voter_info = auth_service.pending_otp_verifications[temp_token]['voter_info']
        
        # Generate and send new OTP
        otp = otp_service.generate_otp()
        otp_service.store_otp(email, otp)
        
        email_sent, test_otp = otp_service.send_otp_email(
            email, 
            voter_info['name'], 
            otp
        )
        
        response_data = {
            'success': True,
            'message': 'New OTP sent successfully'
        }
        
        if test_otp:
            response_data['test_otp'] = test_otp
        
        return jsonify(response_data), 200
        
    except Exception as e:
        print(f"Error in resend_otp: {e}")
        return jsonify({
            'success': False,
            'error': 'Failed to resend OTP'
        }), 500

@app.route('/api/kyc/upload', methods=['POST'])
def upload_kyc():
    """KYC image upload endpoint"""
    try:
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        voter_info = auth_service.verify_session(session_token)
        if not voter_info:
            return jsonify({'error': 'Invalid session'}), 401
        
        if 'kyc_image' not in request.files:
            return jsonify({'error': 'No image provided'}), 400
        
        image_file = request.files['kyc_image']
        image_bytes = image_file.read()
        timestamp = request.form.get('timestamp')
        
        image_hash, file_path = kyc_service.process_kyc_image(
            image_bytes,
            voter_info['voter_id'],
            timestamp
        )
        
        return jsonify({
            'success': True,
            'image_hash': image_hash,
            'encrypted_reference': os.path.basename(file_path)
        }), 200
    except Exception as e:
        print(f"Error in upload_kyc: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/vote/submit', methods=['POST'])
def submit_vote():
    """Vote submission endpoint"""
    try:
        data = request.json
        session_token = request.headers.get('Authorization', '').replace('Bearer ', '')
        
        voter_info = auth_service.verify_session(session_token)
        if not voter_info:
            return jsonify({'error': 'Invalid session'}), 401
        
        # Anti-replay check
        voter_id_hash = hashlib.sha256(voter_info['voter_id'].encode()).hexdigest()
        can_vote, error = anti_replay.check_duplicate_vote(voter_id_hash)
        if not can_vote:
            return jsonify({'error': error}), 403
        
        # Generate nonce
        nonce = anti_replay.generate_nonce(voter_info['voter_id'], data['timestamp'])
        
        # Process vote
        success, receipt = vote_processor.process_vote(
            session_token,
            data['vote_choice'],
            data['kyc_image_hash'],
            request.remote_addr
        )
        
        if success:
            # Register vote (anti-replay)
            anti_replay.register_vote(voter_id_hash, nonce, data['timestamp'])
            
            # Mark voter as voted in Excel
            excel_manager.mark_voter_as_voted(voter_info['voter_id'])
            
            # Add vote record to vote_records.xlsx
            excel_manager.add_vote_record(
                voter_id=voter_info['voter_id'],
                voter_name=voter_info.get('name', 'Unknown'),
                candidate_voted=data['vote_choice'],
                ip_address=request.remote_addr,
                geolocation_city='Unknown',  # Can be enhanced with geolocation API
                geolocation_country='Unknown',
                kyc_image_hash=data['kyc_image_hash'],
                block_hash=receipt.get('block_hash', 'N/A'),
                vote_hash=receipt.get('vote_hash', 'N/A')
            )
            
            # Update candidate vote count
            excel_manager.update_candidate_vote_count(data['vote_choice'])
            
            return jsonify({
                'success': True,
                'receipt': receipt
            }), 200
        else:
            return jsonify({
                'success': False,
                'error': receipt.get('error')
            }), 400
    except Exception as e:
        print(f"Error in submit_vote: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({
            'success': False,
            'error': f'Server error: {str(e)}'
        }), 500

@app.route('/api/verify/<voter_id_hash>', methods=['GET'])
def verify_vote(voter_id_hash):
    """Vote verification endpoint (public)"""
    proof = tamper_chain.get_vote_proof(voter_id_hash)
    
    if proof:
        return jsonify({
            'verified': True,
            'proof': proof
        }), 200
    else:
        return jsonify({
            'verified': False,
            'error': 'Vote not found'
        }), 404

@app.route('/api/chain/verify', methods=['GET'])
def verify_chain():
    """Chain integrity verification endpoint"""
    is_valid, error_index = tamper_chain.verify_chain_integrity()
    
    return jsonify({
        'valid': is_valid,
        'total_blocks': len(tamper_chain.chain),
        'error_at_block': error_index
    }), 200

@app.route('/api/admin/export', methods=['POST'])
def export_results():
    """Export vote results to Excel (admin only)"""
    # TODO: Add admin authentication
    
    # Decrypt votes and prepare export data
    vote_records = []
    for voter_id_hash, encrypted_vote in vote_processor.votes_encrypted.items():
        decrypted = auth_service.cipher.decrypt(encrypted_vote)
        vote_data = json.loads(decrypted.decode())
        
        # Get block info
        proof = tamper_chain.get_vote_proof(voter_id_hash)
        
        vote_records.append({
            'Timestamp': vote_data['timestamp'],
            'VoterID': vote_data['voter_id'],
            'Name': vote_data['voter_name'],
            'Vote': vote_data['vote_choice'],
            'GeolocationCity': 'Unknown',  # TODO: Extract from chain
            'GeolocationCountry': 'Unknown',
            'KYCImageHash': proof['vote_hash'],
            'BlockHash': vote_data['block_hash'],
            'VoteHash': proof['vote_hash']
        })
    
    excel_manager.export_vote_log(vote_records)
    
    return jsonify({
        'success': True,
        'file': 'vote_results.xlsx',
        'total_votes': len(vote_records)
    }), 200

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0', port=5000)