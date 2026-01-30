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
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

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
        year_match = re.search(r'\((\d{4})\)', filename)
        if year_match:
            info['year'] = int(year_match.group(1))

        # Extraire la résolution
        resolution_match = re.search(r'\[(?:Digital-)?(\d{3,4}[up]?(?:x\d{3,4})?)\]', filename)
        if resolution_match:
            info['resolution'] = resolution_match.group(1)

        return info

    def get_page_count(self, filepath, file_format):
        """Récupère le nombre de pages d'un fichier"""
        try:
            if file_format == 'pdf':
                reader = PdfReader(filepath)
                return len(reader.pages)

            elif file_format in ['cbz', 'zip']:
                with ZipFile(filepath, 'r') as zf:
                    image_files = [f for f in zf.namelist()
                                 if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))]
                    return len(image_files)

            elif file_format in ['cbr', 'rar']:
                with rarfile.RarFile(filepath, 'r') as rf:
                    image_files = [f for f in rf.namelist()
                                 if f.lower().endswith(('.jpg', '.jpeg', '.png', '.gif', '.webp'))]
                    return len(image_files)

            elif file_format == 'epub':
                book = epub.read_epub(filepath)
                items = list(book.get_items_of_type(ebooklib.ITEM_DOCUMENT))
                return len(items)

        except Exception as e:
            print(f"Erreur lors du comptage des pages de {filepath}: {e}")
            return 0

        return 0

    def scan_directory(self, library_id, library_path):
        """Scanne un répertoire de bibliothèque"""
        print(f"Scan de {library_path}...")

        series_data = defaultdict(list)

        # Parcourir tous les fichiers
        for root, dirs, files in os.walk(library_path):
            for filename in files:
                if filename.lower().endswith(('.pdf', '.cbz', '.cbr', '.epub', '.zip', '.rar')):
                    filepath = os.path.join(root, filename)
                    info = self.parse_filename(filename)

                    # Déterminer le nom de la série
                    series_name = os.path.basename(root) if root != library_path else info['title']

                    # Ajouter les informations du fichier
                    volume_info = {
                        'filename': filename,
                        'filepath': filepath,
                        'part_number': info['part_number'],
                        'part_name': info['part_name'],
                        'volume': info['volume'],
                        'author': info['author'],
                        'year': info['year'],
                        'resolution': info['resolution'],
                        'format': info['format'],
                        'file_size': os.path.getsize(filepath),
                        'page_count': self.get_page_count(filepath, info['format'])
                    }

                    series_data[series_name].append(volume_info)

        # Enregistrer dans la base de données
        self.save_to_database(library_id, series_data, library_path)

        return series_data

    def save_to_database(self, library_id, series_data, library_path):
        """Enregistre les données dans la base de données"""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Supprimer les anciennes données pour cette bibliothèque
        cursor.execute('DELETE FROM series WHERE library_id = ?', (library_id,))

        for series_name, volumes in series_data.items():
            # Vérifier si la série a des parties/arcs
            has_parts = any(v['part_number'] is not None for v in volumes)

            # Grouper par parties si applicable
            if has_parts:
                parts = defaultdict(list)
                for vol in volumes:
                    part_key = vol['part_number'] if vol['part_number'] else 0
                    parts[part_key].append(vol)

                # Calculer les volumes manquants par partie
                all_missing = []
                for part_num in sorted(parts.keys()):
                    part_volumes = parts[part_num]
                    volume_numbers = sorted([v['volume'] for v in part_volumes if v['volume'] is not None])

                    if volume_numbers:
                        for i in range(min(volume_numbers), max(volume_numbers) + 1):
                            if i not in volume_numbers:
                                all_missing.append(f"Part {part_num} - T{i}")
            else:
                # Calculer les volumes manquants normalement
                volume_numbers = sorted([v['volume'] for v in volumes if v['volume'] is not None])
                all_missing = []

                if volume_numbers:
                    for i in range(min(volume_numbers), max(volume_numbers) + 1):
                        if i not in volume_numbers:
                            all_missing.append(i)

            # Insérer la série
            cursor.execute('''
                INSERT INTO series (library_id, title, path, total_volumes, missing_volumes, has_parts)
                VALUES (?, ?, ?, ?, ?, ?)
            ''', (library_id, series_name, library_path, len(volumes), json.dumps(all_missing), 1 if has_parts else 0))

            series_id = cursor.lastrowid

            # Insérer les volumes
            for vol in volumes:
                cursor.execute('''
                    INSERT INTO volumes
                    (series_id, part_number, part_name, volume_number, filename, filepath, author, year,
                     resolution, file_size, page_count, format)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', (
                    series_id, vol['part_number'], vol['part_name'], vol['volume'],
                    vol['filename'], vol['filepath'], vol['author'], vol['year'],
                    vol['resolution'], vol['file_size'], vol['page_count'], vol['format']
                ))

        # Mettre à jour la date de scan de la bibliothèque
        cursor.execute('UPDATE libraries SET last_scanned = CURRENT_TIMESTAMP WHERE id = ?', (library_id,))

        conn.commit()
        conn.close()
        print(f"Sauvegarde terminée: {len(series_data)} séries enregistrées")

# Instance du scanner
scanner = LibraryScanner()

@app.route('/')
def index():
    """Page d'accueil - Liste des bibliothèques"""
    return render_template('index.html')

@app.route('/library/<int:library_id>')
def view_library(library_id):
    """Page d'affichage d'une bibliothèque"""
    return render_template('library.html', library_id=library_id)

@app.route('/import')
def import_view():
    """Page d'import de mangas"""
    return render_template('import.html')

@app.route('/settings')
def settings():
    """Page de configuration de l'application"""
    return render_template('settings.html')

# API - Gestion des bibliothèques

@app.route('/api/libraries', methods=['GET'])
def get_libraries():
    """Récupère toutes les bibliothèques"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT l.*,
               COUNT(DISTINCT s.id) as series_count,
               COUNT(v.id) as volumes_count
        FROM libraries l
        LEFT JOIN series s ON l.id = s.library_id
        LEFT JOIN volumes v ON s.id = v.series_id
        GROUP BY l.id
        ORDER BY l.name
    ''')

    libraries = []
    for row in cursor.fetchall():
        libraries.append({
            'id': row['id'],
            'name': row['name'],
            'path': row['path'],
            'description': row['description'],
            'created_at': row['created_at'],
            'last_scanned': row['last_scanned'],
            'series_count': row['series_count'],
            'volumes_count': row['volumes_count']
        })

    conn.close()
    return jsonify(libraries)

