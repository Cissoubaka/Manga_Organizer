"""
Routes pour la recherche de liens ED2K
"""
from flask import render_template, request, jsonify, current_app
from . import search_bp
import sqlite3
import requests
import json
import os
import re
from encryption import decrypt


def clean_series_name(name):
    """
    Nettoie le nom d'une série pour normaliser les résultats de recherche
    Enlève les ponctuations inutiles, normalise les espaces
    """
    if not name:
        return ""
    
    # Convertir en minuscules pour uniformiser
    cleaned = name.lower().strip()
    
    # Enlever les ponctuations inutiles (virgules, points, apostrophes, deux-points, etc)
    # mais garder les tirets et les parenthèses (elles peuvent être importantes)
    # Utiliser une liste de caractères à enlever
    chars_to_remove = ',;:\'"' + '`'  # virgule, point-virgule, deux-points, guillemets, apostrophe, backtick
    for char in chars_to_remove:
        cleaned = cleaned.replace(char, '')
    
    # Enlever aussi les points
    cleaned = cleaned.replace('.', '')
    
    # Normaliser les espaces multiples en un seul espace
    cleaned = re.sub(r'\s+', ' ', cleaned)
    
    # Enlever les espaces avant/après
    cleaned = cleaned.strip()
    
    return cleaned


def get_db_connection():
    """Retourne une connexion à la base ED2K"""
    conn = sqlite3.connect(current_app.config['DB_FILE'], timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


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


def search_prowlarr(query, volume):
    """Recherche sur les indexeurs Prowlarr
    
    Args:
        query: Titre de la série
        volume: Numéro du volume (optionnel)
    
    Returns:
        Liste des résultats Prowlarr formatés
    """
    try:
        config = load_prowlarr_config()
        
        if not config.get('enabled', False):
            return []
        
        url = config.get('url', '').strip()
        api_key = config.get('api_key_decrypted') or decrypt(config.get('api_key', ''))
        
        if not url or not api_key:
            return []
        
        # Normaliser l'URL
        if not url.startswith('http://') and not url.startswith('https://'):
            url = 'http://' + url
        
        # Nettoyer et construire le titre de recherche
        clean_query = clean_series_name(query)
        search_title = clean_query
        if volume:
            search_title += f' {volume}'
        
        # Appeler l'API Prowlarr
        api_url = f"{url}/api/v1/search"
        headers = {'X-Api-Key': api_key}
        params = {
            'query': search_title,
            'type': 'search'
        }
        
        # Ajouter les indexeurs sélectionnés s'il y en a
        selected_indexers = config.get('selected_indexers', [])
        if selected_indexers:
            params['indexerIds'] = selected_indexers
        
        # Ajouter les catégories sélectionnées
        selected_categories_config = config.get('selected_categories', {})
        all_categories = set()
        for indexer_id in selected_indexers:
            indexer_id_str = str(indexer_id)
            if indexer_id_str in selected_categories_config:
                all_categories.update(selected_categories_config[indexer_id_str])
        
        if all_categories:
            params['categories'] = list(all_categories)
        
        response = requests.get(api_url, headers=headers, params=params, timeout=10)
        
        if response.status_code != 200:
            return []
        
        raw_data = response.json()
        data = raw_data if isinstance(raw_data, list) else raw_data.get('results', [])
        
        results = []
        query_lower = query.lower()
        query_words = query_lower.split()
        
        for item in data:
            title = item.get('title', '').lower()
            
            # Calculer un score de pertinence
            score = 0
            if query_lower in title:
                score += 100
            for word in query_words:
                if len(word) > 2:
                    if word in title:
                        score += 50
                    elif title.startswith(word):
                        score += 75
            
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
                    'source': 'prowlarr',  # Identifier la source
                    'title': item.get('title', 'Sans titre'),
                    'link': item.get('link', ''),
                    'guid': item.get('guid', ''),
                    'download_url': item.get('downloadUrl', ''),
                    'size': item.get('size', 0),
                    'seeders': item.get('seeders', 0),
                    'peers': item.get('peers', 0),
                    'publish_date': item.get('publishDate', ''),
                    'description': item.get('description', ''),
                    'indexer': item.get('indexer', 'Prowlarr'),
                    'tracker': tracker_name,  # Nom du tracker extrait
                    'info_url': info_url,  # URL source clickable
                    'score': score,
                })
        
        results.sort(key=lambda x: (-x['score'], -(x.get('seeders', 0) or 0)))
        for result in results:
            del result['score']
        
        return results
        
    except Exception as e:
        print(f"Erreur recherche Prowlarr: {str(e)}")
        return []


@search_bp.route('/search')
def search_page():
    """Page de recherche ED2K"""
    
    # Récupérer les catégories et statistiques
    conn = get_db_connection()
    cursor = conn.cursor()
    
    # Vérifier si la table ed2k_links existe
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ed2k_links'")
    table_exists = cursor.fetchone() is not None
    
    categories = []
    total_links = 0
    total_threads = 0
    
    if table_exists:
        cursor.execute('SELECT DISTINCT forum_category FROM ed2k_links ORDER BY forum_category')
        categories = [row[0] for row in cursor.fetchall()]
        
        cursor.execute('SELECT COUNT(*) FROM ed2k_links')
        total_links = cursor.fetchone()[0]
        
        cursor.execute('SELECT COUNT(DISTINCT thread_id) FROM ed2k_links')
        total_threads = cursor.fetchone()[0]
    
    conn.close()
    
    return render_template('search.html', 
                          categories=categories, 
                          total_links=total_links,
                          total_threads=total_threads,
                          database_empty=not table_exists)


