"""
Gestionnaire du scraping automatique pour ebdz.net
"""
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import json
import os
from datetime import datetime


class EBDZScheduler:
    """Gestionnaire du scraping automatique EBDZ"""
    
    def __init__(self, app=None):
        self.scheduler = None
        self.app = app
        self.job_id = 'ebdz_auto_scrape'
        
    def init_app(self, app):
        """Initialiser le scheduler avec l'app Flask"""
        self.app = app
        
    def start(self):
        """Démarrer le scheduler"""
        if self.scheduler is None:
            self.scheduler = BackgroundScheduler(daemon=True)
            self.scheduler.start()
            print("✓ Scheduler EBDZ démarré")
        
    def stop(self):
        """Arrêter le scheduler"""
        if self.scheduler and self.scheduler.running:
            self.scheduler.shutdown(wait=False)
            self.scheduler = None
            print("✓ Scheduler EBDZ arrêté")
    
    def add_job(self, interval_value, interval_unit):
        """Ajouter une tâche de scraping automatique"""
        self.start()
        
        # Supprimer la tâche existante si elle existe
        if self.scheduler.get_job(self.job_id):
            self.scheduler.remove_job(self.job_id)
        
        # Ajouter la nouvelle tâche
        self.scheduler.add_job(
            func=self._scrape_ebdz,
            trigger=IntervalTrigger(**{interval_unit: interval_value}),
            id=self.job_id,
            name='EBDZ Auto Scrape',
            replace_existing=True
        )
        
        print(f"✓ Tâche de scraping EBDZ programmée: tous les {interval_value} {interval_unit}")
    
    def remove_job(self):
        """Supprimer la tâche de scraping automatique"""
        if self.scheduler and self.scheduler.get_job(self.job_id):
            self.scheduler.remove_job(self.job_id)
            print("✓ Tâche de scraping EBDZ supprimée")
    
    def _scrape_ebdz(self):
        """Fonction appelée par le scheduler pour scraper EBDZ"""
        if not self.app:
            print("Erreur: App Flask non initialisée")
            return
        
        with self.app.app_context():
            try:
                print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] 🕷️ Scraping automatique EBDZ en cours...")
                
                # Import local pour éviter les boucles circulaires
                from . import routes
                from .scraper import MyBBScraper
                import sqlite3
                from flask import current_app
                from encryption import decrypt
                
                # Charger la configuration EBDZ
                config = routes.load_ebdz_config()
                username = config.get('username', '')
                password = config.get('password_decrypted', '')
                all_forums = config.get('forums', [])
                
                if not username or not password or not all_forums:
                    print("⚠️ Configuration EBDZ incomplète, scraping annulé")
                    return
                
                total_links = 0
                forums_scraped = 0
                
                for forum_cfg in all_forums:
                    fid = forum_cfg['fid']
                    category = forum_cfg['category']
                    max_pages = forum_cfg.get('max_pages')
                    
                    forum_url = f"https://ebdz.net/forum/forumdisplay.php?fid={fid}"
                    
                    print(f"  → Forum fid={fid} catégorie='{category}'...")
                    
                    scraper = MyBBScraper(
                        base_url=forum_url,
                        db_file=current_app.config['DB_FILE'],
                        username=username,
                        password=password,
                        forum_category=category
                    )
                    
                    scraper.run(max_pages=max_pages)
                    forums_scraped += 1
                    
                    # Compter les liens
                    try:
                        conn = sqlite3.connect(current_app.config['DB_FILE'])
                        cursor = conn.cursor()
                        cursor.execute('SELECT COUNT(*) FROM ed2k_links WHERE forum_category = ?', (category,))
                        count = cursor.fetchone()[0]
                        total_links += count
                        conn.close()
                    except:
                        pass
                
                print(f"✓ Scraping EBDZ terminé: {forums_scraped} forum(s), {total_links} lien(s)")
                
            except Exception as e:
                print(f"✗ Erreur lors du scraping automatique EBDZ: {e}")
                import traceback
                traceback.print_exc()


# Instance globale du scheduler
ebdz_scheduler = EBDZScheduler()