@app.route('/api/libraries/<int:library_id>', methods=['GET'])
def get_library(library_id):
    """Récupère une bibliothèque spécifique"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM libraries WHERE id = ?', (library_id,))
    library = cursor.fetchone()

    if not library:
        conn.close()
        return jsonify({'error': 'Bibliothèque non trouvée'}), 404

    result = {
        'id': library['id'],
        'name': library['name'],
        'path': library['path'],
        'description': library['description'],
        'created_at': library['created_at'],
        'last_scanned': library['last_scanned']
    }

    conn.close()
    return jsonify(result)

@app.route('/api/libraries', methods=['POST'])
def create_library():
    """Crée une nouvelle bibliothèque"""
    data = request.json

    if not data.get('name') or not data.get('path'):
        return jsonify({'error': 'Nom et chemin requis'}), 400

    if not os.path.exists(data['path']):
        return jsonify({'error': 'Le chemin spécifié n\'existe pas'}), 400

    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute('''
            INSERT INTO libraries (name, path, description)
            VALUES (?, ?, ?)
        ''', (data['name'], data['path'], data.get('description', '')))

        library_id = cursor.lastrowid
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'library_id': library_id,
            'message': 'Bibliothèque créée avec succès'
        })

    except sqlite3.IntegrityError:
        return jsonify({'error': 'Une bibliothèque avec ce nom existe déjà'}), 400
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/libraries/<int:library_id>', methods=['DELETE'])
def delete_library(library_id):
    """Supprime une bibliothèque"""
    try:
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        cursor.execute('DELETE FROM libraries WHERE id = ?', (library_id,))

        if cursor.rowcount == 0:
            conn.close()
            return jsonify({'error': 'Bibliothèque non trouvée'}), 404

        conn.commit()
        conn.close()

        return jsonify({'success': True, 'message': 'Bibliothèque supprimée'})

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/scan/<int:library_id>')
def scan_library(library_id):
    """Scanne une bibliothèque spécifique"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM libraries WHERE id = ?', (library_id,))
    library = cursor.fetchone()
    conn.close()

    if not library:
        return jsonify({'error': 'Bibliothèque non trouvée'}), 404

    if not os.path.exists(library['path']):
        return jsonify({'error': 'Chemin de bibliothèque inexistant'}), 404

    try:
        series_data = scanner.scan_directory(library_id, library['path'])
        return jsonify({
            'success': True,
            'series_count': len(series_data),
            'message': f'{len(series_data)} séries scannées'
        })
    except Exception as e:
        import traceback
        print("=" * 60)
        print("ERREUR LORS DU SCAN:")
        print(traceback.format_exc())
        print("=" * 60)
        return jsonify({'error': str(e)}), 500

# API - Séries et volumes

