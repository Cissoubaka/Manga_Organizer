"""
Détecteur de volumes manquants
"""
import sqlite3
import json
from flask import current_app
from datetime import datetime, timedelta
from typing import List, Dict, Tuple


class MissingVolumeDetector:
    """Détecte les volumes manquants dans les séries suivies"""
    
    def __init__(self, db_path=None):
        self.db_path = db_path or current_app.config['DATABASE']
    
    def get_monitored_series(self) -> List[Dict]:
        """Récupère toutes les séries en surveillance avec volumes manquants
        
        Returns:
            Liste des séries avec volumes manquants
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT 
                s.id,
                s.title,
                s.path,
                s.total_volumes,
                s.missing_volumes,
                s.nautiljon_total_volumes,
                s.nautiljon_status,
                l.name as library_name,
                mm.id as monitor_id,
                mm.enabled,
                mm.last_checked,
                mm.search_sources,
                mm.auto_download_enabled
            FROM series s
            JOIN libraries l ON s.library_id = l.id
            JOIN missing_volume_monitor mm ON s.id = mm.series_id
            WHERE s.missing_volumes != '[]'
            AND mm.enabled = 1
            ORDER BY s.title
        ''')
        
        series_list = []
        for row in cursor.fetchall():
            missing_vols = json.loads(row[4]) if row[4] else []
            
            if missing_vols:
                series_list.append({
                    'series_id': row[0],
                    'title': row[1],
                    'path': row[2],
                    'total_volumes': row[3],
                    'missing_volumes': missing_vols,
                    'nautiljon_total_volumes': row[5],
                    'nautiljon_status': row[6],
                    'library_name': row[7],
                    'monitor_id': row[8],
                    'enabled': row[9] if row[9] is not None else True,
                    'last_checked': row[10],
                    'search_sources': json.loads(row[11]) if row[11] else ['ebdz', 'prowlarr'],
                    'auto_download_enabled': row[12] if row[12] is not None else False
                })
        
        conn.close()
        return series_list
    
    def get_series_for_new_volume_check(self) -> List[Dict]:
        """Récupère les séries en surveillance pour vérifier les nouveaux volumes
        
        Returns:
            Liste des séries avec leurs infos actuelles (pas seulement les volumes manquants)
        """
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        
        # Récupérer TOUTES les séries en surveillance (pas seulement celles avec volumes manquants)
        cursor.execute('''
            SELECT 
                s.id,
                s.title,
                s.total_volumes,
                s.nautiljon_total_volumes,
                s.nautiljon_status,
                l.name as library_name,
                mnm.id as monitor_id,
                mnm.enabled
            FROM series s
            JOIN libraries l ON s.library_id = l.id
            JOIN missing_volume_monitor mnm ON s.id = mnm.series_id
            WHERE mnm.enabled = 1
            ORDER BY s.title
        ''')
        
        series_list = []
        for row in cursor.fetchall():
            series_list.append({
                'series_id': row[0],
                'title': row[1],
                'total_volumes': row[2],
                'nautiljon_total_volumes': row[3],
                'nautiljon_status': row[4],
                'library_name': row[5],
                'monitor_id': row[6],
                'enabled': row[7]
            })
        
        conn.close()
        return series_list
    
    def get_series_by_status(self, status: str) -> List[Dict]:
        """Récupère les séries filtrées par statut
        
        Args:
            status: 'incomplete', 'missing', 'incomplete_missing' ou 'all'
            
        Returns:
            Liste des séries correspondantes
        """
        series = self.get_monitored_series()
        
        if status == 'incomplete':
            # Série incomplète: volumes manquants + pas terminée sur Nautiljon
            return [s for s in series 
                   if s['nautiljon_status'] and 
                   not s['nautiljon_status'].lower().startswith('termin')]
        
        elif status == 'missing':
            # Série avec "volumes manquants": terminée sur Nautiljon + volumes manquants
            return [s for s in series 
                   if s['nautiljon_status'] and 
                   s['nautiljon_status'].lower().startswith('termin')]
        
        elif status == 'incomplete_missing':
            # Les deux
            return series
        
        return series
    
    def get_search_queries(self, series: Dict) -> List[str]:
        """Génère les requêtes de recherche pour une série
        
        Args:
            series: Données de la série
            
        Returns:
            Liste de requêtes de recherche (ex: "Manga Title vol 1 scan")
        """
        queries = []
        title = series['title'].strip()
        
        for vol_num in series['missing_volumes']:
            # Format: "Manga Title vol 1"
            queries.append(f"{title} vol {vol_num}")
            queries.append(f"{title} volume {vol_num}")
            
            # Variantes courantes
            queries.append(f"{title} {vol_num}")
        
        return queries
    
    def create_monitor_entry(self, series_id: int, config_data: Dict = None) -> bool:
        """Crée une entrée de surveillance pour une série
        
        Args:
            series_id: ID de la série
            config_data: Configuration optionnelle (sources, auto_download, etc.)
            
        Returns:
            True si succès
        """
        if config_data is None:
            config_data = {}
        
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        try:
            # Vérifier si une entrée existe déjà
            cursor.execute('SELECT id FROM missing_volume_monitor WHERE series_id = ?', (series_id,))
            if cursor.fetchone():
                conn.close()
                return True  # Déjà existante
            
            enabled = config_data.get('enabled', True)
            search_sources = json.dumps(config_data.get('search_sources', 
                                                       ['ebdz', 'prowlarr', 'nautiljon']))
            auto_download = config_data.get('auto_download_enabled', False)
            
            cursor.execute('''
                INSERT INTO missing_volume_monitor 
                (series_id, enabled, search_sources, auto_download_enabled, created_at)
                VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (series_id, enabled, search_sources, auto_download))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Erreur création monitor: {e}")
            conn.close()
            return False
    
    def update_last_checked(self, monitor_id: int) -> bool:
        """Met à jour le timestamp de dernière vérification
        
        Args:
            monitor_id: ID du monitor
            
        Returns:
            True si succès
        """
        if not monitor_id:
            return False
        
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        cursor = conn.cursor()
        
        try:
            cursor.execute('''
                UPDATE missing_volume_monitor
                SET last_checked = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (monitor_id,))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Erreur update last_checked: {e}")
            conn.close()
            return False
    
    def get_monitored_series_count(self) -> int:
        """Compte le nombre de séries en surveillance"""
        series = self.get_monitored_series()
        return len(series)
    
    def get_total_missing_volumes(self) -> int:
        """Compte le nombre total de volumes manquants"""
        series = self.get_monitored_series()
        return sum(len(s['missing_volumes']) for s in series)
