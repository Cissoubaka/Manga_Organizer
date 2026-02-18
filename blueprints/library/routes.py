"""
Routes pour la gestion des bibliothèques
"""
from flask import render_template, request, jsonify, current_app
from . import library_bp
from .scanner import LibraryScanner
import sqlite3
import json
import os
import time
import shutil


def get_db_connection():
    """Retourne une connexion à la base de données"""
    conn = sqlite3.connect(current_app.config['DATABASE'], timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


# ========== ROUTES HTML ==========

@library_bp.route('/nautiljon')
def nautiljon_page():
    """Page d'enrichissement Nautiljon"""
    return render_template('nautiljon.html')


@library_bp.route('/')
def index():
    """Page d'accueil - Liste des bibliothèques"""
    return render_template('index.html')


@library_bp.route('/library/<int:library_id>')
def library_detail(library_id):
    """Détails d'une bibliothèque"""
    return render_template('library.html', library_id=library_id)


@library_bp.route('/import')
def import_page():
    """Page d'import de mangas"""
    return render_template('import.html')


@library_bp.route('/transfer')
def transfer_page():
    """Page de transfert de séries entre bibliothèques"""
    return render_template('transfer.html')


# ========== API ==========

@library_bp.route('/api/libraries', methods=['GET', 'POST'])
def libraries():
    """Liste ou crée des bibliothèques"""
    
    if request.method == 'GET':
        # Lister toutes les bibliothèques
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                l.id,
                l.name,
                l.path,
                l.description,
                l.created_at,
                l.last_scanned,
                COUNT(DISTINCT s.id) as series_count,
                COUNT(v.id) as volumes_count
            FROM libraries l
            LEFT JOIN series s ON s.library_id = l.id
            LEFT JOIN volumes v ON v.series_id = s.id
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
    
    else:  # POST
        # Créer une nouvelle bibliothèque
        data = request.get_json()
        name = data.get('name')
        path = data.get('path')
        description = data.get('description', '')
        
        if not name or not path:
            return jsonify({'success': False, 'error': 'Nom et chemin requis'}), 400
        
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO libraries (name, path, description)
                VALUES (?, ?, ?)
            ''', (name, path, description))
            
            library_id = cursor.lastrowid
            conn.commit()
            conn.close()
            
            return jsonify({'success': True, 'id': library_id})
        
        except sqlite3.IntegrityError:
            return jsonify({'success': False, 'error': 'Une bibliothèque avec ce nom existe déjà'}), 400
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


@library_bp.route('/api/libraries/<int:library_id>', methods=['GET', 'DELETE'])
def library_operations(library_id):
    """Récupère ou supprime une bibliothèque"""
    
    if request.method == 'GET':
        # Détails de la bibliothèque
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT * FROM libraries WHERE id = ?', (library_id,))
        library = cursor.fetchone()
        
        if not library:
            conn.close()
            return jsonify({'error': 'Bibliothèque non trouvée'}), 404
        
        # Récupérer les séries
        cursor.execute('''
            SELECT * FROM series WHERE library_id = ?
            ORDER BY title
        ''', (library_id,))
        
        series_list = []
        for row in cursor.fetchall():
            series_list.append(dict(row))
        
        conn.close()
        
        return jsonify({
            'id': library['id'],
            'name': library['name'],
            'path': library['path'],
            'description': library['description'],
            'series': series_list
        })
    
    else:  # DELETE
        try:
            conn = get_db_connection()
            cursor = conn.cursor()
            
            cursor.execute('DELETE FROM libraries WHERE id = ?', (library_id,))
            
            conn.commit()
            conn.close()
            
            return jsonify({'success': True})
        
        except Exception as e:
            return jsonify({'success': False, 'error': str(e)}), 500


@library_bp.route('/api/scan/<int:library_id>', methods=['GET', 'POST'])
def scan_library(library_id):
    """Scanne une bibliothèque (détecte séries et volumes, sans enrichissement)"""
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT name, path FROM libraries WHERE id = ?', (library_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({'success': False, 'error': 'Bibliothèque non trouvée'}), 404
        
        library_name = result['name']
        library_path = result['path']
        
        # Vérifier que le chemin est accessible avant de scanner
        if not os.path.exists(library_path):
            return jsonify({
                'success': False, 
                'error': f'Le dossier de la bibliothèque "{library_name}" n\'existe pas ou n\'est pas accessible.\nChemin: {library_path}'
            }), 400
        
        if not os.path.isdir(library_path):
            return jsonify({
                'success': False, 
                'error': f'Le chemin n\'est pas un répertoire: {library_path}'
            }), 400
        
        # Scanner sans enrichissement (voir bouton d'enrichissement séparé)
        scanner = LibraryScanner()
        series_count = scanner.scan_directory(library_id, library_path, auto_enrich=False)
        
        return jsonify({'success': True, 'series_count': series_count})
    
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Erreur lors du scan de la bibliothèque {library_id}: {error_msg}")
        return jsonify({
            'success': False, 
            'error': f'Erreur lors du scan: {error_msg}'
        }), 500


@library_bp.route('/api/library/<int:library_id>/enrich', methods=['POST'])
def enrich_library(library_id):
    """Enrichit toutes les séries sans infos Nautiljon d'une bibliothèque"""
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Récupérer toutes les séries sans infos Nautiljon
        cursor.execute('''
            SELECT id, title FROM series
            WHERE library_id = ? AND nautiljon_url IS NULL
            ORDER BY title
        ''', (library_id,))
        
        series_list = cursor.fetchall()
        conn.close()
        
        if not series_list:
            return jsonify({
                'success': True,
                'message': 'Aucune série à enrichir',
                'enriched_count': 0
            })
        
        # Importer le scraper Nautiljon
        from blueprints.nautiljon.scraper import NautiljonScraper, NautiljonDatabase
        import logging
        logger = logging.getLogger(__name__)
        
        scraper = NautiljonScraper()
        db_manager = NautiljonDatabase(current_app.config['DATABASE'])
        
        enriched_count = 0
        failed_count = 0
        
        for series_id, series_title in series_list:
            try:
                # Chercher les infos Nautiljon
                info = scraper.search_and_get_best_match(series_title)
                
                if info:
                    # Sauvegarder les infos
                    db_manager.update_series_nautiljon_info(series_id, info)
                    enriched_count += 1
                    print(f"✓ Enrichi: {series_title}")
                else:
                    failed_count += 1
                    print(f"⚠️ Pas trouvé: {series_title}")
            except Exception as e:
                failed_count += 1
                logger.error(f"Erreur enrichissement {series_title}: {e}")
                print(f"❌ Erreur: {series_title} - {e}")
            
            # Respecter les délais pour éviter de surcharger Nautiljon
            time.sleep(5)
        
        return jsonify({
            'success': True,
            'enriched_count': enriched_count,
            'failed_count': failed_count,
            'total': len(series_list),
            'message': f'Enrichissement terminé: {enriched_count} séries enrichies, {failed_count} non trouvées'
        })
    
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Erreur enrichissement bibliothèque {library_id}: {error_msg}")
        return jsonify({
            'success': False,
            'error': f'Erreur lors de l\'enrichissement: {error_msg}'
        }), 500


@library_bp.route('/api/series/<int:series_id>/volumes', methods=['GET'])
def get_series_volumes(series_id):
    """Récupère tous les volumes d'une série"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT * FROM volumes
        WHERE series_id = ?
        ORDER BY part_number, volume_number
    ''', (series_id,))
    
    volumes = []
    for row in cursor.fetchall():
        volumes.append(dict(row))
    
    conn.close()
    
    return jsonify(volumes)

