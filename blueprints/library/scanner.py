"""
Scanner pour analyser les bibliothèques de mangas
"""
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
from flask import current_app


class LibraryScanner:
    def __init__(self, db_path=None):
        if db_path is None:
            db_path = current_app.config['DATABASE']
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
                r'\s(\d{1,2})\s*(?:\(|\[)',       # 01 ( ou 01 [ - nombre avant parenthèse/crochet
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
            # Essayer progressivement différents patterns pour extraire le titre
            title_patterns = [
                r'^(.+?)\s+(?:Tome|T[\s\.]?\d+|Vol|Volume|v[\s\.]?\d+|#\d+|-\s*\d+)',  # Patterns explicites
                r'^(.+?)\s+(\d{1,2})\s*(?:\(|\[)',  # Titre avant nombre + parenthèse/crochet (ex: "Golden kamui 01 (Noda)")
            ]
            title_match = None
            for pattern in title_patterns:
                title_match = re.match(pattern, normalized_name, re.IGNORECASE)
                if title_match:
                    break

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

        # Vérifier que le chemin existe et est bien un répertoire
        if not os.path.exists(library_path):
            raise Exception(f"Le chemin n'existe pas: '{library_path}'")
        
        if not os.path.isdir(library_path):
            raise Exception(f"Le chemin n'est pas un répertoire: '{library_path}'")

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
            raise Exception(f"Permission refusée pour accéder à: '{library_path}'")
        except (FileNotFoundError, NotADirectoryError, OSError) as e:
            raise Exception(f"Impossible d'accéder au répertoire '{library_path}': {str(e)}")
        
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
                except (PermissionError, OSError) as e:
                    print(f"⚠️  Impossible d'accéder à la série '{series_title}' ('{item_path}'): {str(e)}")
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

        # ===== FIX: Supprimer les séries qui ne sont plus sur le disque =====
        # Récupérer toutes les séries actuellement en base de données pour cette bibliothèque
        cursor.execute('''
            SELECT id, title FROM series WHERE library_id = ?
        ''', (library_id,))
        
        series_in_db = {row[1]: row[0] for row in cursor.fetchall()}  # {title: id}
        series_on_disk = set(series_data.keys())  # Titres des séries trouvées sur disque
        
        # Trouver les séries en base de données qui n'existent plus sur disque
        orphaned_series = set(series_in_db.keys()) - series_on_disk
        
        # Supprimer les séries orphelines (les volumes seront supprimés en cascade)
        for orphaned_title in orphaned_series:
            series_id = series_in_db[orphaned_title]
            try:
                cursor.execute('DELETE FROM series WHERE id = ?', (series_id,))
                print(f"  🗑️  Série supprimée (répertoire absent): {orphaned_title}")
            except Exception as e:
                print(f"  ⚠️  Erreur lors de la suppression de '{orphaned_title}': {e}")
        # ====================================================================

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
