"""
Rate Limiting Middleware - Protect APIs from abuse & brute force
Implements IP-based tracking, progressive backoff, and security measures
"""
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask import request, jsonify
from datetime import datetime, timedelta
import json
import os
from pathlib import Path

# Configuration
RATE_LIMIT_STORAGE = Path('data/rate_limits')
RATE_LIMIT_STORAGE.mkdir(parents=True, exist_ok=True)

# IP Blocking configuration
MAX_FAILED_ATTEMPTS = 10
BLOCK_DURATION_MINUTES = 30
FAILED_ATTEMPTS_FILE = RATE_LIMIT_STORAGE / 'failed_attempts.json'


class IPBlocker:
    """Manage IP blocking for failed login attempts"""
    
    @staticmethod
    def _load_attempts():
        """Load failed attempts from file"""
        if FAILED_ATTEMPTS_FILE.exists():
            try:
                with open(FAILED_ATTEMPTS_FILE, 'r') as f:
                    return json.load(f)
            except (json.JSONDecodeError, IOError):
                return {}
        return {}
    
    @staticmethod
    def _save_attempts(attempts):
        """Save failed attempts to file"""
        with open(FAILED_ATTEMPTS_FILE, 'w') as f:
            json.dump(attempts, f, indent=2)
    
    @staticmethod
    def record_failed_attempt(ip_address):
        """Record a failed login attempt for an IP"""
        attempts = IPBlocker._load_attempts()
        
        if ip_address not in attempts:
            attempts[ip_address] = {
                'count': 0,
                'first_attempt': None,
                'blocked_until': None
            }
        
        now = datetime.utcnow().isoformat()
        attempts[ip_address]['count'] += 1
        
        if attempts[ip_address]['first_attempt'] is None:
            attempts[ip_address]['first_attempt'] = now
        
        # Block if threshold exceeded
        if attempts[ip_address]['count'] >= MAX_FAILED_ATTEMPTS:
            blocked_until = (datetime.utcnow() + timedelta(minutes=BLOCK_DURATION_MINUTES)).isoformat()
            attempts[ip_address]['blocked_until'] = blocked_until
            print(f"🚫 IP BLOCKED: {ip_address} for {BLOCK_DURATION_MINUTES} minutes")
        else:
            remaining = MAX_FAILED_ATTEMPTS - attempts[ip_address]['count']
            print(f"⚠️ Failed attempt #{attempts[ip_address]['count']}/10 from {ip_address} ({remaining} remaining)")
        
        IPBlocker._save_attempts(attempts)
        return attempts[ip_address]['count']
    
    @staticmethod
    def record_successful_attempt(ip_address):
        """Clear failed attempts after successful login"""
        attempts = IPBlocker._load_attempts()
        if ip_address in attempts:
            attempts[ip_address] = {
                'count': 0,
                'first_attempt': None,
                'blocked_until': None
            }
            IPBlocker._save_attempts(attempts)
            print(f"✓ Cleared failed attempts for {ip_address}")
    
    @staticmethod
    def is_ip_blocked(ip_address):
        """Check if IP is currently blocked"""
        attempts = IPBlocker._load_attempts()
        
        if ip_address not in attempts:
            return False
        
        blocked_until = attempts[ip_address].get('blocked_until')
        if not blocked_until:
            return False
        
        blocked_until_time = datetime.fromisoformat(blocked_until)
        now = datetime.utcnow()
        
        # Block period expired
        if now > blocked_until_time:
            attempts[ip_address] = {
                'count': 0,
                'first_attempt': None,
                'blocked_until': None
            }
            IPBlocker._save_attempts(attempts)
            return False
        
        return True
    
    @staticmethod
    def get_block_status(ip_address):
        """Get detailed block status"""
        attempts = IPBlocker._load_attempts()
        
        if ip_address not in attempts:
            return None
        
        data = attempts[ip_address]
        blocked_until = data.get('blocked_until')
        
        if not blocked_until:
            return {
                'blocked': False,
                'attempts': data['count'],
                'max_attempts': MAX_FAILED_ATTEMPTS
            }
        
        blocked_until_time = datetime.fromisoformat(blocked_until)
        now = datetime.utcnow()
        
        if now > blocked_until_time:
            return {
                'blocked': False,
                'attempts': data['count'],
                'max_attempts': MAX_FAILED_ATTEMPTS
            }
        
        return {
            'blocked': True,
            'attempts': data['count'],
            'max_attempts': MAX_FAILED_ATTEMPTS,
            'blocked_until': blocked_until,
            'minutes_remaining': int((blocked_until_time - now).total_seconds() / 60)
        }
    
    @staticmethod
    def clear_all_blocks():
        """Clear all blocks (admin only)"""
        if FAILED_ATTEMPTS_FILE.exists():
            with open(FAILED_ATTEMPTS_FILE, 'w') as f:
                json.dump({}, f)
        print("✓ All IP blocks cleared")


def init_rate_limiter(app):
    """Initialize Flask-Limiter with app"""
    limiter = Limiter(
        app=app,
        key_func=get_remote_address,
        default_limits=["1000 per day", "100 per hour"],
        storage_uri="memory://",
        strategy="fixed-window"
    )
    
    print("✓ Rate limiter initialized")
    return limiter


def check_ip_block():
    """Middleware to check if IP is blocked"""
    ip_address = get_remote_address()
    
    if IPBlocker.is_ip_blocked(ip_address):
        status = IPBlocker.get_block_status(ip_address)
        return jsonify({
            'success': False,
            'error': 'Trop de tentatives échouées. Réessayez plus tard.',
            'details': {
                'blocked': True,
                'minutes_remaining': status.get('minutes_remaining', 30)
            }
        }), 429


def rate_limit_auth_endpoints(limiter):
    """Apply specific rate limits to auth endpoints"""
    return {
        'login': limiter.limit("5 per 15 minutes"),
        'change_password': limiter.limit("3 per hour"),
        'reset_password': limiter.limit("2 per hour"),
        'create_user': limiter.limit("10 per hour"),
    }