@library_bp.route('/api/library/<int:library_id>/series')
def get_library_series(library_id):
    try:
        conn = sqlite3.connect(current_app.config['DATABASE'])
        cursor = conn.cursor()

        # Récupérer toutes les séries avec les données Nautiljon
        cursor.execute('''
            SELECT id, title, path, total_volumes, missing_volumes, has_parts, last_scanned,
                   nautiljon_status, nautiljon_total_volumes, nautiljon_url, nautiljon_cover_path
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
                'last_scanned': row[6],
                'nautiljon_status': row[7],
                'nautiljon_total_volumes': row[8],
                'nautiljon_url': row[9],
                'nautiljon_cover_path': row[10]
            })

        conn.close()
        return jsonify(series_list)

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@library_bp.route('/api/series/<int:series_id>')
def get_series_details(series_id):
    try:
        conn = sqlite3.connect(current_app.config['DATABASE'])
        cursor = conn.cursor()

        # Récupérer les infos de la série avec les données Nautiljon
        cursor.execute('''
            SELECT s.id, s.title, s.path, s.total_volumes, s.missing_volumes, s.has_parts,
                   l.id, l.name,
                   s.nautiljon_url, s.nautiljon_cover_path, s.nautiljon_total_volumes, s.nautiljon_french_volumes,
                   s.nautiljon_editor, s.nautiljon_status, s.nautiljon_mangaka,
                   s.nautiljon_year_start, s.nautiljon_year_end, s.nautiljon_updated_at
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
            'nautiljon': {
                'url': series_row[8],
                'cover_path': series_row[9],
                'total_volumes': series_row[10],
                'french_volumes': series_row[11],
                'editor': series_row[12],
                'status': series_row[13],
                'mangaka': series_row[14],
                'year_start': series_row[15],
                'year_end': series_row[16],
                'updated_at': series_row[17]
            },
            'volumes': volumes
        })

    except Exception as e:
        return jsonify({'error': str(e)}), 500

