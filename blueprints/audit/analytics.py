"""
Analytics helper functions for dashboard and reporting
Processes audit logs into aggregated statistics
"""
import json
import os
from datetime import datetime, timedelta
from collections import defaultdict, Counter
from audit_log import read_audit_logs


class ActivityAnalytics:
    """Analytics engine for audit data"""
    
    @staticmethod
    def get_activity_trend(days=7, action_filter=None):
        """Get activity trend over last N days"""
        try:
            logs = read_audit_logs(limit=10000)
            trend = defaultdict(int)
            
            now = datetime.now()
            
            for log in logs:
                try:
                    log_date = datetime.fromisoformat(log.get('timestamp', ''))
                    days_ago = (now - log_date).days
                    
                    if days_ago < days:
                        date_key = (now - timedelta(days=days_ago)).strftime('%Y-%m-%d')
                        if action_filter is None or log.get('action') == action_filter:
                            trend[date_key] += 1
                except:
                    pass
            
            # Fill in missing dates with 0
            result = {}
            for i in range(days):
                date_key = (now - timedelta(days=i)).strftime('%Y-%m-%d')
                result[date_key] = trend.get(date_key, 0)
            
            return dict(sorted(result.items()))
        except Exception as e:
            return {}
    
    @staticmethod
    def get_user_activity_chart(limit=10):
        """Get most active users"""
        try:
            logs = read_audit_logs(limit=10000)
            user_counts = Counter()
            
            for log in logs:
                username = log.get('username')
                if username:
                    user_counts[username] += 1
            
            return dict(user_counts.most_common(limit))
        except Exception as e:
            return {}
    
    @staticmethod
    def get_failed_login_stats(days=7):
        """Get failed login attempts over time"""
        try:
            logs = read_audit_logs(limit=10000)
            stats = defaultdict(int)
            
            now = datetime.now()
            
            for log in logs:
                try:
                    if 'Tentative de connexion échouée' in log.get('action', ''):
                        log_date = datetime.fromisoformat(log.get('timestamp', ''))
                        days_ago = (now - log_date).days
                        
                        if days_ago < days:
                            date_key = (now - timedelta(days=days_ago)).strftime('%Y-%m-%d')
                            stats[date_key] += 1
                except:
                    pass
            
            # Fill in missing dates
            result = {}
            for i in range(days):
                date_key = (now - timedelta(days=i)).strftime('%Y-%m-%d')
                result[date_key] = stats.get(date_key, 0)
            
            return dict(sorted(result.items()))
        except Exception as e:
            return {}
    
    @staticmethod
    def get_ip_statistics(limit=10):
        """Get activity by IP address"""
        try:
            logs = read_audit_logs(limit=10000)
            ip_counts = Counter()
            
            for log in logs:
                ip = log.get('ip_address')
                if ip:
                    ip_counts[ip] += 1
            
            return dict(ip_counts.most_common(limit))
        except Exception as e:
            return {}
    
    @staticmethod
    def get_quick_stats():
        """Get quick statistics cards"""
        try:
            logs = read_audit_logs(limit=10000)
            
            stats = {
                'total_events': len(logs),
                'failed_logins': 0,
                'user_creations': 0,
                'user_deletions': 0,
                'unique_users': len(set(log.get('username') for log in logs)),
                'unique_ips': len(set(log.get('ip_address') for log in logs if log.get('ip_address')))
            }
            
            for log in logs:
                action = log.get('action', '')
                if 'Tentative de connexion échouée' in action:
                    stats['failed_logins'] += 1
                elif 'Utilisateur créé' in action:
                    stats['user_creations'] += 1
                elif 'Utilisateur supprimé' in action:
                    stats['user_deletions'] += 1
            
            return stats
        except Exception as e:
            return {
                'total_events': 0,
                'failed_logins': 0,
                'user_creations': 0,
                'user_deletions': 0,
                'unique_users': 0,
                'unique_ips': 0
            }
    
    @staticmethod
    def get_recent_activity(limit=50):
        """Get recent activity events"""
        try:
            logs = read_audit_logs(limit=limit)
            
            activity = []
            for log in logs:
                activity.append({
                    'timestamp': log.get('timestamp'),
                    'username': log.get('username'),
                    'action': log.get('action'),
                    'ip_address': log.get('ip_address'),
                    'level': log.get('level', 'INFO')
                })
            
            return activity
        except Exception as e:
            return []
    
    @staticmethod
    def get_action_distribution():
        """Get distribution of action types"""
        try:
            logs = read_audit_logs(limit=10000)
            actions = Counter()
            
            for log in logs:
                action = log.get('action', 'Unknown')
                # Simplify action names
                if 'connexion' in action.lower():
                    actions['Login Attempts'] += 1
                elif 'utilisateur' in action.lower():
                    actions['User Management'] += 1
                elif 'mot de passe' in action.lower():
                    actions['Password Changes'] += 1
                else:
                    actions['Other'] += 1
            
            return dict(actions)
        except Exception as e:
            return {}


