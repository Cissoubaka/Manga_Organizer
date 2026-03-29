"""
Routes pour l'intégration qBittorrent
"""
from flask import request, jsonify, current_app
from flask_login import login_required
from . import qbittorrent_bp
import json
import os
import requests
from encryption import encrypt, decrypt


def load_qbittorrent_config():
    """Charge la configuration qBittorrent"""
    config_file = current_app.config['QBITTORRENT_CONFIG_FILE']
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            cfg = json.load(f)
    else:
        cfg = current_app.config['QBITTORRENT_CONFIG'].copy()

    # Déchiffrer le mot de passe s'il existe
    password = cfg.get('password', '')
    if password:
        decrypted = decrypt(password)
        if decrypted:
            cfg['password_decrypted'] = decrypted
    
    return cfg


def save_qbittorrent_config(config):
    """Sauvegarde la configuration qBittorrent"""
    config_file = current_app.config['QBITTORRENT_CONFIG_FILE']
    
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
        print(f"Erreur sauvegarde config qBittorrent : {e}")
        return False


@qbittorrent_bp.route('/config', methods=['GET', 'POST'])
@login_required
def qbittorrent_config():
    """Configuration qBittorrent"""
    
    if request.method == 'GET':
        config = load_qbittorrent_config()
        
        # Retourner le mot de passe déchiffré (c'est une API d'administration)
        return jsonify({
            'enabled': config.get('enabled', False),
            'url': config.get('url', ''),
            'port': config.get('port', 8080),
            'username': config.get('username', ''),
            'password': config.get('password_decrypted', ''),
            'default_category': config.get('default_category', '')
        })
    
    else:  # POST
        try:
            new_config = request.get_json()
            config = load_qbittorrent_config()

            config['enabled'] = new_config.get('enabled', False)
            config['url'] = new_config.get('url', '').strip()
            config['port'] = new_config.get('port', 8080)
            config['username'] = new_config.get('username', '').strip()
            config['default_category'] = new_config.get('default_category', '').strip()

            # Mettre à jour le mot de passe s'il est fourni
            new_password = new_config.get('password', '')
            if new_password:
                config['password_decrypted'] = new_password

            if save_qbittorrent_config(config):
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Erreur de sauvegarde'}), 500

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


