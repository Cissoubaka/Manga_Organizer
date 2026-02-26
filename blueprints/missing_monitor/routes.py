"""
Routes API pour la surveillance des volumes manquants
"""
from flask import request, jsonify, current_app
from . import missing_monitor_bp
import sqlite3
import json
from datetime import datetime
from .detector import MissingVolumeDetector
from .searcher import MissingVolumeSearcher
from .downloader import MissingVolumeDownloader
from .scheduler import MissingVolumeScheduler, monitor_manager


def get_db_connection():
    """Retourne une connexion à la base de données"""
    conn = sqlite3.connect(current_app.config['DATABASE'], timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


def get_detector():
    """Crée une instance du détecteur"""
    return MissingVolumeDetector()


def get_searcher():
    """Crée une instance du chercheur"""
    return MissingVolumeSearcher()


def get_downloader():
    """Crée une instance du downloader"""
    return MissingVolumeDownloader()


def load_monitor_config():
    """Charge la configuration de surveillance"""
    config_file = current_app.config.get('MISSING_MONITOR_CONFIG_FILE', 'data/missing_monitor_config.json')
    
    if not config_file:
        return get_default_monitor_config()
    
    try:
        with open(config_file, 'r') as f:
            return json.load(f)
    except:
        return get_default_monitor_config()


def get_default_monitor_config():
    """Configuration par défaut"""
    return {
        'enabled': False,
        'auto_check_enabled': False,
        'auto_check_interval': 60,
        'auto_check_interval_unit': 'minutes',
        'monitor_missing_volumes': {
            'enabled': True,
            'search_enabled': True,
            'auto_download_enabled': False,
            'search_sources': ['ebdz', 'prowlarr'],
            'check_interval': 12,  # Par défaut 12 heures
            'check_interval_unit': 'hours'  # Par défaut en heures
        },
        'monitor_new_volumes': {
            'enabled': False,
            'search_enabled': True,
            'auto_download_enabled': False,
            'check_nautiljon_updates': True,
            'search_sources': ['ebdz', 'prowlarr'],
            'check_interval': 6,  # Par défaut 6 heures
            'check_interval_unit': 'hours'  # Par défaut en heures
        },
        'search_sources': ['ebdz', 'prowlarr'],
        'auto_download_enabled': False,
        'preferred_client': 'qbittorrent'
    }


def save_monitor_config(config):
    """Sauvegarde la configuration"""
    config_file = current_app.config.get('MISSING_MONITOR_CONFIG_FILE', 'data/missing_monitor_config.json')
    
    if not config_file:
        return False
    
    try:
        import os
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Erreur sauvegarde config: {e}")
        return False


# ========== ROUTES ==========

# ========== ROUTES BIBLIOTHEQUES ==========

@missing_monitor_bp.route('/libraries', methods=['GET'])
def get_libraries():
    """Liste les bibliothèques avec leur statut de surveillance"""
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Récupérer toutes les bibliothèques
        cursor.execute('''
            SELECT 
                l.id, 
                l.name, 
                COUNT(s.id) as total_series,
                COALESCE(mvl.enabled, 0) as monitored
            FROM libraries l
            LEFT JOIN series s ON l.id = s.library_id
            LEFT JOIN missing_volume_library mvl ON l.id = mvl.library_id
            GROUP BY l.id
            ORDER BY l.name
        ''')
        
        libraries = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'count': len(libraries),
            'libraries': libraries
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@missing_monitor_bp.route('/libraries/<int:library_id>/monitor', methods=['POST'])
def configure_library_monitor(library_id):
    """Configure la surveillance pour une bibliothèque"""
    
    try:
        data = request.get_json()
        enabled = data.get('enabled', True)
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Vérifier que la bibliothèque existe
        cursor.execute('SELECT id FROM libraries WHERE id = ?', (library_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Bibliothèque introuvable'}), 404
        
        # Vérifier si un monitor existe déjà
        cursor.execute('SELECT id FROM missing_volume_library WHERE library_id = ?', (library_id,))
        existing = cursor.fetchone()
        
        if existing:
            # Mettre à jour
            cursor.execute('''
                UPDATE missing_volume_library
                SET enabled = ?
                WHERE library_id = ?
            ''', (1 if enabled else 0, library_id))
        else:
            # Créer
            cursor.execute('''
                INSERT INTO missing_volume_library (library_id, enabled, created_at)
                VALUES (?, ?, CURRENT_TIMESTAMP)
            ''', (library_id, 1 if enabled else 0))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@missing_monitor_bp.route('/libraries/<int:library_id>/series', methods=['GET'])
def get_library_series(library_id):
    """Récupère les séries d'une bibliothèque"""
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Vérifier que la bibliothèque existe
        cursor.execute('SELECT id FROM libraries WHERE id = ?', (library_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Bibliothèque introuvable'}), 404
        
        # Récupérer les séries de cette bibliothèque
        cursor.execute('''
            SELECT 
                s.id,
                s.title,
                s.total_volumes as total_local,
                s.missing_volumes,
                s.tags,
                COALESCE(s.nautiljon_status, 'Inconnu') as nautiljon_status,
                COALESCE(mm.enabled, 0) as enabled,
                mm.search_sources,
                COALESCE(s.nautiljon_total_volumes, 0) as nautiljon_total_volumes
            FROM series s
            LEFT JOIN missing_volume_monitor mm ON s.id = mm.series_id
            WHERE s.library_id = ?
            ORDER BY s.title
        ''', (library_id,))
        
        series = [dict(row) for row in cursor.fetchall()]
        conn.close()
        
        return jsonify({
            'success': True,
            'count': len(series),
            'series': series
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@missing_monitor_bp.route('/config', methods=['GET', 'POST'])
def monitor_config():
    """Configuration générale de la surveillance"""
    
    if request.method == 'GET':
        config = load_monitor_config()
        return jsonify(config)
    
    else:  # POST
        try:
            data = request.get_json()
            config = load_monitor_config()
            
            # Mettre à jour les paramètres généraux
            config['enabled'] = data.get('enabled', False)
            config['auto_check_enabled'] = data.get('auto_check_enabled', False)
            config['auto_check_interval'] = int(data.get('auto_check_interval', 60))
            config['auto_check_interval_unit'] = data.get('auto_check_interval_unit', 'minutes')
            config['search_sources'] = data.get('search_sources', ['ebdz', 'prowlarr'])
            config['preferred_client'] = data.get('preferred_client', 'qbittorrent')
            
            # Mettre à jour la configuration des volumes manquants
            missing_config = data.get('monitor_missing_volumes', {})
            config['monitor_missing_volumes'] = {
                'enabled': missing_config.get('enabled', True),
                'search_enabled': missing_config.get('search_enabled', True),
                'auto_download_enabled': missing_config.get('auto_download_enabled', False),
                'search_sources': missing_config.get('search_sources', ['ebdz', 'prowlarr']),
                'check_interval': int(missing_config.get('check_interval', 12)),
                'check_interval_unit': missing_config.get('check_interval_unit', 'hours')
            }
            
            # Mettre à jour la configuration des nouveaux volumes
            new_config = data.get('monitor_new_volumes', {})
            config['monitor_new_volumes'] = {
                'enabled': new_config.get('enabled', False),
                'search_enabled': new_config.get('search_enabled', True),
                'auto_download_enabled': new_config.get('auto_download_enabled', False),
                'check_nautiljon_updates': new_config.get('check_nautiljon_updates', True),
                'search_sources': new_config.get('search_sources', ['ebdz', 'prowlarr']),
                'check_interval': int(new_config.get('check_interval', 6)),
                'check_interval_unit': new_config.get('check_interval_unit', 'hours')
            }
            
            if save_monitor_config(config):
                # Mettre à jour le scheduler avec les jobs séparés
                scheduler = MissingVolumeScheduler()
                
                # Gérer le job pour les volumes manquants
                if config.get('monitor_missing_volumes', {}).get('enabled', True):
                    missing_interval = config['monitor_missing_volumes'].get('check_interval', 12)
                    missing_unit = config['monitor_missing_volumes'].get('check_interval_unit', 'hours')
                    scheduler.add_missing_volume_job(missing_interval, missing_unit)
                else:
                    scheduler.remove_missing_volume_job()
                
                # Gérer le job pour les nouveaux volumes
                if config.get('monitor_new_volumes', {}).get('enabled', False):
                    new_interval = config['monitor_new_volumes'].get('check_interval', 6)
                    new_unit = config['monitor_new_volumes'].get('check_interval_unit', 'hours')
                    scheduler.add_new_volume_job(new_interval, new_unit)
                else:
                    scheduler.remove_new_volume_job()
                
                # Mantenir la compatibilité avec l'ancien paramètre auto_check_enabled (optionnel)
                if config.get('auto_check_enabled'):
                    scheduler.add_monitor_job(
                        config['auto_check_interval'],
                        config['auto_check_interval_unit']
                    )
                else:
                    scheduler.remove_monitor_job()
                
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Erreur sauvegarde'}), 500
        
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


@missing_monitor_bp.route('/series', methods=['GET'])
def get_monitored_series():
    """Liste les séries en surveillance"""
    
    try:
        status = request.args.get('status', 'all')  # 'all', 'incomplete', 'missing'
        
        detector = get_detector()
        series = detector.get_series_by_status(status)
        
        return jsonify({
            'success': True,
            'count': len(series),
            'series': series
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@missing_monitor_bp.route('/series/<int:series_id>/monitor', methods=['POST'])
def configure_series_monitor(series_id):
    """Configure la surveillance pour une série spécifique"""
    
    try:
        data = request.get_json()
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Vérifier que la série existe
        cursor.execute('SELECT id FROM series WHERE id = ?', (series_id,))
        if not cursor.fetchone():
            conn.close()
            return jsonify({'success': False, 'error': 'Série introuvable'}), 404
        
        # Vérifier si un monitor existe déjà
        cursor.execute('SELECT id FROM missing_volume_monitor WHERE series_id = ?', (series_id,))
        existing = cursor.fetchone()
        
        enabled = data.get('enabled', True)
        search_sources = json.dumps(data.get('search_sources', 
                                            ['ebdz', 'prowlarr', 'nautiljon']))
        auto_download = data.get('auto_download_enabled', False)
        
        if existing:
            # Mettre à jour
            cursor.execute('''
                UPDATE missing_volume_monitor
                SET enabled = ?, search_sources = ?, auto_download_enabled = ?
                WHERE series_id = ?
            ''', (enabled, search_sources, auto_download, series_id))
        else:
            # Créer
            cursor.execute('''
                INSERT INTO missing_volume_monitor
                (series_id, enabled, search_sources, auto_download_enabled, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (series_id, enabled, search_sources, auto_download))
        
        conn.commit()
        conn.close()
        
        return jsonify({'success': True})
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@missing_monitor_bp.route('/search', methods=['POST'])
def search_volume():
    """Recherche un volume spécifique"""
    
    try:
        data = request.get_json()
        title = data.get('title', '').strip()
        volume_num = int(data.get('volume_num', 0))
        sources = data.get('sources')  # None = tous
        
        if not title or volume_num <= 0:
            return jsonify({'success': False, 'error': 'Paramètres invalides'}), 400
        
        searcher = get_searcher()
        results = searcher.search_for_volume(title, volume_num, sources)
        
        return jsonify({
            'success': True,
            'query': f"{title} Vol {volume_num}",
            'results_count': len(results),
            'results': results[:20]  # Limiter à 20 résultats
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@missing_monitor_bp.route('/download', methods=['POST'])
def trigger_download():
    """Envoie un téléchargement au client"""
    
    try:
        data = request.get_json()
        link = data.get('link', '').strip()
        title = data.get('title', '').strip()
        volume_num = int(data.get('volume_num', 0))
        client = data.get('client')  # None = auto-détection
        
        if not link or not title or volume_num <= 0:
            return jsonify({'success': False, 'error': 'Paramètres invalides'}), 400
        
        downloader = get_downloader()
        success, message = downloader.send_torrent_download(
            link, title, volume_num, client
        )
        
        return jsonify({
            'success': success,
            'message': message,
            'title': title,
            'volume': volume_num
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@missing_monitor_bp.route('/run-check', methods=['POST'])
def run_monitor_check():
    """Exécute une vérification manuelle des volumes manquants"""
    
    try:
        data = request.get_json() or {}
        
        search_enabled = data.get('search_enabled', True)
        download_enabled = data.get('auto_download', False)
        
        # Initialiser le gestionnaire
        monitor_manager.initialize()
        
        # Exécuter la vérification
        stats = monitor_manager.run_missing_volume_check(
            search_enabled=search_enabled,
            download_enabled=download_enabled
        )
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@missing_monitor_bp.route('/run-check-new-volumes', methods=['POST'])
def run_new_volume_check():
    """Exécute une vérification manuelle des nouveaux volumes"""
    
    try:
        data = request.get_json() or {}
        
        auto_download = data.get('auto_download', False)
        
        # Initialiser le gestionnaire
        monitor_manager.initialize()
        
        # Exécuter la vérification
        stats = monitor_manager.run_new_volume_check(
            auto_download_enabled=auto_download
        )
        
        return jsonify({
            'success': True,
            'stats': stats
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@missing_monitor_bp.route('/stats', methods=['GET'])
def get_monitor_stats():
    """Récupère les statistiques de surveillance"""
    
    try:
        detector = get_detector()
        downloader = get_downloader()
        total_series = detector.get_monitored_series_count()
        total_missing = detector.get_total_missing_volumes()
        downloads = downloader.get_download_history(limit=10)
        
        return jsonify({
            'success': True,
            'monitored_series': total_series,
            'total_missing_volumes': total_missing,
            'recent_downloads': downloads
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@missing_monitor_bp.route('/performance', methods=['GET'])
def get_performance_stats():
    """Récupère les statistiques de performance du monitoring"""
    
    try:
        searcher = get_searcher()
        
        # Récupérer les stats du cache et du throttler
        cache_stats = searcher._cache.stats() if hasattr(searcher, '_cache') else {}
        
        # Info sur le throttler
        throttler_info = {
            'requests_per_minute': searcher._throttler.requests_per_minute if hasattr(searcher, '_throttler') else 30,
            'min_interval_seconds': searcher._throttler.min_interval if hasattr(searcher, '_throttler') else 2.0
        }
        
        return jsonify({
            'success': True,
            'cache': cache_stats,
            'throttler': throttler_info,
            'description': {
                'cache': 'Les résultats de recherche sont mis en cache pour éviter les requêtes répétées',
                'throttler': 'La fréquence des requêtes Prowlarr est limitée pour éviter les surcharges'
            }
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@missing_monitor_bp.route('/history', methods=['GET'])
def get_download_history():
    """Récupère l'historique des téléchargements"""
    
    try:
        limit = request.args.get('limit', 50, type=int)
        
        downloader = get_downloader()
        history = downloader.get_download_history(limit=limit)
        
        return jsonify({
            'success': True,
            'count': len(history),
            'history': history
        })
    
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
