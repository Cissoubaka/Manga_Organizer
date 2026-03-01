"""
Gestionnaire du scraping automatique pour l'importation de fichiers
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import json
import os
from datetime import datetime
from flask import current_app


class LibraryImportScheduler:
    """Gestionnaire de l'import automatique de fichiers"""
    
    def __init__(self, app=None):
        self.scheduler = None
        self.app = app
        self.job_id = 'library_auto_import'
        
    def init_app(self, app):
        """Initialiser le scheduler avec l'app Flask"""
        self.app = app
        
    def start(self):
        """Démarrer le scheduler"""
        if self.scheduler is None:
            self.scheduler = BackgroundScheduler(daemon=True)
            self.scheduler.start()
            print("✓ Scheduler d'import automatique démarré")
        
    def stop(self):
        """Arrêter le scheduler"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self.scheduler = None
            print("✓ Scheduler d'import automatique arrêté")
    
    def add_job(self, interval_value, interval_unit):
        """Ajouter une tâche d'import automatique"""
        self.start()
        
        # Supprimer la tâche existante si elle existe
        if self.scheduler.get_job(self.job_id):
            self.scheduler.remove_job(self.job_id)
        
        # Ajouter la nouvelle tâche
        self.scheduler.add_job(
            func=self._auto_import,
            trigger=IntervalTrigger(**{interval_unit: interval_value}),
            id=self.job_id,
            name='Library Auto Import',
            replace_existing=True
        )
        
        print(f"✓ Tâche d'import automatique programmée: tous les {interval_value} {interval_unit}")
    
    def remove_job(self):
        """Supprimer la tâche d'import automatique"""
        if self.scheduler and self.scheduler.get_job(self.job_id):
            self.scheduler.remove_job(self.job_id)
            print("✓ Tâche d'import automatique supprimée")
    
    def _auto_import(self):
        """Fonction appelée par le scheduler pour importer automatiquement les fichiers"""
        if not self.app:
            print("Erreur: App Flask non initialisée")
            return
        
        with self.app.app_context():
            try:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 📦 Import automatique en cours...")
                
                # Import local pour éviter les boucles circulaires
                from . import routes
                from .scanner import LibraryScanner
                import sqlite3
                from flask import current_app
                
                # Charger la configuration d'import
                config = routes.load_library_import_config()
                
                if not config.get('auto_import_enabled', False):
                    print("⚠️ Import automatique désactivé")
                    return
                
                import_path = config.get('import_path', '')
                if not import_path or not os.path.exists(import_path):
                    print(f"⚠️ Chemin d'import invalide ou inexistant: {import_path}")
                    return
                
                # Scanner les fichiers à importer
                scanner = LibraryScanner()
                supported_extensions = {'.cbz', '.cbr', '.zip', '.rar', '.pdf', '.epub'}
                
                files_to_import = []
                
                # Parcourir le répertoire
                for root, dirs, files in os.walk(import_path):
                    # Ignorer les répertoires spéciaux
                    dirs[:] = [d for d in dirs if d not in ['_old_files', '_doublons']]
                    
                    for filename in files:
                        ext = os.path.splitext(filename)[1].lower()
                        
                        if ext in supported_extensions:
                            filepath = os.path.join(root, filename)
                            parsed = scanner.parse_filename(filename)
                            
                            # Vérifier si le fichier peut être auto-assigné
                            if routes.can_auto_assign(parsed, config):
                                # Déterminer la destination
                                destination = routes.find_auto_assign_destination(parsed, config)
                                
                                if destination:
                                    files_to_import.append({
                                        'filename': filename,
                                        'filepath': filepath,
                                        'file_size': os.path.getsize(filepath),
                                        'parsed': parsed,
                                        'destination': destination
                                    })
                
                if not files_to_import:
                    print("ℹ️ Aucun fichier à auto-importer trouvé")
                    return
                
                print(f"📦 {len(files_to_import)} fichier(s) trouvé(s) pour import automatique")
                
                # Exécuter l'import
                from . import routes as lib_routes
                success, stats = lib_routes.execute_auto_import(files_to_import, import_path)
                
                if success:
                    print(f"✓ Import automatique complété: {stats['imported_count']} importés")
                else:
                    print(f"✗ Erreur lors de l'import automatique")
                
            except Exception as e:
                print(f"✗ Erreur lors de l'import automatique: {e}")
                import traceback
                traceback.print_exc()


# Instance globale du scheduler
library_import_scheduler = LibraryImportScheduler()