@app.route('/api/library/<int:library_id>/series')
def get_library_series(library_id):
    """Récupère toutes les séries d'une bibliothèque"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('''
        SELECT s.*, COUNT(v.id) as volume_count
        FROM series s
        LEFT JOIN volumes v ON s.id = v.series_id
        WHERE s.library_id = ?
        GROUP BY s.id
        ORDER BY s.title
    ''', (library_id,))

    series = []
    for row in cursor.fetchall():
        series.append({
            'id': row['id'],
            'title': row['title'],
            'total_volumes': row['total_volumes'],
            'missing_volumes': json.loads(row['missing_volumes']) if row['missing_volumes'] else [],
            'last_scanned': row['last_scanned']
        })

    conn.close()
    return jsonify(series)

@app.route('/api/series/<int:series_id>')
def get_series_details(series_id):
    """Récupère les détails d'une série"""
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()

    cursor.execute('SELECT * FROM series WHERE id = ?', (series_id,))
    series = cursor.fetchone()

    if not series:
        conn.close()
        return jsonify({'error': 'Série non trouvée'}), 404

    cursor.execute('''
        SELECT * FROM volumes
        WHERE series_id = ?
        ORDER BY part_number, volume_number
    ''', (series_id,))

    volumes = []
    parts = defaultdict(list)
    has_parts = series['has_parts']

    for row in cursor.fetchall():
        volume_data = {
            'id': row['id'],
            'part_number': row['part_number'],
            'part_name': row['part_name'],
            'volume_number': row['volume_number'],
            'filename': row['filename'],
            'author': row['author'],
            'year': row['year'],
            'resolution': row['resolution'],
            'file_size': row['file_size'],
            'page_count': row['page_count'],
            'format': row['format']
        }

        if has_parts and row['part_number'] is not None:
            parts[row['part_number']].append(volume_data)
        else:
            volumes.append(volume_data)

    conn.close()

    result = {
        'title': series['title'],
        'total_volumes': series['total_volumes'],
        'missing_volumes': json.loads(series['missing_volumes']) if series['missing_volumes'] else [],
        'has_parts': bool(has_parts)
    }

    if has_parts:
        result['parts'] = {}
        for part_num in sorted(parts.keys()):
            part_volumes = parts[part_num]
            part_name = part_volumes[0]['part_name'] if part_volumes and part_volumes[0]['part_name'] else f"Part {part_num}"
            result['parts'][part_num] = {
                'name': part_name,
                'volumes': part_volumes
            }
    else:
        result['volumes'] = volumes

    return jsonify(result)

@app.route('/api/library/<int:library_id>/stats')
def get_library_stats(library_id):
    """Récupère les statistiques d'une bibliothèque"""
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()

    cursor.execute('''
        SELECT
            COUNT(DISTINCT s.id) as total_series,
            COUNT(v.id) as total_volumes,
            SUM(v.file_size) as total_size,
            AVG(v.page_count) as avg_pages
        FROM series s
        LEFT JOIN volumes v ON s.id = v.series_id
        WHERE s.library_id = ?
    ''', (library_id,))

    stats = cursor.fetchone()
    conn.close()

    return jsonify({
        'total_series': stats[0] or 0,
        'total_volumes': stats[1] or 0,
        'total_size': stats[2] or 0,
        'avg_pages': round(stats[3] or 0, 1)
    })

# API - Import de fichiers