@qbittorrent_bp.route('/test', methods=['POST', 'GET'])
@login_required
def test_qbittorrent_connection():
    """Teste la connexion à qBittorrent"""
    try:
        import sys
        
        # Utiliser la config du POST si fournie, sinon charger la config sauvegardée
        post_config = request.get_json() if request.method == 'POST' and request.get_json() else None
        
        if post_config:
            # Utiliser la configuration temporaire du formulaire pour le test
            config = post_config
            print(f"[qBittorrent Test] Config du formulaire: url={config.get('url')}, port={config.get('port')}", file=sys.stderr)
        else:
            # Charger la configuration sauvegardée
            config = load_qbittorrent_config()
            if not config.get('enabled', False):
                return jsonify({'success': False, 'error': 'Intégration qBittorrent désactivée'}), 400
        
        if not config.get('url', '').strip():
            return jsonify({'success': False, 'error': 'URL manquante'}), 400
        
        print(f"[qBittorrent Test] Création de session...", file=sys.stderr)
        
        # Créer une session authentifiée
        session, base_url, error = create_qbittorrent_session(config)
        if error:
            return jsonify({'success': False, 'error': f"Erreur config: {error}"}), 500
        
        api_url = f"{base_url}/api/v2/app/webuiVersion"
        
        print(f"[qBittorrent Test] URL API: {api_url}", file=sys.stderr)
        print(f"[qBittorrent Test] Requête GET...", file=sys.stderr)
        
        response = session.get(api_url, timeout=5, verify=False)
        
        print(f"[qBittorrent Test] Réponse status: {response.status_code}", file=sys.stderr)
        
        # Si 404 sur webuiVersion, essayer d'autres endpoints
        if response.status_code == 404:
            print(f"[qBittorrent Test] Endpoint webuiVersion non trouvé, essai d'autres endpoints...", file=sys.stderr)
            
            # Essayer /api/v2/app/preferences (indique si auth marche)
            api_url_alt = f"{base_url}/api/v2/app/preferences"
            print(f"[qBittorrent Test] Essai: {api_url_alt}", file=sys.stderr)
            response = session.get(api_url_alt, timeout=5, verify=False)
            print(f"[qBittorrent Test] Réponse: {response.status_code}", file=sys.stderr)
            
            if response.status_code == 200:
                return jsonify({
                    'success': True,
                    'message': f"✅ Connexion réussie à qBittorrent (authentification OK)"
                })
        
        if response.status_code == 200:
            version = response.text.strip()
            return jsonify({
                'success': True,
                'message': f"✅ Connexion réussie à qBittorrent (Web UI Version: {version})"
            })
        elif response.status_code == 403:
            print(f"[qBittorrent Test] 403 reçu, tentative sans authentification...", file=sys.stderr)
            no_auth_session = requests.Session()
            no_auth_response = no_auth_session.get(api_url, timeout=5, verify=False)
            print(f"[qBittorrent Test] Réponse sans auth: {no_auth_response.status_code}", file=sys.stderr)
            
            if no_auth_response.status_code == 200:
                # C'était un problème d'identifiant
                return jsonify({
                    'success': False,
                    'error': "❌ Identifiants incorrects - qBittorrent est accessible mais le login a échoué.\n\nVérifiez:\n- Nom d'utilisateur correct\n- Mot de passe correct\n\nOu, si vous n'avez pas d'authentification:\n- Laissez les champs vides"
                }), 403
            else:
                # qBittorrent demande l'auth ET elle échoue
                return jsonify({
                    'success': False,
                    'error': "❌ Accès refusé (403) - Les identifiants semblent incorrects ou qBittorrent rejette votre authentification"
                }), 403
        elif response.status_code == 401:
            return jsonify({
                'success': False,
                'error': "Non authentifié (401) - Vérifiez vos identifiants"
            }), 401
        else:
            error_detail = response.text[:300] if response.text else 'Pas de détail'
            return jsonify({
                'success': False,
                'error': f"Erreur HTTP {response.status_code}: {error_detail}"
            }), response.status_code
            
    except requests.exceptions.Timeout:
        print(f"[qBittorrent Test] Timeout", file=sys.stderr)
        return jsonify({
            'success': False,
            'error': '⏱️ Timeout - Impossible de se connecter à qBittorrent.\n\nVérifiez:\n- L\'URL est correcte\n- Le port est correct (défaut: 8080)\n- qBittorrent est démarré\n- Le Web UI est activé\n- qBittorrent est accessible sur le réseau'
        }), 500
    except requests.exceptions.ConnectionError as ce:
        print(f"[qBittorrent Test] Erreur de connexion: {str(ce)}", file=sys.stderr)
        return jsonify({
            'success': False,
            'error': f"🔌 Impossible de se connecter à qBittorrent.\n\nVérifiez:\n- L'URL: {config.get('url')}\n- Le port: {config.get('port')}\n- qBittorrent est démarré\n- Le Web UI est activé\n- Pas de pare-feu bloquant\n\nErreur: {str(ce)[:80]}"
        }), 500
    except Exception as e:
        print(f"[qBittorrent Test] Erreur: {str(e)}", file=sys.stderr)
        return jsonify({
            'success': False,
            'error': f"Erreur: {str(e)}"
        }), 500


@qbittorrent_bp.route('/categories_and_tags', methods=['GET'])
@login_required
def get_categories_and_tags():
    """Récupère les catégories et tags disponibles dans qBittorrent"""
    try:
        import sys
        
        config = load_qbittorrent_config()
        
        if not config.get('enabled', False):
            return jsonify({
                'success': False,
                'error': 'qBittorrent n\'est pas activé',
                'categories': [],
                'tags': []
            }), 400
        
        # Créer une session authentifiée
        session, base_url, error = create_qbittorrent_session(config)
        if error:
            return jsonify({
                'success': False,
                'error': f"Erreur config: {error}",
                'categories': [],
                'tags': []
            }), 500
        
        categories = []
        tags = []
        
        # Récupérer les catégories
        try:
            cat_url = f"{base_url}/api/v2/torrents/categories"
            cat_response = session.get(cat_url, timeout=5, verify=False)
            
            if cat_response.status_code == 200:
                cat_data = cat_response.json()
                if isinstance(cat_data, dict):
                    categories = list(cat_data.keys())
                print(f"[qBittorrent] Catégories récupérées: {categories}", file=sys.stderr)
        except Exception as e:
            print(f"[qBittorrent] Erreur récupération catégories: {str(e)}", file=sys.stderr)
        
        # Récupérer les tags
        try:
            tag_url = f"{base_url}/api/v2/tags"
            tag_response = session.get(tag_url, timeout=5, verify=False)
            
            if tag_response.status_code == 200:
                tags = tag_response.json()
                if not isinstance(tags, list):
                    tags = []
                print(f"[qBittorrent] Tags récupérés: {tags}", file=sys.stderr)
        except Exception as e:
            print(f"[qBittorrent] Erreur récupération tags: {str(e)}", file=sys.stderr)
        
        return jsonify({
            'success': True,
            'categories': categories,
            'tags': tags
        })
    
    except Exception as e:
        import sys
        print(f"[qBittorrent] Erreur: {str(e)}", file=sys.stderr)
        return jsonify({
            'success': False,
            'error': f"Erreur: {str(e)}",
            'categories': [],
            'tags': []
        }), 500


