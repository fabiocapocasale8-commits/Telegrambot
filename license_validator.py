import json
import os
import hashlib
from datetime import datetime
from cryptography.fernet import Fernet

class LicenseValidator:
    """License validation only - NO key generation capabilities"""
    def __init__(self):
        # Create directories if they don't exist
        os.makedirs("licenses", exist_ok=True)
        os.makedirs("users", exist_ok=True)
        
        # Load encryption key and data
        self.key_file = "licenses/master.key"
        self.license_file = "licenses/valid_keys.json"
        self.users_file = "users/used_keys.json"
        
        # Initialize encryption
        self._init_encryption()
        
        # Load existing data
        self.valid_keys = self._load_valid_keys()
        self.used_keys = self._load_used_keys()
    
    def _init_encryption(self):
        """Initialize encryption system with master key"""
        if os.path.exists(self.key_file):
            with open(self.key_file, 'rb') as f:
                self.master_key = f.read()
        else:
            # If no master key exists, create a dummy one
            # In real deployment, this should be provided by the bot owner
            self.master_key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(self.master_key)
            os.chmod(self.key_file, 0o600)
        
        self.cipher = Fernet(self.master_key)
    
    def _load_valid_keys(self):
        """Load valid license keys from encrypted file"""
        if os.path.exists(self.license_file):
            try:
                with open(self.license_file, 'rb') as f:
                    encrypted_data = f.read()
                decrypted_data = self.cipher.decrypt(encrypted_data)
                return json.loads(decrypted_data.decode())
            except:
                return {}
        return {}
    
    def _save_used_keys(self):
        """Save used keys tracking"""
        data = json.dumps(self.used_keys, indent=2).encode()
        encrypted_data = self.cipher.encrypt(data)
        with open(self.users_file, 'wb') as f:
            f.write(encrypted_data)
        os.chmod(self.users_file, 0o600)
    
    def _load_used_keys(self):
        """Load used keys tracking"""
        if os.path.exists(self.users_file):
            try:
                with open(self.users_file, 'rb') as f:
                    encrypted_data = f.read()
                decrypted_data = self.cipher.decrypt(encrypted_data)
                return json.loads(decrypted_data.decode())
            except:
                return {}
        return {}
    
    def validate_key(self, license_key, user_identifier=None):
        """
        Validate a license key and mark it as used for a specific user
        Returns: (is_valid, reason, time_remaining)
        """
        if not license_key or license_key not in self.valid_keys:
            return False, "Invalid or unknown license key", None
        
        key_data = self.valid_keys[license_key]
        
        # Check if key has expired
        if key_data["expiry"]:
            expiry_date = datetime.fromisoformat(key_data["expiry"])
            if datetime.now() > expiry_date:
                return False, "License key has expired", None
        
        # Check if user has already used this key
        if user_identifier:
            user_hash = hashlib.sha256(user_identifier.encode()).hexdigest()
            
            # Check if this user already used this specific key
            if user_hash in key_data["used_by"]:
                return False, "This key has already been used by this user", None
        
        # Mark key as used by this user
        if user_identifier:
            user_hash = hashlib.sha256(user_identifier.encode()).hexdigest()
            key_data["used_by"].append(user_hash)
            
            # Update user tracking
            user_key = f"user_{user_hash}"
            self.used_keys[user_key] = {
                "key_used": license_key,
                "last_used": datetime.now().isoformat(),
                "key_type": key_data["type"]
            }
            
            # Save changes (we can't save valid_keys as we don't have generation rights)
            self._save_used_keys()
        
        # Calculate remaining time
        time_remaining = None
        if key_data["expiry"]:
            expiry_date = datetime.fromisoformat(key_data["expiry"])
            time_remaining = expiry_date - datetime.now()
        
        return True, "Valid license key", time_remaining
    
    def check_user_access(self, user_identifier):
        """
        Check if a user currently has valid access
        Returns: (has_access, key_type, time_remaining)
        """
        if not user_identifier:
            return False, None, None
        
        user_hash = hashlib.sha256(user_identifier.encode()).hexdigest()
        user_key = f"user_{user_hash}"
        
        if user_key not in self.used_keys:
            return False, None, None
        
        user_data = self.used_keys[user_key]
        license_key = user_data["key_used"]
        
        if license_key not in self.valid_keys:
            return False, None, None
        
        key_data = self.valid_keys[license_key]
        
        # Check if key has expired
        if key_data["expiry"]:
            expiry_date = datetime.fromisoformat(key_data["expiry"])
            if datetime.now() > expiry_date:
                return False, None, None
            time_remaining = expiry_date - datetime.now()
        else:
            time_remaining = None  # Permanent key
        
        return True, key_data["type"], time_remaining

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