@app.route('/api/import/scan', methods=['POST'])
def scan_import_directory():
    """Scanne un répertoire d'import pour trouver les fichiers manga"""
    data = request.json
    import_path = data.get('path', '')

    if not import_path or not os.path.exists(import_path):
        return jsonify({'error': 'Chemin invalide ou inexistant'}), 400

    try:
        files = []

        # Parcourir tous les fichiers du répertoire
        for root, dirs, filenames in os.walk(import_path):
            # Ignorer les répertoires spéciaux
            dirs[:] = [d for d in dirs if d not in ['_old_files', '_doublons']]

            for filename in filenames:
                if filename.lower().endswith(('.pdf', '.cbz', '.cbr', '.epub', '.zip', '.rar')):
                    filepath = os.path.join(root, filename)

                    # Parser le nom de fichier
                    parsed = scanner.parse_filename(filename)

                    file_info = {
                        'filename': filename,
                        'filepath': filepath,
                        'file_size': os.path.getsize(filepath),
                        'parsed': {
                            'title': parsed['title'],
                            'volume': parsed['volume'],
                            'part_number': parsed['part_number'],
                            'part_name': parsed['part_name'],
                            'author': parsed['author'],
                            'year': parsed['year'],
                            'resolution': parsed['resolution'],
                            'format': parsed['format']
                        },
                        'destination': None
                    }

                    files.append(file_info)

        return jsonify({
            'success': True,
            'files': files,
            'count': len(files)
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/import/execute', methods=['POST'])
def execute_import():
    """Exécute l'import des fichiers vers leurs destinations"""
    data = request.json
    files_to_import = data.get('files', [])
    import_base_path = data.get('import_path', '')

    if not files_to_import:
        return jsonify({'error': 'Aucun fichier à importer'}), 400

    imported_count = 0
    replaced_count = 0
    skipped_count = 0
    failed_count = 0
    failures = []

    # Créer les répertoires spéciaux dans le répertoire d'import
    if import_base_path:
        old_files_dir = os.path.join(import_base_path, '_old_files')
        doublons_dir = os.path.join(import_base_path, '_doublons')
        os.makedirs(old_files_dir, exist_ok=True)
        os.makedirs(doublons_dir, exist_ok=True)

    try:
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
                conn = sqlite3.connect(DATABASE)
                cursor = conn.cursor()

                if destination.get('is_new_series'):
                    # Créer une nouvelle série
                    series_title = destination['series_title']
                    library_id = destination['library_id']
                    library_path = destination['library_path']

                    # Créer le dossier de la série
                    series_path = os.path.join(library_path, series_title)
                    os.makedirs(series_path, exist_ok=True)

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

                    # Récupérer le chemin de la série
                    cursor.execute('SELECT path FROM series WHERE id = ?', (series_id,))
                    result = cursor.fetchone()

                    if result and result[0]:
                        target_dir = result[0]
                    else:
                        # Pas de chemin défini, utiliser le nom de la série dans la bibliothèque
                        library_path = destination['library_path']
                        series_title = destination['series_title']
                        target_dir = os.path.join(library_path, series_title)
                        os.makedirs(target_dir, exist_ok=True)

                        # Mettre à jour le chemin de la série
                        cursor.execute('UPDATE series SET path = ? WHERE id = ?', (target_dir, series_id))

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
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()

        # Récupérer toutes les séries uniques qui ont reçu des fichiers
        series_ids = set()
        for file_data in files_to_import:
            dest = file_data.get('destination')
            if dest and dest.get('series_id'):
                series_ids.add(dest['series_id'])

        # Mettre à jour chaque série
        for series_id in series_ids:
            scanner.update_series_stats(series_id)

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


@app.route('/search')
def searchebdz():
    connection = sqlite3.connect(DB_FILE)
    cursor = connection.cursor()

    # Compte total des liens
    cursor.execute("SELECT COUNT(*) FROM ed2k_links")
    total_links = cursor.fetchone()[0]

    # Compte total des threads uniques
    cursor.execute("SELECT COUNT(DISTINCT thread_id) FROM ed2k_links")
    total_threads = cursor.fetchone()[0]

    # Récupère les catégories uniques
    cursor.execute("SELECT DISTINCT forum_category FROM ed2k_links WHERE forum_category IS NOT NULL")
    categories = [row[0] for row in cursor.fetchall()]

    connection.close()

    return render_template('search.html',
                         total_links=total_links,
                         total_threads=total_threads,
                         categories=categories)

@app.route('/api/search')
def search():
    query = request.args.get('query', '')
    volume = request.args.get('volume', '')
    category = request.args.get('category', '')

    connection = sqlite3.connect(DB_FILE)
    connection.row_factory = sqlite3.Row
    cursor = connection.cursor()

    sql = "SELECT * FROM ed2k_links WHERE 1=1"
    params = []

    if query:
        sql += " AND (filename LIKE ? OR thread_title LIKE ?)"
        search_term = f"%{query}%"
        params.extend([search_term, search_term])

    if volume:
        sql += " AND volume = ?"
        params.append(int(volume))

    if category:
        sql += " AND forum_category = ?"
        params.append(category)

    sql += " ORDER BY thread_title, volume, filename"

    cursor.execute(sql, params)
    results = [dict(row) for row in cursor.fetchall()]
    connection.close()

    return jsonify({'results': results})

@app.route('/covers/<path:filename>')
def serve_cover(filename):
    return send_from_directory('./data/covers', filename)

@app.route('/api/emule/add', methods=['POST'])
def emule_add():
    if not EMULE_CONFIG['enabled']:
        return jsonify({'success': False, 'error': 'aMule non activé'}), 400

    try:
        data = request.get_json()
        link = data.get('link')

        if not link:
            return jsonify({'success': False, 'error': 'Aucun lien fourni'}), 400

        if EMULE_CONFIG['type'] == 'amule':
            import subprocess

            try:
                # Essaie d'abord avec amulecmd
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
                    print(f"[ERROR] amulecmd failed: {result.stderr}")
                    raise Exception(result.stderr)
            except FileNotFoundError:
                print("[WARNING] amulecmd non trouvé, utilisation du protocole EC")
                # Fallback: utilise le protocole EC binaire simplifié
                return add_link_ec_protocol(link)
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