def create_qbittorrent_session(config, for_test=False):
    """Crée une session requests authentifiée pour qBittorrent
    
    Args:
        config: Configuration dict avec url, port, username, password
        for_test: Si True, continue même si auth échoue (pour le diagnostic)
    
    Returns:
        Tuple (session, base_url, error_message)
    """
    try:
        import sys
        
        url = config.get('url', '').strip()
        port = config.get('port', 8080)
        
        # Normaliser l'URL
        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'http://' + url
        
        # Construire l'URL de base
        if ':' in url.split('://')[-1]:  # Port déjà présent
            base_url = url
        else:  # Port absent
            base_url = f"{url}:{port}"
        
        session = requests.Session()
        
        username = config.get('username', '').strip()
        
        # Gérer plusieurs cas de mot de passe:
        # 1. password_decrypted: mot de passe en texte clair (du formulaire)
        # 2. password: mot de passe chiffré (de la config sauvegardée)
        password = ''
        if config.get('password_decrypted'):
            # Du formulaire (texte clair)
            password = config.get('password_decrypted')
        elif config.get('password'):
            # De la config sauvegardée (chiffré)
            try:
                password = decrypt(config.get('password'))
            except Exception as decrypt_error:
                print(f"[qBittorrent] Erreur déchiffrement: {str(decrypt_error)}", file=sys.stderr)
                password = ''
        
        if username and password:
            print(f"[qBittorrent] Tentative authentification avec {username}", file=sys.stderr)
            
            # Essayer de se logger d'abord
            login_url = f"{base_url}/api/v2/auth/login"
            try:
                login_response = session.post(login_url, 
                    data={'username': username, 'password': password}, 
                    timeout=5, verify=False)
                
                if login_response.status_code == 200:
                    print(f"[qBittorrent] Login par cookie réussi", file=sys.stderr)
                    return session, base_url, None
                else:
                    print(f"[qBittorrent] Login par cookie échoué ({login_response.status_code})", file=sys.stderr)
                    # Essayer avec Basic Auth
                    session.auth = (username, password)
                    return session, base_url, None
            except Exception as login_error:
                print(f"[qBittorrent] Erreur login: {str(login_error)}", file=sys.stderr)
                # Fallback to Basic Auth
                session.auth = (username, password)
                return session, base_url, None
        
        return session, base_url, None
        
    except Exception as e:
        return None, None, str(e)


