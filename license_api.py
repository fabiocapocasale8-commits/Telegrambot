#!/usr/bin/env python3
"""
License Database API Server - ADMIN ONLY
Keep this separate from your shareable bot template!
"""

from flask import Flask, request, jsonify, render_template, session, redirect, url_for
from flask_cors import CORS
import os
import secrets
import hashlib
from admin.license_system import LicenseKeySystem

app = Flask(__name__)
CORS(app)

# Set a secret key for sessions
app.secret_key = secrets.token_hex(32)

# Initialize the license system
license_system = LicenseKeySystem()

# API Authentication token (generated once, save this!)
API_TOKEN_FILE = "api_token.txt"
if os.path.exists(API_TOKEN_FILE):
    with open(API_TOKEN_FILE, 'r') as f:
        API_TOKEN = f.read().strip()
else:
    API_TOKEN = secrets.token_urlsafe(32)
    with open(API_TOKEN_FILE, 'w') as f:
        f.write(API_TOKEN)
    print(f"🔑 Generated new API token: {API_TOKEN}")
    print("⚠️  Save this token - you'll need it to configure client repls!")

# Admin password (generated once, save this!)
ADMIN_PASSWORD_FILE = "admin_password.txt"
if os.path.exists(ADMIN_PASSWORD_FILE):
    with open(ADMIN_PASSWORD_FILE, 'r') as f:
        ADMIN_PASSWORD = f.read().strip()
else:
    ADMIN_PASSWORD = secrets.token_urlsafe(16)
    with open(ADMIN_PASSWORD_FILE, 'w') as f:
        f.write(ADMIN_PASSWORD)
    print(f"🔐 Generated new admin password: {ADMIN_PASSWORD}")
    print("⚠️  Save this password - you'll need it to access the admin panel!")

def require_auth():
    """Check if request has valid API token"""
    auth_header = request.headers.get('Authorization')
    if not auth_header or not auth_header.startswith('Bearer '):
        return False
    token = auth_header[7:]  # Remove "Bearer " prefix
    return token == API_TOKEN

def require_admin_login():
    """Check if user is logged in as admin"""
    return session.get('admin_logged_in', False)

@app.route('/')
def admin_panel():
    """Admin panel interface"""
    if not require_admin_login():
        return redirect(url_for('login'))
    return render_template('admin.html', api_token=API_TOKEN)

@app.route('/login', methods=['GET', 'POST'])
def login():
    """Admin login page"""
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['admin_logged_in'] = True
            return redirect(url_for('admin_panel'))
        else:
            return render_template('login.html', error='Invalid password')
    return render_template('login.html')

@app.route('/logout')
def logout():
    """Admin logout"""
    session.pop('admin_logged_in', None)
    return redirect(url_for('login'))

@app.route('/user')
def user_panel():
    """User interface for key validation"""
    return render_template('user.html', api_token=API_TOKEN)

@app.route('/health', methods=['GET'])
def health_check():
    """Health check endpoint"""
    return jsonify({"status": "healthy", "service": "license-api"})

@app.route('/api/validate', methods=['POST'])
def validate_key():
    """Validate a license key"""
    if not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    if not data or 'license_key' not in data:
        return jsonify({"error": "Missing license_key"}), 400
    
    license_key = data['license_key']
    user_identifier = data.get('user_identifier')
    
    try:
        is_valid, reason, time_remaining = license_system.validate_key(license_key, user_identifier)
        
        # Convert timedelta to seconds for JSON serialization
        time_remaining_seconds = None
        if time_remaining:
            time_remaining_seconds = int(time_remaining.total_seconds())
        
        return jsonify({
            "is_valid": is_valid,
            "reason": reason,
            "time_remaining_seconds": time_remaining_seconds
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/check_access', methods=['POST'])
def check_user_access():
    """Check if user has valid access"""
    if not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    if not data or 'user_identifier' not in data:
        return jsonify({"error": "Missing user_identifier"}), 400
    
    user_identifier = data['user_identifier']
    
    try:
        has_access, key_type, time_remaining = license_system.check_user_access(user_identifier)
        
        # Convert timedelta to seconds for JSON serialization
        time_remaining_seconds = None
        if time_remaining:
            time_remaining_seconds = int(time_remaining.total_seconds())
        
        return jsonify({
            "has_access": has_access,
            "key_type": key_type,
            "time_remaining_seconds": time_remaining_seconds
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/generate', methods=['POST'])
def generate_key():
    """Generate a new license key (admin only)"""
    if not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    if not data or 'key_type' not in data:
        return jsonify({"error": "Missing key_type"}), 400
    
    key_type = data['key_type']
    custom_data = data.get('custom_data')
    
    try:
        new_key = license_system.generate_key(key_type, custom_data)
        return jsonify({
            "success": True,
            "license_key": new_key,
            "key_type": key_type
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/list_keys', methods=['GET'])
def list_keys():
    """List all keys (admin only)"""
    if not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    
    try:
        keys = license_system.list_keys()
        return jsonify({"keys": keys})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/api/revoke', methods=['POST'])
def revoke_key():
    """Revoke a license key (admin only)"""
    if not require_auth():
        return jsonify({"error": "Unauthorized"}), 401
    
    data = request.get_json()
    if not data or 'license_key' not in data:
        return jsonify({"error": "Missing license_key"}), 400
    
    license_key = data['license_key']
    
    try:
        success = license_system.revoke_key(license_key)
        return jsonify({
            "success": success,
            "message": "Key revoked successfully" if success else "Key not found"
        })
    except Exception as e:
        return jsonify({"error": str(e)}), 500

if __name__ == '__main__':
    print("🚀 Starting License Database API Server")
    print(f"🔑 API Token: {API_TOKEN}")
    print(f"🔐 Admin Password: {ADMIN_PASSWORD}")
    print("⚠️  Keep these credentials secure!")
    print("📡 API will be available at: http://your-repl-url.replit.dev")
    print()
    
    # Run on port 5000 as required by Replit free tier
    app.run(host='0.0.0.0', port=5000, debug=True)