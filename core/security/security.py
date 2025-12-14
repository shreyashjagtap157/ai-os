#!/usr/bin/env python3
"""
AI-OS Security Module
Handles permissions, sandboxing, and security policies.
"""

import os
import sys
import json
import hashlib
import secrets
from pathlib import Path
from typing import Dict, List, Optional, Set
from dataclasses import dataclass, field
from enum import Enum
from datetime import datetime
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('aios-security')


class Permission(Enum):
    """System permissions"""
    # Filesystem
    FILESYSTEM_READ = "filesystem.read"
    FILESYSTEM_WRITE = "filesystem.write"
    FILESYSTEM_EXECUTE = "filesystem.execute"
    
    # Network
    NETWORK_ACCESS = "network.access"
    NETWORK_BIND = "network.bind"
    
    # Hardware
    HARDWARE_DISPLAY = "hardware.display"
    HARDWARE_AUDIO = "hardware.audio"
    HARDWARE_CAMERA = "hardware.camera"
    HARDWARE_MICROPHONE = "hardware.microphone"
    HARDWARE_BLUETOOTH = "hardware.bluetooth"
    HARDWARE_USB = "hardware.usb"
    
    # System
    SYSTEM_SETTINGS = "system.settings"
    SYSTEM_POWER = "system.power"
    SYSTEM_SERVICES = "system.services"
    SYSTEM_APPS = "system.apps"
    
    # AI Agent
    AGENT_CHAT = "agent.chat"
    AGENT_ACTIONS = "agent.actions"
    AGENT_DANGEROUS = "agent.dangerous"


@dataclass
class AppPermissions:
    """Permissions for an application"""
    app_id: str
    granted: Set[str] = field(default_factory=set)
    denied: Set[str] = field(default_factory=set)
    ask_always: Set[str] = field(default_factory=set)


@dataclass
class SecurityPolicy:
    """System-wide security policy"""
    require_permission_prompt: bool = True
    allow_root_apps: bool = False
    sandbox_apps: bool = True
    log_all_actions: bool = True
    dangerous_confirmation: bool = True
    max_failed_auth: int = 5
    lockout_duration: int = 300  # seconds


