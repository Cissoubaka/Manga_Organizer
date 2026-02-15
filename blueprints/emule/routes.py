"""
Routes pour l'intégration eMule/aMule
"""
from flask import request, jsonify, current_app
from . import emule_bp
import json
import os
import subprocess
from encryption import encrypt, decrypt



def load_emule_config():
    """Charge la configuration eMule"""
    config_file = current_app.config['CONFIG_FILE']
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            cfg = json.load(f)
    else:
        cfg = current_app.config['EMULE_CONFIG'].copy()

    # Déchiffrer le mot de passe s'il existe
    pwd = cfg.get('password', '')
    if pwd:
        decrypted = decrypt(pwd)
        if decrypted:
            cfg['password_decrypted'] = decrypted
    
    return cfg


def save_emule_config(config):
    """Sauvegarde la configuration eMule"""
    config_file = current_app.config['CONFIG_FILE']
    
    try:
        # Préparer une copie pour la sauvegarde
        config_to_save = config.copy()
        
        # Chiffrer le mot de passe avant la sauvegarde
        if config_to_save.get('password') or config_to_save.get('password_decrypted'):
            password_to_encrypt = config_to_save.get('password_decrypted') or config_to_save.get('password')
            if password_to_encrypt:
                config_to_save['password'] = encrypt(password_to_encrypt)
            if 'password_decrypted' in config_to_save:
                del config_to_save['password_decrypted']
        
        with open(config_file, 'w') as f:
            json.dump(config_to_save, f, indent=4)
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
                config['password_decrypted'] = new_password

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
            '-P', config.get('password_decrypted', ''),
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
            '-P', config.get('password_decrypted', ''),
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