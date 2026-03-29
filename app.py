"""
Point d'entrée principal de l'application Manga Manager
"""
from flask import Flask, send_from_directory, request, jsonify, redirect
from dotenv import load_dotenv
import os
import sys

# Charger les variables d'environnement depuis .env (dans le répertoire de l'app)
env_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), '.env')
load_dotenv(env_path)

from config import config
from encryption import ensure_encryption_key

def create_app(config_name='default'):
    """Factory pour créer l'application Flask"""
    
    # Initialiser la clé de chiffrement
    ensure_encryption_key()
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialiser l'app (créer les répertoires)
    config[config_name].init_app(app)
    
    # 🔐 SÉCURITÉ: Initialiser la protection CSRF avec Flask-WTF
    from flask_wtf.csrf import CSRFProtect
    csrf = CSRFProtect(app)
    print("✓ Protection CSRF prête (désactivée par défaut pour les APIs)")
    
    # 🔐 SÉCURITÉ: Initialiser CORS avec restrictions
    from flask_cors import CORS
    CORS(app, 
         origins=['http://localhost:5000', 'http://localhost:3000', 'http://127.0.0.1:5000'],
         methods=['GET', 'POST', 'PUT', 'DELETE', 'OPTIONS'],
         allow_headers=['Content-Type', 'Authorization'],
         supports_credentials=True,
         max_age=3600)
    print("✓ CORS configuré")
    
    # 🔐 SÉCURITÉ: Ajouter les en-têtes HTTP de sécurité
    @app.after_request
    def set_security_headers(response):
        # Empêcher le clickjacking
        response.headers['X-Frame-Options'] = 'SAMEORIGIN'
        # Empêcher le MIME sniffing
        response.headers['X-Content-Type-Options'] = 'nosniff'
        # Empêcher XSS (si le navigateur détecte une attaque)
        response.headers['X-XSS-Protection'] = '1; mode=block'
        # Content Security Policy (restrictif)
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline'; "
            "img-src 'self' data: https:; "
            "font-src 'self'; "
            "connect-src 'self'; "
            "frame-ancestors 'self'"
        )
        # HSTS (HTTPS only) - utilisé uniquement en production
        if os.environ.get('FLASK_ENV') == 'production':
            response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
        return response
    
    print("✓ En-têtes de sécurité HTTP activés")
    
    # 🔐 SÉCURITÉ: INITIALISER Flask-Login AVANT les blueprints  
    from auth import login_manager, auth_bp, _create_default_user
    login_manager.init_app(app)
    
    # 🔐 SÉCURITÉ: Handler pour les requêtes non-authentifiées (retourner 401 JSON pour API)
    @login_manager.unauthorized_handler
    def unauthorized():
        """Retourner 401 pour les API requests au lieu de rediriger"""
        if request.path.startswith('/api/') or request.path.startswith('/test-protected'):
            return jsonify({'success': False, 'error': 'Authentification requise'}), 401
        # Pour les pages HTML, rediriger vers la login page
        return redirect('/auth/login?next=' + request.url)
    
    print("✓ Authentification Flask-Login initialisée")
    
    # ⚡ PERFORMANCE: Initialiser Rate Limiting et Caching
    from middleware import init_rate_limiter, cache_manager
    limiter = init_rate_limiter(app)
    cache_manager.init_app(app)
    print("✓ Performance middleware initialisé (rate limiting + caching)")
    
    # Route pour servir les couvertures
    @app.route('/covers/<path:filename>')
    def serve_cover(filename):
        return send_from_directory(app.config['COVERS_DIR'], filename)
    
    # Enregistrer les blueprints APRÈS que login_manager soit initialisé
    from blueprints.library import library_bp
    from blueprints.search import search_bp
    from blueprints.emule import emule_bp
    from blueprints.ebdz import ebdz_bp
    from blueprints.prowlarr import prowlarr_bp
    from blueprints.nautiljon import nautiljon_bp
    from blueprints.settings import settings_bp
    from blueprints.qbittorrent import qbittorrent_bp
    from blueprints.missing_monitor import missing_monitor_bp
    from blueprints.audit import audit_bp
    
    app.register_blueprint(library_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(emule_bp, url_prefix='/api/emule')
    app.register_blueprint(ebdz_bp, url_prefix='/api/ebdz')
    app.register_blueprint(prowlarr_bp, url_prefix='/api/prowlarr')
    app.register_blueprint(nautiljon_bp, url_prefix='/api/nautiljon')
    app.register_blueprint(qbittorrent_bp)
    app.register_blueprint(settings_bp)
    app.register_blueprint(missing_monitor_bp, url_prefix='/api/missing-monitor')
    app.register_blueprint(audit_bp)
    
    app.register_blueprint(auth_bp)
    
    # Créer l'utilisateur par défaut s'il n'existe pas
    _create_default_user()
    
    # Initialiser le scheduler EBDZ
    from blueprints.ebdz.scheduler import ebdz_scheduler
    ebdz_scheduler.init_app(app)
    
    # Initialiser le scheduler de surveillance des volumes manquants
    from blueprints.missing_monitor.scheduler import MissingVolumeScheduler
    missing_volume_scheduler = MissingVolumeScheduler()
    missing_volume_scheduler.init_app(app)
    
    # Initialiser le scheduler d'import automatique
    from blueprints.library.scheduler import library_import_scheduler
    library_import_scheduler.init_app(app)
    
    # Démarrer les schedulers et charger les configurations automatiques
    with app.app_context():
        # Initialiser la table d'historique des imports
        from blueprints.library.import_history import init_import_history_table
        init_import_history_table()
        
        from blueprints.ebdz.routes import load_ebdz_config
        ebdz_config = load_ebdz_config()
        
        if ebdz_config.get('auto_scrape_enabled', False):
            interval = ebdz_config.get('auto_scrape_interval', 60)
            interval_unit = ebdz_config.get('auto_scrape_interval_unit', 'minutes')
            ebdz_scheduler.add_job(interval, interval_unit)
            print(f"✓ Scraping automatique EBDZ activé: tous les {interval} {interval_unit}")
        
        # Charger la configuration d'import automatique
        from blueprints.library.routes import load_library_import_config
        import_config = load_library_import_config()
        
        if import_config.get('auto_import_enabled', False):
            interval = import_config.get('auto_import_interval', 60)
            interval_unit = import_config.get('auto_import_interval_unit', 'minutes')
            library_import_scheduler.add_job(interval, interval_unit)
            print(f"✓ Import automatique activé: tous les {interval} {interval_unit}")
        
        # Charger la configuration de surveillance des volumes manquants
        from blueprints.missing_monitor.routes import load_monitor_config
        monitor_config = load_monitor_config()
        
        if monitor_config.get('auto_check_enabled', False):
            interval = monitor_config.get('auto_check_interval', 60)
            interval_unit = monitor_config.get('auto_check_interval_unit', 'minutes')
            missing_volume_scheduler.add_monitor_job(interval, interval_unit)
            print(f"✓ Surveillance des volumes manquants activée: tous les {interval} {interval_unit}")
    
    # 🧪 ROUTE DE TEST - Vérifier que @login_required fonctionne
    from flask_login import login_required, current_user
    @app.route('/test-protected')
    @login_required
    def test_protected():
        """Route de test protégée"""
        return jsonify({
            'message': 'Vous êtes authentifié!',
            'user_id': current_user.id,
            'username': current_user.username
        })
    
    return app


if __name__ == '__main__':
    # Déterminer le mode (développement ou production)
    # FLASK_ENV peut être: development ou production (défaut: development)
    config_name = os.getenv('FLASK_ENV', 'development')
    
    app = create_app(config_name)
    
    debug_mode = config_name == 'development'
    
    print("=" * 60)
    print("Gestionnaire Multi-Bibliothèques Manga")
    print("=" * 60)
    print(f"Mode: {config_name.upper()}")
    print("Accédez à http://localhost:5000")
    print("Écoute sur IPv4 uniquement")
    print("=" * 60)
    
    app.run(debug=debug_mode, host='0.0.0.0', port=5000, use_reloader=False)