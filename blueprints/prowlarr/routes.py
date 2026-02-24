"""
Routes pour l'intégration Prowlarr
"""
from flask import request, jsonify, current_app
from . import prowlarr_bp
import json
import os
import requests
from encryption import encrypt, decrypt


def load_prowlarr_config():
    """Charge la configuration Prowlarr"""
    config_file = current_app.config['PROWLARR_CONFIG_FILE']
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            cfg = json.load(f)
    else:
        cfg = current_app.config['PROWLARR_CONFIG'].copy()

    # Déchiffrer la clé API s'il existe
    api_key = cfg.get('api_key', '')
    if api_key:
        decrypted = decrypt(api_key)
        if decrypted:
            cfg['api_key_decrypted'] = decrypted
    
    return cfg


def save_prowlarr_config(config):
    """Sauvegarde la configuration Prowlarr"""
    config_file = current_app.config['PROWLARR_CONFIG_FILE']
    
    try:
        # Préparer une copie pour la sauvegarde
        config_to_save = config.copy()
        
        # Chiffrer la clé API avant la sauvegarde
        if config_to_save.get('api_key') or config_to_save.get('api_key_decrypted'):
            api_key_to_encrypt = config_to_save.get('api_key_decrypted') or config_to_save.get('api_key')
            if api_key_to_encrypt:
                config_to_save['api_key'] = encrypt(api_key_to_encrypt)
            if 'api_key_decrypted' in config_to_save:
                del config_to_save['api_key_decrypted']
        
        with open(config_file, 'w') as f:
            json.dump(config_to_save, f, indent=4)
        return True
    except Exception as e:
        print(f"Erreur sauvegarde config Prowlarr : {e}")
        return False


@prowlarr_bp.route('/config', methods=['GET', 'POST'])
def prowlarr_config():
    """Configuration Prowlarr"""
    
    if request.method == 'GET':
        config = load_prowlarr_config()
        
        # Masquer la clé API
        return jsonify({
            'enabled': config['enabled'],
            'url': config.get('url', ''),
            'port': config.get('port', 9696),
            'api_key': '****' if config.get('api_key') else ''
        })
    
    else:  # POST
        try:
            new_config = request.get_json()
            config = load_prowlarr_config()

            config['enabled'] = new_config.get('enabled', False)
            config['url'] = new_config.get('url', '').strip()
            config['port'] = new_config.get('port', 9696)

            # Ne change la clé API que si elle n'est pas masquée
            new_api_key = new_config.get('api_key', '')
            if new_api_key and new_api_key != '****':
                config['api_key_decrypted'] = new_api_key

            if save_prowlarr_config(config):
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Erreur de sauvegarde'}), 500

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


@prowlarr_bp.route('/test', methods=['POST', 'GET'])
def test_prowlarr_connection():
    """Teste la connexion à Prowlarr"""
    try:
        config = load_prowlarr_config()
        
        if not config['enabled']:
            return jsonify({'success': False, 'error': 'Integration Prowlarr désactivée'}), 400
        
        url = config.get('url', '').strip()
        api_key = config.get('api_key_decrypted') or decrypt(config.get('api_key', ''))
        
        if not url or not api_key:
            return jsonify({'success': False, 'error': 'URL ou clé API manquante'}), 400
        
        # Normaliser l'URL
        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'http://' + url
        
        # URL de l'API Prowlarr
        test_url = f"{url}/api/v1/system/status"
        headers = {'X-Api-Key': api_key}
        
        response = requests.get(test_url, headers=headers, timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            return jsonify({
                'success': True,
                'message': f"Connexion réussie à Prowlarr v{data.get('version', 'N/A')}"
            })
        else:
            return jsonify({
                'success': False,
                'error': f"Erreur HTTP {response.status_code}: {response.text[:200]}"
            }), response.status_code
            
    except requests.exceptions.Timeout:
        return jsonify({
            'success': False,
            'error': 'Timeout: impossible de se connecter à Prowlarr'
        }), 500
    except requests.exceptions.ConnectionError:
        return jsonify({
            'success': False,
            'error': 'Impossible de se connecter à Prowlarr. Vérifiez l\'URL.'
        }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'error': f"Erreur: {str(e)}"
        }), 500


