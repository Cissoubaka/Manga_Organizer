"""
Module d'authentification pour l'application
Implémente une authentification basique avec Flask-Login
"""
from flask import Blueprint, request, jsonify, render_template
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from werkzeug.security import generate_password_hash, check_password_hash
import os
import json
from audit_log import log_login, log_logout, read_audit_logs, get_user_activity, log_audit
from middleware import IPBlocker, cache_response
from flask_limiter.util import get_remote_address

# Initialize LoginManager
login_manager = LoginManager()
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Authentification requise'

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')

# 🔒 Stockage simple des utilisateurs dans un fichier JSON
USERS_FILE = os.path.join(os.environ.get('DATA_DIR', './data'), 'users.json')


class User(UserMixin):
    """Modèle d'utilisateur pour Flask-Login"""
    
    def __init__(self, id, username, password_hash=None):
        self.id = id
        self.username = username
        self.password_hash = password_hash
    
    def set_password(self, password):
        """Hache le mot de passe"""
        self.password_hash = generate_password_hash(password)
    
    def check_password(self, password):
        """Vérifie le mot de passe"""
        return check_password_hash(self.password_hash, password) if self.password_hash else False
    
    def get_id(self):
        return str(self.id)


def _load_users():
    """Charge les utilisateurs depuis le fichier JSON"""
    if os.path.exists(USERS_FILE):
        try:
            with open(USERS_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}
    return {}


def _save_users(users):
    """Sauvegarde les utilisateurs dans le fichier JSON"""
    try:
        os.makedirs(os.path.dirname(USERS_FILE), exist_ok=True)
        with open(USERS_FILE, 'w') as f:
            json.dump(users, f, indent=4)
        print(f"✅ Utilisateurs sauvegardés dans {USERS_FILE}")
        return True
    except Exception as e:
        print(f"❌ ERREUR sauvegarde utilisateurs: {e}")
        print(f"   Chemin: {USERS_FILE}")
        print(f"   Current directory: {os.getcwd()}")
        return False


def _create_default_user():
    """Crée l'utilisateur administrateur par défaut si pas d'utilisateurs"""
    users = _load_users()
    
    if not users:
        print("⚠️ Aucun utilisateur trouvé. Création de l'utilisateur admin par défaut...")
        
        # Créer un user admin avec un mot de passe par défaut
        admin_user = {
            'id': '1',
            'username': 'admin',
            'password_hash': generate_password_hash('admin123'),  # À CHANGER!
            'is_admin': True
        }
        
        users = {'1': admin_user}
        if not _save_users(users):
            print("❌ ERREUR: Impossible de sauvegarder l'utilisateur admin par défaut!")
            return {}
        
        print("✓ Utilisateur admin créé:")
        print("  → Username: admin")
        print("  → Password: admin123")
        print("  → ⚠️ À CHANGER APRÈS PREMIÈRE CONNEXION!")
        
        return users
    
    return users


@login_manager.user_loader
def user_loader(user_id):
    """Charge un utilisateur depuis le fichier"""
    users = _load_users()
    if user_id in users:
        user_data = users[user_id]
        return User(user_data['id'], user_data['username'], user_data['password_hash'])
    return None


@auth_bp.route('/login', methods=['GET'])
def login_page():
    """Affiche la page de connexion"""
    return render_template('auth.html')


