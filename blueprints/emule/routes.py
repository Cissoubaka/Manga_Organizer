"""
Routes pour l'intégration eMule/aMule
"""
from flask import request, jsonify, current_app
from . import emule_bp
import json
import os
import subprocess


def get_or_create_key():
    key_file = current_app.config['KEY_FILE']
    """Génère ou récupère la clé de chiffrement"""
    try:
        from cryptography.fernet import Fernet
        import os

        if os.path.exists(key_file):
            with open(key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(key_file, 'wb') as f:
                f.write(key)
            print(f"✓ Clé de chiffrement générée dans {key_file}")
            return key
    except ImportError:
        print("⚠️ Module cryptography non installé. Mot de passe non chiffré.")
        return None

def encrypt_password(password):
    """Chiffre le mot de passe"""
    if not password:
        return ''
    try:
        from cryptography.fernet import Fernet
        key = get_or_create_key()
        if key:
            f = Fernet(key)
            return f.encrypt(password.encode()).decode()
        return password
    except:
        return password

def decrypt_password(encrypted_password):
    """Déchiffre le mot de passe"""
    if not encrypted_password:
        return ''
    try:
        from cryptography.fernet import Fernet
        key = get_or_create_key()
        if key:
            f = Fernet(key)
            return f.decrypt(encrypted_password.encode()).decode()
        return encrypted_password
    except:
        return encrypted_password



def load_emule_config():
    """Charge la configuration eMule"""
    config_file = current_app.config['CONFIG_FILE']
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return json.load(f)
    
    return current_app.config['EMULE_CONFIG'].copy()


def save_emule_config(config):
    """Sauvegarde la configuration eMule"""
    config_file = current_app.config['CONFIG_FILE']
    
    try:
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Erreur sauvegarde config : {e}")
        return False


@emule_bp.route('/config', methods=['GET', 'POST'])
def emule_config():
    """Configuration eMule"""
    
    if request.method == 'GET':
        config = load_emule_config()
        
        # Masquer le mot de passe
        return jsonify({
            'enabled': config['enabled'],
            'type': config['type'],
            'host': config['host'],
            'ec_port': config['ec_port'],
            'password': '****' if config.get('password') else ''
        })
    
    else:  # POST
        try:
            new_config = request.get_json()
            config = load_emule_config()
            
            config['enabled'] = new_config.get('enabled', False)
            config['type'] = new_config.get('type', 'amule')
            config['host'] = new_config.get('host', '127.0.0.1')
            config['ec_port'] = new_config.get('ec_port', 4712)
            
            # Ne change le mot de passe que s'il n'est pas masqué
            new_password = new_config.get('password', '')
            if new_password and new_password != '****':
                config['password'] = new_password
            
            if save_emule_config(config):
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Erreur de sauvegarde'}), 500
        
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


@emule_bp.route('/add', methods=['POST'])
def add_to_emule():
    """Ajoute un lien ED2K à eMule"""
    
    config = load_emule_config()
    
    if not config['enabled']:
        return jsonify({'success': False, 'error': 'aMule non activé'}), 400
    
    data = request.get_json()
    link = data.get('link')
    
    if not link:
        return jsonify({'success': False, 'error': 'Lien manquant'}), 400
    
    try:
        cmd = [
            'amulecmd',
            '-h', config['host'],
            '-P', config['password'],
            '-p', str(config['ec_port']),
            '-c', f'add {link}'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': result.stderr}), 500
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@emule_bp.route('/test', methods=['GET'])
def test_connection():
    """Test la connexion à eMule"""
    
    config = load_emule_config()
    
    if not config['enabled']:
        return jsonify({'success': False, 'error': 'aMule non activé'}), 400
    
    try:
        cmd = [
            'amulecmd',
            '-h', config['host'],
            '-P', config['password'],
            '-p', str(config['ec_port']),
            '-c', 'status'
        ]
        
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)
        
        if result.returncode == 0:
            return jsonify({'success': True, 'message': 'Connexion réussie'})
        else:
            return jsonify({'success': False, 'error': result.stderr}), 500
    
    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'amulecmd introuvable'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500