@prowlarr_bp.route('/search', methods=['GET'])
def search_prowlarr():
    """Recherche sur les indexeurs Prowlarr"""
    
    query = request.args.get('query', '').strip()
    volume = request.args.get('volume', '').strip()
    
    if not query:
        return jsonify({'error': 'Veuillez entrer au moins un titre'}), 400
    
    try:
        config = load_prowlarr_config()
        
        if not config['enabled']:
            return jsonify({
                'error': 'Prowlarr n\'est pas activé. Allez dans la configuration pour l\'activer.'
            }), 400
        
        url = config.get('url', '').strip()
        api_key = config.get('api_key_decrypted') or decrypt(config.get('api_key', ''))
        
        if not url or not api_key:
            return jsonify({
                'error': 'Configuration Prowlarr incomplète. Veuillez la compléter.'
            }), 400
        
        # Normaliser l'URL
        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'http://' + url
        
        # Construire le titre de recherche
        search_title = query
        if volume:
            search_title += f' {volume}'
        
        # Appeler l'API Prowlarr pour chercher les résultats
        api_url = f"{url}/api/v1/search"
        headers = {'X-Api-Key': api_key}
        params = {
            'query': search_title,
            'type': 'search'
        }
        
        # Ajouter les indexeurs sélectionnés s'il y en a
        selected_indexers = config.get('selected_indexers', [])
        if selected_indexers:
            # Passer les indexeurs comme paramètres répétés, pas comme une chaîne CSV
            params['indexerIds'] = selected_indexers
        
        # Ajouter les catégories sélectionnées s'il y en a
        selected_categories_config = config.get('selected_categories', {})
        all_categories = set()
        
        # Collecter toutes les catégories sélectionnées pour tous les indexeurs sélectionnés
        for indexer_id in selected_indexers:
            indexer_id_str = str(indexer_id)
            if indexer_id_str in selected_categories_config:
                all_categories.update(selected_categories_config[indexer_id_str])
        
        if all_categories:
            params['categories'] = list(all_categories)
        
        response = requests.get(api_url, headers=headers, params=params, timeout=30)
        
        if response.status_code != 200:
            # Afficher l'erreur complète pour le debugging
            import sys
            error_details = f"URL: {api_url}, Params: {params}, Response: {response.text[:500]}"
            print(f"[PROWLARR ERROR] {error_details}", file=sys.stderr)
            
            return jsonify({
                'error': f'Erreur Prowlarr ({response.status_code}). Détails: {response.text[:200]}'
            }), response.status_code
        
        raw_data = response.json()
        
        # Formater les résultats avec scoring de pertinence
        results = []
        query_lower = query.lower()
        query_words = query_lower.split()
        
        # La réponse peut être une liste directement ou dans un objet
        data = raw_data if isinstance(raw_data, list) else raw_data.get('results', [])
        
        for item in data:
            title = item.get('title', '').lower()
            
            # Calculer un score de pertinence
            score = 0
            
            # Score élevé si le titre contient exactement la requête
            if query_lower in title:
                score += 100
            
            # Ajouter des points pour chaque mot de la requête trouvé
            for word in query_words:
                if len(word) > 2:  # Ignorer les petits mots
                    if word in title:
                        score += 50
                    elif title.startswith(word):
                        score += 75
            
            # Ne garder que les résultats avec un score minimal
            if score > 0:
                # Extraire le tracker/source depuis infoUrl
                info_url = item.get('infoUrl', '')
                tracker_name = ''
                
                # Essayer d'extraire le nom du domaine depuis infoUrl
                if info_url:
                    from urllib.parse import urlparse
                    try:
                        parsed = urlparse(info_url)
                        tracker_name = parsed.netloc or parsed.path
                        # Nettoyer le tracker name
                        tracker_name = tracker_name.split('?')[0].split('#')[0]
                    except:
                        tracker_name = info_url[:50]  # Fallback si erreur parsing
                
                results.append({
                    'title': item.get('title', 'Sans titre'),
                    'indexer': item.get('indexer', 'Prowlarr'),  # Récupérer l'indexer d'origine
                    'link': item.get('link', ''),
                    'guid': item.get('guid', ''),
                    'download_url': item.get('downloadUrl', ''),
                    'size': item.get('size', 0),
                    'seeders': item.get('seeders', 0),
                    'peers': item.get('peers', 0),
                    'publish_date': item.get('publishDate', ''),
                    'description': item.get('description', ''),
                    'tracker': tracker_name,  # Nom du tracker extrait
                    'info_url': info_url,  # URL source clickable
                    'score': score
                })
        
        # Trier par score décroissant et par seeders si le score est égal
        results.sort(key=lambda x: (-x['score'], -(x.get('seeders', 0) or 0)))
        
        # Retirer le score de la réponse finale
        for result in results:
            del result['score']
        
        return jsonify({'results': results})
        
    except requests.exceptions.Timeout:
        return jsonify({
            'error': 'Timeout: impossible de se connecter à Prowlarr'
        }), 500
    except requests.exceptions.ConnectionError:
        return jsonify({
            'error': 'Impossible de se connecter à Prowlarr. Vérifiez l\'URL.'
        }), 500
    except Exception as e:
        return jsonify({
            'error': f'Erreur de recherche: {str(e)}'
        }), 500


