from flask import Flask, render_template, request, jsonify, redirect, url_for, send_from_directory
import sqlite3
import os
import re
from pathlib import Path
from zipfile import ZipFile
import rarfile
import ebooklib
from ebooklib import epub
from PyPDF2 import PdfReader
from PIL import Image
import io
from collections import defaultdict
import json
import shutil

app = Flask(__name__)

# Route pour servir les fichiers statiques
@app.route('/static/<path:filename>')
def static_files(filename):
    return send_from_directory('static', filename)

# Configuration
DATABASE = './data/manga_library.db'
DB_FILE = "./data/ebdz.db"
CONFIG_FILE = "./data/emule_config.json"
KEY_FILE = "./data/.emule_key"
EBDZ_CONFIG_FILE = "./data/ebdz_config.json"

# Créer les répertoires nécessaires
os.makedirs('./data/covers', exist_ok=True)
os.makedirs('./templates', exist_ok=True)
os.makedirs('./static/css', exist_ok=True)
os.makedirs('./static/js', exist_ok=True)



# Configuration eMule/aMule - À PERSONNALISER
EMULE_CONFIG = {
    'enabled': False,  # Mettre True pour activer
    'type': 'amule',  # 'emule' ou 'amule'
    'host': '127.0.0.1',
    'port': 4711,  # Port interface web (non utilisé pour amule EC)
    'ec_port': 4712,  # Port External Connections pour aMule
    'password': ''  # Mot de passe admin / EC
}

# Configuration du scraper ebdz.net
EBDZ_CONFIG = {
    'username': '',
    'password': '',
    'forums': []
    # Chaque forum : { 'fid': int, 'category': str, 'max_pages': int|None }
}