@qbittorrent_bp.route('/add', methods=['POST'])
@login_required
def add_torrent():
    """Ajoute un torrent à qBittorrent
    
    Procédure:
    - Les magnet links sont envoyés directement
    - Les URLs de fichiers torrent sont téléchargées puis envoyées comme fichier
    """
    try:
        import sys
        import tempfile
        import shutil
        
        config = load_qbittorrent_config()
        
        if not config.get('enabled', False):
            return jsonify({'success': False, 'error': 'qBittorrent n\'est pas activé'}), 400
        
        data = request.get_json()
        torrent_url = data.get('torrent_url') or data.get('url')
        
        if not torrent_url:
            return jsonify({'success': False, 'error': 'URL du torrent manquante'}), 400
        
        print(f"[qBittorrent Add] Ajout torrent: {torrent_url}", file=sys.stderr)
        
        # Créer une session authentifiée
        session, base_url, error = create_qbittorrent_session(config)
        if error:
            return jsonify({'success': False, 'error': f"Erreur config: {error}"}), 500
        
        # Ajouter le torrent
        api_url = f"{base_url}/api/v2/torrents/add"
        
        print(f"[qBittorrent Add] URL API: {api_url}", file=sys.stderr)
        
        # Préparer le payload
        payload = {'paused': 'false'}  # String 'false' pour qBittorrent API
        files_to_send = None
        torrent_file_path = None
        
        # Ajouter la catégorie si fournie
        category = data.get('category', '').strip()
        if category:
            payload['category'] = category
            print(f"[qBittorrent Add] Catégorie: {category}", file=sys.stderr)
        
        # Ajouter les tags si fournis
        tags = data.get('tags', [])
        if tags:
            if isinstance(tags, str):
                tags = [t.strip() for t in tags.split(',') if t.strip()]
            if tags:
                payload['tags'] = ','.join(tags)
                print(f"[qBittorrent Add] Tags: {payload['tags']}", file=sys.stderr)
        
        # Vérifier si c'est un magnet link
        if torrent_url.startswith('magnet:'):
            # Magnet link - envoyer directement comme URL
            payload['urls'] = torrent_url
            print(f"[qBittorrent Add] Magnet link détecté", file=sys.stderr)
        else:
            # C'est une URL de fichier torrent - télécharger le fichier
            print(f"[qBittorrent Add] URL de fichier torrent détectée - téléchargement en cours...", file=sys.stderr)
            
            try:
                # Télécharger le fichier torrent
                torrent_response = requests.get(torrent_url, timeout=30, verify=False)
                torrent_response.raise_for_status()
                
                # Créer un fichier temporaire
                temp_dir = tempfile.gettempdir()
                torrent_file_path = os.path.join(temp_dir, 'manga_organizer_torrent.torrent')
                
                # Écrire le fichier
                with open(torrent_file_path, 'wb') as f:
                    f.write(torrent_response.content)
                
                print(f"[qBittorrent Add] Torrent téléchargé: {torrent_file_path} ({len(torrent_response.content)} bytes)", file=sys.stderr)
                
                # Préparer le fichier à envoyer en multipart
                files_to_send = {
                    'torrents': ('torrent.torrent', open(torrent_file_path, 'rb'), 'application/x-bittorrent')
                }
                
            except requests.exceptions.Timeout:
                return jsonify({
                    'success': False,
                    'error': 'Timeout lors du téléchargement du torrent'
                }), 500
            except requests.exceptions.ConnectionError:
                return jsonify({
                    'success': False,
                    'error': 'Impossible de télécharger le torrent depuis Prowlarr/ED2K'
                }), 500
            except Exception as e:
                print(f"[qBittorrent Add] Erreur téléchargement torrent: {str(e)}", file=sys.stderr)
                return jsonify({
                    'success': False,
                    'error': f"Erreur lors du téléchargement du torrent: {str(e)}"
                }), 500
        
        # Convertir tous les paramètres en strings pour le form-data
        data_payload = {k: str(v) if not isinstance(v, str) else v for k, v in payload.items()}
        
        print(f"[qBittorrent Add] Payload avant envoi: {data_payload}", file=sys.stderr)
        print(f"[qBittorrent Add] Fichier à envoyer: {files_to_send is not None}", file=sys.stderr)
        
        # Envoyer à qBittorrent
        try:
            if files_to_send:
                # Envoyer le fichier binaire avec les paramètres en data
                print(f"[qBittorrent Add] Envoi du fichier torrent (multipart)", file=sys.stderr)
                response = session.post(api_url, data=data_payload, files=files_to_send, timeout=10, verify=False)
                print(f"[qBittorrent Add] Réponse après file upload: status={response.status_code}, body={response.text[:200] if response.text else 'vide'}", file=sys.stderr)
            else:
                # Envoyer comme URL (magnet)
                print(f"[qBittorrent Add] Envoi du magnet link", file=sys.stderr)
                response = session.post(api_url, data=data_payload, timeout=10, verify=False)
                print(f"[qBittorrent Add] Réponse après URL: status={response.status_code}, body={response.text[:200] if response.text else 'vide'}", file=sys.stderr)
        finally:
            # Fermer et supprimer le fichier temporaire
            if files_to_send and torrent_file_path:
                try:
                    files_to_send['torrents'][1].close()
                    if os.path.exists(torrent_file_path):
                        os.remove(torrent_file_path)
                    print(f"[qBittorrent Add] Fichier temporaire supprimé", file=sys.stderr)
                except Exception as e:
                    print(f"[qBittorrent Add] Erreur suppression fichier temp: {str(e)}", file=sys.stderr)
        
        print(f"[qBittorrent Add] Réponse status final: {response.status_code}", file=sys.stderr)
        
        if response.status_code == 200:
            return jsonify({
                'success': True,
                'message': 'Torrent ajouté à qBittorrent'
            })
        elif response.status_code == 403:
            return jsonify({
                'success': False,
                'error': 'Accès refusé - Vérifiez les identifiants'
            }), 403
        elif response.status_code == 401:
            return jsonify({
                'success': False,
                'error': 'Non authentifié - Vérifiez vos identifiants'
            }), 401
        else:
            error_detail = response.text[:200] if response.text else 'Pas de détail'
            return jsonify({
                'success': False,
                'error': f"Erreur qBittorrent ({response.status_code}): {error_detail}"
            }), response.status_code
    
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Timeout: impossible de se connecter à qBittorrent'
        }), 500
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Impossible de se connecter à qBittorrent'
        }), 500
    except Exception as e:
        import sys
        print(f"[qBittorrent Add] Erreur: {str(e)}", file=sys.stderr)
        return jsonify({
            'success': False,
            'error': f"Erreur: {str(e)}"
        }), 500
