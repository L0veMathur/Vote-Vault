// kyc.js
class KYCCapture {
    constructor() {
        this.stream = null;
        this.capturedImageBlob = null;
        this.kycImageHash = null;
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
            
            // Hide camera, show preview
            document.getElementById('cameraContainer').style.display = 'none';
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
            
            this.kycImageHash = data.image_hash;
            
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
let sessionToken;

async function loadCandidates() {
    try {
        const response = await fetch('http://localhost:5000/api/candidates');
        const data = await response.json();
        
        if (data.success && data.candidates) {
            const candidatesList = document.getElementById('candidatesList');
            candidatesList.innerHTML = '';
            
            data.candidates.forEach((candidate, index) => {
                const candidateDiv = document.createElement('div');
                candidateDiv.className = 'bg-white dark:bg-gray-700/50 border-2 border-gray-200 dark:border-gray-600 rounded-lg p-4 cursor-pointer transition-all hover:border-primary hover:bg-blue-50 dark:hover:bg-gray-700';
                candidateDiv.innerHTML = `
                    <label class="flex items-start gap-4 cursor-pointer w-full">
                        <input type="radio" id="candidate${index}" name="candidate" 
                               value="${candidate.CandidateName}" ${index === 0 ? 'required' : ''}
                               class="mt-1 w-5 h-5 text-primary focus:ring-primary focus:ring-2">
                        <div class="flex-1">
                            <div class="font-bold text-lg text-body-text-light dark:text-body-text-dark">${candidate.CandidateName}</div>
                            <div class="text-sm text-secondary-text mt-1">${candidate.PoliticalParty} ${candidate.PartySymbol || ''}</div>
                            <div class="text-sm italic text-gray-600 dark:text-gray-400 mt-1">"${candidate.Slogan || ''}"</div>
                        </div>
                    </label>
                `;
                
                // Add click event to select radio when clicking the entire div
                candidateDiv.addEventListener('click', () => {
                    document.getElementById(`candidate${index}`).checked = true;
                });
                
                candidatesList.appendChild(candidateDiv);
            });
        }
    } catch (error) {
        console.error('Error loading candidates:', error);
        document.getElementById('candidatesList').innerHTML = 
            '<div class="text-center py-8"><p class="text-red-600 dark:text-red-400">Error loading candidates. Please refresh the page.</p></div>';
    }
}

document.addEventListener('DOMContentLoaded', async () => {
    // Get session token from storage
    sessionToken = sessionStorage.getItem('voting_session');
    
    if (!sessionToken) {
        alert('Session expired. Please login again.');
        window.location.href = 'login.html';
        return;
    }
    
    // Initialize webcam
    kycCapture = new KYCCapture();
    const webcamStarted = await kycCapture.initWebcam();
    
    if (!webcamStarted) {
        const errorDiv = document.getElementById('error-message');
        errorDiv.querySelector('p').textContent = 'Unable to access camera. Please grant camera permissions.';
        errorDiv.classList.remove('hidden');
        return;
    }
    
    // Capture button event
    document.getElementById('captureBtn').addEventListener('click', () => {
        kycCapture.capturePhoto();
    });
    
    // Retake button event
    document.getElementById('retakeBtn').addEventListener('click', () => {
        document.getElementById('cameraContainer').style.display = 'block';
        document.getElementById('previewContainer').classList.add('hidden');
        document.getElementById('captureBtn').classList.remove('hidden');
    });
    
    // Confirm photo button event
    document.getElementById('confirmPhotoBtn').addEventListener('click', async () => {
        const errorDiv = document.getElementById('error-message');
        errorDiv.classList.add('hidden');
        
        // Upload KYC image
        const uploadResult = await kycCapture.uploadKYCImage(sessionToken);
        
        if (uploadResult.success) {
            // Stop webcam
            kycCapture.stopWebcam();
            
            // Load candidates
            await loadCandidates();
            
            // Update progress bar to Phase 3
            const progressText = document.querySelector('.text-base.font-medium.leading-normal.text-body-text-light');
            if (progressText) {
                progressText.textContent = 'Protocol Phase 3 of 3: Vote Casting';
            }
            
            const progressBar = document.querySelector('.rounded.bg-primary');
            if (progressBar) {
                progressBar.style.width = '100%';
            }
            
            // Update tab styling
            const kycTab = document.getElementById('kycTab');
            const voteTab = document.getElementById('voteTab');
            if (kycTab && voteTab) {
                kycTab.classList.remove('border-primary', 'text-primary');
                kycTab.classList.add('border-transparent', 'text-gray-500', 'dark:text-gray-400');
                
                voteTab.classList.remove('border-transparent', 'text-gray-500', 'dark:text-gray-400');
                voteTab.classList.add('border-primary', 'text-primary');
                voteTab.setAttribute('aria-current', 'page');
            }
            
            // Hide KYC section, show voting section
            document.getElementById('kycSection').classList.add('hidden');
            document.getElementById('voteSection').classList.remove('hidden');
        } else {
            const errorDiv = document.getElementById('error-message');
            errorDiv.querySelector('p').textContent = 'Failed to upload photo: ' + uploadResult.error;
            errorDiv.classList.remove('hidden');
        }
    });
    
    // Vote form submission
    document.getElementById('voteForm').addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const selectedCandidate = document.querySelector('input[name="candidate"]:checked');
        if (!selectedCandidate) {
            alert('Please select a candidate');
            return;
        }
        
        const voteData = {
            vote_choice: selectedCandidate.value,
            kyc_image_hash: kycCapture.kycImageHash,
            timestamp: new Date().toISOString()
        };
        
        try {
            const response = await fetch('http://localhost:5000/api/vote/submit', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                    'Authorization': `Bearer ${sessionToken}`
                },
                body: JSON.stringify(voteData)
            });
            
            const data = await response.json();
            
            if (response.ok && data.success) {
                const messageDiv = document.getElementById('voteMessage');
                messageDiv.className = 'bg-green-50 dark:bg-green-950/30 border border-green-200 dark:border-green-800 text-green-700 dark:text-green-300 font-medium';
                messageDiv.textContent = '✅ Vote submitted successfully! Your vote has been recorded securely.';
                messageDiv.classList.remove('hidden');
                
                // Disable form
                document.getElementById('voteForm').style.display = 'none';
                
                // Clear session after 3 seconds
                setTimeout(() => {
                    sessionStorage.removeItem('voting_session');
                    alert('Thank you for voting! You will be redirected to the login page.');
                    window.location.href = 'login.html';
                }, 3000);
            } else {
                const errorDiv = document.getElementById('error-message');
                errorDiv.querySelector('p').textContent = 'Failed to submit vote: ' + (data.error || 'Unknown error');
                errorDiv.classList.remove('hidden');
            }
        } catch (error) {
            const errorDiv = document.getElementById('error-message');
            errorDiv.querySelector('p').textContent = 'Network error: ' + error.message;
            errorDiv.classList.remove('hidden');
        }
    });
});
