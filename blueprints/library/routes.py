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
    conn = sqlite3.connect(current_app.config['DATABASE'], timeout=120.0, check_same_thread=False)
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


@library_bp.route('/missing-monitor')
def missing_monitor_page():
    """Page de surveillance des volumes manquants"""
    return render_template('missing-monitor.html')


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


@library_bp.route('/api/scan/series/<int:series_id>', methods=['POST'])
def scan_series(series_id):
    """Scanne une seule série (met à jour ses volumes)"""
    
    try:
        scanner = LibraryScanner()
        volumes_count = scanner.scan_single_series(series_id)
        
        return jsonify({'success': True, 'volumes_count': volumes_count})
    
    except Exception as e:
        error_msg = str(e)
        print(f"❌ Erreur lors du scan de la série {series_id}: {error_msg}")
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
                   s.nautiljon_year_start, s.nautiljon_year_end, s.nautiljon_updated_at, s.is_oneshot
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
            'is_oneshot': bool(series_row[18]),
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

@library_bp.route('/api/series/<int:series_id>/toggle-oneshot', methods=['POST'])
def toggle_series_oneshot(series_id):
    """Bascule le statut one-shot d'une série"""
    try:
        conn = sqlite3.connect(current_app.config['DATABASE'])
        cursor = conn.cursor()

        # Récupérer le statut actuel
        cursor.execute('SELECT is_oneshot FROM series WHERE id = ?', (series_id,))
        result = cursor.fetchone()
        
        if not result:
            conn.close()
            return jsonify({'error': 'Série introuvable'}), 404

        current_oneshot = result[0] or 0
        new_oneshot = 1 - current_oneshot  # Basculer entre 0 et 1

        # Si on marque comme one-shot, vider les volumes manquants et les numéros de volume
        if new_oneshot == 1:
            cursor.execute(
                'UPDATE series SET is_oneshot = ?, missing_volumes = ? WHERE id = ?', 
                (new_oneshot, None, series_id)
            )
            # Vider aussi les numéros de volume pour les volumes existants
            cursor.execute('UPDATE volumes SET volume_number = NULL WHERE series_id = ?', (series_id,))
        else:
            # Si on démarque le one-shot, juste mettre à jour le statut
            cursor.execute('UPDATE series SET is_oneshot = ? WHERE id = ?', (new_oneshot, series_id))
        
        conn.commit()
        conn.close()

        return jsonify({
            'success': True,
            'is_oneshot': bool(new_oneshot),
            'message': 'One-shot marqué' if new_oneshot else 'One-shot démarqué'
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
    import uuid
    from .import_history import log_import_operation, log_import_file, update_import_operation
    
    data = request.json
    files_to_import = data.get('files', [])
    import_base_path = data.get('import_path', '')

    if not files_to_import:
        return jsonify({'error': 'Aucun fichier à importer'}), 400

    try:
        # Générer un ID d'opération unique
        operation_id = str(uuid.uuid4())
        
        # Enregistrer le début de l'opération
        log_import_operation(operation_id, 'manual_import', import_base_path, 'started')
        
        # Liste pour accumuler les logs à enregistrer ($pour éviter les problèmes de verrou SQLite)
        logs_to_record = []
        
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
                conn = sqlite3.connect(current_app.config['DATABASE'], timeout=120.0, check_same_thread=False)
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
                        
                        # Ajouter à la liste de logs
                        logs_to_record.append({
                            'operation_id': operation_id,
                            'filename': file_data['filename'],
                            'source_path': source_path,
                            'destination_path': target_path,
                            'series_title': series_title,
                            'action': 'replaced',
                            'status': 'success',
                            'message': ''
                        })

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
                        
                        # Ajouter à la liste de logs
                        logs_to_record.append({
                            'operation_id': operation_id,
                            'filename': file_data['filename'],
                            'source_path': source_path,
                            'destination_path': doublon_path,
                            'series_title': series_title,
                            'action': 'skipped',
                            'status': 'success',
                            'message': ''
                        })
                        
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
                    
                    # Ajouter à la liste de logs
                    logs_to_record.append({
                        'operation_id': operation_id,
                        'filename': file_data['filename'],
                        'source_path': source_path,
                        'destination_path': target_path,
                        'series_title': series_title,
                        'action': 'imported',
                        'status': 'success',
                        'message': ''
                    })

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
                
                # Ajouter à la liste de logs
                logs_to_record.append({
                    'operation_id': operation_id,
                    'filename': file_data['filename'],
                    'source_path': file_data.get('filepath', ''),
                    'destination_path': '',
                    'series_title': '',
                    'action': 'failed',
                    'status': 'error',
                    'message': str(e)
                })
                
                import traceback
                traceback.print_exc()

        # Enregistrer tous les logs accumulés APRÈS la fin de la boucle d'import
        # pour éviter les problèmes de verrou SQLite
        for log_entry in logs_to_record:
            try:
                log_import_file(
                    log_entry['operation_id'],
                    log_entry['filename'],
                    log_entry['source_path'],
                    log_entry['destination_path'],
                    log_entry['series_title'],
                    log_entry['action'],
                    log_entry['status'],
                    log_entry.get('message', '')
                )
            except Exception as log_err:
                print(f"Erreur lors de l'enregistrement du log: {log_err}")

        # Mettre à jour les statistiques des séries concernées
        conn = sqlite3.connect(current_app.config['DATABASE'], timeout=120.0, check_same_thread=False)
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

        # Mettre à jour l'opération avec le statut final
        update_import_operation(operation_id, 'completed', imported_count, replaced_count, skipped_count, failed_count)

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


# ========== RENOMMAGE DE FICHIERS ==========

@library_bp.route('/api/series/<int:series_id>/rename/preview', methods=['POST'])
def preview_rename(series_id):
    """Génère un aperçu du renommage avant de l'effectuer"""
    try:
        data = request.get_json()
        pattern = data.get('pattern', '')
        
        if not pattern:
            return jsonify({'error': 'Pattern vide'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Récupérer les infos de la série
        cursor.execute('''
            SELECT s.id, s.title, s.path
            FROM series s
            WHERE s.id = ?
        ''', (series_id,))
        
        series = cursor.fetchone()
        if not series:
            return jsonify({'error': 'Série introuvable'}), 404
        
        series_id, series_title, series_path = series
        
        # Récupérer tous les volumes
        cursor.execute('''
            SELECT filename, volume_number, part_number
            FROM volumes
            WHERE series_id = ?
            ORDER BY part_number, volume_number
        ''', (series_id,))
        
        volumes = []
        for vol in cursor.fetchall():
            volumes.append({
                'filename': vol[0],
                'volume_number': vol[1],
                'part_number': vol[2],
                'series_title': series_title
            })
        
        conn.close()
        
        if not volumes:
            return jsonify({'error': 'Aucun volume trouvé'}), 404
        
        # Générer l'aperçu
        from rename_handler import RenamePattern
        
        rename_pattern = RenamePattern(pattern)
        is_valid, error = rename_pattern.validate()
        
        if not is_valid:
            return jsonify({'error': error}), 400
        
        preview = rename_pattern.preview(volumes)
        
        return jsonify({
            'success': True,
            'series_title': series_title,
            'series_path': series_path,
            'preview': preview
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@library_bp.route('/api/series/<int:series_id>/rename/execute', methods=['POST'])
def execute_rename(series_id):
    """Effectue le renommage des fichiers de la série"""
    try:
        data = request.get_json()
        pattern = data.get('pattern', '')
        files_to_rename = data.get('files', [])
        
        if not pattern or not files_to_rename:
            return jsonify({'error': 'Pattern ou liste de fichiers manquante'}), 400
        
        conn = get_db_connection()
        cursor = conn.cursor()
        
        # Récupérer les infos de la série
        cursor.execute('''
            SELECT s.id, s.title, s.path
            FROM series s
            WHERE s.id = ?
        ''', (series_id,))
        
        series = cursor.fetchone()
        if not series:
            return jsonify({'error': 'Série introuvable'}), 404
        
        series_id, series_title, series_path = series
        conn.close()
        
        # Effectuer le renommage
        from rename_handler import FileRenamer
        
        success, results, error = FileRenamer.rename_series_files(
            series_path=series_path,
            pattern=pattern,
            files_to_rename=files_to_rename,
            series_title=series_title,
            dry_run=False
        )
        
        if not success:
            return jsonify({'error': error}), 500
        
        # Après succès, rescanner la série pour mettre à jour la base de données
        try:
            from .scanner import LibraryScanner
            scanner = LibraryScanner()
            scanner.scan_single_series(series_id)
        except Exception as e:
            print(f"Erreur lors du re-scan: {e}")
            import traceback
            traceback.print_exc()
        
        return jsonify({
            'success': True,
            'results': results
        })
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@library_bp.route('/api/libraries/<int:library_id>/create-series', methods=['POST'])
def create_series_directory(library_id):
    """Crée un répertoire pour une nouvelle série dans une bibliothèque"""
    try:
        data = request.get_json()
        series_name = data.get('series_name', '').strip()
        
        if not series_name:
            return jsonify({'error': 'Le nom de la série est requis'}), 400
        
        # Récupérer les infos de la bibliothèque
        conn = get_db_connection()
        cursor = conn.cursor()
        
        cursor.execute('SELECT path FROM libraries WHERE id = ?', (library_id,))
        library = cursor.fetchone()
        
        if not library:
            conn.close()
            return jsonify({'error': 'Bibliothèque non trouvée'}), 404
        
        library_path = library['path']
        
        # Vérifier si la série existe déjà dans la base de données
        cursor.execute('''
            SELECT id FROM series WHERE library_id = ? AND title = ?
        ''', (library_id, series_name))
        existing_series = cursor.fetchone()
        series_exists_in_db = existing_series is not None
        
        # Construire le chemin du répertoire de la série
        series_path = os.path.join(library_path, series_name)
        
        # Vérifier si le répertoire existe déjà
        directory_exists = os.path.exists(series_path)
        
        # Si TOUT existe déjà, retourner sans rien faire
        if series_exists_in_db and directory_exists:
            conn.close()
            return jsonify({
                'success': True,
                'path': series_path,
                'message': 'La série existe déjà',
                'series_exists_in_db': True,
                'directory_exists': True,
                'exists': True
            })
        
        try:
            # Créer le répertoire s'il n'existe pas
            if not directory_exists:
                os.makedirs(series_path, exist_ok=True)
            
            # Ajouter la série à la base de données si elle n'existe pas
            if not series_exists_in_db:
                cursor.execute('''
                    INSERT INTO series (library_id, title, path, total_volumes, missing_volumes, has_parts)
                    VALUES (?, ?, ?, 0, '[]', 0)
                ''', (library_id, series_name, series_path))
            
            conn.commit()
            conn.close()
            
            return jsonify({
                'success': True,
                'path': series_path,
                'message': f'Répertoire créé et série ajoutée : {series_path}',
                'series_exists_in_db': series_exists_in_db,
                'directory_exists': directory_exists,
                'exists': False
            })
        
        except PermissionError:
            conn.close()
            return jsonify({
                'error': f'Permission refusée pour créer le répertoire : {series_path}'
            }), 403
        
        except OSError as e:
            conn.close()
            return jsonify({'error': f'Erreur lors de la création du répertoire : {str(e)}'}), 500
    
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


# ========== FONCTIONS D'IMPORT AUTOMATIQUE ==========

def load_library_import_config():
    """Charge la configuration d'import automatique"""
    config_file = current_app.config['LIBRARY_IMPORT_CONFIG_FILE']
    
    if os.path.exists(config_file):
        with open(config_file, 'r') as f:
            return json.load(f)
    
    return current_app.config['LIBRARY_IMPORT_CONFIG'].copy()


def save_library_import_config(config):
    """Sauvegarde la configuration d'import automatique"""
    config_file = current_app.config['LIBRARY_IMPORT_CONFIG_FILE']
    
    try:
        os.makedirs(os.path.dirname(config_file), exist_ok=True)
        with open(config_file, 'w') as f:
            json.dump(config, f, indent=4)
        return True
    except Exception as e:
        print(f"Erreur lors de la sauvegarde de la configuration d'import: {e}")
        return False


def can_auto_assign(parsed, config):
    """Détermine si un fichier peut être auto-assigné
    
    Args:
        parsed: Dictionnaire de données parsées du nom de fichier
        config: Configuration d'import
        
    Returns:
        True si le fichier peut être auto-assigné, False sinon
    """
    if not config.get('auto_assign_enabled', True):
        return False
    
    # Vérifier que les informations minimales sont disponibles
    # On doit avoir au moins le titre du manga et le numéro de volume
    if not parsed.get('title') or parsed.get('volume') is None:
        return False
    
    return True


def find_auto_assign_destination(parsed, config):
    """Trouve la destination automatique pour un fichier
    
    Args:
        parsed: Dictionnaire de données parsées du nom de fichier
        config: Configuration d'import
        
    Returns:
        Dictionnaire avec destination ou None
    """
    try:
        conn = get_db_connection()
        cursor = conn.cursor()
        
        title = parsed.get('title', '').strip()
        
        # Rechercher une série existante avec un titre similaire
        # Faire une recherche case-insensitive et avec tolérance
        cursor.execute('''
            SELECT s.id, s.library_id, l.path, s.title
            FROM series s
            JOIN libraries l ON s.library_id = l.id
            WHERE LOWER(s.title) = LOWER(?)
            LIMIT 1
        ''', (title,))
        
        result = cursor.fetchone()
        conn.close()
        
        if result:
            series_id, library_id, library_path, series_title = result
            return {
                'series_id': series_id,
                'library_id': library_id,
                'library_path': library_path,
                'series_title': series_title,
                'is_new_series': False
            }
        
        # Pas de série existante encontrée, et création auto désactivée
        return None
        
    except Exception as e:
        print(f"Erreur lors de la recherche de destination: {e}")
        return None


def execute_auto_import(files_to_import, import_base_path):
    """Exécute l'import automatique des fichiers
    
    Args:
        files_to_import: Liste des fichiers à importer
        import_base_path: Chemin de base du répertoire d'import
        
    Returns:
        Tuple (success: bool, stats: dict) avec les statistiques d'import
    """
    try:
        import uuid
        from .import_history import log_import_operation, log_import_file, update_import_operation
        
        # Générer un ID d'opération unique
        operation_id = str(uuid.uuid4())
        
        # Enregistrer le début de l'opération
        log_import_operation(operation_id, 'auto_import', import_base_path, 'started')
        
        scanner = LibraryScanner()
        imported_count = 0
        replaced_count = 0
        skipped_count = 0
        failed_count = 0
        
        # Liste pour accumuler les logs à faire après fermeture de toutes les connexions
        logs_to_record = []
        
        # Créer les répertoires spéciaux
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
                
                if not destination or not os.path.exists(source_path):
                    failed_count += 1
                    continue
                
                # Récupérer ou créer la série
                conn = sqlite3.connect(current_app.config['DATABASE'], timeout=120.0, check_same_thread=False)
                cursor = conn.cursor()
                
                if destination.get('is_new_series'):
                    # Créer une nouvelle série
                    series_title = destination['series_title']
                    library_id = destination['library_id']
                    library_path = destination['library_path']
                    
                    series_path = os.path.join(library_path, series_title)
                    os.makedirs(series_path, exist_ok=True)
                    
                    cursor.execute('''
                        INSERT INTO series (library_id, title, path, total_volumes, missing_volumes, has_parts)
                        VALUES (?, ?, ?, 0, '[]', 0)
                    ''', (library_id, series_title, series_path))
                    
                    series_id = cursor.lastrowid
                    destination['series_id'] = series_id
                    target_dir = series_path
                    series_title_for_log = series_title
                else:
                    # Utiliser une série existante
                    series_id = destination['series_id']
                    library_path = destination['library_path']
                    series_title = destination['series_title']
                    series_title_for_log = series_title
                    
                    target_dir = os.path.join(library_path, series_title)
                    os.makedirs(target_dir, exist_ok=True)
                    
                    cursor.execute('UPDATE series SET path = ? WHERE id = ?', (target_dir, series_id))
                
                # Construire le chemin de destination
                target_path = os.path.join(target_dir, file_data['filename'])
                
                # Vérifier si un fichier existe déjà avec le même numéro de volume
                volume_number = file_data['parsed'].get('volume')
                existing_file_path = None
                existing_file_size = 0
                
                if volume_number:
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
                        # Remplacer
                        old_filename = os.path.basename(existing_file_path)
                        old_dest_path = os.path.join(old_files_dir, old_filename)
                        
                        if os.path.exists(old_dest_path):
                            from datetime import datetime
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            base, ext = os.path.splitext(old_filename)
                            old_dest_path = os.path.join(old_files_dir, f"{base}_{timestamp}{ext}")
                        
                        shutil.move(existing_file_path, old_dest_path)
                        cursor.execute('DELETE FROM volumes WHERE filepath = ?', (existing_file_path,))
                        shutil.move(source_path, target_path)
                        action_taken = 'replaced'
                        replaced_count += 1
                        
                        conn.commit()
                        conn.close()
                        
                        # Ajouter à la liste de logs
                        logs_to_record.append({
                            'operation_id': operation_id,
                            'filename': file_data['filename'],
                            'source_path': source_path,
                            'destination_path': target_path,
                            'series_title': destination.get('series_title', ''),
                            'action': 'replaced',
                            'status': 'success',
                            'message': ''
                        })
                        continue
                    else:
                        # Ignorer (fichier plus petit ou égal)
                        doublon_path = os.path.join(doublons_dir, file_data['filename'])
                        
                        if os.path.exists(doublon_path):
                            from datetime import datetime
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                            base, ext = os.path.splitext(file_data['filename'])
                            doublon_path = os.path.join(doublons_dir, f"{base}_{timestamp}{ext}")
                        
                        shutil.move(source_path, doublon_path)
                        action_taken = 'skipped_duplicate'
                        skipped_count += 1
                        
                        conn.commit()
                        conn.close()
                        
                        # Ajouter à la liste de logs
                        logs_to_record.append({
                            'operation_id': operation_id,
                            'filename': file_data['filename'],
                            'source_path': source_path,
                            'destination_path': doublon_path,
                            'series_title': destination.get('series_title', ''),
                            'action': 'skipped',
                            'status': 'success',
                            'message': ''
                        })
                        
                        continue
                else:
                    # Import normal
                    if os.path.exists(target_path):
                        base, ext = os.path.splitext(file_data['filename'])
                        counter = 1
                        while os.path.exists(target_path):
                            target_path = os.path.join(target_dir, f"{base}_{counter}{ext}")
                            counter += 1
                    
                    shutil.move(source_path, target_path)
                    action_taken = 'imported'
                    imported_count += 1
                    
                    # Ajouter le volume à la base de données
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
                    
                    # Ajouter à la liste de logs
                    logs_to_record.append({
                        'operation_id': operation_id,
                        'filename': file_data['filename'],
                        'source_path': source_path,
                        'destination_path': target_path,
                        'series_title': destination.get('series_title', ''),
                        'action': 'imported',
                        'status': 'success',
                        'message': ''
                    })
                
            except Exception as e:
                failed_count += 1
                print(f"Erreur import {file_data['filename']}: {e}")
                
                # Ajouter à la liste de logs
                logs_to_record.append({
                    'operation_id': operation_id,
                    'filename': file_data['filename'],
                    'source_path': file_data.get('filepath', ''),
                    'destination_path': '',
                    'series_title': '',
                    'action': 'failed',
                    'status': 'error',
                    'message': str(e)
                })
        
        # Enregistrer tous les logs accumulés APRÈS la fin de la boucle d'import
        # pour éviter les problèmes de verrou SQLite
        for log_entry in logs_to_record:
            try:
                log_import_file(
                    log_entry['operation_id'],
                    log_entry['filename'],
                    log_entry['source_path'],
                    log_entry['destination_path'],
                    log_entry['series_title'],
                    log_entry['action'],
                    log_entry['status'],
                    log_entry.get('message', '')
                )
            except Exception as log_err:
                print(f"Erreur lors de l'enregistrement du log: {log_err}")
        
        # Mettre à jour les statistiques des séries
        conn = sqlite3.connect(current_app.config['DATABASE'], timeout=120.0, check_same_thread=False)
        cursor = conn.cursor()
        
        series_ids = set()
        for file_data in files_to_import:
            dest = file_data.get('destination')
            if dest and dest.get('series_id'):
                series_ids.add(dest['series_id'])
        
        for series_id in series_ids:
            scanner.update_series_stats(series_id, conn)
        
        conn.close()
        
        # Nettoyer les répertoires vides
        if import_base_path:
            cleanup_empty_directories(import_base_path)
        
        # Mettre à jour l'opération avec le statut final
        update_import_operation(operation_id, 'completed', imported_count, replaced_count, skipped_count, failed_count)
        
        print(f"✓ Import automatique terminé: {imported_count} importés, {replaced_count} remplacés, {skipped_count} ignorés, {failed_count} erreurs")
        return True, {
            'operation_id': operation_id,
            'imported_count': imported_count,
            'replaced_count': replaced_count,
            'skipped_count': skipped_count,
            'failed_count': failed_count
        }
        
    except Exception as e:
        print(f"✗ Erreur lors de l'import automatique: {e}")
        import traceback
        traceback.print_exc()
        return False, {
            'operation_id': None,
            'imported_count': 0,
            'replaced_count': 0,
            'skipped_count': 0,
            'failed_count': 0
        }


# ========== ROUTES API D'IMPORT AUTOMATIQUE ==========

@library_bp.route('/api/import/config', methods=['GET', 'POST'])
def import_config():
    """Récupère ou met à jour la configuration d'import automatique"""
    
    if request.method == 'GET':
        config = load_library_import_config()
        return jsonify(config)
    
    else:  # POST
        data = request.get_json()
        config = load_library_import_config()
        
        # Mettre à jour les champs
        if 'auto_import_enabled' in data:
            config['auto_import_enabled'] = data['auto_import_enabled']
        if 'import_path' in data:
            config['import_path'] = data['import_path']
        if 'auto_assign_enabled' in data:
            config['auto_assign_enabled'] = data['auto_assign_enabled']
        if 'auto_import_interval' in data:
            config['auto_import_interval'] = data['auto_import_interval']
        if 'auto_import_interval_unit' in data:
            config['auto_import_interval_unit'] = data['auto_import_interval_unit']
        
        if save_library_import_config(config):
            # Redémarrer le scheduler si nécessaire
            if config.get('auto_import_enabled'):
                from .scheduler import library_import_scheduler
                interval = config.get('auto_import_interval', 60)
                interval_unit = config.get('auto_import_interval_unit', 'minutes')
                library_import_scheduler.add_job(interval, interval_unit)
            else:
                from .scheduler import library_import_scheduler
                library_import_scheduler.remove_job()
            
            return jsonify({'success': True, 'config': config})
        else:
            return jsonify({'error': 'Erreur lors de la sauvegarde'}), 500

# ========== ROUTES API D'HISTORIQUE D'IMPORT ==========

@library_bp.route('/api/import/history', methods=['GET'])
def import_history():
    """Récupère l'historique des imports"""
    try:
        from .import_history import get_import_history
        
        limit = request.args.get('limit', 50, type=int)
        history = get_import_history(limit)
        
        return jsonify({'success': True, 'history': history})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@library_bp.route('/api/import/history/<operation_id>', methods=['GET'])
def import_operation_details(operation_id):
    """Récupère les détails d'une opération d'import"""
    try:
        from .import_history import get_operation_details
        
        details = get_operation_details(operation_id)
        
        if not details:
            return jsonify({'error': 'Opération non trouvée'}), 404
        
        return jsonify({'success': True, 'details': details})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@library_bp.route('/api/import/history/<operation_id>/undo', methods=['POST'])
def undo_import_operation(operation_id):
    """Annule une opération d'import"""
    try:
        from .import_history import undo_import_operation as do_undo
        
        success, message, errors = do_undo(operation_id)
        
        if success:
            return jsonify({'success': True, 'message': message, 'errors': errors})
        else:
            return jsonify({'error': message}), 400
            
    except Exception as e:
        return jsonify({'error': str(e)}), 500