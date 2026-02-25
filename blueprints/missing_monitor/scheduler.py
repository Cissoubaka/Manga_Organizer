"""
Scheduleur pour surveillance automatique des volumes manquants
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from datetime import datetime
from flask import current_app
import json
import os
import logging
from typing import Dict

logger = logging.getLogger(__name__)


class MissingVolumeScheduler:
    """Gère la surveillance automatique des volumes manquants"""
    
    def __init__(self, app=None):
        self.scheduler = None
        self.app = app
        self.job_id = 'missing_monitor_auto_check'
        
    def init_app(self, app):
        """Initialiser le scheduler avec l'app Flask"""
        self.app = app
    
    def start(self):
        """Démarrer le scheduler"""
        if self.scheduler is None:
            self.scheduler = BackgroundScheduler(daemon=True)
            self.scheduler.start()
            print("✓ Scheduler de surveillance des volumes manquants démarré")
    
    def stop(self):
        """Arrêter le scheduler"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self.scheduler = None
            print("✓ Scheduler de surveillance arrêté")
    
    def add_monitor_job(self, interval_value: int, interval_unit: str):
        """Ajouter une tâche de surveillance automatique
        
        Args:
            interval_value: Valeur de l'intervalle
            interval_unit: Unité ('minutes', 'hours', 'days')
        """
        self.start()
        
        # Supprimer la tâche existante si elle existe
        if self.scheduler.get_job(self.job_id):
            self.scheduler.remove_job(self.job_id)
        
        # Ajouter la nouvelle tâche
        self.scheduler.add_job(
            func=self._run_monitor,
            trigger=IntervalTrigger(**{interval_unit: interval_value}),
            id=self.job_id,
            name='Missing Volume Monitor',
            replace_existing=True
        )
        
        print(f"✓ Surveillance des volumes manquants programmée: tous les {interval_value} {interval_unit}")
    
    def remove_monitor_job(self):
        """Supprimer la tâche de surveillance"""
        if self.scheduler and self.scheduler.get_job(self.job_id):
            self.scheduler.remove_job(self.job_id)
            print("✓ Tâche de surveillance des volumes manquants supprimée")
    
    def _run_monitor(self):
        """Fonction appelée par le scheduler pour surveiller les volumes"""
        if not self.app:
            logger.error("App Flask non initialisée")
            return
        
        with self.app.app_context():
            try:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"\n[{timestamp}] 📚 Surveillance des volumes manquants en cours...")
                
                from . import monitor_manager
                
                # Exécuter la surveillance
                stats = monitor_manager.run_missing_volume_check()
                
                print(f"✓ Surveillance complétée: {stats['total_series']} séries, "
                      f"{stats['total_missing']} volumes manquants, "
                      f"{stats['downloads_sent']} téléchargements envoyés")
                
            except Exception as e:
                logger.error(f"Erreur surveillance volumes: {e}", exc_info=True)


class MonitorManager:
    """Gestionnaire central de la surveillance"""
    
    def __init__(self):
        self.detector = None
        self.searcher = None
        self.downloader = None
    
    def initialize(self):
        """Initialise tous les composants"""
        from .detector import MissingVolumeDetector
        from .searcher import MissingVolumeSearcher
        from .downloader import MissingVolumeDownloader
        
        self.detector = MissingVolumeDetector()
        self.searcher = MissingVolumeSearcher()
        self.downloader = MissingVolumeDownloader()
    
    def run_missing_volume_check(self, search_enabled: bool = True, 
                                download_enabled: bool = False) -> Dict:
        """Exécute une vérification complète des volumes manquants
        
        Args:
            search_enabled: Activer la recherche automatique
            download_enabled: Activer l'envoi automatique aux clients
            
        Returns:
            Statistiques de l'exécution
        """
        if not self.detector:
            self.initialize()
        
        stats = {
            'total_series': 0,
            'total_missing': 0,
            'searches_performed': 0,
            'results_found': 0,
            'downloads_sent': 0,
            'errors': []
        }
        
        try:
            # Récupérer les séries en surveillance
            series_list = self.detector.get_monitored_series()
            stats['total_series'] = len(series_list)
            
            for series in series_list:
                stats['total_missing'] += len(series['missing_volumes'])
                
                if not series['enabled']:
                    continue
                
                series_id = series['series_id']
                monitor_id = series['monitor_id']
                title = series['title']
                sources = series['search_sources']
                auto_download = series['auto_download_enabled']
                
                # Chercher les volumes manquants
                for vol_num in series['missing_volumes']:
                    if search_enabled and sources:
                        try:
                            results = self.searcher.search_for_volume(
                                title, vol_num, sources
                            )
                            
                            if results:
                                stats['searches_performed'] += 1
                                stats['results_found'] += len(results)
                                
                                # Envoyer au client si configuré
                                if auto_download and results:
                                    best_result = results[0]  # Meilleur résultat
                                    link = best_result.get('link', '')
                                    
                                    if link:
                                        success, msg = self.downloader.send_torrent_download(
                                            link, title, vol_num
                                        )
                                        if success:
                                            stats['downloads_sent'] += 1
                                        
                                        print(msg)
                        
                        except Exception as e:
                            msg = f"Erreur recherche {title} vol {vol_num}: {e}"
                            stats['errors'].append(msg)
                            logger.error(msg)
                
                # Mettre à jour le timestamp de vérification
                if monitor_id:
                    self.detector.update_last_checked(monitor_id)
        
        except Exception as e:
            msg = f"Erreur exécution surveillance: {e}"
            stats['errors'].append(msg)
            logger.error(msg, exc_info=True)
        
        return stats


# Instance globale du gestionnaire
monitor_manager = MonitorManager()
