"""
🔍 Audit Logging - Traçabilité des actions sensibles
Enregistre toutes les actions de sécurité dans un fichier de log audit
"""

import os
import json
import logging
from datetime import datetime
from functools import wraps
from flask import request, g, has_request_context
from pathlib import Path

# Créer le répertoire des logs s'il n'existe pas
LOG_DIR = Path('data/audit_logs')
LOG_DIR.mkdir(parents=True, exist_ok=True)

# Configurer le logger d'audit
audit_logger = logging.getLogger('audit')
audit_logger.setLevel(logging.INFO)

# Créer un handler qui écrit dans un fichier JSON
log_file = LOG_DIR / f'audit.log'

class AuditLogHandler(logging.FileHandler):
    """Handler personnalisé pour les logs d'audit en JSON"""
    
    def emit(self, record):
        """Émettre un record formaté en JSON"""
        try:
            log_entry = {
                'timestamp': datetime.utcnow().isoformat(),
                'action': record.name.replace('audit.', ''),
                'level': record.levelname,
                'message': record.getMessage(),
                # Les informations supplémentaires sont dans record.__dict__
            }
            
            # Ajouter les champs supplémentaires
            if hasattr(record, 'user'):
                log_entry['user'] = record.user
            if hasattr(record, 'ip_address'):
                log_entry['ip_address'] = record.ip_address
            if hasattr(record, 'endpoint'):
                log_entry['endpoint'] = record.endpoint
            if hasattr(record, 'status_code'):
                log_entry['status_code'] = record.status_code
            if hasattr(record, 'details'):
                log_entry['details'] = record.details
            
            # Écrire le JSON
            with open(log_file, 'a') as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + '\n')
        except Exception:
            self.handleError(record)

# Ajouter le handler personnalisé
handler = AuditLogHandler(str(log_file))
formatter = logging.Formatter('%(message)s')
handler.setFormatter(formatter)
audit_logger.addHandler(handler)

# ============================================================================
# FUNCTIONS UTILITAIRES
# ============================================================================

def get_request_info():
    """Récupère les informations de la requête actuelle"""
    if not has_request_context():
        return {}
    
    from flask_login import current_user
    
    return {
        'user': current_user.username if current_user and current_user.is_authenticated else 'anonymous',
        'ip_address': request.remote_addr,
        'endpoint': request.endpoint or 'unknown',
        'method': request.method
    }

def log_audit(action, message, level='INFO', **details):
    """
    Enregistre un événement d'audit
    
    Args:
        action: Type d'action (e.g., 'AUTH', 'USER', 'DATA', 'ERROR')
        message: Message descriptif
        level: Niveau de log (INFO, WARNING, ERROR, CRITICAL)
        **details: Informations supplémentaires à enregistrer
    """
    if not has_request_context():
        return
    
    info = get_request_info()
    info['details'] = details
    
    # Créer un record de log
    record = logging.LogRecord(
        name=f'audit.{action}',
        level=getattr(logging, level, logging.INFO),
        pathname='',
        lineno=0,
        msg=message,
        args=(),
        exc_info=None
    )
    
    # Ajouter les attributs supplémentaires
    for key, value in info.items():
        setattr(record, key, value)
    
    # Émettre le record
    audit_logger.handle(record)

# ============================================================================
# DÉCORATEURS
# ============================================================================

def audit_action(action_type, message_template=None):
    """
    Décorateur pour enregistrer automatiquement une action dans l'audit log
    
    Usage:
        @audit_action('USER', 'Connexion utilisateur: {username}')
        def login():
            ...
    """
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            try:
                result = f(*args, **kwargs)
                
                # Déterminer le message
                if message_template:
                    if has_request_context():
                        from flask_login import current_user
                        msg = message_template.format(
                            username=current_user.username if current_user and current_user.is_authenticated else 'unknown'
                        )
                    else:
                        msg = message_template
                else:
                    msg = f'Action: {f.__name__}'
                
                # Log succès
                log_audit(action_type, msg, level='INFO', function=f.__name__)
                
                return result
            except Exception as e:
                # Log erreur
                log_audit(action_type, f'Erreur: {str(e)}', level='ERROR', 
                         function=f.__name__, error=str(e))
                raise
        
        return decorated_function
    return decorator

# ============================================================================
# TYPES D'ACTIONS D'AUDIT
# ============================================================================

