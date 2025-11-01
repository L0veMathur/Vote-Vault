// kyc.js
class KYCCapture {
    constructor() {
        this.stream = null;
        this.capturedImageBlob = null;
    }
    
    async initWebcam() {
        try {
            this.stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: { ideal: 1280 },
                    height: { ideal: 720 },
                    facingMode: 'user'
                }
            });
            
            const videoElement = document.getElementById('webcam');
            videoElement.srcObject = this.stream;
            
            return true;
        } catch (error) {
            console.error('Webcam access denied:', error);
            alert('Camera access required for identity verification');
            return false;
        }
    }
    
    capturePhoto() {
        const video = document.getElementById('webcam');
        const canvas = document.getElementById('snapshot');
        const context = canvas.getContext('2d');
        
        canvas.width = video.videoWidth;
        canvas.height = video.videoHeight;
        context.drawImage(video, 0, 0);
        
        // Convert to blob for upload
        canvas.toBlob((blob) => {
            this.capturedImageBlob = blob;
            
            // Show preview
            const preview = document.getElementById('capturedImage');
            preview.src = URL.createObjectURL(blob);
            
            document.getElementById('previewContainer').classList.remove('hidden');
            document.getElementById('captureBtn').classList.add('hidden');
        }, 'image/jpeg', 0.85);
    }
    
    async uploadKYCImage(sessionToken) {
        if (!this.capturedImageBlob) {
            throw new Error('No image captured');
        }
        
        const formData = new FormData();
        formData.append('kyc_image', this.capturedImageBlob, 'kyc_photo.jpg');
        formData.append('timestamp', new Date().toISOString());
        
        try {
            const response = await fetch('http://localhost:5000/api/kyc/upload', {
                method: 'POST',
                headers: {
                    'Authorization': `Bearer ${sessionToken}`
                },
                body: formData
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Upload failed');
            }
            
            return {
                success: true,
                imageHash: data.image_hash,
                encryptedRef: data.encrypted_reference
            };
        } catch (error) {
            return {
                success: false,
                error: error.message
            };
        }
    }
    
    stopWebcam() {
        if (this.stream) {
            this.stream.getTracks().forEach(track => track.stop());
        }
    }
}

// Initialize KYC on page load
let kycCapture;
document.addEventListener('DOMContentLoaded', async () => {
    kycCapture = new KYCCapture();
    await kycCapture.initWebcam();
    
    document.getElementById('captureBtn').addEventListener('click', () => {
        kycCapture.capturePhoto();
    });
    
    document.getElementById('retakeBtn').addEventListener('click', () => {
        document.getElementById('previewContainer').classList.add('hidden');
        document.getElementById('captureBtn').classList.remove('hidden');
    });
});