class SecurityManager:
    """Main security manager for AI-OS"""
    
    CONFIG_PATH = Path("/etc/aios/security.json")
    PERMISSIONS_PATH = Path("/var/lib/aios/permissions.json")
    AUTH_LOG_PATH = Path("/var/log/aios/auth.log")
    
    def __init__(self):
        self.policy = SecurityPolicy()
        self.app_permissions: Dict[str, AppPermissions] = {}
        self._load_config()
        self._load_permissions()
    
    def _load_config(self):
        """Load security configuration"""
        if self.CONFIG_PATH.exists():
            try:
                with open(self.CONFIG_PATH) as f:
                    data = json.load(f)
                for key, value in data.items():
                    if hasattr(self.policy, key):
                        setattr(self.policy, key, value)
            except Exception as e:
                logger.warning(f"Failed to load security config: {e}")
    
    def _load_permissions(self):
        """Load app permissions"""
        if self.PERMISSIONS_PATH.exists():
            try:
                with open(self.PERMISSIONS_PATH) as f:
                    data = json.load(f)
                for app_id, perms in data.items():
                    self.app_permissions[app_id] = AppPermissions(
                        app_id=app_id,
                        granted=set(perms.get('granted', [])),
                        denied=set(perms.get('denied', [])),
                        ask_always=set(perms.get('ask_always', []))
                    )
            except Exception as e:
                logger.warning(f"Failed to load permissions: {e}")
    
    def _save_permissions(self):
        """Save app permissions"""
        try:
            self.PERMISSIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
            data = {}
            for app_id, perms in self.app_permissions.items():
                data[app_id] = {
                    'granted': list(perms.granted),
                    'denied': list(perms.denied),
                    'ask_always': list(perms.ask_always)
                }
            with open(self.PERMISSIONS_PATH, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.error(f"Failed to save permissions: {e}")
    
    def check_permission(self, app_id: str, permission: str) -> bool:
        """Check if an app has a permission"""
        perms = self.app_permissions.get(app_id)
        
        if perms is None:
            # New app, use default policy
            if self.policy.require_permission_prompt:
                return False  # Require explicit grant
            return True
        
        if permission in perms.denied:
            return False
        
        if permission in perms.granted:
            return True
        
        if permission in perms.ask_always:
            # Should prompt user
            return False
        
        return not self.policy.require_permission_prompt
    
    def grant_permission(self, app_id: str, permission: str, permanent: bool = True):
        """Grant a permission to an app"""
        if app_id not in self.app_permissions:
            self.app_permissions[app_id] = AppPermissions(app_id=app_id)
        
        perms = self.app_permissions[app_id]
        
        if permanent:
            perms.granted.add(permission)
            perms.denied.discard(permission)
        else:
            perms.ask_always.add(permission)
        
        self._save_permissions()
        self._log_auth(app_id, f"Permission granted: {permission}")
    
    def deny_permission(self, app_id: str, permission: str):
        """Deny a permission to an app"""
        if app_id not in self.app_permissions:
            self.app_permissions[app_id] = AppPermissions(app_id=app_id)
        
        perms = self.app_permissions[app_id]
        perms.denied.add(permission)
        perms.granted.discard(permission)
        
        self._save_permissions()
        self._log_auth(app_id, f"Permission denied: {permission}")
    
    def revoke_all_permissions(self, app_id: str):
        """Revoke all permissions for an app"""
        if app_id in self.app_permissions:
            del self.app_permissions[app_id]
            self._save_permissions()
            self._log_auth(app_id, "All permissions revoked")
    
    def _log_auth(self, app_id: str, message: str):
        """Log authentication/authorization event"""
        if self.policy.log_all_actions:
            try:
                self.AUTH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
                timestamp = datetime.now().isoformat()
                with open(self.AUTH_LOG_PATH, 'a') as f:
                    f.write(f"{timestamp} [{app_id}] {message}\n")
            except:
                pass
    
    def is_dangerous_action(self, action: str) -> bool:
        """Check if an action is considered dangerous"""
        dangerous_actions = {
            'shutdown', 'reboot', 'wipe', 'format',
            'delete_all', 'factory_reset', 'install_app',
            'uninstall_app', 'modify_system', 'grant_permission'
        }
        return action.lower() in dangerous_actions
    
    def confirm_dangerous_action(self, action: str, details: str = "") -> bool:
        """Request confirmation for dangerous action"""
        if not self.policy.dangerous_confirmation:
            return True
        
        # In a full implementation, this would show a dialog
        # For now, just log
        logger.warning(f"Dangerous action requested: {action} - {details}")
        return True  # Would return False until user confirms
    
    def generate_token(self, length: int = 32) -> str:
        """Generate a secure random token"""
        return secrets.token_hex(length)
    
    def hash_secret(self, secret: str, salt: Optional[str] = None) -> tuple:
        """Hash a secret with salt"""
        if salt is None:
            salt = secrets.token_hex(16)
        
        hashed = hashlib.pbkdf2_hmac('sha256', secret.encode(), salt.encode(), 100000)
        return salt, hashed.hex()
    
    def verify_secret(self, secret: str, salt: str, expected_hash: str) -> bool:
        """Verify a secret against its hash"""
        _, actual_hash = self.hash_secret(secret, salt)
        return secrets.compare_digest(actual_hash, expected_hash)
    
    def get_app_permissions(self, app_id: str) -> List[str]:
        """Get list of granted permissions for an app"""
        perms = self.app_permissions.get(app_id)
        if perms:
            return list(perms.granted)
        return []
    
    def get_all_permissions(self) -> List[str]:
        """Get all available permissions"""
        return [p.value for p in Permission]


# Sandbox utilities
class Sandbox:
    """Application sandboxing utilities"""
    
    @staticmethod
    def create_namespace() -> bool:
        """Create a new namespace for sandboxing"""
        # Would use unshare/namespaces
        # Placeholder implementation
        return True
    
    @staticmethod
    def apply_seccomp_filter(allowed_syscalls: List[str]) -> bool:
        """Apply seccomp filter to restrict syscalls"""
        # Would use seccomp
        # Placeholder implementation
        return True
    
    @staticmethod
    def setup_cgroups(limits: Dict[str, int]) -> bool:
        """Setup cgroup resource limits"""
        # Would configure cgroups v2
        # Placeholder implementation
        return True
    
    @staticmethod
    def mount_overlay(lower: str, upper: str, work: str, merged: str) -> bool:
        """Setup overlay filesystem for isolation"""
        try:
            os.system(f'mount -t overlay overlay -o lowerdir={lower},upperdir={upper},workdir={work} {merged}')
            return True
        except:
            return False


# Global security manager instance
_security_manager: Optional[SecurityManager] = None


def get_security_manager() -> SecurityManager:
    """Get the global security manager instance"""
    global _security_manager
    if _security_manager is None:
        _security_manager = SecurityManager()
    return _security_manager


# Permission decorator for functions
def require_permission(permission: str):
    """Decorator to require a permission for a function"""
    def decorator(func):
        def wrapper(*args, **kwargs):
            # Get app_id from context (simplified)
            app_id = os.environ.get('AIOS_APP_ID', 'unknown')
            
            manager = get_security_manager()
            if not manager.check_permission(app_id, permission):
                raise PermissionError(f"Permission denied: {permission}")
            
            return func(*args, **kwargs)
        return wrapper
    return decorator


if __name__ == '__main__':
    # Test security manager
    manager = SecurityManager()
    
    print("Available permissions:")
    for p in manager.get_all_permissions():
        print(f"  - {p}")
    
    print("\nTesting permission system...")
    manager.grant_permission("test-app", "filesystem.read")
    print(f"test-app has filesystem.read: {manager.check_permission('test-app', 'filesystem.read')}")
    
    manager.deny_permission("test-app", "system.power")
    print(f"test-app has system.power: {manager.check_permission('test-app', 'system.power')}")
