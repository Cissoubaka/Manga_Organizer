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
                r'\s(\d+)$'                       # 08 (juste un nombre à la fin)
            ]

            for pattern in volume_patterns:
                match = re.search(pattern, normalized_name, re.IGNORECASE)
                if match:
                    info['volume'] = int(match.group(1))
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

            print(f"  ✓ {series_title}: {total_volumes} volumes")

        # Mettre à jour la date de scan de la bibliothèque
        cursor.execute('''
            UPDATE libraries
            SET last_scanned = CURRENT_TIMESTAMP
            WHERE id = ?
        ''', (library_id,))

        conn.commit()
        conn.close()

        return len(series_data)

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

# ROUTES WEB
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


if __name__ == '__main__':
    print("=" * 60)
    print("Gestionnaire Multi-Bibliothèques Manga")
    print("=" * 60)
    print("Accédez à http://localhost:5000")
    print("=" * 60)
    app.run(debug=True, host='0.0.0.0', port=5000, use_reloader=False)
