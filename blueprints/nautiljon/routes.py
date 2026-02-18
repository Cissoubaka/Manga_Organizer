"""
Routes pour l'intégration Nautiljon
"""
from flask import request, jsonify, current_app
from . import nautiljon_bp
from .scraper import NautiljonScraper, NautiljonDatabase
import sqlite3
import logging
import time

logger = logging.getLogger(__name__)


def get_db_connection():
    """Retourne une connexion à la base de données"""
    conn = sqlite3.connect(current_app.config['DATABASE'], timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


@nautiljon_bp.route('/search', methods=['GET'])
def search_nautiljon():
    """
    Recherche un manga sur Nautiljon
    Query params: ?q=titre_du_manga
    """
    query = request.args.get('q', '').strip()
    
    if not query:
        return jsonify({'error': 'Paramètre q requis'}), 400
    
    try:
        scraper = NautiljonScraper()
        results = scraper.search_manga(query)
        
        return jsonify({
            'success': True,
            'query': query,
            'results': results
        })
    
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@nautiljon_bp.route('/info', methods=['GET'])
def get_nautiljon_info():
    """
    Récupère les infos détaillées d'un manga
    Query params: ?url=nautiljon_url ou ?title=titre_manga
    """
    url = request.args.get('url', '').strip()
    title = request.args.get('title', '').strip()
    
    if not url and not title:
        return jsonify({'error': 'Paramètre url ou title requis'}), 400
    
    try:
        scraper = NautiljonScraper()
        
        if url:
            info = scraper.get_manga_info(url)
        else:
            info = scraper.search_and_get_best_match(title)
        
        if not info:
            return jsonify({
                'success': False,
                'error': 'Manga non trouvé ou impossible à récupérer'
            }), 404
        
        return jsonify({
            'success': True,
            'info': info
        })
    
    except Exception as e:
        logger.error(f"Erreur lors de la récupération des infos: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@nautiljon_bp.route('/search-results/<int:series_id>', methods=['GET'])
def get_search_results_for_series(series_id):
    """
    Cherche tous les résultats pour une série et montre les infos de chaque
    Query params: ?title=override_title (optional pour chercher autre chose)
    """
    query_title = request.args.get('title', '').strip()
    
    try:
        # Récupère la série
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT title FROM series WHERE id = ?', (series_id,))
        series = cursor.fetchone()
        conn.close()
        
        if not series:
            return jsonify({'error': 'Série non trouvée'}), 404
        
        # Utilise le titre fourni ou le titre de la série
        search_title = query_title or series['title']
        
        # Recherche les résultats
        scraper = NautiljonScraper()
        search_results = scraper.search_manga(search_title)
        
        if not search_results:
            return jsonify({
                'success': True,
                'series_id': series_id,
                'series_title': series['title'],
                'search_query': search_title,
                'results': []
            })
        
        # Pour chaque résultat, récupère une prévisualisation
        results_with_info = []
        for idx, result in enumerate(search_results[:10]):  # Limiter à 10 pour ne pas faire trop de requêtes
            try:
                info = scraper.get_manga_info(result['url'])
                if info:
                    result['preview'] = {
                        'total_volumes': info.get('total_volumes'),
                        'french_volumes': info.get('french_volumes'),
                        'editor': info.get('editor'),
                        'mangaka': info.get('mangaka'),
                        'status': info.get('status'),
                        'year_start': info.get('year_start'),
                        'year_end': info.get('year_end')
                    }
                results_with_info.append(result)
            except Exception as e:
                logger.warning(f"Erreur récupération infos pour {result['url']}: {e}")
                results_with_info.append(result)
        
        return jsonify({
            'success': True,
            'series_id': series_id,
            'series_title': series['title'],
            'search_query': search_title,
            'results': results_with_info
        })
    
    except Exception as e:
        logger.error(f"Erreur lors de la recherche: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@nautiljon_bp.route('/enrich/<int:series_id>', methods=['POST'])
def enrich_series(series_id):
    """
    Enrichit une série avec les infos Nautiljon
    Body: {
        "search_by": "title" ou "url",
        "value": "titre_manga" ou "nautiljon_url"
    }
    """
    data = request.get_json()
    
    if not data:
        return jsonify({'error': 'Corps de requête JSON requis'}), 400
    
    search_by = data.get('search_by', 'title').lower()
    value = data.get('value', '').strip()
    
    if not value:
        return jsonify({'error': 'Paramètre value requis'}), 400
    
    if search_by not in ['title', 'url']:
        return jsonify({'error': 'search_by doit être "title" ou "url"'}), 400
    
    try:
        # Récupère la série
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute('SELECT title FROM series WHERE id = ?', (series_id,))
        series = cursor.fetchone()
        conn.close()
        
        if not series:
            return jsonify({'error': 'Série non trouvée'}), 404
        
        logger.info(f"Enrichissement de la série #{series_id} ({series['title']}) avec {search_by}={value}")
        
        # Récupère les infos Nautiljon
        scraper = NautiljonScraper()
        
        if search_by == 'url':
            info = scraper.get_manga_info(value)
        else:
            info = scraper.search_and_get_best_match(value)
        
        if not info:
            logger.warning(f"Aucune info trouvée pour la série #{series_id}")
            return jsonify({
                'success': False,
                'error': 'Impossible de trouver le manga sur Nautiljon'
            }), 404
        
        logger.info(f"Infos trouvées: {info.get('title')} - {info.get('total_volumes')} volumes")
        
        # Sauvegarde les infos
        db_manager = NautiljonDatabase(current_app.config['DATABASE'])
        save_result = db_manager.update_series_nautiljon_info(series_id, info)
        
        if not save_result:
            logger.error(f"Erreur sauvegarde pour la série #{series_id}")
            return jsonify({
                'success': False,
                'error': f'Impossible de sauvegarder les infos pour la série #{series_id}'
            }), 500
        
        logger.info(f"✓ Série #{series_id} enrichie avec succès")
        
        # Récupère les données mises à jour depuis la base
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            cursor.execute('''
                SELECT 
                    id, nautiljon_url, nautiljon_cover_path,
                    nautiljon_total_volumes, nautiljon_french_volumes,
                    nautiljon_editor, nautiljon_status, nautiljon_mangaka,
                    nautiljon_year_start, nautiljon_year_end, nautiljon_updated_at
                FROM series WHERE id = ?
            ''', (series_id,))
            updated_series = cursor.fetchone()
            conn.close()
            
            updated_nautiljon_data = None
            if updated_series:
                updated_nautiljon_data = {
                    'url': updated_series['nautiljon_url'],
                    'cover_path': updated_series['nautiljon_cover_path'],
                    'total_volumes': updated_series['nautiljon_total_volumes'],
                    'french_volumes': updated_series['nautiljon_french_volumes'],
                    'editor': updated_series['nautiljon_editor'],
                    'status': updated_series['nautiljon_status'],
                    'mangaka': updated_series['nautiljon_mangaka'],
                    'year_start': updated_series['nautiljon_year_start'],
                    'year_end': updated_series['nautiljon_year_end'],
                    'updated_at': updated_series['nautiljon_updated_at']
                }
                logger.info(f"Données mises à jour vérifiées pour série #{series_id}: {updated_nautiljon_data['url']}")
        except Exception as e:
            logger.warning(f"Impossible de vérifier les données mises à jour: {e}")
            updated_nautiljon_data = info
        
        return jsonify({
            'success': True,
            'info': info,
            'nautiljon_data': updated_nautiljon_data,
            'message': f"Infos récupérées pour: {info.get('title', series['title'])}"
        })
    
    except Exception as e:
        logger.error(f"Erreur lors de l'enrichissement: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@nautiljon_bp.route('/series/<int:series_id>', methods=['GET'])
def get_series_nautiljon_info(series_id):
    """Récupère les infos Nautiljon d'une série"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                id,
                title,
                nautiljon_url,
                nautiljon_total_volumes,
                nautiljon_french_volumes,
                nautiljon_editor,
                nautiljon_status,
                nautiljon_mangaka,
                nautiljon_year_start,
                nautiljon_year_end,
                nautiljon_updated_at
            FROM series
            WHERE id = ?
        ''', (series_id,))
        
        row = cursor.fetchone()
        conn.close()
        
        if not row:
            return jsonify({'error': 'Série non trouvée'}), 404
        
        return jsonify(dict(row))
    
    except Exception as e:
        logger.error(f"Erreur: {e}")
        return jsonify({'error': str(e)}), 500


@nautiljon_bp.route('/batch-enrich', methods=['POST'])
def batch_enrich_series():
    """
    Enrichit plusieurs séries avec les infos Nautiljon
    Body: {
        "series_ids": [1, 2, 3, ...],
        "search_by": "title" (défaut) ou "url"
    }
    """
    data = request.get_json()
    
    if not data or 'series_ids' not in data:
        return jsonify({'error': 'Parameter series_ids requis'}), 400
    
    series_ids = data.get('series_ids', [])
    search_by = data.get('search_by', 'title').lower()
    
    if not isinstance(series_ids, list):
        return jsonify({'error': 'series_ids doit être une liste'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        scraper = NautiljonScraper()
        db_manager = NautiljonDatabase(current_app.config['DATABASE'])
        
        results = {
            'success': [],
            'failed': []
        }
        
        for series_id in series_ids:
            try:
                # Récupère la série
                cursor.execute('SELECT title FROM series WHERE id = ?', (series_id,))
                series = cursor.fetchone()
                
                if not series:
                    results['failed'].append({
                        'id': series_id,
                        'error': 'Série non trouvée'
                    })
                    continue
                
                # Cherche les infos
                info = scraper.search_and_get_best_match(series['title'])
                
                if info:
                    db_manager.update_series_nautiljon_info(series_id, info)
                    results['success'].append({
                        'id': series_id,
                        'title': series['title'],
                        'info': info
                    })
                else:
                    results['failed'].append({
                        'id': series_id,
                        'title': series['title'],
                        'error': 'Manga non trouvé sur Nautiljon'
                    })
            
            except Exception as e:
                results['failed'].append({
                    'id': series_id,
                    'error': str(e)
                })
            
            # Respecter les délais pour éviter de surcharger Nautiljon
            time.sleep(5)
        
        conn.close()
        
        return jsonify({
            'success': True,
            'total': len(series_ids),
            'succeeded': len(results['success']),
            'failed': len(results['failed']),
            'results': results
        })
    
    except Exception as e:
        logger.error(f"Erreur batch enrich: {e}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500


@nautiljon_bp.route('/diagnostic', methods=['GET'])
def diagnostic():
    """Route de diagnostic pour vérifier l'état de la base de données"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Vérifier le schéma de la table series
        cursor.execute("PRAGMA table_info(series)")
        columns = cursor.fetchall()
        
        nautiljon_columns = {col[1]: col[2] for col in columns if col[1].startswith('nautiljon_')}
        
        # Vérifier une série avec les infos Nautiljon
        cursor.execute('''
            SELECT id, title, nautiljon_url, nautiljon_total_volumes 
            FROM series 
            WHERE nautiljon_url IS NOT NULL 
            LIMIT 1
        ''')
        sample_series = cursor.fetchone()
        
        conn.close()
        
        return jsonify({
            'success': True,
            'nautiljon_columns': nautiljon_columns,
            'columns_count': len(nautiljon_columns),
            'expected_columns': [
                'nautiljon_url',
                'nautiljon_cover_path',
                'nautiljon_total_volumes',
                'nautiljon_french_volumes',
                'nautiljon_editor',
                'nautiljon_status',
                'nautiljon_mangaka',
                'nautiljon_year_start',
                'nautiljon_year_end',
                'nautiljon_updated_at'
            ],
            'sample_data': dict(sample_series) if sample_series else None,
            'status': 'OK' if len(nautiljon_columns) >= 10 else 'MISSING_COLUMNS'
        })
    
    except Exception as e:
        logger.error(f"Diagnostic error: {e}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500
