"""
Historique des imports de fichiers
"""
import sqlite3
from datetime import datetime
from flask import current_app


def init_import_history_table():
    """Initialise la table d'historique des imports"""
    try:
        conn = sqlite3.connect(current_app.config['DATABASE'], timeout=120.0, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS import_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_id TEXT UNIQUE,
                operation_type TEXT,
                status TEXT,
                import_path TEXT,
                files_processed INTEGER DEFAULT 0,
                files_imported INTEGER DEFAULT 0,
                files_replaced INTEGER DEFAULT 0,
                files_skipped INTEGER DEFAULT 0,
                files_failed INTEGER DEFAULT 0,
                details TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                completed_at TIMESTAMP
            )
        ''')
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS import_history_files (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                operation_id TEXT,
                filename TEXT,
                source_path TEXT,
                destination_path TEXT,
                series_id INTEGER,
                series_title TEXT,
                action TEXT,
                status TEXT,
                message TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (operation_id) REFERENCES import_history(operation_id),
                FOREIGN KEY (series_id) REFERENCES series(id) ON DELETE SET NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        print(f"Erreur lors de la création de la table d'historique: {e}")
        return False


def log_import_operation(operation_id, operation_type, import_path, status='started', details=None):
    """Enregistre une opération d'import"""
    conn = None
    try:
        conn = sqlite3.connect(current_app.config['DATABASE'], timeout=120.0, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('''
            INSERT INTO import_history 
            (operation_id, operation_type, import_path, status, details)
            VALUES (?, ?, ?, ?, ?)
        ''', (operation_id, operation_type, import_path, status, details))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Erreur lors de l'enregistrement de l'opération: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def log_import_file(operation_id, filename, source_path, destination_path, series_title, action, status, message=''):
    """Enregistre l'import d'un fichier"""
    conn = None
    try:
        conn = sqlite3.connect(current_app.config['DATABASE'], timeout=120.0, check_same_thread=False)
        cursor = conn.cursor()
        
        # Chercher le series_id si la série existe
        series_id = None
        if series_title:
            cursor.execute('SELECT id FROM series WHERE title = ?', (series_title,))
            result = cursor.fetchone()
            if result:
                series_id = result[0]
        
        cursor.execute('''
            INSERT INTO import_history_files 
            (operation_id, filename, source_path, destination_path, series_id, series_title, action, status, message)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (operation_id, filename, source_path, destination_path, series_id, series_title, action, status, message))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Erreur lors de l'enregistrement du fichier: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def update_import_operation(operation_id, status, imported_count, replaced_count, skipped_count, failed_count):
    """Met à jour le statut d'une opération d'import"""
    conn = None
    try:
        conn = sqlite3.connect(current_app.config['DATABASE'], timeout=120.0, check_same_thread=False)
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE import_history 
            SET status = ?, files_imported = ?, files_replaced = ?, 
                files_skipped = ?, files_failed = ?, completed_at = CURRENT_TIMESTAMP
            WHERE operation_id = ?
        ''', (status, imported_count, replaced_count, skipped_count, failed_count, operation_id))
        
        conn.commit()
        return True
    except Exception as e:
        print(f"Erreur lors de la mise à jour de l'opération: {e}")
        return False
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_import_history(limit=50):
    """Récupère l'historique des imports"""
    conn = None
    try:
        conn = sqlite3.connect(current_app.config['DATABASE'], timeout=120.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT * FROM import_history 
            ORDER BY created_at DESC 
            LIMIT ?
        ''', (limit,))
        
        history = [dict(row) for row in cursor.fetchall()]
        return history
    except Exception as e:
        print(f"Erreur lors de la récupération de l'historique: {e}")
        return []
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def get_operation_details(operation_id):
    """Récupère les détails d'une opération"""
    conn = None
    try:
        conn = sqlite3.connect(current_app.config['DATABASE'], timeout=120.0, check_same_thread=False)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Récupérer l'opération
        cursor.execute('SELECT * FROM import_history WHERE operation_id = ?', (operation_id,))
        row = cursor.fetchone()
        operation = dict(row) if row else None
        
        # Récupérer les fichiers de cette opération
        cursor.execute('''
            SELECT * FROM import_history_files 
            WHERE operation_id = ? 
            ORDER BY created_at
        ''', (operation_id,))
        
        files = [dict(row) for row in cursor.fetchall()]
        
        return {'operation': operation, 'files': files}
    except Exception as e:
        print(f"Erreur lors de la récupération des détails: {e}")
        return None
    finally:
        if conn:
            try:
                conn.close()
            except:
                pass


def undo_import_operation(operation_id):
    """Annule une opération d'import en déplaçant les fichiers"""
    try:
        import os
        import shutil
        from datetime import datetime
        
        operation_details = get_operation_details(operation_id)
        if not operation_details or not operation_details['operation']:
            return False, "Opération non trouvée", []
        
        operation = operation_details['operation']
        files = operation_details['files']
        
        if operation['status'] != 'completed':
            return False, "Seules les opérations complétées peuvent être annulées", []
        
        undo_count = 0
        error_count = 0
        errors = []
        
        # Créer un dossier d'undo
        import_path = operation['import_path']
        undo_dir = os.path.join(import_path, f'_undo_{operation_id}')
        os.makedirs(undo_dir, exist_ok=True)
        
        for file_record in files:
            try:
                if file_record['status'] in ['imported', 'replaced']:
                    # Le fichier a été importé/remplacé, le déplacer vers undo
                    if os.path.exists(file_record['destination_path']):
                        shutil.move(file_record['destination_path'], 
                                   os.path.join(undo_dir, os.path.basename(file_record['destination_path'])))
                        undo_count += 1
                        
                        # Mettre à jour le statut
                        conn = None
                        try:
                            conn = sqlite3.connect(current_app.config['DATABASE'], timeout=120.0, check_same_thread=False)
                            cursor = conn.cursor()
                            cursor.execute('''
                                UPDATE import_history_files 
                                SET status = 'undone' 
                                WHERE operation_id = ? AND filename = ?
                            ''', (operation_id, file_record['filename']))
                            conn.commit()
                        finally:
                            if conn:
                                try:
                                    conn.close()
                                except:
                                    pass
            except Exception as e:
                error_count += 1
                errors.append(f"{file_record['filename']}: {str(e)}")
        
        # Mettre à jour l'opération
        conn = None
        try:
            conn = sqlite3.connect(current_app.config['DATABASE'], timeout=120.0, check_same_thread=False)
            cursor = conn.cursor()
            cursor.execute('''
                UPDATE import_history 
                SET status = 'undone' 
                WHERE operation_id = ?
            ''', (operation_id,))
            conn.commit()
        finally:
            if conn:
                try:
                    conn.close()
                except:
                    pass
        
        message = f"Annulation complétée: {undo_count} fichier(s) déplacé(s) vers {undo_dir}"
        if error_count > 0:
            message += f" ({error_count} erreur(s))"
        
        return True, message, errors
        
    except Exception as e:
        print(f"Erreur lors de l'annulation: {e}")
        return False, str(e), []