class AuditActions:
    """Catégories et types d'événements d'audit"""
    
    # Authentification
    LOGIN_SUCCESS = ('AUTH', 'Connexion réussie')
    LOGIN_FAILED = ('AUTH', 'Tentative de connexion échouée')
    LOGOUT_SUCCESS = ('AUTH', 'Déconnexion réussie')
    SESSION_EXPIRED = ('AUTH', 'Session expirée')
    UNAUTHORIZED_ACCESS = ('AUTH', 'Accès non autorisé à ressource protégée')
    
    # Gestion des utilisateurs
    USER_CREATED = ('USER', 'Utilisateur créé')
    USER_MODIFIED = ('USER', 'Utilisateur modifié')
    USER_DELETED = ('USER', 'Utilisateur supprimé')
    PASSWORD_CHANGED = ('USER', 'Mot de passe changé')
    
    # Données
    DATA_IMPORTED = ('DATA', 'Données importées')
    DATA_EXPORTED = ('DATA', 'Données exportées')
    DATA_MODIFIED = ('DATA', 'Données modifiées')
    DATA_DELETED = ('DATA', 'Données supprimées')
    
    # Sécurité
    CSRF_VALIDATION_FAILED = ('SECURITY', 'Validation CSRF échouée')
    SUSPICIOUS_ACTIVITY = ('SECURITY', 'Activité suspecte détectée')
    RATE_LIMIT_EXCEEDED = ('SECURITY', 'Limite de taux dépassée')
    
    # Erreurs
    ERROR_OCCURRED = ('ERROR', 'Erreur applicative')

# ============================================================================
# HELPER POUR LES APPELS D'AUDIT
# ============================================================================

def log_login(username, success=True, ip_address=None, attempt_count=None):
    """Enregistre une tentative de connexion"""
    action, msg = AuditActions.LOGIN_SUCCESS if success else AuditActions.LOGIN_FAILED
    
    # Préparer les détails à enregistrer
    audit_details = {'username': username}
    if ip_address is not None:
        audit_details['ip_address'] = ip_address
    if attempt_count is not None:
        audit_details['attempt_count'] = attempt_count
    
    log_audit(action, msg, **audit_details)

def log_logout(username):
    """Enregistre une déconnexion"""
    action, msg = AuditActions.LOGOUT_SUCCESS
    log_audit(action, msg, username=username)

def log_unauthorized_access(resource):
    """Enregistre une tentative d'accès non autorisé"""
    action, msg = AuditActions.UNAUTHORIZED_ACCESS
    log_audit(action, msg, resource=resource)

def log_csrf_failure(reason=''):
    """Enregistre une validation CSRF échouée"""
    action, msg = AuditActions.CSRF_VALIDATION_FAILED
    log_audit(action, msg, reason=reason)

def log_data_import(count, source):
    """Enregistre une importation de données"""
    action, msg = AuditActions.DATA_IMPORTED
    log_audit(action, msg, count=count, source=source)

def log_data_modification(resource, old_value, new_value):
    """Enregistre une modification de données"""
    action, msg = AuditActions.DATA_MODIFIED
    log_audit(action, msg, resource=resource, old=old_value, new=new_value)

def log_rate_limit_exceeded(endpoint, ip_address):
    """Enregistre un dépassement de limite de taux"""
    action, msg = AuditActions.RATE_LIMIT_EXCEEDED
    log_audit(action, msg, endpoint=endpoint, ip=ip_address)

# ============================================================================
# LECTURE DES LOGS D'AUDIT
# ============================================================================

def read_audit_logs(limit=100, action_filter=None, user_filter=None):
    """
    Lit les logs d'audit
    
    Args:
        limit: Nombre maximum de lignes à retourner
        action_filter: Filtrer par type d'action (ex: 'AUTH', 'USER')
        user_filter: Filtrer par utilisateur
    
    Returns:
        List de dictionnaires avec les entrées de log
    """
    logs = []
    
    if not log_file.exists():
        return logs
    
    with open(log_file, 'r') as f:
        lines = f.readlines()
    
    # Traiter les dernières lignes (les plus récentes)
    for line in reversed(lines[-limit:]):
        try:
            entry = json.loads(line)
            
            # Appliquer les filtres
            if action_filter and entry.get('action') != action_filter:
                continue
            if user_filter and entry.get('user') != user_filter:
                continue
            
            logs.append(entry)
        except json.JSONDecodeError:
            continue
    
    return list(reversed(logs))

def get_user_activity(username, limit=50):
    """Récupère l'activité d'un utilisateur spécifique"""
    return read_audit_logs(limit=limit, user_filter=username)

def get_action_count(action, start_date=None, end_date=None):
    """Compte le nombre d'actions d'un certain type"""
    count = 0
    
    if not log_file.exists():
        return count
    
    with open(log_file, 'r') as f:
        for line in f:
            try:
                entry = json.loads(line)
                if entry.get('action') == action:
                    count += 1
            except json.JSONDecodeError:
                continue
    
    return count