@library_bp.route('/api/library/<int:library_id>/stats')
def get_library_stats_route(library_id):
    """Récupère les statistiques détaillées d'une bibliothèque"""
    try:
        conn = sqlite3.connect(current_app.config['DATABASE'])
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

@library_bp.route('/api/libraries/<int:library_id>')
def get_library_info(library_id):
    """Récupère les informations d'une bibliothèque spécifique"""
    try:
        conn = sqlite3.connect(current_app.config['DATABASE'])
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
    
    ###### ROUTE IMPORT ########

@library_bp.route('/api/import/scan', methods=['POST'])
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

@library_bp.route('/api/import/execute', methods=['POST'])
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
                conn = sqlite3.connect(current_app.config['DATABASE'], timeout=30)
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
                    # ===== FIX: Enregistrer le series_id dans destination pour mise à jour ultérieure =====
                    destination['series_id'] = series_id
                    # =============================
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
        conn = sqlite3.connect(current_app.config['DATABASE'], timeout=30.0)
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


# ========== ROUTES DE TRANSFERT DE SÉRIES ==========

@library_bp.route('/api/transfer/series/<int:library_id>', methods=['GET'])
def get_transfer_series(library_id):
    """Récupère les séries d'une bibliothèque pour le transfert"""
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT id, name FROM libraries WHERE id = ?', (library_id,))
    library = cursor.fetchone()
    
    if not library:
        conn.close()
        return jsonify({'error': 'Bibliothèque non trouvée'}), 404
    
    cursor.execute('''
        SELECT 
            id, 
            title, 
            total_volumes,
            missing_volumes,
            tags,
            nautiljon_total_volumes,
            nautiljon_status
        FROM series 
        WHERE library_id = ?
        ORDER BY title
    ''', (library_id,))
    
    series_list = []
    for row in cursor.fetchall():
        # Parsage des tags (JSON array stocké en texte)
        tags = []
        if row['tags']:
            try:
                tags = json.loads(row['tags'])
            except (json.JSONDecodeError, TypeError):
                tags = []
        
        # Parsage du missing_volumes (JSON array)
        missing_volumes = []
        if row['missing_volumes']:
            try:
                missing_volumes = json.loads(row['missing_volumes'])
            except (json.JSONDecodeError, TypeError):
                missing_volumes = []
        
        series_list.append({
            'id': row['id'],
            'title': row['title'],
            'total_volumes': row['total_volumes'],
            'missing_volumes': missing_volumes,
            'tags': tags,
            'nautiljon_total_volumes': row['nautiljon_total_volumes'],
            'nautiljon_status': row['nautiljon_status']
        })
    
    conn.close()
    
    return jsonify({
        'library_id': library_id,
        'library_name': library['name'],
        'series': series_list
    })


