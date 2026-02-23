"""
Routes pour le scraper ebdz.net
"""
from flask import request, jsonify, current_app
from . import ebdz_bp
import json
import os
import sqlite3
from encryption import encrypt, decrypt, ensure_encryption_key


def load_ebdz_config():
    """Charge la configuration ebdz"""
    config_file = current_app.config['EBDZ_CONFIG_FILE']
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            config = json.load(f)
            # Déchiffrer le mot de passe s'il est chiffré
            if config.get('password'):
                config['password_decrypted'] = decrypt(config.get('password'))
            return config
    
    default_config = current_app.config['EBDZ_CONFIG'].copy()
    if default_config.get('password'):
        default_config['password_decrypted'] = decrypt(default_config.get('password'))
    return default_config


def save_ebdz_config(config):
    """Sauvegarde la configuration ebdz"""
    config_file = current_app.config['EBDZ_CONFIG_FILE']
    
    try:
        # Préparer une copie pour la sauvegarde
        config_to_save = config.copy()
        
        # Chiffrer le mot de passe avant la sauvegarde
        if config_to_save.get('password'):
            # Enlever le flag _decrypted temporaire aux fins de sauvegarde
            if 'password_decrypted' in config_to_save:
                # Utiliser le mot de passe déchiffré pour le chiffrer à nouveau
                config_to_save['password'] = encrypt(config_to_save['password_decrypted'])
                del config_to_save['password_decrypted']
            else:
                # Le mot de passe est déjà en clair, le chiffrer
                config_to_save['password'] = encrypt(config_to_save['password'])
        
        with open(config_file, 'w') as f:
            json.dump(config_to_save, f, indent=4)
        return True
    except Exception as e:
        print(f"Erreur sauvegarde config : {e}")
        return False


@ebdz_bp.route('/config', methods=['GET', 'POST'])
def ebdz_config():
    """Configuration ebdz.net"""
    
    if request.method == 'GET':
        config = load_ebdz_config()
        
        return jsonify({
            'username': config.get('username', ''),
            'password': '****' if config.get('password') else '',
            'forums': config.get('forums', [])
        })
    
    else:  # POST
        try:
            data = request.get_json()
            config = load_ebdz_config()
            
            config['username'] = data.get('username', '').strip()
            
            # Ne met à jour le mot de passe que s'il n'est pas masqué
            new_password = data.get('password', '')
            if new_password and new_password != '****':
                config['password_decrypted'] = new_password
            
            # Validation des forums
            forums = []
            for f in data.get('forums', []):
                fid = f.get('fid')
                if fid is not None:
                    forums.append({
                        'fid': int(fid),
                        'category': f.get('category', '').strip() or f'Forum {fid}',
                        'max_pages': int(f['max_pages']) if f.get('max_pages') else None
                    })
            
            config['forums'] = forums
            
            if save_ebdz_config(config):
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Erreur de sauvegarde'}), 500
        
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


@ebdz_bp.route('/scrape', methods=['POST'])
def scrape():
    """Lance le scraper ebdz.net"""
    
    try:
        config = load_ebdz_config()
        username = config.get('username', '')
        password = config.get('password_decrypted', '')  # Utiliser le mot de passe déchiffré
        all_forums = config.get('forums', [])
        
        if not username or not password:
            return jsonify({'success': False, 'error': 'Identifiants non configurés'}), 400
        
        if not all_forums:
            return jsonify({'success': False, 'error': 'Aucun forum configuré'}), 400
        
        # Filtrer par les fid envoyés depuis le front
        data = request.get_json(silent=True) or {}
        requested_fids = data.get('fids', [])
        
        if requested_fids:
            forums = [f for f in all_forums if f.get('fid') in requested_fids]
            if not forums:
                return jsonify({'success': False, 'error': 'Aucun forum correspondant'}), 400
        else:
            forums = all_forums
        
        # Import dynamique du scraper
        from .scraper import MyBBScraper
        
        total_links = 0
        forums_scraped = 0
        
        for forum_cfg in forums:
            fid = forum_cfg['fid']
            category = forum_cfg['category']
            max_pages = forum_cfg.get('max_pages')
            
            forum_url = f"https://ebdz.net/forum/forumdisplay.php?fid={fid}"
            
            print(f"\n� Scraping forum fid={fid} catégorie='{category}'...")
            
            scraper = MyBBScraper(
                base_url=forum_url,
                db_file=current_app.config['DB_FILE'],
                username=username,
                password=password,
                forum_category=category
            )
            
            scraper.run(max_pages=max_pages)
            forums_scraped += 1
            
            # Compter les liens
            conn = sqlite3.connect(current_app.config['DB_FILE'])
            cursor = conn.cursor()
            cursor.execute('SELECT COUNT(*) FROM ed2k_links WHERE forum_category = ?', (category,))
            total_links += cursor.fetchone()[0]
            conn.close()
        
        return jsonify({
            'success': True,
            'forums_scraped': forums_scraped,
            'total_links': total_links
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500


@ebdz_bp.route('/auto-scrape/config', methods=['GET', 'POST'])
def auto_scrape_config():
    """Configuration du scraping automatique EBDZ"""
    
    if request.method == 'GET':
        config = load_ebdz_config()
        return jsonify({
            'auto_scrape_enabled': config.get('auto_scrape_enabled', False),
            'auto_scrape_interval': config.get('auto_scrape_interval', 60),
            'auto_scrape_interval_unit': config.get('auto_scrape_interval_unit', 'minutes')
        })
    
    else:  # POST
        try:
            data = request.get_json()
            config = load_ebdz_config()
            
            # Mettre à jour la configuration
            enabled = data.get('auto_scrape_enabled', False)
            interval = int(data.get('auto_scrape_interval', 60))
            interval_unit = data.get('auto_scrape_interval_unit', 'minutes')
            
            if interval < 1:
                return jsonify({'success': False, 'error': 'L\'intervalle doit être >= 1'}), 400
            
            if interval_unit not in ['minutes', 'hours', 'days']:
                return jsonify({'success': False, 'error': 'Unité de temps invalide'}), 400
            
            config['auto_scrape_enabled'] = enabled
            config['auto_scrape_interval'] = interval
            config['auto_scrape_interval_unit'] = interval_unit
            
            if save_ebdz_config(config):
                # Gérer le scheduler
                if enabled:
                    from .scheduler import ebdz_scheduler
                    ebdz_scheduler.add_job(interval, interval_unit)
                else:
                    from .scheduler import ebdz_scheduler
                    ebdz_scheduler.remove_job()
                
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': 'Erreur de sauvegarde'}), 500
        
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


@ebdz_bp.route('/auto-scrape/status', methods=['GET'])
def auto_scrape_status():
    """Récupérer le statut du scraping automatique"""
    try:
        from .scheduler import ebdz_scheduler
        
        is_running = False
        next_run = None
        
        if ebdz_scheduler.scheduler and ebdz_scheduler.scheduler.running:
            is_running = True
            job = ebdz_scheduler.scheduler.get_job(ebdz_scheduler.job_id)
            if job:
                next_run = job.next_run_time.isoformat() if job.next_run_time else None
        
        return jsonify({
            'success': True,
            'is_running': is_running,
            'next_run': next_run
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500