@prowlarr_bp.route('/indexers', methods=['GET', 'POST'])
def prowlarr_indexers():
    """Gère la liste des indexeurs Prowlarr"""
    
    if request.method == 'GET':
        # Récupérer les indexeurs depuis Prowlarr
        try:
            config = load_prowlarr_config()
            
            if not config['enabled']:
                return jsonify({
                    'success': False,
                    'error': 'Prowlarr n\'est pas activé'
                }), 400
            
            url = config.get('url', '').strip()
            api_key = config.get('api_key_decrypted') or decrypt(config.get('api_key', ''))
            
            if not url or not api_key:
                return jsonify({
                    'success': False,
                    'error': 'Configuration Prowlarr incomplète'
                }), 400
            
            # Normaliser l'URL
            if not url.startswith('http://') and not url.startswith('https://'):
                url = 'http://' + url
            
            # Supprime le port s'il est déjà dans l'URL
            if ':' in url and '/api' not in url:
                # C'est une URL avec port
                pass
            else:
                # Ajouter le port si spécifié
                port = config.get('port', '')
                if port and ':' not in url.split('//')[-1]:
                    url = url.rstrip('/') + ':' + str(port)
            
            # Récupérer les indexeurs - essayer plusieurs endpoints possibles
            indexers_url = f"{url}/api/v1/indexer"
            headers = {'X-Api-Key': api_key}
            
            print(f"[DEBUG] Tentative GET: {indexers_url}", file=__import__('sys').stderr)
            response = requests.get(indexers_url, headers=headers, timeout=10)
            print(f"[DEBUG] Réponse status: {response.status_code}", file=__import__('sys').stderr)
            
            if response.status_code != 200:
                # Essayer un autre endpoint
                indexers_url = f"{url}/api/v1/indexers"
                print(f"[DEBUG] Tentative GET: {indexers_url}", file=__import__('sys').stderr)
                response = requests.get(indexers_url, headers=headers, timeout=10)
                print(f"[DEBUG] Réponse status: {response.status_code}", file=__import__('sys').stderr)
            
            if response.status_code != 200:
                return jsonify({
                    'success': False,
                    'error': f'Erreur Prowlarr ({response.status_code}) - Vérifie l\'URL et la clé API de Prowlarr. URLs essayées: {url}/api/v1/indexer et {url}/api/v1/indexers'
                }), response.status_code
            
            indexers_data = response.json()
            
            # Charger la sélection sauvegardée
            saved_config = load_prowlarr_config()
            selected_ids = saved_config.get('selected_indexers', [])
            selected_categories = saved_config.get('selected_categories', {})  # Format: {indexer_id: [cat_ids]}
            
            # Formater les indexeurs
            indexers = []
            if isinstance(indexers_data, list):
                indexers_list = indexers_data
            elif isinstance(indexers_data, dict) and 'indexers' in indexers_data:
                indexers_list = indexers_data['indexers']
            else:
                indexers_list = []
            
            for indexer in indexers_list:
                indexer_id = indexer.get('id')
                selected_cats_for_indexer = selected_categories.get(str(indexer_id), [])
                
                # Extraire les catégories depuis capabilities
                categories = []
                capabilities = indexer.get('capabilities', {})
                if isinstance(capabilities, dict):
                    caps_categories = capabilities.get('categories', [])
                    
                    # Aplatir les catégories et sous-catégories
                    def flatten_categories(cats):
                        result = []
                        for cat in cats:
                            result.append({
                                'id': cat.get('id'),
                                'name': cat.get('name', 'Catégorie')
                            })
                            # Ajouter les sous-catégories
                            for subcat in cat.get('subCategories', []):
                                result.append({
                                    'id': subcat.get('id'),
                                    'name': f"  ↳ {subcat.get('name', 'Sous-catégorie')}"
                                })
                        return result
                    
                    categories = flatten_categories(caps_categories)
                
                indexers.append({
                    'id': indexer_id,
                    'name': indexer.get('name', 'Indexeur'),
                    'language': indexer.get('language'),
                    'selected': indexer_id in selected_ids,
                    'categories': [
                        {
                            'id': cat['id'],
                            'name': cat['name'],
                            'selected': cat['id'] in selected_cats_for_indexer
                        }
                        for cat in categories
                    ]
                })
            
            return jsonify({
                'success': True,
                'indexers': indexers
            })
            
        except requests.exceptions.Timeout:
            return jsonify({
                'success': False,
                'error': 'Timeout: impossible de se connecter à Prowlarr'
            }), 500
        except requests.exceptions.ConnectionError:
            return jsonify({
                'success': False,
                'error': 'Impossible de se connecter à Prowlarr'
            }), 500
        except Exception as e:
            return jsonify({
                'success': False,
                'error': f'Erreur: {str(e)}'
            }), 500
    
    else:  # POST - Sauvegarder la sélection
        try:
            data = request.get_json()
            selected_indexers = data.get('selected_indexers', [])
            selected_categories = data.get('selected_categories', {})  # Format: {indexer_id: [cat_ids]}
            
            config = load_prowlarr_config()
            config['selected_indexers'] = selected_indexers
            config['selected_categories'] = selected_categories
            
            if save_prowlarr_config(config):
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Erreur de sauvegarde'}), 500
                
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500
