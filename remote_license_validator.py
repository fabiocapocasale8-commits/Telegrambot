#!/usr/bin/env python3
"""
Remote License Validator
Connects to a remote license API server instead of using local files
Use this in your shareable bot template instead of the local validator
"""

import requests
import hashlib
import os
from datetime import datetime, timedelta

class RemoteLicenseValidator:
    """License validation using remote API - NO local files needed"""
    
    def __init__(self, api_url=None, api_token=None):
        # Get API configuration from environment or parameters
        self.api_url = api_url or os.getenv('LICENSE_API_URL', '')
        self.api_token = api_token or os.getenv('LICENSE_API_TOKEN', '')
        
        if not self.api_url:
            raise ValueError("LICENSE_API_URL must be set in environment or passed as parameter")
        if not self.api_token:
            raise ValueError("LICENSE_API_TOKEN must be set in environment or passed as parameter")
        
        # Remove trailing slash from URL
        self.api_url = self.api_url.rstrip('/')
        
        # Set up headers for authentication
        self.headers = {
            'Authorization': f'Bearer {self.api_token}',
            'Content-Type': 'application/json'
        }
    
    def _make_request(self, endpoint, method='GET', data=None):
        """Make authenticated request to API"""
        url = f"{self.api_url}{endpoint}"
        
        try:
            if method == 'GET':
                response = requests.get(url, headers=self.headers, timeout=10)
            elif method == 'POST':
                response = requests.post(url, headers=self.headers, json=data, timeout=10)
            else:
                raise ValueError(f"Unsupported method: {method}")
            
            response.raise_for_status()
            return response.json()
        
        except requests.exceptions.RequestException as e:
            print(f"❌ Error connecting to license server: {e}")
            # In case of API failure, deny access for security
            return None
    
    def validate_key(self, license_key, user_identifier=None):
        """
        Validate a license key using remote API
        Returns: (is_valid, reason, time_remaining)
        """
        data = {
            'license_key': license_key,
            'user_identifier': user_identifier
        }
        
        result = self._make_request('/api/validate', method='POST', data=data)
        
        if result is None:
            return False, "Unable to verify license - server unavailable", None
        
        if 'error' in result:
            return False, f"Validation error: {result['error']}", None
        
        is_valid = result.get('is_valid', False)
        reason = result.get('reason', 'Unknown error')
        time_remaining_seconds = result.get('time_remaining_seconds')
        
        # Convert seconds back to timedelta
        time_remaining = None
        if time_remaining_seconds is not None:
            time_remaining = timedelta(seconds=time_remaining_seconds)
        
        return is_valid, reason, time_remaining
    
    def check_user_access(self, user_identifier):
        """
        Check if a user currently has valid access using remote API
        Returns: (has_access, key_type, time_remaining)
        """
        data = {'user_identifier': user_identifier}
        
        result = self._make_request('/api/check_access', method='POST', data=data)
        
        if result is None:
            return False, None, None
        
        if 'error' in result:
            return False, None, None
        
        has_access = result.get('has_access', False)
        key_type = result.get('key_type')
        time_remaining_seconds = result.get('time_remaining_seconds')
        
        # Convert seconds back to timedelta
        time_remaining = None
        if time_remaining_seconds is not None:
            time_remaining = timedelta(seconds=time_remaining_seconds)
        
        return has_access, key_type, time_remaining
    
    def health_check(self):
        """Check if the license API is available"""
        result = self._make_request('/health', method='GET')
        return result is not None and result.get('status') == 'healthy'

def get_hardware_id():
    """Generate a hardware-based identifier for additional security"""
    import platform
    import uuid
    
    # Combine multiple hardware identifiers
    identifiers = [
        platform.node(),           # Computer name
        platform.processor(),      # Processor info
        str(uuid.getnode()),      # MAC address
        platform.platform(),      # OS info
    ]
    
    # Create hash of combined identifiers
    combined = "".join(identifiers)
    hardware_id = hashlib.sha256(combined.encode()).hexdigest()[:16]
    return hardware_id

# Backward compatibility - try to auto-detect which validator to use
def LicenseValidator():
    """
    Smart license validator that auto-detects configuration
    Uses remote API if configured, falls back to local files
    """
    try:
        # Check if we have remote API configuration
        api_url = os.getenv('LICENSE_API_URL')
        api_token = os.getenv('LICENSE_API_TOKEN')
        
        if api_url and api_token:
            # Use remote validator
            remote_validator = RemoteLicenseValidator(api_url, api_token)
            if remote_validator.health_check():
                print("🌐 Using remote license validation")
                return remote_validator
            else:
                print("⚠️  Remote license server unavailable, falling back to local")
        
        # Fall back to local validator
        from .license_validator import LicenseValidator as LocalValidator
        print("💾 Using local license validation")
        return LocalValidator()
        
    except Exception as e:
        print(f"❌ License validation setup error: {e}")
        # For security, create a dummy validator that denies all access
        class DummyValidator:
            def validate_key(self, *args, **kwargs):
                return False, "License system unavailable", None
            def check_user_access(self, *args, **kwargs):
                return False, None, None
        return DummyValidator()