@search_bp.route('/discover')
def discover_page():
    """Page de découverte et ajout de séries"""
    return render_template('discover.html')


@search_bp.route('/api/search')
def search_ed2k():
    """Recherche de liens ED2K et Prowlarr"""
    query = request.args.get('query', '').strip()
    volume = request.args.get('volume', '').strip()
    category = request.args.get('category', '').strip()

    try:
        all_results = []
        
        # ===== RECHERCHE ED2K =====
        try:
            conn = sqlite3.connect(current_app.config['DB_FILE'], timeout=30.0)
            cursor = conn.cursor()
            
            # Vérifier si la table ed2k_links existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ed2k_links'")
            if cursor.fetchone() is not None:
                sql = '''
                    SELECT thread_id, thread_title, thread_url, forum_category, cover_image,
                           link, filename, filesize, volume, description
                    FROM ed2k_links
                    WHERE 1=1
                '''
                params = []

                if query:
                    sql += ' AND (thread_title LIKE ? OR filename LIKE ?)'
                    search_term = f'%{query}%'
                    params.extend([search_term, search_term])

                if volume:
                    sql += ' AND volume = ?'
                    params.append(int(volume))

                if category:
                    sql += ' AND forum_category = ?'
                    params.append(category)

                sql += ' ORDER BY thread_id, volume'

                cursor.execute(sql, params)
                results = cursor.fetchall()

                for row in results:
                    all_results.append({
                        'source': 'ebdz',  # Identifier la source
                        'thread_id': row[0],
                        'thread_title': row[1],
                        'thread_url': row[2],
                        'forum_category': row[3],
                        'cover_image': row[4],
                        'link': row[5],
                        'filename': row[6],
                        'filesize': row[7],
                        'volume': row[8],
                        'description': row[9]
                    })

            conn.close()
        except Exception as e:
            print(f"Erreur recherche ED2K: {str(e)}")
        
        # ===== RECHERCHE PROWLARR =====
        if query:  # Prowlarr nécessite au minimum une requête
            prowlarr_results = search_prowlarr(query, volume)
            all_results.extend(prowlarr_results)
        
        return jsonify({'results': all_results})

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@search_bp.route('/api/search/ebdz')
def search_ebdz_api():
    """API pour rechercher dans la base ED2K (pour la page discover)"""
    query = request.args.get('q', '').strip()
    volume = request.args.get('volume', '').strip()
    category = request.args.get('category', '').strip()

    if not query:
        return jsonify({
            'success': False,
            'error': 'Paramètre q requis'
        }), 400

    try:
        results = []
        
        conn = sqlite3.connect(current_app.config['DB_FILE'], timeout=30.0)
        cursor = conn.cursor()
        
        # Vérifier si la table ed2k_links existe
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ed2k_links'")
        if cursor.fetchone() is not None:
            # Nettoyer la requête pour une meilleure correspondance
            clean_query = clean_series_name(query)
            
            sql = '''
                SELECT DISTINCT thread_id, thread_title, thread_url, forum_category, 
                       link, filename, filesize, volume
                FROM ed2k_links
                WHERE 1=1
            '''
            params = []

            # Recherche avec la version nettoyée ET la version originale
            # Cela permet de trouver des résultats même si les données stockées diffèrent légèrement
            sql += ' AND (thread_title LIKE ? OR filename LIKE ? OR thread_title LIKE ? OR filename LIKE ?)'
            search_term_clean = f'%{clean_query}%'
            search_term_orig = f'%{query}%'
            params.extend([search_term_clean, search_term_clean, search_term_orig, search_term_orig])

            if volume:
                try:
                    sql += ' AND volume = ?'
                    params.append(int(volume))
                except ValueError:
                    pass

            if category:
                sql += ' AND forum_category = ?'
                params.append(category)

            sql += ' ORDER BY volume DESC, thread_id DESC LIMIT 50'

            cursor.execute(sql, params)
            rows = cursor.fetchall()

            for row in rows:
                results.append({
                    'thread_id': row[0],
                    'title': row[1],
                    'forum': row[3],
                    'filename': row[5],
                    'size': row[6],
                    'volume': row[7],
                    'ed2k_link': row[4]
                })

        conn.close()
        
        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        print(f"Erreur recherche EBDZ: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@search_bp.route('/api/search/prowlarr')
def search_prowlarr_api():
    """API pour rechercher dans Prowlarr (pour la page discover)"""
    query = request.args.get('q', '').strip()
    volume = request.args.get('volume', '').strip()

    if not query:
        return jsonify({
            'success': False,
            'error': 'Paramètre q requis'
        }), 400

    try:
        results = search_prowlarr(query, volume)
        
        return jsonify({
            'success': True,
            'results': results
        })

    except Exception as e:
        print(f"Erreur recherche Prowlarr: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
