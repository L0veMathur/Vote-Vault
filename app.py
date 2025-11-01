# app.py (Flask example)
from flask import Flask, request, jsonify, send_file
from flask_cors import CORS
from werkzeug.utils import secure_filename
import os
import hashlib
import json

# Import services
from auth_service import VoterAuthService
from kyc_service import KYCService
from blockchain_lite import TamperEvidenceChain
from vote_service import VoteProcessor
from excel_manager import ExcelManager
from anti_replay import AntiReplayProtection
from security_config import SecurityConfig

app = Flask(__name__)
CORS(app)  # Enable CORS for frontend

# Initialize services
keys = SecurityConfig.load_keys()
auth_service = VoterAuthService('voter_registry.xlsx', keys['session_key'])
kyc_service = KYCService('kyc_storage', keys['pii_encryption_key'])
tamper_chain = TamperEvidenceChain('vote_chain.json')
vote_processor = VoteProcessor(auth_service, kyc_service, tamper_chain)
excel_manager = ExcelManager('voter_registry.xlsx', 'vote_results.xlsx')
anti_replay = AntiReplayProtection()

# Load voter registry at startup
excel_manager.load_voter_registry()

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

# ========== API ENDPOINTS ==========

@app.route('/api/auth/login', methods=['POST'])
def login():
    """Voter authentication endpoint"""
    data = request.json
    
    success, token, voter_info = auth_service.validate_voter(
        data['voter_id'],
        data['dob'],
        data['email']
    )
    
    if success:
        return jsonify({
            'success': True,
            'session_token': token,
            'voter_info': voter_info
        }), 200
    else:
        return jsonify({
            'success': False,
            'error': voter_info.get('error', 'Authentication failed')
        }), 401

@app.route('/api/kyc/upload', methods=['POST'])
def upload_kyc():
    """KYC image upload endpoint"""
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

@app.route('/api/vote/submit', methods=['POST'])
def submit_vote():
    """Vote submission endpoint"""
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
        
        return jsonify({
            'success': True,
            'receipt': receipt
        }), 200
    else:
        return jsonify({
            'success': False,
            'error': receipt.get('error')
        }), 400

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