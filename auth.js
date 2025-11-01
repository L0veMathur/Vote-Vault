// auth.js
class AuthManager {
    constructor(apiBaseUrl) {
        this.apiBaseUrl = apiBaseUrl;
        this.sessionToken = null;
        this.tempToken = null;
        this.email = null;
    }
    
    async requestOTP(voterId, dob, email) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/auth/login`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    voter_id: voterId,
                    dob: dob,
                    email: email
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Authentication failed');
            }
            
            this.tempToken = data.temp_token;
            this.email = email;
            
            return {
                success: true,
                message: data.message,
                testOtp: data.test_otp  // For development/testing
            };
        } catch (error) {
            return {
                success: false,
                error: error.message
            };
        }
    }
    
    async verifyOTP(otp) {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/auth/verify-otp`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: this.email,
                    otp: otp,
                    temp_token: this.tempToken
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'OTP verification failed');
            }
            
            this.sessionToken = data.session_token;
            sessionStorage.setItem('voting_session', this.sessionToken);
            
            return {
                success: true,
                voterInfo: data.voter_info
            };
        } catch (error) {
            return {
                success: false,
                error: error.message
            };
        }
    }
    
    async resendOTP() {
        try {
            const response = await fetch(`${this.apiBaseUrl}/api/auth/resend-otp`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({
                    email: this.email,
                    temp_token: this.tempToken
                })
            });
            
            const data = await response.json();
            
            if (!response.ok) {
                throw new Error(data.error || 'Failed to resend OTP');
            }
            
            return {
                success: true,
                message: data.message,
                testOtp: data.test_otp
            };
        } catch (error) {
            return {
                success: false,
                error: error.message
            };
        }
    }
    
    getSessionToken() {
        return this.sessionToken || sessionStorage.getItem('voting_session');
    }
    
    logout() {
        this.sessionToken = null;
        this.tempToken = null;
        this.email = null;
        sessionStorage.removeItem('voting_session');
    }
}

// Form handling
document.addEventListener('DOMContentLoaded', () => {
    const authManager = new AuthManager('http://localhost:5000');
    const loginForm = document.getElementById('loginForm');
    const otpForm = document.getElementById('otpForm');
    const otpSection = document.getElementById('otpSection');
    const errorDiv = document.getElementById('error-message');
    const resendBtn = document.getElementById('resendOtpBtn');
    const resendTimer = document.getElementById('resendTimer');
    
    let resendCooldown = 60;
    let timerInterval = null;
    
    // Step 1: Request OTP
    loginForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const voterId = document.getElementById('voterId').value;
        const dob = document.getElementById('dob').value;
        const email = document.getElementById('email').value;
        
        errorDiv.classList.add('hidden');
        
        // Disable submit button
        const submitBtn = loginForm.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Sending OTP...';
        
        const result = await authManager.requestOTP(voterId, dob, email);
        
        submitBtn.disabled = false;
        submitBtn.textContent = 'Request OTP';
        
        if (result.success) {
            // Hide login form, show OTP section
            loginForm.style.display = 'none';
            otpSection.classList.remove('hidden');
            
            // Update message
            document.getElementById('otpMessage').innerHTML = 
                `✉️ ${result.message}<br><small>Please check your email for the OTP code</small>`;
            
            // Show test OTP if available
            if (result.testOtp) {
                document.getElementById('otpMessage').innerHTML += 
                    `<br><br><strong style="color: #667eea;">Test OTP: ${result.testOtp}</strong>`;
            }
            
            // Start resend cooldown
            startResendCooldown();
            
            // Focus on OTP input
            document.getElementById('otpInput').focus();
        } else {
            errorDiv.textContent = result.error;
            errorDiv.classList.remove('hidden');
        }
    });
    
    // Step 2: Verify OTP
    otpForm.addEventListener('submit', async (e) => {
        e.preventDefault();
        
        const otp = document.getElementById('otpInput').value;
        
        errorDiv.classList.add('hidden');
        
        const submitBtn = otpForm.querySelector('button[type="submit"]');
        submitBtn.disabled = true;
        submitBtn.textContent = 'Verifying...';
        
        const result = await authManager.verifyOTP(otp);
        
        submitBtn.disabled = false;
        submitBtn.textContent = 'Verify OTP';
        
        if (result.success) {
            // Redirect to voting page
            window.location.href = 'voting.html';
        } else {
            errorDiv.textContent = result.error;
            errorDiv.classList.remove('hidden');
            document.getElementById('otpInput').value = '';
            document.getElementById('otpInput').focus();
        }
    });
    
    // Resend OTP
    resendBtn.addEventListener('click', async () => {
        if (resendBtn.disabled) return;
        
        resendBtn.disabled = true;
        resendBtn.textContent = 'Sending...';
        
        const result = await authManager.resendOTP();
        
        if (result.success) {
            errorDiv.classList.remove('error');
            errorDiv.classList.add('success');
            errorDiv.textContent = result.message;
            errorDiv.classList.remove('hidden');
            
            // Show test OTP if available
            if (result.testOtp) {
                errorDiv.textContent += ` | Test OTP: ${result.testOtp}`;
            }
            
            // Hide success message after 3 seconds
            setTimeout(() => {
                errorDiv.classList.add('hidden');
                errorDiv.classList.remove('success');
                errorDiv.classList.add('error');
            }, 3000);
            
            // Restart cooldown
            resendCooldown = 60;
            startResendCooldown();
        } else {
            errorDiv.textContent = result.error;
            errorDiv.classList.remove('hidden');
            resendBtn.disabled = false;
            resendBtn.textContent = 'Resend OTP';
        }
    });
    
    function startResendCooldown() {
        resendBtn.disabled = true;
        resendCooldown = 60;
        
        if (timerInterval) clearInterval(timerInterval);
        
        timerInterval = setInterval(() => {
            resendCooldown--;
            resendTimer.textContent = resendCooldown;
            
            if (resendCooldown <= 0) {
                clearInterval(timerInterval);
                resendBtn.disabled = false;
                resendBtn.innerHTML = 'Resend OTP';
            } else {
                resendBtn.innerHTML = `Resend OTP (<span id="resendTimer">${resendCooldown}</span>s)`;
            }
        }, 1000);
    }
    
    // Auto-submit when 6 digits entered
    document.getElementById('otpInput').addEventListener('input', (e) => {
        if (e.target.value.length === 6) {
            otpForm.dispatchEvent(new Event('submit'));
        }
    });
});