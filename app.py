"""
Point d'entrée principal de l'application Manga Manager
"""
from flask import Flask, send_from_directory
from config import config
import os
from encryption import ensure_encryption_key

def create_app(config_name='default'):
    """Factory pour créer l'application Flask"""
    
    # Initialiser la clé de chiffrement
    ensure_encryption_key()
    
    app = Flask(__name__)
    app.config.from_object(config[config_name])
    
    # Initialiser l'app (créer les répertoires)
    config[config_name].init_app(app)
    
    # Route pour servir les couvertures
    @app.route('/covers/<path:filename>')
    def serve_cover(filename):
        return send_from_directory(app.config['COVERS_DIR'], filename)
    
    # Enregistrer les blueprints
    from blueprints.library import library_bp
    from blueprints.search import search_bp
    from blueprints.emule import emule_bp
    from blueprints.ebdz import ebdz_bp
    from blueprints.prowlarr import prowlarr_bp
    from blueprints.nautiljon import nautiljon_bp
    from blueprints.settings import settings_bp
    from blueprints.qbittorrent import qbittorrent_bp
    
    app.register_blueprint(library_bp)
    app.register_blueprint(search_bp)
    app.register_blueprint(emule_bp, url_prefix='/api/emule')
    app.register_blueprint(ebdz_bp, url_prefix='/api/ebdz')
    app.register_blueprint(prowlarr_bp, url_prefix='/api/prowlarr')
    app.register_blueprint(nautiljon_bp, url_prefix='/api/nautiljon')
    app.register_blueprint(qbittorrent_bp)
    app.register_blueprint(settings_bp)
    
    return app


if __name__ == '__main__':
    app = create_app('development')
    
    print("=" * 60)
    print("Gestionnaire Multi-Bibliothèques Manga")
    print("=" * 60)
    print("Accédez à http://localhost:5000")
    print("=" * 60)
    
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)