@library_bp.route('/api/transfer/move', methods=['POST'])
def move_series():
    """Transfère une série d'une bibliothèque à une autre (fichiers + BD)"""
    data = request.get_json()
    
    series_id = data.get('series_id')
    from_library_id = data.get('from_library_id')
    to_library_id = data.get('to_library_id')
    
    if not all([series_id, from_library_id, to_library_id]):
        return jsonify({'error': 'Paramètres manquants'}), 400
    
    if from_library_id == to_library_id:
        return jsonify({'error': 'Les bibliothèques doivent être différentes'}), 400
    
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Récupérer les infos de la série
        cursor.execute('''
            SELECT id, library_id, title, path FROM series WHERE id = ?
        ''', (series_id,))
        series = cursor.fetchone()
        
        if not series:
            conn.close()
            return jsonify({'error': 'Série non trouvée'}), 404
        
        if series['library_id'] != from_library_id:
            conn.close()
            return jsonify({'error': 'La série n\'appartient pas à cette bibliothèque'}), 400
        
        # Récupérer les infos des deux bibliothèques
        cursor.execute('''
            SELECT id, path FROM libraries WHERE id IN (?, ?)
        ''', (from_library_id, to_library_id))
        
        libraries = {}
        for lib in cursor.fetchall():
            libraries[lib['id']] = lib['path']
        
        if len(libraries) != 2:
            conn.close()
            return jsonify({'error': 'Une ou plusieurs bibliothèques n\'existent pas'}), 404
        
        from_lib_path = libraries[from_library_id]
        to_lib_path = libraries[to_library_id]
        
        # Construire les chemins source et destination
        # Si le chemin n'existe pas en BD, on le reconstruit
        if series['path']:
            old_series_path = series['path']
        else:
            old_series_path = os.path.join(from_lib_path, series['title'])
        
        new_series_path = os.path.join(to_lib_path, series['title'])
        
        # Vérifier que le chemin source existe
        if not os.path.exists(old_series_path):
            conn.close()
            return jsonify({
                'error': f'Le dossier de la série n\'existe pas: {old_series_path}'
            }), 400
        
        try:
            # Créer le dossier destination s'il n'existe pas
            os.makedirs(to_lib_path, exist_ok=True)
            
            # Vérifier que la destination n'existe pas déjà
            if os.path.exists(new_series_path):
                conn.close()
                return jsonify({
                    'error': f'Une série avec ce nom existe déjà dans la destination'
                }), 400
            
            # Déplacer le dossier de la série
            shutil.move(old_series_path, new_series_path)
            
            # Mettre à jour le chemin de la série en BD
            cursor.execute('''
                UPDATE series SET library_id = ?, path = ? WHERE id = ?
            ''', (to_library_id, new_series_path, series_id))
            
            # Récupérer et mettre à jour les chemins de tous les volumes
            cursor.execute('''
                SELECT id, filepath FROM volumes WHERE series_id = ?
            ''', (series_id,))
            
            volumes = cursor.fetchall()
            for volume in volumes:
                old_volume_path = volume['filepath']
                # Remplacer le chemin source par le chemin destination
                new_volume_path = old_volume_path.replace(old_series_path, new_series_path, 1)
                
                cursor.execute('''
                    UPDATE volumes SET filepath = ? WHERE id = ?
                ''', (new_volume_path, volume['id']))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'message': f'Série transférée avec succès vers la bibliothèque {to_library_id}',
                'new_path': new_series_path
            })
        
        except Exception as e:
            conn.close()
            print(f"❌ Erreur lors du déplacement des fichiers: {e}")
            import traceback
            traceback.print_exc()
            return jsonify({
                'error': f'Erreur lors du déplacement des fichiers: {str(e)}'
            }), 500
    
    except Exception as e:
        print(f"❌ Erreur transfert série: {e}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@library_bp.route('/api/series/<int:series_id>/tags', methods=['GET', 'PUT'])
def manage_series_tags(series_id):
    """Récupère ou met à jour les tags d'une série"""
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    if request.method == 'GET':
        # Récupérer les tags
        cursor.execute('SELECT tags FROM series WHERE id = ?', (series_id,))
        result = cursor.fetchone()
        conn.close()
        
        if not result:
            return jsonify({'error': 'Série non trouvée'}), 404
        
        tags = []
        if result['tags']:
            try:
                tags = json.loads(result['tags'])
            except (json.JSONDecodeError, TypeError):
                tags = []
        
        return jsonify({'tags': tags})
    
    elif request.method == 'PUT':
        # Mettre à jour les tags
        data = request.get_json()
        tags = data.get('tags', [])
        
        # Valider que c'est une liste de strings
        if not isinstance(tags, list):
            conn.close()
            return jsonify({'error': 'Les tags doivent être une liste'}), 400
        
        tags_list = [str(tag).strip() for tag in tags if tag]
        
        try:
            # Mettre à jour les tags comme JSON
            cursor.execute(
                'UPDATE series SET tags = ? WHERE id = ?',
                (json.dumps(tags_list), series_id)
            )
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'tags': tags_list,
                'message': 'Tags mis à jour avec succès'
            })
        
        except Exception as e:
            conn.close()
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

@library_bp.route('/api/import/cleanup', methods=['POST'])
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