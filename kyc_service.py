# kyc_service.py
import os
import hashlib
from datetime import datetime
from cryptography.fernet import Fernet
from PIL import Image
import io

class KYCService:
    def __init__(self, storage_path, encryption_key):
        self.storage_path = storage_path
        self.cipher = Fernet(encryption_key)
        os.makedirs(storage_path, exist_ok=True)
    
    def process_kyc_image(self, image_bytes, voter_id, timestamp):
        """
        Process KYC image: encrypt, store, return hash reference
        Returns: (image_hash, encrypted_file_path)
        """
        # Generate SHA-256 hash of original image
        image_hash = hashlib.sha256(image_bytes).hexdigest()
        
        # Encrypt image data
        encrypted_data = self.cipher.encrypt(image_bytes)
        
        # Create privacy-preserving filename (hash-based, no PII)
        filename = f"{image_hash[:16]}_{timestamp.replace(':', '-')}.enc"
        filepath = os.path.join(self.storage_path, filename)
        
        # Store encrypted image
        with open(filepath, 'wb') as f:
            f.write(encrypted_data)
        
        # Create metadata (also encrypted)
        metadata = {
            'image_hash': image_hash,
            'voter_id_hash': hashlib.sha256(voter_id.encode()).hexdigest(),
            'timestamp': timestamp,
            'file_path': filepath
        }
        
        metadata_path = filepath + '.meta'
        with open(metadata_path, 'wb') as f:
            f.write(self.cipher.encrypt(str(metadata).encode()))
        
        return image_hash, filepath
    
    def retrieve_kyc_image(self, image_hash, authorized=True):
        """
        Retrieve and decrypt KYC image (only for authorized audit)
        """
        if not authorized:
            raise PermissionError("Unauthorized access to PII")
        
        # Search for file by hash prefix
        for filename in os.listdir(self.storage_path):
            if filename.startswith(image_hash[:16]) and filename.endswith('.enc'):
                filepath = os.path.join(self.storage_path, filename)
                
                with open(filepath, 'rb') as f:
                    encrypted_data = f.read()
                
                decrypted_data = self.cipher.decrypt(encrypted_data)
                return decrypted_data
        
        return None