"""
Configuration centralisée de l'application
"""
import os

class Config:
    """Configuration de base"""
    
    # Flask
    SECRET_KEY = os.environ.get('SECRET_KEY') or 'dev-secret-key-change-in-production'
    DEBUG = True
    
    # Chemins
    BASE_DIR = os.path.abspath(os.path.dirname(__file__))
    DATA_DIR = os.path.join(BASE_DIR, 'data')
    COVERS_DIR = os.path.join(DATA_DIR, 'covers')
    
    # Bases de données
    DATABASE = os.path.join(DATA_DIR, 'manga_library.db')
    DB_FILE = os.path.join(DATA_DIR, 'ebdz.db')
    
    # Fichiers de configuration
    CONFIG_FILE = os.path.join(DATA_DIR, 'emule_config.json')
    KEY_FILE = os.path.join(DATA_DIR, '.emule_key')
    EBDZ_CONFIG_FILE = os.path.join(DATA_DIR, 'ebdz_config.json')
    
    # eMule/aMule par défaut
    EMULE_CONFIG = {
        'enabled': False,
        'type': 'amule',
        'host': '127.0.0.1',
        'port': 4711,
        'ec_port': 4712,
        'password': ''
    }
    
    # ebdz.net par défaut
    EBDZ_CONFIG = {
        'username': '',
        'password': '',
        'forums': []
    }
    
    @staticmethod
    def init_app(app):
        """Initialise les répertoires nécessaires"""
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        os.makedirs(Config.COVERS_DIR, exist_ok=True)


class DevelopmentConfig(Config):
    """Configuration de développement"""
    DEBUG = True


class ProductionConfig(Config):
    """Configuration de production"""
    DEBUG = False


config = {
    'development': DevelopmentConfig,
    'production': ProductionConfig,
    'default': DevelopmentConfig
}
