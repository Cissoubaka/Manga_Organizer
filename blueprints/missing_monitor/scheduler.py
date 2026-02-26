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
        self.job_id_missing = 'missing_monitor_missing_volumes'
        self.job_id_new = 'missing_monitor_new_volumes'
        
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
    
    def add_missing_volume_job(self, interval_value: int, interval_unit: str):
        """Ajouter une tâche de surveillance des volumes manquants
        
        Args:
            interval_value: Valeur de l'intervalle
            interval_unit: Unité ('hours', 'days')
        """
        self.start()
        
        # Supprimer la tâche existante si elle existe
        if self.scheduler.get_job(self.job_id_missing):
            self.scheduler.remove_job(self.job_id_missing)
        
        # Ajouter la nouvelle tâche
        self.scheduler.add_job(
            func=self._run_missing_volume_monitor,
            trigger=IntervalTrigger(**{interval_unit: interval_value}),
            id=self.job_id_missing,
            name='Missing Volumes Monitor',
            replace_existing=True
        )
        
        print(f"✓ Surveillance des volumes manquants programmée: tous les {interval_value} {interval_unit}")
    
    def add_new_volume_job(self, interval_value: int, interval_unit: str):
        """Ajouter une tâche de surveillance des nouveaux volumes
        
        Args:
            interval_value: Valeur de l'intervalle
            interval_unit: Unité ('hours', 'days')
        """
        self.start()
        
        # Supprimer la tâche existante si elle existe
        if self.scheduler.get_job(self.job_id_new):
            self.scheduler.remove_job(self.job_id_new)
        
        # Ajouter la nouvelle tâche
        self.scheduler.add_job(
            func=self._run_new_volume_monitor,
            trigger=IntervalTrigger(**{interval_unit: interval_value}),
            id=self.job_id_new,
            name='New Volumes Monitor',
            replace_existing=True
        )
        
        print(f"✓ Surveillance des nouveaux volumes programmée: tous les {interval_value} {interval_unit}")
    
    def remove_monitor_job(self):
        """Supprimer la tâche de surveillance"""
        if self.scheduler and self.scheduler.get_job(self.job_id):
            self.scheduler.remove_job(self.job_id)
            print("✓ Tâche de surveillance des volumes manquants supprimée")
    
    def remove_missing_volume_job(self):
        """Supprimer la tâche de surveillance des volumes manquants"""
        if self.scheduler and self.scheduler.get_job(self.job_id_missing):
            self.scheduler.remove_job(self.job_id_missing)
            print("✓ Tâche de surveillance des volumes manquants supprimée")
    
    def remove_new_volume_job(self):
        """Supprimer la tâche de surveillance des nouveaux volumes"""
        if self.scheduler and self.scheduler.get_job(self.job_id_new):
            self.scheduler.remove_job(self.job_id_new)
            print("✓ Tâche de surveillance des nouveaux volumes supprimée")
    
    def _run_monitor(self):
        """Fonction appelée par le scheduler pour surveiller les volumes"""
        if not self.app:
            logger.error("App Flask non initialisée")
            return
        
        with self.app.app_context():
            try:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"\n[{timestamp}] 📚 Surveillance des volumes en cours...")
                
                from . import monitor_manager
                from blueprints.missing_monitor.routes import load_monitor_config
                
                config = load_monitor_config()
                
                # Vérifier les volumes manquants
                if config.get('monitor_missing_volumes', {}).get('enabled', True):
                    print(f"[{timestamp}] 🔍 Vérification des volumes manquants...")
                    stats_missing = monitor_manager.run_missing_volume_check(
                        search_enabled=config.get('monitor_missing_volumes', {}).get('search_enabled', True),
                        download_enabled=config.get('monitor_missing_volumes', {}).get('auto_download_enabled', False)
                    )
                    
                    print(f"  ✓ {stats_missing['total_series']} séries, "
                          f"{stats_missing['total_missing']} volumes manquants, "
                          f"{stats_missing['searches_performed']} recherches, "
                          f"{stats_missing['downloads_sent']} téléchargements")
                
                # Vérifier les nouveaux volumes
                if config.get('monitor_new_volumes', {}).get('enabled', False):
                    print(f"[{timestamp}] ✨ Vérification des nouveaux volumes...")
                    stats_new = monitor_manager.run_new_volume_check(
                        auto_download_enabled=config.get('monitor_new_volumes', {}).get('auto_download_enabled', False)
                    )
                    
                    print(f"  ✓ {stats_new['nautiljon_checks']} vérifications Nautiljon, "
                          f"{stats_new['new_volumes_found']} nouveaux volumes trouvés, "
                          f"{stats_new['downloads_sent']} téléchargements")
                
                print(f"[{timestamp}] ✅ Surveillance complétée")
                
            except Exception as e:
                logger.error(f"Erreur surveillance volumes: {e}", exc_info=True)
    
    def _run_missing_volume_monitor(self):
        """Fonction appelée par le scheduler pour surveiller uniquement les volumes manquants"""
        if not self.app:
            logger.error("App Flask non initialisée")
            return
        
        with self.app.app_context():
            try:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"\n[{timestamp}] 🔍 Vérification des volumes manquants en cours...")
                
                from . import monitor_manager
                from blueprints.missing_monitor.routes import load_monitor_config
                
                config = load_monitor_config()
                
                # Vérifier les volumes manquants
                if config.get('monitor_missing_volumes', {}).get('enabled', True):
                    stats_missing = monitor_manager.run_missing_volume_check(
                        search_enabled=config.get('monitor_missing_volumes', {}).get('search_enabled', True),
                        download_enabled=config.get('monitor_missing_volumes', {}).get('auto_download_enabled', False)
                    )
                    
                    print(f"  ✓ {stats_missing['total_series']} séries, "
                          f"{stats_missing['total_missing']} volumes manquants, "
                          f"{stats_missing['searches_performed']} recherches, "
                          f"{stats_missing['downloads_sent']} téléchargements")
                    print(f"[{timestamp}] ✅ Vérification des volumes manquants complétée")
                
            except Exception as e:
                logger.error(f"Erreur vérification volumes manquants: {e}", exc_info=True)
    
    def _run_new_volume_monitor(self):
        """Fonction appelée par le scheduler pour surveiller uniquement les nouveaux volumes"""
        if not self.app:
            logger.error("App Flask non initialisée")
            return
        
        with self.app.app_context():
            try:
                timestamp = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
                print(f"\n[{timestamp}] ✨ Vérification des nouveaux volumes en cours...")
                
                from . import monitor_manager
                from blueprints.missing_monitor.routes import load_monitor_config
                
                config = load_monitor_config()
                
                # Vérifier les nouveaux volumes
                if config.get('monitor_new_volumes', {}).get('enabled', False):
                    stats_new = monitor_manager.run_new_volume_check(
                        auto_download_enabled=config.get('monitor_new_volumes', {}).get('auto_download_enabled', False)
                    )
                    
                    print(f"  ✓ {stats_new['nautiljon_checks']} vérifications Nautiljon, "
                          f"{stats_new['new_volumes_found']} nouveaux volumes trouvés, "
                          f"{stats_new['downloads_sent']} téléchargements")
                    print(f"[{timestamp}] ✅ Vérification des nouveaux volumes complétée")
                
            except Exception as e:
                logger.error(f"Erreur vérification nouveaux volumes: {e}", exc_info=True)


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
        
        N'utilise PAS Nautiljon - seulement EBDZ et Prowlarr
        
        Args:
            search_enabled: Activer la recherche automatique
            download_enabled: Activer l'envoi automatique aux clients
            
        Returns:
            Statistiques de l'exécution
        """
        from datetime import datetime as dt
        
        if not self.detector:
            self.initialize()
        
        check_start = dt.now()
        
        stats = {
            'check_type': 'missing_volumes',
            'total_series': 0,
            'total_missing': 0,
            'searches_performed': 0,
            'results_found': 0,
            'downloads_sent': 0,
            'errors': [],
            'duration_seconds': 0,
            'cache_stats': {},
            'request_stats': {}
        }
        
        try:
            # Récupérer les séries en surveillance
            series_list = self.detector.get_monitored_series()
            stats['total_series'] = len(series_list)
            
            total_missing = sum(len(s['missing_volumes']) for s in series_list)
            stats['total_missing'] = total_missing
            
            # Optimaliser les sources selon la volumétrie
            if series_list and search_enabled:
                preferred_sources = series_list[0].get('search_sources', ['ebdz', 'prowlarr'])
                optimized_sources = self.searcher._optimizer.should_prioritize_source(
                    len(series_list), total_missing, preferred_sources
                )
                print(f"🎯 Sources optimisées pour {total_missing} volumes: {optimized_sources}")
            
            for series in series_list:
                if not series['enabled']:
                    continue
                
                series_id = series['series_id']
                monitor_id = series['monitor_id']
                title = series['title']
                sources = series['search_sources']
                auto_download = series['auto_download_enabled']
                
                # Chercher les volumes manquants (sans Nautiljon)
                for vol_num in series['missing_volumes']:
                    if search_enabled and sources:
                        try:
                            results = self.searcher.search_for_volume(
                                title, vol_num, sources
                            )
                        except Exception as e:
                            msg = f"Erreur recherche {title} vol {vol_num}: {e}"
                            stats['errors'].append(msg)
                            logger.error(msg)
                            continue
                        
                        if results:
                            stats['searches_performed'] += 1
                            stats['results_found'] += len(results)
                            
                            # Envoyer au client si configuré
                            if auto_download and results:
                                # Grouper les résultats par source
                                by_source = {}
                                for result in results:
                                    source = result.get('source', 'unknown')
                                    if source not in by_source:
                                        by_source[source] = result
                                
                                # Envoyer le meilleur résultat de chaque source
                                for source, result in by_source.items():
                                    link = result.get('link', '')
                                    
                                    if link:
                                        try:
                                            # Le downloader auto-détecte le client selon le type de lien
                                            success, msg = self.downloader.send_torrent_download(
                                                link, title, vol_num
                                            )
                                            if success:
                                                stats['downloads_sent'] += 1
                                            
                                            print(msg)
                                        except Exception as e:
                                            msg = f"Erreur envoi {source} pour {title} vol {vol_num}: {e}"
                                            stats['errors'].append(msg)
                                            logger.error(msg)
                                            # Continuer avec les autres sources au lieu de s'arrêter
                                            continue
                
                # Mettre à jour le timestamp de vérification
                if monitor_id:
                    self.detector.update_last_checked(monitor_id)
        
        except Exception as e:
            msg = f"Erreur exécution surveillance: {e}"
            stats['errors'].append(msg)
            logger.error(msg, exc_info=True)
        
        # Ajouter les stats de performance
        stats['duration_seconds'] = (dt.now() - check_start).total_seconds()
        
        if search_enabled and hasattr(self.searcher, '_cache'):
            stats['cache_stats'] = self.searcher._cache.stats()
        
        return stats
    
    def run_new_volume_check(self, auto_download_enabled: bool = False) -> Dict:
        """Détecte les nouveaux volumes via Nautiljon, puis cherche sur EBDZ/Prowlarr
        
        Flux:
        1. Vérifier sur Nautiljon s'il y a un nouveau volume
        2. Si OUI: Chercher sur EBDZ et Prowlarr
        3. Si NON: Ignorer cette série
        
        Args:
            auto_download_enabled: Activer l'envoi automatique aux clients
            
        Returns:
            Statistiques de l'exécution
        """
        from datetime import datetime as dt
        
        if not self.detector:
            self.initialize()
        
        check_start = dt.now()
        
        stats = {
            'check_type': 'new_volumes',
            'total_series': 0,
            'nautiljon_checks': 0,
            'new_volumes_found': 0,
            'searches_performed': 0,
            'results_found': 0,
            'downloads_sent': 0,
            'errors': [],
            'duration_seconds': 0
        }
        
        try:
            # Récupérer toutes les séries en surveillance (pas seulement celles avec volumes manquants)
            series_list = self.detector.get_series_for_new_volume_check()
            stats['total_series'] = len(series_list)
            
            for series in series_list:
                if not series['enabled']:
                    continue
                
                title = series['title']
                current_total = series['total_volumes'] or 0
                nautiljon_total = series['nautiljon_total_volumes'] or 0
                
                try:
                    # 1. Vérifier sur Nautiljon s'il y a un nouveau volume
                    has_new_volume, new_total = self.searcher.check_new_volume_on_nautiljon(
                        title, current_total
                    )
                    stats['nautiljon_checks'] += 1
                    
                    if has_new_volume:
                        # Il y a un nouveau volume!
                        new_volume_num = current_total + 1
                        
                        print(f"✨ Nouveau volume détecté: {title} Vol {new_volume_num} "
                              f"(Nautiljon: {new_total})")
                        
                        stats['new_volumes_found'] += 1
                        
                        # 2. Chercher le nouveau volume sur EBDZ et Prowlarr
                        results = self.searcher.search_for_new_volumes(
                            title, new_volume_num
                        )
                        
                        if results:
                            stats['searches_performed'] += 1
                            stats['results_found'] += len(results)
                            print(f"   Trouvé {len(results)} résultat(s)")
                            
                            # 3. Envoyer au client si configuré
                            if auto_download_enabled and results:
                                best_result = results[0]
                                link = best_result.get('link', '')
                                
                                if link:
                                    success, msg = self.downloader.send_torrent_download(
                                        link, title, new_volume_num
                                    )
                                    if success:
                                        stats['downloads_sent'] += 1
                                    
                                    print(msg)
                
                except Exception as e:
                    msg = f"Erreur vérification {title}: {e}"
                    stats['errors'].append(msg)
                    logger.error(msg)
        
        except Exception as e:
            msg = f"Erreur exécution surveillance nouveaux volumes: {e}"
            stats['errors'].append(msg)
            logger.error(msg, exc_info=True)
        
        # Ajouter les stats de performance
        stats['duration_seconds'] = (dt.now() - check_start).total_seconds()
        
        return stats


# Instance globale du gestionnaire
monitor_manager = MonitorManager()
