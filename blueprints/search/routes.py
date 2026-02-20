"""
Routes pour la recherche de liens ED2K
"""
from flask import render_template, request, jsonify, current_app
from . import search_bp
import sqlite3
import requests
import json
import os
from encryption import decrypt


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
        
        # Construire le titre de recherche
        search_title = query
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
                    'score': score,
                    'indexer': item.get('indexer', 'Prowlarr'),
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