class AlertSystem:
    """Alert detection and management"""
    
    THRESHOLDS = {
        'failed_logins_per_minute': 5,
        'failed_logins_per_hour': 20,
        'blocked_ips': 3,
        'user_deletions': 2
    }
    
    @staticmethod
    def check_failed_login_spike(minutes=1):
        """Detect rapid failed login attempts"""
        try:
            logs = read_audit_logs(limit=1000)
            now = datetime.now()
            
            recent_failures = 0
            for log in logs:
                try:
                    log_date = datetime.fromisoformat(log.get('timestamp', ''))
                    if (now - log_date).total_seconds() < minutes * 60:
                        if 'Tentative de connexion échouée' in log.get('action', ''):
                            recent_failures += 1
                except:
                    pass
            
            if recent_failures >= AlertSystem.THRESHOLDS['failed_logins_per_minute']:
                return {
                    'alert': True,
                    'type': 'failed_login_spike',
                    'severity': 'HIGH',
                    'message': f'Multiple failed login attempts detected: {recent_failures}',
                    'count': recent_failures
                }
            
            return {'alert': False}
        except Exception as e:
            return {'alert': False}
    
    @staticmethod
    def check_blocked_ips():
        """Check if multiple IPs are blocked"""
        try:
            from middleware import IPBlocker
            
            # Get all blocks
            blocked_count = 0
            failed_attempts_file = os.path.join(
                os.environ.get('DATA_DIR', './data'), 
                'rate_limits', 
                'failed_attempts.json'
            )
            
            if os.path.exists(failed_attempts_file):
                with open(failed_attempts_file, 'r') as f:
                    attempts = json.load(f)
                    for ip, data in attempts.items():
                        if data.get('blocked'):
                            blocked_count += 1
            
            if blocked_count >= AlertSystem.THRESHOLDS['blocked_ips']:
                return {
                    'alert': True,
                    'type': 'multiple_blocked_ips',
                    'severity': 'MEDIUM',
                    'message': f'{blocked_count} IP addresses are currently blocked',
                    'count': blocked_count
                }
            
            return {'alert': False}
        except Exception as e:
            return {'alert': False}


class ReportGenerator:
    """Generate reports in various formats"""
    
    @staticmethod
    def apply_filters(logs, filters):
        """Apply filters to logs"""
        filtered = logs
        
        if 'username' in filters and filters['username']:
            filtered = [l for l in filtered if l.get('username') == filters['username']]
        
        if 'action' in filters and filters['action']:
            filtered = [l for l in filtered if filters['action'] in l.get('action', '')]
        
        if 'ip_address' in filters and filters['ip_address']:
            filtered = [l for l in filtered if l.get('ip_address') == filters['ip_address']]
        
        if 'level' in filters and filters['level']:
            filtered = [l for l in filtered if l.get('level') == filters['level']]
        
        if 'date_from' in filters and filters['date_from']:
            try:
                date_from = datetime.fromisoformat(filters['date_from'])
                filtered = [l for l in filtered 
                           if datetime.fromisoformat(l.get('timestamp', '')) >= date_from]
            except:
                pass
        
        if 'date_to' in filters and filters['date_to']:
            try:
                date_to = datetime.fromisoformat(filters['date_to'])
                filtered = [l for l in filtered 
                           if datetime.fromisoformat(l.get('timestamp', '')) <= date_to]
            except:
                pass
        
        return filtered
    
    @staticmethod
    def get_available_filters():
        """Get available filter options"""
        try:
            logs = read_audit_logs(limit=10000)
            
            usernames = sorted(set(l.get('username') for l in logs if l.get('username')))
            ips = sorted(set(l.get('ip_address') for l in logs if l.get('ip_address')))
            actions = sorted(set(l.get('action') for l in logs if l.get('action')))
            levels = sorted(set(l.get('level', 'INFO') for l in logs))
            
            return {
                'usernames': usernames,
                'ips': ips,
                'actions': actions,
                'levels': levels
            }
        except Exception as e:
            return {
                'usernames': [],
                'ips': [],
                'actions': [],
                'levels': ['INFO', 'WARNING', 'ERROR']
            }
