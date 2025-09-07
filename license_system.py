import json
import os
import hashlib
import hmac
import secrets
import base64
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

class LicenseKeySystem:
    def __init__(self):
        # Create directories if they don't exist
        os.makedirs("licenses", exist_ok=True)
        os.makedirs("users", exist_ok=True)
        
        # Generate or load encryption key
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
            # Generate new master key
            self.master_key = Fernet.generate_key()
            with open(self.key_file, 'wb') as f:
                f.write(self.master_key)
            os.chmod(self.key_file, 0o600)  # Restrict access to owner only
        
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
    
    def _save_valid_keys(self):
        """Save valid license keys to encrypted file"""
        data = json.dumps(self.valid_keys, indent=2).encode()
        encrypted_data = self.cipher.encrypt(data)
        with open(self.license_file, 'wb') as f:
            f.write(encrypted_data)
        os.chmod(self.license_file, 0o600)
    
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
    
    def _save_used_keys(self):
        """Save used keys tracking"""
        data = json.dumps(self.used_keys, indent=2).encode()
        encrypted_data = self.cipher.encrypt(data)
        with open(self.users_file, 'wb') as f:
            f.write(encrypted_data)
        os.chmod(self.users_file, 0o600)
    
    def generate_key(self, key_type="7d", custom_data=None):
        """
        Generate a new license key
        key_type: Flexible time format like "30mins", "2h", "7d", "1w", "permanent"
        custom_data: Optional custom data to embed in key
        """
        # Create unique key ID
        key_id = secrets.token_hex(16)
        
        # Calculate expiration using flexible time format
        now = datetime.now()
        time_delta, type_code = self._parse_time_duration(key_type)
        if time_delta:
            expiry = now + time_delta
        else:
            expiry = None
        
        # Create key data
        key_data = {
            "id": key_id,
            "type": key_type,
            "created": now.isoformat(),
            "expiry": expiry.isoformat() if expiry else None,
            "used_by": [],
            "max_uses": 1,  # Each key can only be used once per unique user
            "custom_data": custom_data
        }
        
        # Generate the actual license key string
        # Format: TYPE-KEYID-CHECKSUM
        key_string = f"{type_code}-{key_id[:8].upper()}-{key_id[8:16].upper()}-{key_id[16:24].upper()}"
        
        # Add to valid keys
        self.valid_keys[key_string] = key_data
        self._save_valid_keys()
        
        return key_string
    
    def _parse_time_duration(self, duration_str):
        """
        Parse flexible time duration formats
        Supports: 30mins, 2h, 7d, 1w, 1m (month), permanent
        Returns: (timedelta_object, type_code)
        """
        duration_str = duration_str.lower().strip()
        
        # Handle permanent keys
        if duration_str in ['permanent', 'perm', 'lifetime']:
            return None, "PM"
        
        # Handle legacy formats
        if duration_str == "7d":
            return timedelta(days=7), "7D"
        elif duration_str == "30d":
            return timedelta(days=30), "30"
        
        # Parse flexible format
        import re
        match = re.match(r'^(\d+)(\w+)$', duration_str)
        if not match:
            raise ValueError(f"Invalid duration format: {duration_str}. Use formats like '30mins', '2h', '7d', '1w', 'permanent'")
        
        amount = int(match.group(1))
        unit = match.group(2)
        
        # Convert to timedelta and generate type code
        if unit in ['min', 'mins', 'minute', 'minutes', 'm']:
            delta = timedelta(minutes=amount)
            type_code = f"{amount}M"
        elif unit in ['h', 'hr', 'hrs', 'hour', 'hours']:
            delta = timedelta(hours=amount)
            type_code = f"{amount}H"
        elif unit in ['d', 'day', 'days']:
            delta = timedelta(days=amount)
            type_code = f"{amount}D"
        elif unit in ['w', 'week', 'weeks']:
            delta = timedelta(weeks=amount)
            type_code = f"{amount}W"
        elif unit in ['month', 'months', 'mo']:
            delta = timedelta(days=amount * 30)  # Approximate month as 30 days
            type_code = f"{amount}MO"
        elif unit in ['y', 'year', 'years']:
            delta = timedelta(days=amount * 365)  # Approximate year as 365 days
            type_code = f"{amount}Y"
        else:
            raise ValueError(f"Unknown time unit: {unit}. Use: mins, h, d, w, month, y, or permanent")
        
        # Limit type code to 3 chars max for key format
        if len(type_code) > 3:
            type_code = type_code[:3]
        
        return delta, type_code
    
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
            
            # User can use new keys anytime (cooldown restriction removed)
        
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
            
            self._save_valid_keys()
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
    
    def list_keys(self):
        """List all generated keys (for admin purposes)"""
        result = []
        for key, data in self.valid_keys.items():
            result.append({
                "key": key,
                "type": data["type"],
                "created": data["created"],
                "expiry": data["expiry"],
                "used_count": len(data["used_by"]),
                "max_uses": data["max_uses"]
            })
        return result
    
    def revoke_key(self, license_key):
        """Revoke a license key"""
        if license_key in self.valid_keys:
            del self.valid_keys[license_key]
            self._save_valid_keys()
            return True
        return False