class LibraryScanner:
    def __init__(self, db_path=DATABASE):
        self.db_path = db_path
        self.init_database()

    def init_database(self):
        """Initialise la base de données"""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
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

    def parse_filename(self, filename):
        """Parse le nom de fichier pour extraire les métadonnées"""
        info = {
            'title': '',
            'part_number': None,
            'part_name': None,
            'volume': None,
            'author': None,
            'year': None,
            'resolution': None,
            'format': filename.split('.')[-1].lower()
        }

        # Retirer l'extension pour faciliter le parsing
        name_without_ext = os.path.splitext(filename)[0]

        # AMÉLIORATION: Normaliser le nom en remplaçant les points et underscores par des espaces
        # Sauf pour les points dans les nombres (comme 1.5)
        # On garde aussi les points dans les patterns spéciaux comme "Vol." ou "T.01"
        normalized_name = name_without_ext

        # Remplacer les points par des espaces, sauf si précédés/suivis d'un chiffre
        normalized_name = re.sub(r'\.(?!\d)', ' ', normalized_name)  # Point non suivi d'un chiffre
        normalized_name = re.sub(r'(?<!\d)\.', ' ', normalized_name)  # Point non précédé d'un chiffre
        normalized_name = re.sub(r'_', ' ', normalized_name)  # Underscores

        # Nettoyer les espaces multiples
        normalized_name = re.sub(r'\s+', ' ', normalized_name).strip()

        # Extraire la partie/arc (Part XX, Arc XX, Partie XX)
        part_match = re.search(r'(?:Part|Arc|Partie)\s+(\d+)', normalized_name, re.IGNORECASE)
        if part_match:
            info['part_number'] = int(part_match.group(1))
            # Essayer d'extraire le nom de la partie
            part_name_match = re.search(r'(?:Part|Arc|Partie)\s+\d+\s*-\s*([^T]+?)(?=\s+T\d+)', normalized_name, re.IGNORECASE)
            if part_name_match:
                info['part_name'] = part_name_match.group(1).strip()

        # Extraire le numéro de tome avec patterns améliorés
        # Si on a une partie, chercher d'abord un volume explicite APRÈS la partie
        if info['part_number']:
            # Chercher après "Part X" ou "Part X - Nom" un pattern "T Y" ou "- T Y"
            after_part = re.search(r'(?:Part|Arc|Partie)\s+\d+(?:\s*-\s*[^T-]*?)?\s*-?\s*T[\s\.]?(\d+)', normalized_name, re.IGNORECASE)
            if after_part:
                info['volume'] = int(after_part.group(1))

        # Si pas encore trouvé de volume, utiliser les patterns standard
        if not info['volume']:
            volume_patterns = [
                r'Tome[\s\.](\d+)',               # Tome 09, Tome.09
                r'T[\s\.]?(\d+)',                 # T04, T.04, T 4
                r'Vol\.?\s*(\d+)',                # Vol. 4, Vol 4, Vol.4
                r'Volume[\s\.](\d+)',             # Volume 4, Volume.4
                r'v[\s\.]?(\d+)',                 # v4, v.4
                r'#(\d+)',                        # #4
                r'-\s*(\d+)(?:\s|$)',             # - 08 (à la fin ou suivi d'espace)
                r'\s(\d+)\s*(?:FR|EN|VF|VO)',    # 09 FR (nombre avant langue)
                r'\s(\d{1,3})$'                   # 08 (nombre de 1-3 chiffres à la fin, évite les années)
            ]

            for pattern in volume_patterns:
                match = re.search(pattern, normalized_name, re.IGNORECASE)
                if match:
                    potential_volume = int(match.group(1))
                    # Filtrer les fausses détections :
                    # - Années (entre 1800-2099)
                    # - Nombres trop grands pour être des volumes (> 999)
                    if not (1800 <= potential_volume <= 2099 or potential_volume > 999):
                        info['volume'] = potential_volume
                        break

        # Extraire le titre (avant Part/Arc ou avant le numéro de tome)
        if info['part_number']:
            title_match = re.match(r'^(.+?)\s+(?:Part|Arc|Partie)\s*\d+', normalized_name, re.IGNORECASE)
        else:
            title_match = re.match(r'^(.+?)\s+(?:Tome|T[\s\.]?\d+|Vol|Volume|v[\s\.]?\d+|#\d+|-\s*\d+)', normalized_name, re.IGNORECASE)

        if title_match:
            info['title'] = title_match.group(1).strip()
        else:
            # Si aucun pattern de tome trouvé, essayer de nettoyer le titre
            # Retirer les tags courants à la fin
            clean_title = re.sub(r'\s*(?:FR|EN|VF|VO|FRENCH|ENGLISH).*$', '', normalized_name, flags=re.IGNORECASE)
            clean_title = re.sub(r'\s*-\s*[A-Za-z0-9]+$', '', clean_title)  # Retirer les tags de release
            info['title'] = clean_title.strip() if clean_title else normalized_name

        # Nettoyer le titre (retirer les tirets multiples, espaces superflus)
        info['title'] = re.sub(r'\s*-\s*$', '', info['title'])
        info['title'] = re.sub(r'\s+', ' ', info['title']).strip()

        # Extraire l'auteur (cherche dans le nom complet avec extension)
        author_match = re.search(r'\(([^)]+?)\)', filename)
        if author_match:
            potential_author = author_match.group(1)
            # Éviter de prendre l'année comme auteur
            if not re.match(r'^\d{4}$', potential_author):
                info['author'] = potential_author

        # Chercher aussi l'auteur après un tiret (format: titre - auteur)
        if not info['author']:
            author_dash_match = re.search(r'-\s*([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)\s*(?:T\d+|Tome|Vol)', normalized_name)
            if author_dash_match:
                info['author'] = author_dash_match.group(1).strip()

        # Extraire l'année
        year_match = re.search(r'\b(19\d{2}|20\d{2})\b', filename)
        if year_match:
            info['year'] = int(year_match.group(1))

        # Extraire la résolution (1920x1080, etc.)
        resolution_match = re.search(r'(\d{3,4}x\d{3,4})', filename)
        if resolution_match:
            info['resolution'] = resolution_match.group(1)

        return info

    def get_page_count(self, filepath, format_type):
        """Récupère le nombre de pages d'un fichier"""
        try:
            format_type = format_type.lower()

            if format_type in ['cbz', 'zip']:
                with ZipFile(filepath, 'r') as zip_file:
                    # Compte les images (jpg, jpeg, png, webp)
                    image_files = [f for f in zip_file.namelist()
                                 if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
                    return len(image_files)

            elif format_type in ['cbr', 'rar']:
                with rarfile.RarFile(filepath) as rar_file:
                    image_files = [f for f in rar_file.namelist()
                                 if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))]
                    return len(image_files)

            elif format_type == 'pdf':
                with open(filepath, 'rb') as f:
                    pdf = PdfReader(f)
                    return len(pdf.pages)

            elif format_type == 'epub':
                book = epub.read_epub(filepath)
                # Compte les chapitres/documents
                return len(list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT)))

        except Exception as e:
            print(f"Erreur lecture {filepath}: {e}")
            return 0

        return 0

    def scan_directory(self, library_id, library_path):
        """Scanne un répertoire pour détecter les séries et volumes
        
        CORRECTION DU BUG:
        - Les sous-répertoires directs de library_path sont les séries
        - Les fichiers dans chaque sous-répertoire sont les volumes de cette série
        """
        print(f"\n📂 Scan du répertoire: {library_path}")

        if not os.path.exists(library_path):
            raise Exception(f"Le chemin {library_path} n'existe pas")

        # Extensions supportées
        supported_extensions = {'.cbz', '.cbr', '.zip', '.rar', '.pdf', '.epub'}

        # Structure pour grouper les fichiers par série
        # Clé = nom du sous-répertoire (= nom de la série)
        series_data = defaultdict(lambda: {
            'volumes': [],
            'path': None
        })

        # Parcourir le répertoire de la bibliothèque
        try:
            # Lister tous les éléments dans le répertoire de la bibliothèque
            items = os.listdir(library_path)
        except PermissionError as e:
            raise Exception(f"Permission refusée pour accéder à {library_path}")
        
        for item in items:
            item_path = os.path.join(library_path, item)
            
            # Si c'est un répertoire, c'est une série
            if os.path.isdir(item_path):
                series_title = item  # Le nom du dossier EST le nom de la série
                series_data[series_title]['path'] = item_path
                
                # Scanner tous les fichiers dans ce répertoire de série
                try:
                    for filename in os.listdir(item_path):
                        filepath = os.path.join(item_path, filename)
                        
                        # Ignorer les sous-répertoires
                        if os.path.isdir(filepath):
                            continue
                        
                        ext = os.path.splitext(filename)[1].lower()
                        
                        if ext in supported_extensions:
                            parsed = self.parse_filename(filename)
                            
                            series_data[series_title]['volumes'].append({
                                'filename': filename,
                                'filepath': filepath,
                                'parsed': parsed,
                                'file_size': os.path.getsize(filepath)
                            })
                except PermissionError:
                    print(f"⚠️  Permission refusée pour {item_path}")
                    continue
            
            # Si c'est un fichier directement dans la bibliothèque (pas dans un sous-dossier)
            elif os.path.isfile(item_path):
                ext = os.path.splitext(item)[1].lower()
                
                if ext in supported_extensions:
                    # Parser le nom de fichier pour extraire le titre
                    parsed = self.parse_filename(item)
                    
                    # Utiliser le titre extrait comme nom de série
                    # (fallback si fichiers pas organisés en dossiers)
                    if parsed['title']:
                        series_title = parsed['title']
                    else:
                        # Si pas de titre détecté, utiliser le nom du fichier sans extension
                        series_title = os.path.splitext(item)[0]
                    
                    # Le path de la série sera la bibliothèque elle-même
                    if not series_data[series_title]['path']:
                        series_data[series_title]['path'] = library_path
                    
                    series_data[series_title]['volumes'].append({
                        'filename': item,
                        'filepath': item_path,
                        'parsed': parsed,
                        'file_size': os.path.getsize(item_path)
                    })

        print(f"✓ {len(series_data)} séries détectées")

        # Insérer/mettre à jour dans la base de données
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()

        for series_title, data in series_data.items():
            volumes = data['volumes']
            series_path = data['path']

            try:
                # Vérifier si la série existe déjà
                cursor.execute('''
                    SELECT id FROM series
                    WHERE library_id = ? AND title = ?
                ''', (library_id, series_title))

                result = cursor.fetchone()

                if result:
                    # Mettre à jour la série existante
                    series_id = result[0]
                    
                    # Mettre à jour le path de la série
                    if series_path:
                        cursor.execute('UPDATE series SET path = ? WHERE id = ?', (series_path, series_id))

                    # Supprimer les anciens volumes pour cette série
                    cursor.execute('DELETE FROM volumes WHERE series_id = ?', (series_id,))
                else:
                    # Créer une nouvelle série
                    if not series_path:
                        series_path = os.path.join(library_path, series_title)
                    
                    cursor.execute('''
                        INSERT INTO series (library_id, title, path, total_volumes, missing_volumes, has_parts)
                        VALUES (?, ?, ?, 0, '[]', 0)
                    ''', (library_id, series_title, series_path))

                    series_id = cursor.lastrowid

                # Ajouter tous les volumes
                for volume in volumes:
                    try:
                        parsed = volume['parsed']
                        page_count = self.get_page_count(volume['filepath'], parsed['format'])

                        cursor.execute('''
                            INSERT INTO volumes
                            (series_id, part_number, part_name, volume_number, filename, filepath,
                             author, year, resolution, file_size, page_count, format)
                            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            series_id,
                            parsed['part_number'],
                            parsed['part_name'],
                            parsed['volume'],
                            volume['filename'],
                            volume['filepath'],
                            parsed['author'],
                            parsed['year'],
                            parsed['resolution'],
                            volume['file_size'],
                            page_count,
                            parsed['format']
                        ))
                    except Exception as vol_error:
                        # Log l'erreur mais continue avec les autres volumes
                        print(f"    ⚠️  Erreur sur volume {volume.get('filename', '?')}: {vol_error}")
                        continue

                # Calculer les statistiques de la série
                cursor.execute('''
                    SELECT COUNT(*), MAX(volume_number)
                    FROM volumes
                    WHERE series_id = ?
                ''', (series_id,))

                total_volumes, max_volume = cursor.fetchone()

                # Détecter s'il y a des parties
                cursor.execute('''
                    SELECT COUNT(DISTINCT part_number)
                    FROM volumes
                    WHERE series_id = ? AND part_number IS NOT NULL
                ''', (series_id,))

                has_parts = cursor.fetchone()[0] > 0

                # Calculer les volumes manquants
                cursor.execute('''
                    SELECT volume_number FROM volumes
                    WHERE series_id = ? AND volume_number IS NOT NULL
                    ORDER BY volume_number
                ''', (series_id,))

                existing_volumes = [row[0] for row in cursor.fetchall()]
                missing_volumes = []

                if max_volume and existing_volumes:
                    for i in range(1, max_volume + 1):
                        if i not in existing_volumes:
                            missing_volumes.append(i)

                # Mettre à jour la série
                cursor.execute('''
                    UPDATE series
                    SET total_volumes = ?,
                        missing_volumes = ?,
                        has_parts = ?,
                        last_scanned = CURRENT_TIMESTAMP
                    WHERE id = ?
                ''', (total_volumes, json.dumps(missing_volumes), 1 if has_parts else 0, series_id))

                # Affichage sécurisé avec gestion des caractères spéciaux
                try:
                    print(f"  ✓ {series_title}: {total_volumes} volumes")
                except UnicodeEncodeError:
                    # Si le print échoue à cause de l'encodage, essayer en ASCII
                    safe_title = series_title.encode('ascii', 'ignore').decode('ascii')
                    print(f"  ✓ {safe_title}: {total_volumes} volumes")
                
            except Exception as series_error:
                # Log l'erreur mais continue avec les autres séries
                try:
                    print(f"  ⚠️  Erreur sur série '{series_title}': {series_error}")
                except UnicodeEncodeError:
                    print(f"  ⚠️  Erreur sur une série: {series_error}")
                continue

        # Mettre à jour la date de scan de la bibliothèque
        cursor.execute('''
            UPDATE libraries
            SET last_scanned = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (library_id,))

        conn.commit()
        conn.close()

        return len(series_data)
        
        
    def update_series_stats(self, series_id, conn=None):
        """Met à jour les statistiques d'une série (total volumes, volumes manquants)
        
        Args:
            series_id: ID de la série à mettre à jour
            conn: Connexion SQLite existante (optionnel). Si None, une nouvelle connexion sera créée.
        """
        # Si aucune connexion n'est fournie, en créer une nouvelle
        close_conn = False
        if conn is None:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            close_conn = True
        
        cursor = conn.cursor()

        # Récupérer tous les numéros de volumes
        cursor.execute('''
            SELECT DISTINCT volume_number
            FROM volumes
            WHERE series_id = ? AND volume_number IS NOT NULL
            ORDER BY volume_number
        ''', (series_id,))

        volume_numbers = [row[0] for row in cursor.fetchall()]

        if not volume_numbers:
            cursor.execute('''
                UPDATE series
                SET total_volumes = 0, missing_volumes = '[]', has_parts = 0
                WHERE id = ?
            ''', (series_id,))
            if close_conn:
                conn.commit()
                conn.close()
            return

        # Détecter les volumes manquants
        min_vol = min(volume_numbers)
        max_vol = max(volume_numbers)
        expected_volumes = set(range(min_vol, max_vol + 1))
        actual_volumes = set(volume_numbers)
        missing_volumes = sorted(expected_volumes - actual_volumes)

        # Vérifier si la série a des parties
        cursor.execute('''
            SELECT COUNT(DISTINCT part_number)
            FROM volumes
            WHERE series_id = ? AND part_number IS NOT NULL
        ''', (series_id,))

        has_parts = cursor.fetchone()[0] > 1

        # Mettre à jour
        cursor.execute('''
            UPDATE series
            SET total_volumes = ?,
                missing_volumes = ?,
                has_parts = ?,
                last_scanned = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (
            len(volume_numbers),
            json.dumps(missing_volumes),
            1 if has_parts else 0,
            series_id
        ))

        # Commit et fermeture seulement si on a créé la connexion
        if close_conn:
            conn.commit()
            conn.close()


    def get_library_stats(self, library_id):
        """Récupère les statistiques d'une bibliothèque"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Nombre de séries
        cursor.execute('SELECT COUNT(*) FROM series WHERE library_id = ?', (library_id,))
        series_count = cursor.fetchone()[0]

        # Nombre total de volumes
        cursor.execute('''
            SELECT COUNT(*)
            FROM volumes v
            JOIN series s ON v.series_id = s.id
            WHERE s.library_id = ?
        ''', (library_id,))
        volumes_count = cursor.fetchone()[0]

        conn.close()

        return {
            'series_count': series_count,
            'volumes_count': volumes_count
        }


def load_emule_config():
    """Charge la configuration eMule depuis le fichier"""
    global EMULE_CONFIG
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                saved_config = json.load(f)
                EMULE_CONFIG.update(saved_config)
                print("[CONFIG] Configuration eMule chargée")
    except Exception as e:
        print(f"[ERROR] Erreur chargement config: {e}")

def save_emule_config():
    """Sauvegarde la configuration eMule dans le fichier"""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(EMULE_CONFIG, f, indent=2)
        print("[CONFIG] Configuration eMule sauvegardée")
        return True
    except Exception as e:
        print(f"[ERROR] Erreur sauvegarde config: {e}")
        return False

# Charger la config au démarrage
load_emule_config()


# ─── Config ebdz.net ────────────────────────────────────────

def load_ebdz_config():
    """Charge la configuration du scraper ebdz depuis le fichier JSON"""
    global EBDZ_CONFIG
    try:
        if os.path.exists(EBDZ_CONFIG_FILE):
            with open(EBDZ_CONFIG_FILE, 'r') as f:
                saved = json.load(f)
                # Déchiffre le mot de passe
                if 'password' in saved:
                    saved['password'] = decrypt_password(saved['password'])
                EBDZ_CONFIG.update(saved)
                print(f"✓ Configuration ebdz.net chargée depuis {EBDZ_CONFIG_FILE}")
    except Exception as e:
        print(f"⚠️ Impossible de charger la config ebdz: {e}")

def save_ebdz_config():
    """Sauvegarde la configuration du scraper ebdz dans le fichier JSON"""
    try:
        config_to_save = EBDZ_CONFIG.copy()
        config_to_save['password'] = encrypt_password(EBDZ_CONFIG['password'])
        with open(EBDZ_CONFIG_FILE, 'w') as f:
            json.dump(config_to_save, f, indent=4, ensure_ascii=False)
        print(f"✓ Configuration ebdz.net sauvegardée dans {EBDZ_CONFIG_FILE}")
        return True
    except Exception as e:
        print(f"✗ Erreur sauvegarde config ebdz: {e}")
        return False

load_ebdz_config()
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/library/<int:library_id>')
def library_view(library_id):
    return render_template('library.html', library_id=library_id)

@app.route('/import')
def import_page():
    return render_template('import.html')

@app.route('/search')
def search_page():
    """Page de recherche ED2K"""
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    
    # Récupérer les statistiques
    cursor.execute('SELECT COUNT(*) FROM ed2k_links')
    total_links = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT thread_id) FROM ed2k_links')
    total_threads = cursor.fetchone()[0]
    
    # Récupérer les catégories uniques
    cursor.execute('SELECT DISTINCT forum_category FROM ed2k_links WHERE forum_category IS NOT NULL ORDER BY forum_category')
    categories = [row[0] for row in cursor.fetchall()]
    
    conn.close()
    
    return render_template('search.html', 
                         total_links=total_links, 
                         total_threads=total_threads,
                         categories=categories)

@app.route('/settings')
def settings_page():
    return render_template('settings.html')

# API ROUTES

@app.route('/api/libraries', methods=['GET', 'POST'])
def libraries():
    scanner = LibraryScanner()

    if request.method == 'GET':
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute('SELECT * FROM libraries ORDER BY name')
        libraries = cursor.fetchall()

        result = []
        for lib in libraries:
            stats = scanner.get_library_stats(lib[0])
            result.append({
                'id': lib[0],
                'name': lib[1],
                'path': lib[2],
                'description': lib[3],
                'created_at': lib[4],
                'last_scanned': lib[5],
                'series_count': stats['series_count'],
                'volumes_count': stats['volumes_count']
            })

        conn.close()
        return jsonify(result)

    else:  # POST
        data = request.get_json()
        name = data.get('name')
        path = data.get('path')
        description = data.get('description', '')

        if not name or not path:
            return jsonify({'success': False, 'error': 'Nom et chemin requis'}), 400

        try:
            conn = sqlite3.connect(DATABASE)
            cursor = conn.cursor()

            cursor.execute('''
                INSERT INTO libraries (name, path, description)
                VALUES (?, ?, ?)
            ''', (name, path, description))

            conn.commit()
            conn.close()

            return jsonify({'success': True})

        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'error': 'Une bibliothèque avec ce nom existe déjà'}), 400
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/libraries/<int:library_id>', methods=['DELETE'])
def delete_library(library_id):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Supprimer la bibliothèque (cascade supprime aussi les séries et volumes)
        cursor.execute('DELETE FROM libraries WHERE id = ?', (library_id,))

        conn.commit()
        conn.close()

        return jsonify({'success': True})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/scan/<int:library_id>')
def scan_library(library_id):
    try:
        scanner = LibraryScanner()

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute('SELECT path FROM libraries WHERE id = ?', (library_id,))
        result = cursor.fetchone()
        conn.close()

        if not result:
            return jsonify({'success': False, 'error': 'Bibliothèque introuvable'}), 404

        library_path = result[0]
        series_count = scanner.scan_directory(library_id, library_path)

        return jsonify({'success': True, 'series_count': series_count})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/library/<int:library_id>/series')
def get_library_series(library_id):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Récupérer toutes les séries de la bibliothèque
        cursor.execute('''
            SELECT id, title, path, total_volumes, missing_volumes, has_parts, last_scanned
            FROM series
            WHERE library_id = ?
            ORDER BY title
        ''', (library_id,))

        series_list = []
        for row in cursor.fetchall():
            missing_volumes = json.loads(row[4]) if row[4] else []

            series_list.append({
                'id': row[0],
                'title': row[1],
                'path': row[2],
                'total_volumes': row[3],
                'missing_volumes': missing_volumes,
                'has_parts': bool(row[5]),
                'last_scanned': row[6]
            })

        conn.close()
        return jsonify(series_list)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/series/<int:series_id>')
def get_series_details(series_id):
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Récupérer les infos de la série
        cursor.execute('''
            SELECT s.id, s.title, s.path, s.total_volumes, s.missing_volumes, s.has_parts,
                   l.id, l.name
            FROM series s
            JOIN libraries l ON s.library_id = l.id
            WHERE s.id = ?
        ''', (series_id,))

        series_row = cursor.fetchone()

        if not series_row:
            return jsonify({'error': 'Série introuvable'}), 404

        missing_volumes = json.loads(series_row[4]) if series_row[4] else []

        # Récupérer tous les volumes
        cursor.execute('''
            SELECT id, part_number, part_name, volume_number, filename, filepath,
                   author, year, resolution, file_size, page_count, format
            FROM volumes
            WHERE series_id = ?
            ORDER BY part_number, volume_number
        ''', (series_id,))

        volumes = []
        for vol in cursor.fetchall():
            volumes.append({
                'id': vol[0],
                'part_number': vol[1],
                'part_name': vol[2],
                'volume_number': vol[3],
                'filename': vol[4],
                'filepath': vol[5],
                'author': vol[6],
                'year': vol[7],
                'resolution': vol[8],
                'file_size': vol[9],
                'page_count': vol[10],
                'format': vol[11]
            })

        conn.close()

        return jsonify({
            'id': series_row[0],
            'title': series_row[1],
            'path': series_row[2],
            'total_volumes': series_row[3],
            'missing_volumes': missing_volumes,
            'has_parts': bool(series_row[5]),
            'library': {
                'id': series_row[6],
                'name': series_row[7]
            },
            'volumes': volumes
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/library/<int:library_id>/stats')
def get_library_stats_route(library_id):
    """Récupère les statistiques détaillées d'une bibliothèque"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Nombre total de séries
        cursor.execute('''
            SELECT COUNT(*) FROM series WHERE library_id = ?
        ''', (library_id,))
        total_series = cursor.fetchone()[0]

        # Nombre total de volumes
        cursor.execute('''
            SELECT COUNT(*) 
            FROM volumes v
            JOIN series s ON v.series_id = s.id
            WHERE s.library_id = ?
        ''', (library_id,))
        total_volumes = cursor.fetchone()[0]

        # Taille totale
        cursor.execute('''
            SELECT COALESCE(SUM(v.file_size), 0)
            FROM volumes v
            JOIN series s ON v.series_id = s.id
            WHERE s.library_id = ?
        ''', (library_id,))
        total_size = cursor.fetchone()[0]

        # Moyenne de pages
        cursor.execute('''
            SELECT COALESCE(AVG(v.page_count), 0)
            FROM volumes v
            JOIN series s ON v.series_id = s.id
            WHERE s.library_id = ? AND v.page_count > 0
        ''', (library_id,))
        avg_pages = int(cursor.fetchone()[0])

        conn.close()

        return jsonify({
            'total_series': total_series,
            'total_volumes': total_volumes,
            'total_size': total_size,
            'avg_pages': avg_pages
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/libraries/<int:library_id>')
def get_library_info(library_id):
    """Récupère les informations d'une bibliothèque spécifique"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute('''
            SELECT id, name, path, description, created_at, last_scanned
            FROM libraries
            WHERE id = ?
        ''', (library_id,))
        
        result = cursor.fetchone()
        conn.close()

        if not result:
            return jsonify({'error': 'Bibliothèque introuvable'}), 404

        return jsonify({
            'id': result[0],
            'name': result[1],
            'path': result[2],
            'description': result[3],
            'created_at': result[4],
            'last_scanned': result[5]
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/search')
def search_ed2k():
    query = request.args.get('query', '').strip()
    volume = request.args.get('volume', '').strip()
    category = request.args.get('category', '').strip()

    try:
        conn = sqlite3.connect(DB_FILE)
        cursor = conn.cursor()

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

        links = []
        for row in results:
            links.append({
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

        return jsonify({'results': links})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/import/scan', methods=['POST'])
def scan_import_directory():
    """Scanne un répertoire pour trouver les fichiers à importer"""
    data = request.json
    import_path = data.get('path', '')

    if not import_path or not os.path.exists(import_path):
        return jsonify({'error': 'Chemin invalide ou inexistant'}), 400

    try:
        scanner = LibraryScanner()
        supported_extensions = {'.cbz', '.cbr', '.zip', '.rar', '.pdf', '.epub'}

        files_found = []

        # Parcourir le répertoire
        for root, dirs, files in os.walk(import_path):
            # Ignorer les répertoires spéciaux
            dirs[:] = [d for d in dirs if d not in ['_old_files', '_doublons']]
            
            for filename in files:
                ext = os.path.splitext(filename)[1].lower()

                if ext in supported_extensions:
                    filepath = os.path.join(root, filename)
                    parsed = scanner.parse_filename(filename)

                    files_found.append({
                        'filename': filename,
                        'filepath': filepath,
                        'relative_path': os.path.relpath(filepath, import_path),
                        'file_size': os.path.getsize(filepath),
                        'parsed': parsed
                    })

        return jsonify({
            'success': True,
            'files': files_found,
            'count': len(files_found)
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/api/import/execute', methods=['POST'])
def execute_import():
    """Exécute l'import des fichiers vers leurs destinations"""
    data = request.json
    files_to_import = data.get('files', [])
    import_base_path = data.get('import_path', '')

    if not files_to_import:
        return jsonify({'error': 'Aucun fichier à importer'}), 400

    try:
        scanner = LibraryScanner()
        imported_count = 0
        replaced_count = 0
        skipped_count = 0
        failed_count = 0
        failures = []

        # Créer les répertoires spéciaux à la racine du répertoire d'import
        if import_base_path:
            old_files_dir = os.path.join(import_base_path, '_old_files')
            doublons_dir = os.path.join(import_base_path, '_doublons')
            os.makedirs(old_files_dir, exist_ok=True)
            os.makedirs(doublons_dir, exist_ok=True)

        # Traiter chaque fichier
        for file_data in files_to_import:
            try:
                source_path = file_data['filepath']
                destination = file_data.get('destination')
                source_size = file_data.get('file_size', 0)

                if not destination:
                    failed_count += 1
                    failures.append({
                        'file': file_data['filename'],
                        'error': 'Pas de destination définie'
                    })
                    continue

                # Récupérer ou créer la série
                conn = sqlite3.connect(DATABASE, timeout=30)
                #conn.row_factory = sqlite3.Row
                cursor = conn.cursor()

                if destination.get('is_new_series'):
                    # Créer une nouvelle série
                    series_title = destination['series_title']
                    library_id = destination['library_id']
                    library_path = destination['library_path']

                    # ===== CORRECTION DU BUG =====
                    # Créer le dossier de la série DANS le dossier de la bibliothèque
                    series_path = os.path.join(library_path, series_title)
                    os.makedirs(series_path, exist_ok=True)
                    # =============================

                    # Insérer la série dans la base
                    cursor.execute('''
                        INSERT INTO series (library_id, title, path, total_volumes, missing_volumes, has_parts)
                        VALUES (?, ?, ?, 0, '[]', 0)
                    ''', (library_id, series_title, series_path))

                    series_id = cursor.lastrowid
                    target_dir = series_path
                else:
                    # Utiliser une série existante
                    series_id = destination['series_id']
                    library_path = destination['library_path']
                    series_title = destination['series_title']

                    # ===== CORRECTION DU BUG =====
                    # TOUJOURS construire le chemin correct basé sur bibliothèque + nom série
                    # Ne PAS faire confiance au path en base de données qui peut être incorrect
                    target_dir = os.path.join(library_path, series_title)
                    
                    # Créer le dossier s'il n'existe pas
                    os.makedirs(target_dir, exist_ok=True)
                    
                    # Mettre à jour le chemin de la série dans la base de données
                    cursor.execute('UPDATE series SET path = ? WHERE id = ?', (target_dir, series_id))
                    # =============================

                # Construire le chemin de destination
                target_path = os.path.join(target_dir, file_data['filename'])

                # NOUVELLE LOGIQUE : Vérifier si un fichier existe déjà avec le même numéro de volume
                import shutil
                volume_number = file_data['parsed'].get('volume')
                existing_file_path = None
                existing_file_size = 0

                if volume_number:
                    # Chercher un fichier existant pour ce volume dans la base de données
                    cursor.execute('''
                        SELECT filepath, file_size FROM volumes
                        WHERE series_id = ? AND volume_number = ?
                        ORDER BY id DESC LIMIT 1
                    ''', (series_id, volume_number))

                    existing_volume = cursor.fetchone()
                    if existing_volume:
                        existing_file_path = existing_volume[0]
                        existing_file_size = existing_volume[1]

                action_taken = None

                # Si un fichier existe déjà pour ce volume
                if existing_file_path and os.path.exists(existing_file_path):
                    # Comparer les tailles
                    if source_size > existing_file_size:
                        # Le nouveau fichier est plus gros : remplacer
                        print(f"Remplacement: {file_data['filename']} ({source_size} bytes) > ancien ({existing_file_size} bytes)")

                        # Déplacer l'ancien fichier vers _old_files
                        old_filename = os.path.basename(existing_file_path)
                        old_dest_path = os.path.join(old_files_dir, old_filename)

                        # Si le fichier existe déjà dans _old_files, ajouter un timestamp
                        if os.path.exists(old_dest_path):
                            from datetime import datetime
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            base, ext = os.path.splitext(old_filename)
                            old_dest_path = os.path.join(old_files_dir, f"{base}_{timestamp}{ext}")

                        shutil.move(existing_file_path, old_dest_path)

                        # Supprimer l'ancien volume de la base de données
                        cursor.execute('DELETE FROM volumes WHERE filepath = ?', (existing_file_path,))

                        # Déplacer le nouveau fichier
                        shutil.move(source_path, target_path)
                        action_taken = 'replaced'
                        replaced_count += 1

                    else:
                        # Le nouveau fichier est plus petit ou égal : ne pas importer
                        print(f"Doublon ignoré: {file_data['filename']} ({source_size} bytes) <= existant ({existing_file_size} bytes)")

                        # Déplacer vers _doublons
                        doublon_path = os.path.join(doublons_dir, file_data['filename'])

                        # Si le fichier existe déjà dans _doublons, ajouter un timestamp
                        if os.path.exists(doublon_path):
                            from datetime import datetime
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            base, ext = os.path.splitext(file_data['filename'])
                            doublon_path = os.path.join(doublons_dir, f"{base}_{timestamp}{ext}")

                        shutil.move(source_path, doublon_path)
                        action_taken = 'skipped_duplicate'
                        skipped_count += 1
                        conn.close()
                        continue
                else:
                    # Pas de fichier existant : import normal
                    # Si le fichier de destination existe déjà (même nom de fichier)
                    if os.path.exists(target_path):
                        base, ext = os.path.splitext(file_data['filename'])
                        counter = 1
                        while os.path.exists(target_path):
                            target_path = os.path.join(target_dir, f"{base}_{counter}{ext}")
                            counter += 1

                    # Déplacer le fichier
                    shutil.move(source_path, target_path)
                    action_taken = 'imported'
                    imported_count += 1

                # Ajouter le volume à la base de données (sauf si skipped)
                if action_taken != 'skipped_duplicate':
                    parsed = file_data['parsed']
                    page_count = scanner.get_page_count(target_path, parsed['format'])

                    cursor.execute('''
                        INSERT INTO volumes
                        (series_id, part_number, part_name, volume_number, filename, filepath,
                         author, year, resolution, file_size, page_count, format)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                    ''', (
                        series_id, parsed['part_number'], parsed['part_name'], parsed['volume'],
                        os.path.basename(target_path), target_path, parsed['author'], parsed['year'],
                        parsed['resolution'], source_size, page_count, parsed['format']
                    ))

                conn.commit()
                conn.close()

            except Exception as e:
                failed_count += 1
                failures.append({
                    'file': file_data['filename'],
                    'error': str(e)
                })
                print(f"Erreur import {file_data['filename']}: {e}")
                import traceback
                traceback.print_exc()

        # Mettre à jour les statistiques des séries concernées
        conn = sqlite3.connect(DATABASE, timeout=30.0)
        cursor = conn.cursor()

        # Récupérer toutes les séries uniques qui ont reçu des fichiers
        series_ids = set()
        for file_data in files_to_import:
            dest = file_data.get('destination')
            if dest and dest.get('series_id'):
                series_ids.add(dest['series_id'])

        # Mettre à jour chaque série
        for series_id in series_ids:
            scanner.update_series_stats(series_id, conn)

        conn.close()

        # Nettoyer les répertoires vides dans le répertoire d'import
        if import_base_path:
            cleaned_dirs = cleanup_empty_directories(import_base_path)
        else:
            cleaned_dirs = 0

        return jsonify({
            'success': True,
            'imported_count': imported_count,
            'replaced_count': replaced_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count,
            'failures': failures,
            'cleaned_directories': cleaned_dirs
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

def cleanup_empty_directories(base_path):
    """
    Nettoie les répertoires vides dans le chemin d'import
    Ignore _old_files et _doublons
    Retourne le nombre de répertoires supprimés
    """
    if not os.path.exists(base_path):
        return 0

    deleted_count = 0
    protected_dirs = ['_old_files', '_doublons']

    # Parcourir en ordre inverse (du plus profond au plus superficiel)
    # pour supprimer les sous-répertoires vides avant les parents
    for root, dirs, files in os.walk(base_path, topdown=False):
        # Ignorer les répertoires protégés et leurs sous-répertoires
        relative_path = os.path.relpath(root, base_path)
        path_parts = relative_path.split(os.sep)

        # Ne pas toucher aux répertoires protégés
        if any(protected in path_parts for protected in protected_dirs):
            continue

        # Ne pas supprimer le répertoire de base lui-même
        if root == base_path:
            continue

        # Vérifier si le répertoire est vide (pas de fichiers, pas de sous-répertoires)
        try:
            if not os.listdir(root):  # Répertoire complètement vide
                print(f"Suppression du répertoire vide: {root}")
                os.rmdir(root)
                deleted_count += 1
        except (OSError, PermissionError) as e:
            print(f"Impossible de supprimer {root}: {e}")

    return deleted_count

@app.route('/api/import/cleanup', methods=['POST'])
def cleanup_import_directory():
    """Nettoie les répertoires vides du répertoire d'import"""
    data = request.json
    import_path = data.get('path', '')

    if not import_path or not os.path.exists(import_path):
        return jsonify({'error': 'Chemin invalide ou inexistant'}), 400

    try:
        cleaned_count = cleanup_empty_directories(import_path)

        return jsonify({
            'success': True,
            'cleaned_directories': cleaned_count
        })

    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


def get_or_create_key():
    """Génère ou récupère la clé de chiffrement"""
    try:
        from cryptography.fernet import Fernet
        import os

        if os.path.exists(KEY_FILE):
            with open(KEY_FILE, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(KEY_FILE, 'wb') as f:
                f.write(key)
            print(f"✓ Clé de chiffrement générée dans {KEY_FILE}")
            return key
    except ImportError:
        print("⚠️ Module cryptography non installé. Mot de passe non chiffré.")
        return None

def encrypt_password(password):
    """Chiffre le mot de passe"""
    if not password:
        return ''
    try:
        from cryptography.fernet import Fernet
        key = get_or_create_key()
        if key:
            f = Fernet(key)
            return f.encrypt(password.encode()).decode()
        return password
    except:
        return password

def decrypt_password(encrypted_password):
    """Déchiffre le mot de passe"""
    if not encrypted_password:
        return ''
    try:
        from cryptography.fernet import Fernet
        key = get_or_create_key()
        if key:
            f = Fernet(key)
            return f.decrypt(encrypted_password.encode()).decode()
        return encrypted_password
    except:
        return encrypted_password

def load_emule_config():
    """Charge la configuration depuis le fichier JSON"""
    global EMULE_CONFIG
    try:
        import json
        import os
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, 'r') as f:
                saved_config = json.load(f)
                # Déchiffre le mot de passe
                if 'password' in saved_config:
                    saved_config['password'] = decrypt_password(saved_config['password'])
                EMULE_CONFIG.update(saved_config)
                print(f"✓ Configuration aMule chargée depuis {CONFIG_FILE}")
    except Exception as e:
        print(f"⚠️ Impossible de charger la config: {e}")

def save_emule_config():
    """Sauvegarde la configuration dans le fichier JSON"""
    try:
        import json
        # Copie de la config avec mot de passe chiffré
        config_to_save = EMULE_CONFIG.copy()
        config_to_save['password'] = encrypt_password(EMULE_CONFIG['password'])

        with open(CONFIG_FILE, 'w') as f:
            json.dump(config_to_save, f, indent=4)
        print(f"✓ Configuration aMule sauvegardée dans {CONFIG_FILE} (mot de passe chiffré)")
        return True
    except Exception as e:
        print(f"✗ Erreur lors de la sauvegarde: {e}")
        return False

# Charge la config au démarrage
load_emule_config()


@app.route('/covers/<path:filename>')
def serve_cover(filename):
    """Sert les images de couverture"""
    covers_dir = os.path.join(os.path.dirname(DB_FILE), 'covers')
    return send_from_directory(covers_dir, filename)

@app.route('/api/emule/add', methods=['POST'])
def emule_add():
    if not EMULE_CONFIG['enabled']:
        return jsonify({'success': False, 'error': 'eMule/aMule non configuré'}), 400

    try:
        data = request.get_json()
        link = data.get('link')

        if not link:
            return jsonify({'success': False, 'error': 'Lien manquant'}), 400

        if EMULE_CONFIG['type'] == 'amule':
            # aMule via amulecmd
            try:
                import subprocess

                cmd = [
                    'amulecmd',
                    '-h', EMULE_CONFIG['host'],
                    '-P', EMULE_CONFIG['password'],
                    '-p', str(EMULE_CONFIG['ec_port']),
                    '-c', f'add {link}'
                ]

                result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                if result.returncode == 0:
                    return jsonify({'success': True})
                else:
                    print(f"[ERROR] {result.stderr}")
                    return jsonify({'success': False, 'error': result.stderr}), 500

            except FileNotFoundError:
                return jsonify({'success': False, 'error': 'amulecmd introuvable'}), 500
            except subprocess.TimeoutExpired:
                return jsonify({'success': False, 'error': 'Timeout lors de la connexion à aMule'}), 500
            except Exception as e:
                print(f"[ERROR] {str(e)}")
                return jsonify({'success': False, 'error': str(e)}), 500
        else:
            # eMule classique via interface web
            import requests
            from urllib.parse import quote

            encoded_link = quote(link, safe='')
            auth = None
            if EMULE_CONFIG['password']:
                auth = ('', EMULE_CONFIG['password'])

            emule_url = f"http://{EMULE_CONFIG['host']}:{EMULE_CONFIG['port']}/?"
            emule_url += f"ses=&w=&cat=0&c=ed2k&p={encoded_link}"

            response = requests.get(emule_url, auth=auth, timeout=10)

            if response.status_code == 200:
                return jsonify({'success': True})
            else:
                return jsonify({'success': False, 'error': f'HTTP {response.status_code}'}), 500

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'error': str(e)}), 500

def add_link_ec_protocol(link):
    """Ajoute un lien via le protocole EC binaire d'aMule"""
    import socket
    import struct
    import hashlib

    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((EMULE_CONFIG['host'], EMULE_CONFIG['ec_port']))

        # Calcul du hash du mot de passe
        password_hash = hashlib.md5(EMULE_CONFIG['password'].encode()).hexdigest()

        # Construction du paquet EC2 pour ajouter un lien
        link_bytes = link.encode('utf-8')

        # Paquet simple: opcode + longueur + lien
        packet = struct.pack('!BB', 0x20, 0x15)  # FLAGS_ZLIB=0x20, EC_OP_ADD_LINK=0x15
        packet += struct.pack('!H', len(link_bytes))
        packet += link_bytes

        # Envoie le paquet
        sock.send(packet)

        # Attend la réponse
        response = sock.recv(1024)
        sock.close()

        print(f"[DEBUG] Réponse EC (hex): {response.hex()}")

        return jsonify({'success': True})

    except Exception as e:
        print(f"[ERROR] Protocole EC: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/emule/add-multiple', methods=['POST'])
def emule_add_multiple():
    if not EMULE_CONFIG['enabled']:
        return jsonify({'success': False, 'error': 'eMule/aMule non configuré'}), 400

    try:
        data = request.get_json()
        links = data.get('links', [])

        if not links:
            return jsonify({'success': False, 'error': 'Aucun lien fourni'}), 400

        sent = 0
        failed = 0

        if EMULE_CONFIG['type'] == 'amule':
            import subprocess

            print(f"[DEBUG] Envoi de {len(links)} liens via amulecmd...")

            for i, link in enumerate(links, 1):
                try:
                    cmd = [
                        'amulecmd',
                        '-h', EMULE_CONFIG['host'],
                        '-P', EMULE_CONFIG['password'],
                        '-p', str(EMULE_CONFIG['ec_port']),
                        '-c', f'add {link}'
                    ]

                    result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

                    if result.returncode == 0:
                        sent += 1
                        print(f"[DEBUG] [{i}/{len(links)}] ✓")
                    else:
                        failed += 1
                        print(f"[DEBUG] [{i}/{len(links)}] ✗ {result.stderr[:50]}")
                except Exception as e:
                    failed += 1
                    print(f"[DEBUG] [{i}/{len(links)}] ✗ Exception: {str(e)}")
        else:
            # eMule classique
            import requests
            from urllib.parse import quote

            auth = None
            if EMULE_CONFIG['password']:
                auth = ('', EMULE_CONFIG['password'])

            for link in links:
                try:
                    encoded_link = quote(link, safe='')
                    emule_url = f"http://{EMULE_CONFIG['host']}:{EMULE_CONFIG['port']}/?"
                    emule_url += f"ses=&w=&cat=0&c=ed2k&p={encoded_link}"

                    response = requests.get(emule_url, auth=auth, timeout=10)

                    if response.status_code == 200:
                        sent += 1
                    else:
                        failed += 1
                except:
                    failed += 1

        print(f"[DEBUG] Résultat final: {sent} envoyés, {failed} échecs")
        return jsonify({'success': True, 'sent': sent, 'failed': failed})

    except Exception as e:
        print(f"[ERROR] {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/emule/config', methods=['GET', 'POST'])
def emule_config():
    global EMULE_CONFIG

    if request.method == 'GET':
        # Retourne la config actuelle (sans le mot de passe en clair)
        return jsonify({
            'enabled': EMULE_CONFIG['enabled'],
            'type': EMULE_CONFIG['type'],
            'host': EMULE_CONFIG['host'],
            'ec_port': EMULE_CONFIG['ec_port'],
            'password': '****' if EMULE_CONFIG['password'] else ''
        })
    else:
        # Sauvegarde la nouvelle config
        try:
            new_config = request.get_json()

            EMULE_CONFIG['enabled'] = new_config.get('enabled', False)
            EMULE_CONFIG['type'] = new_config.get('type', 'amule')
            EMULE_CONFIG['host'] = new_config.get('host', '127.0.0.1')
            EMULE_CONFIG['ec_port'] = new_config.get('ec_port', 4712)

            # Ne change le mot de passe que s'il n'est pas masqué
            new_password = new_config.get('password', '')
            if new_password and new_password != '****':
                EMULE_CONFIG['password'] = new_password

            # Sauvegarde dans le fichier
            if save_emule_config():
                return jsonify({'success': True, 'message': 'Configuration sauvegardée'})
            else:
                return jsonify({'success': False, 'error': 'Erreur lors de la sauvegarde'}), 500
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/emule/test', methods=['GET'])
def emule_test():
    if not EMULE_CONFIG['enabled']:
        return jsonify({'success': False, 'error': 'aMule non activé'}), 400

    try:
        import subprocess

        # Test avec amulecmd
        cmd = [
            'amulecmd',
            '-h', EMULE_CONFIG['host'],
            '-P', EMULE_CONFIG['password'],
            '-p', str(EMULE_CONFIG['ec_port']),
            '-c', 'status'
        ]

        result = subprocess.run(cmd, capture_output=True, text=True, timeout=10)

        if result.returncode == 0:
            return jsonify({'success': True, 'message': 'Connexion réussie'})
        else:
            return jsonify({'success': False, 'error': result.stderr}), 500

    except FileNotFoundError:
        return jsonify({'success': False, 'error': 'amulecmd introuvable. Installez amule-utils'}), 500
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# ─── API ebdz.net ────────────────────────────────────────────

@app.route('/api/ebdz/config', methods=['GET', 'POST'])
def ebdz_config():
    global EBDZ_CONFIG

    if request.method == 'GET':
        return jsonify({
            'username': EBDZ_CONFIG.get('username', ''),
            'password': '****' if EBDZ_CONFIG.get('password') else '',
            'forums': EBDZ_CONFIG.get('forums', [])
        })
    else:
        try:
            data = request.get_json()

            EBDZ_CONFIG['username'] = data.get('username', '').strip()

            # Ne met à jour le mot de passe que s'il n'est pas masqué
            new_password = data.get('password', '')
            if new_password and new_password != '****':
                EBDZ_CONFIG['password'] = new_password

            # Validation et nettoyage des forums
            forums = []
            for f in data.get('forums', []):
                fid = f.get('fid')
                if fid is None:
                    continue
                forums.append({
                    'fid': int(fid),
                    'category': f.get('category', '').strip() or f'Forum {fid}',
                    'max_pages': int(f['max_pages']) if f.get('max_pages') else None
                })
            EBDZ_CONFIG['forums'] = forums

            if save_ebdz_config():
                return jsonify({'success': True, 'message': 'Configuration ebdz.net sauvegardée'})
            else:
                return jsonify({'success': False, 'error': 'Erreur lors de la sauvegarde'}), 500

        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ebdz/scrape', methods=['POST'])
def ebdz_scrape():
    """Lance le scraper ebdz.net avec la config actuelle.
    Le body JSON peut contenir 'fids': liste de fid à scraper.
    Si absent ou vide, tous les forums configurés sont scrapés.
    """
    try:
        username = EBDZ_CONFIG.get('username', '')
        password = EBDZ_CONFIG.get('password', '')
        all_forums = EBDZ_CONFIG.get('forums', [])

        if not username or not password:
            return jsonify({'success': False, 'error': 'Identifiants non configurés'}), 400

        if not all_forums:
            return jsonify({'success': False, 'error': 'Aucun forum configuré'}), 400

        # Filtrer par les fid envoyés depuis le front (si présents)
        data = request.get_json(silent=True) or {}
        requested_fids = data.get('fids', [])

        if requested_fids:
            forums = [f for f in all_forums if f.get('fid') in requested_fids]
            if not forums:
                return jsonify({'success': False, 'error': 'Aucun forum correspondant aux fid envoyés'}), 400
        else:
            forums = all_forums

        # Import dynamique du scraper
        import importlib.util
        scraper_path = os.path.join(os.path.dirname(__file__), 'scraper.py')
        if not os.path.exists(scraper_path):
            return jsonify({'success': False, 'error': 'scraper.py introuvable dans le répertoire du projet'}), 500

        spec = importlib.util.spec_from_file_location("scraper", scraper_path)
        scraper_module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(scraper_module)

        total_links = 0
        forums_scraped = 0

        for forum_cfg in forums:
            fid = forum_cfg['fid']
            category = forum_cfg['category']
            max_pages = forum_cfg.get('max_pages')

            forum_url = f"https://ebdz.net/forum/forumdisplay.php?fid={fid}"

            print(f"\n📂 Scraping forum fid={fid} catégorie='{category}'...")

            scraper = scraper_module.MyBBScraper(
                base_url=forum_url,
                db_file=DB_FILE,
                username=username,
                password=password,
                forum_category=category
            )

            scraper.run(max_pages=max_pages)
            forums_scraped += 1

            # Compter les liens pour cette catégorie
            conn = sqlite3.connect(DB_FILE)
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


if __name__ == '__main__':
    print("=" * 60)
    print("Gestionnaire Multi-Bibliothèques Manga")
    print("=" * 60)
    print("Accédez à http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