@auth_bp.route('/login', methods=['POST'])
def login():
    """Route de connexion (API JSON)"""
    try:
        # 🔐 SÉCURITÉ: Vérifier si l'IP est bloquée
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
        
        # Note: CSRF protection est globale mais /auth/login est exempté via @csrf.exempt
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '')
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Username et password requis'}), 400
        
        # Charger les utilisateurs
        users = _load_users()
        
        # Chercher l'utilisateur
        user_data = None
        user_id = None
        for uid, u in users.items():
            if u.get('username') == username:
                user_data = u
                user_id = uid
                break
        
        if not user_data or not check_password_hash(user_data.get('password_hash', ''), password):
            print(f"⚠️ Tentative de connexion échouée pour: {username}")
            # 🔐 SÉCURITÉ: Enregistrer la tentative échouée
            attempt_count = IPBlocker.record_failed_attempt(ip_address)
            log_login(username, success=False, ip_address=ip_address, attempt_count=attempt_count)
            return jsonify({'success': False, 'error': 'Username ou password incorrect'}), 401
        
        # Créer l'objet User et enregistrer la session
        user = User(user_id, user_data['username'], user_data.get('password_hash'))
        login_user(user, remember=True)
        
        # 🔐 SÉCURITÉ: Nettoyer les tentatives échouées après succès
        IPBlocker.record_successful_attempt(ip_address)
        
        print(f"✓ Connexion réussie: {username}")
        log_login(username, success=True, ip_address=ip_address)
        
        return jsonify({
            'success': True,
            'message': f'Bienvenue {username}',
            'user': {
                'id': user.id,
                'username': user.username,
                'is_admin': user_data.get('is_admin', False)
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/logout', methods=['POST'])
@login_required
def logout():
    """Route de déconnexion"""
    username = current_user.username
    logout_user()
    print(f"✓ Déconnexion: {username}")
    log_logout(username)
    return jsonify({'success': True, 'message': 'Déconnecté avec succès'})


@auth_bp.route('/current-user', methods=['GET'])
@cache_response(timeout=60)
def get_current_user():
    """Retourne l'utilisateur actuellement connecté"""
    if current_user.is_authenticated:
        return jsonify({
            'success': True,
            'user': {
                'id': current_user.id,
                'username': current_user.username
            }
        })
    else:
        return jsonify({'success': False, 'error': 'Non authentifié'}), 401


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    """Change le mot de passe de l'utilisateur connecté"""
    try:
        data = request.get_json()
        old_password = data.get('old_password', '')
        new_password = data.get('new_password', '')
        
        if not data.get('old_password') or not new_password:
            return jsonify({'success': False, 'error': 'Ancien et nouveau password requis'}), 400
        
        # Charger les utilisateurs
        users = _load_users()
        user_data = users.get(current_user.id, {})
        
        # Vérifier l'ancien mot de passe
        if not check_password_hash(user_data.get('password_hash', ''), old_password):
            return jsonify({'success': False, 'error': 'Ancien password incorrect'}), 401
        
        # Changer le mot de passe
        user_data['password_hash'] = generate_password_hash(new_password)
        users[current_user.id] = user_data
        
        # Sauvegarder ET vérifier le résultat
        if not _save_users(users):
            print(f"⚠️ Erreur lors de la sauvegarde du mot de passe pour {current_user.username}")
            return jsonify({'success': False, 'error': 'Erreur lors de la sauvegarde du mot de passe'}), 500
        
        print(f"✓ Mot de passe changé pour: {current_user.username}")
        
        # 🔐 SÉCURITÉ: Enregistrer l'action en audit
        log_audit('AUTH', f'Mot de passe changé pour {current_user.username}', level='INFO')
        
        return jsonify({'success': True, 'message': 'Mot de passe changé avec succès'})
    
    except Exception as e:
        print(f"❌ Erreur change_password: {e}")
        return jsonify({'success': False, 'error': f'Erreur: {str(e)}'}), 500


@auth_bp.route('/audit-logs', methods=['GET'])
@login_required
@cache_response(timeout=60)
def get_audit_logs():
    """Retourne les logs d'audit (admin only)"""
    try:
        if not current_user.id == '1':  # ID du user admin
            return jsonify({'success': False, 'error': 'Accès refusé (admin requis)'}), 403
        
        limit = request.args.get('limit', 100, type=int)
        action_filter = request.args.get('action', None, type=str)
        
        # Récupérer les logs
        logs = read_audit_logs(limit=limit, action_filter=action_filter)
        
        return jsonify({
            'success': True,
            'count': len(logs),
            'logs': logs
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/user-activity/<username>', methods=['GET'])
@login_required
@cache_response(timeout=60)
def get_user_audit(username):
    """Retourne l'activité d'un utilisateur spécifique (admin only)"""
    try:
        if not current_user.id == '1':  # ID du user admin
            return jsonify({'success': False, 'error': 'Accès refusé (admin requis)'}), 403
        
        limit = request.args.get('limit', 50, type=int)
        
        # Récupérer l'activité
        activity = get_user_activity(username, limit=limit)
        
        return jsonify({
            'success': True,
            'username': username,
            'count': len(activity),
            'activity': activity
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ============================================================================
# PHASE 3 - USER MANAGEMENT (CRUD Operations)
# ============================================================================

def _generate_user_id(users):
    """Génère un nouvel ID utilisateur unique"""
    if not users:
        return "2"
    existing_ids = [int(uid) for uid in users.keys() if uid.isdigit()]
    return str(max(existing_ids) + 1) if existing_ids else "2"


def _validate_username(username):
    """Valide le format du username"""
    if not username or len(username) < 3:
        return False, "Username doit avoir au moins 3 caractères"
    if len(username) > 32:
        return False, "Username doit avoir au maximum 32 caractères"
    if not username.islower():
        return False, "Username doit être en minuscules"
    if not all(c.isalnum() or c == '_' for c in username):
        return False, "Username ne peut contenir que des lettres, chiffres et _"
    return True, ""


def _validate_password(password):
    """Valide la force du mot de passe"""
    if not password or len(password) < 8:
        return False, "Mot de passe doit avoir au moins 8 caractères"
    if len(password) > 128:
        return False, "Mot de passe doit avoir au maximum 128 caractères"
    return True, ""


@auth_bp.route('/users', methods=['POST'])
@login_required
def create_user():
    """Crée un nouvel utilisateur (admin only)"""
    try:
        # Vérifier accès admin
        if not current_user.id == '1':
            log_audit('USER', 'Tentative d\'accès non autorisé à création utilisateur',
                     username=current_user.username)
            return jsonify({'success': False, 'error': 'Accès refusé (admin requis)'}), 403
        
        data = request.get_json()
        username = data.get('username', '').strip().lower()
        password = data.get('password', '')
        is_admin = data.get('is_admin', False)
        
        # Valider username
        valid, msg = _validate_username(username)
        if not valid:
            return jsonify({'success': False, 'error': msg}), 400
        
        # Valider password
        valid, msg = _validate_password(password)
        if not valid:
            return jsonify({'success': False, 'error': msg}), 400
        
        # Charger les utilisateurs
        users = _load_users()
        
        # Vérifier que le username n'existe pas
        for u in users.values():
            if u.get('username') == username:
                log_audit('USER', f'Tentative création utilisateur dupliqué: {username}',
                         admin=current_user.username)
                return jsonify({'success': False, 'error': 'Username déjà utilisé'}), 409
        
        # Créer le nouvel utilisateur
        user_id = _generate_user_id(users)
        new_user = {
            'id': user_id,
            'username': username,
            'password_hash': generate_password_hash(password),
            'is_admin': bool(is_admin)
        }
        
        users[user_id] = new_user
        if not _save_users(users):
            return jsonify({'success': False, 'error': 'Erreur lors de la sauvegarde de l\'utilisateur'}), 500
        
        # Log audit
        log_audit('USER', f'Utilisateur créé: {username}',
                 admin=current_user.username, new_user_id=user_id)
        
        print(f"✓ Utilisateur créé: {username} (ID: {user_id})")
        
        return jsonify({
            'success': True,
            'message': f'Utilisateur {username} créé',
            'user': {
                'id': user_id,
                'username': username,
                'is_admin': bool(is_admin)
            }
        }), 201
    
    except Exception as e:
        log_audit('USER', f'Erreur création utilisateur: {str(e)}', level='ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/users', methods=['GET'])
@login_required
@cache_response(timeout=300)
def list_users():
    """Liste tous les utilisateurs (admin only)"""
    try:
        # Vérifier accès admin
        if not current_user.id == '1':
            log_audit('USER', 'Tentative d\'accès non autorisé à liste utilisateurs',
                     username=current_user.username)
            return jsonify({'success': False, 'error': 'Accès refusé (admin requis)'}), 403
        
        users = _load_users()
        
        # Préparer la liste sans les password hashes
        users_list = []
        for uid, user_data in users.items():
            users_list.append({
                'id': uid,
                'username': user_data.get('username'),
                'is_admin': user_data.get('is_admin', False)
            })
        
        log_audit('USER', 'Liste utilisateurs consultée',
                 admin=current_user.username, count=len(users_list))
        
        return jsonify({
            'success': True,
            'count': len(users_list),
            'users': users_list
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/users/<user_id>', methods=['GET'])
@login_required
@cache_response(timeout=300)
def get_user(user_id):
    """Récupère les détails d'un utilisateur (admin only)"""
    try:
        # Vérifier accès admin
        if not current_user.id == '1':
            return jsonify({'success': False, 'error': 'Accès refusé (admin requis)'}), 403
        
        users = _load_users()
        
        if user_id not in users:
            return jsonify({'success': False, 'error': 'Utilisateur non trouvé'}), 404
        
        user_data = users[user_id]
        
        return jsonify({
            'success': True,
            'user': {
                'id': user_id,
                'username': user_data.get('username'),
                'is_admin': user_data.get('is_admin', False)
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/users/<user_id>', methods=['PUT'])
@login_required
def update_user(user_id):
    """Modifie un utilisateur (admin only)"""
    try:
        # Vérifier accès admin
        if not current_user.id == '1':
            log_audit('USER', f'Tentative modification utilisateur {user_id} non autorisée',
                     username=current_user.username)
            return jsonify({'success': False, 'error': 'Accès refusé (admin requis)'}), 403
        
        data = request.get_json()
        users = _load_users()
        
        if user_id not in users:
            return jsonify({'success': False, 'error': 'Utilisateur non trouvé'}), 404
        
        user_data = users[user_id]
        old_data = user_data.copy()
        
        # Mettre à jour is_admin si fourni
        if 'is_admin' in data:
            # Empêcher de modifier l'admin principal
            if user_id == '1' and not data.get('is_admin'):
                return jsonify({'success': False, 'error': 'Cannot remove admin status from main admin'}), 400
            user_data['is_admin'] = bool(data.get('is_admin'))
        
        users[user_id] = user_data
        if not _save_users(users):
            return jsonify({'success': False, 'error': 'Erreur lors de la sauvegarde des modifications'}), 500
        
        # Log audit
        log_audit('USER', f'Utilisateur modifié: {user_data["username"]}',
                 admin=current_user.username, user_id=user_id, 
                 changes={'is_admin': old_data.get('is_admin') != user_data.get('is_admin')})
        
        print(f"✓ Utilisateur modifié: {user_data['username']}")
        
        return jsonify({
            'success': True,
            'message': f'Utilisateur {user_data["username"]} modifié',
            'user': {
                'id': user_id,
                'username': user_data.get('username'),
                'is_admin': user_data.get('is_admin', False)
            }
        })
    
    except Exception as e:
        log_audit('USER', f'Erreur modification utilisateur {user_id}: {str(e)}',
                 admin=current_user.username, level='ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/users/<user_id>', methods=['DELETE'])
@login_required
def delete_user(user_id):
    """Supprime un utilisateur (admin only)"""
    try:
        # Vérifier accès admin
        if not current_user.id == '1':
            log_audit('USER', f'Tentative suppression utilisateur {user_id} non autorisée',
                     username=current_user.username)
            return jsonify({'success': False, 'error': 'Accès refusé (admin requis)'}), 403
        
        # Empêcher la suppression de l'admin principal
        if user_id == '1':
            return jsonify({'success': False, 'error': 'Cannot delete main admin user'}), 400
        
        users = _load_users()
        
        if user_id not in users:
            return jsonify({'success': False, 'error': 'Utilisateur non trouvé'}), 404
        
        username = users[user_id].get('username', 'unknown')
        del users[user_id]
        if not _save_users(users):
            return jsonify({'success': False, 'error': 'Erreur lors de la suppression de l\'utilisateur'}), 500
        
        # Log audit
        log_audit('USER', f'Utilisateur supprimé: {username}',
                 admin=current_user.username, deleted_user_id=user_id)
        
        print(f"✓ Utilisateur supprimé: {username}")
        
        return jsonify({
            'success': True,
            'message': f'Utilisateur {username} supprimé'
        })
    
    except Exception as e:
        log_audit('USER', f'Erreur suppression utilisateur {user_id}: {str(e)}',
                 admin=current_user.username, level='ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/users/<user_id>/reset-password', methods=['POST'])
@login_required
def reset_user_password(user_id):
    """Réinitialise le mot de passe d'un utilisateur (admin only)"""
    try:
        # Vérifier accès admin
        if not current_user.id == '1':
            log_audit('USER', f'Tentative reset password utilisateur {user_id} non autorisée',
                     username=current_user.username)
            return jsonify({'success': False, 'error': 'Accès refusé (admin requis)'}), 403
        
        data = request.get_json()
        new_password = data.get('password', '')
        
        # Valider password
        valid, msg = _validate_password(new_password)
        if not valid:
            return jsonify({'success': False, 'error': msg}), 400
        
        users = _load_users()
        
        if user_id not in users:
            return jsonify({'success': False, 'error': 'Utilisateur non trouvé'}), 404
        
        user_data = users[user_id]
        username = user_data.get('username')
        
        # Changer le mot de passe
        user_data['password_hash'] = generate_password_hash(new_password)
        users[user_id] = user_data
        if not _save_users(users):
            return jsonify({'success': False, 'error': 'Erreur lors de la sauvegarde du mot de passe'}), 500
        
        # Log audit
        log_audit('USER', f'Mot de passe réinitialisé: {username}',
                 admin=current_user.username, user_id=user_id)
        
        print(f"✓ Mot de passe changé pour: {username}")
        
        return jsonify({
            'success': True,
            'message': f'Mot de passe de {username} réinitialisé'
        })
    
    except Exception as e:
        log_audit('USER', f'Erreur reset password utilisateur {user_id}: {str(e)}',
                 admin=current_user.username, level='ERROR')
        return jsonify({'success': False, 'error': str(e)}), 500


@auth_bp.route('/performance-stats', methods=['GET'])
@login_required
def get_performance_stats():
    """Retourne les statistiques de performance (admin only)"""
    try:
        # Vérifier accès admin
        if not current_user.id == '1':
            return jsonify({'success': False, 'error': 'Accès refusé (admin requis)'}), 403
        
        # Importer le cache_manager depuis l'app
        from app import cache_manager, limiter
        
        # Obtenir les statistiques du cache
        cache_stats = cache_manager.get_stats()
        
        # Calculer les statistiques de rate limiting
        blocked_ips = {}
        failed_attempts_file = os.path.join(os.environ.get('DATA_DIR', './data'), 
                                           'rate_limits', 'failed_attempts.json')
        
        if os.path.exists(failed_attempts_file):
            try:
                with open(failed_attempts_file, 'r') as f:
                    attempts_data = json.load(f)
                    for ip, data in attempts_data.items():
                        if data.get('blocked'):
                            blocked_ips[ip] = {
                                'attempts': data.get('attempts'),
                                'blocked_until': data.get('blocked_until'),
                                'minutes_remaining': data.get('minutes_remaining', 0)
                            }
            except Exception:
                pass
        
        return jsonify({
            'success': True,
            'performance': {
                'cache': cache_stats,
                'rate_limiting': {
                    'blocked_ips': len(blocked_ips),
                    'blocked_ips_details': blocked_ips
                }
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
