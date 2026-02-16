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
    EBDZ_CONFIG_FILE = os.path.join(DATA_DIR, 'ebdz_config.json')
    PROWLARR_CONFIG_FILE = os.path.join(DATA_DIR, 'prowlarr_config.json')
    
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
    
    # Prowlarr par défaut
    PROWLARR_CONFIG = {
        'enabled': False,
        'url': 'http://127.0.0.1',
        'port': 9696,
        'api_key': '',
        'selected_indexers': []
    }
    
    @staticmethod
    def init_app(app):
        """Initialise les répertoires et la base de données"""
        os.makedirs(Config.DATA_DIR, exist_ok=True)
        os.makedirs(Config.COVERS_DIR, exist_ok=True)
        
        # Initialiser la base de données si elle n'existe pas
        Config._init_database(Config.DATABASE)
    
    @staticmethod
    def _init_database(db_path):
        """Initialise les tables de la base de données SQLite"""
        import sqlite3
        
        conn = sqlite3.connect(db_path, timeout=30.0)
        cursor = conn.cursor()
        
        # Activer le mode WAL (Write-Ahead Logging) pour de meilleures performances concurrentes
        cursor.execute('PRAGMA journal_mode=WAL')
        
        # Table des bibliothèques
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS libraries (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL UNIQUE,
                path TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_scanned TIMESTAMP
            )
        ''')
        
        # Table des séries
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS series (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                library_id INTEGER,
                title TEXT NOT NULL,
                path TEXT,
                total_volumes INTEGER,
                missing_volumes TEXT,
                has_parts INTEGER DEFAULT 0,
                last_scanned TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (library_id) REFERENCES libraries(id) ON DELETE CASCADE
            )
        ''')
        
        # Table des volumes
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS volumes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                series_id INTEGER,
                part_number INTEGER,
                part_name TEXT,
                volume_number INTEGER,
                filename TEXT,
                filepath TEXT,
                author TEXT,
                year INTEGER,
                resolution TEXT,
                file_size INTEGER,
                page_count INTEGER,
                format TEXT,
                FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE CASCADE
            )
        ''')
        
        conn.commit()
        conn.close()


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
