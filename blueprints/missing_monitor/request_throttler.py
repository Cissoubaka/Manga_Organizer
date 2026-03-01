"""
Gestionnaire de throttling pour limiter les requêtes aux sources externes (Prowlarr, etc.)
"""
import time
from typing import Callable, Any, Dict, List
from datetime import datetime, timedelta
import threading
from functools import wraps


class RequestThrottler:
    """Limite le nombre de requêtes vers les sources externes"""
    
    def __init__(self, requests_per_minute: int = 6):
        """
        Initialise le throttler
        
        Args:
            requests_per_minute: Nombre maximal de requêtes par minute
        """
        self.requests_per_minute = requests_per_minute
        self.min_interval = 60.0 / requests_per_minute  # Délai minimum entre requêtes
        self.last_request_time = {}  # Par source
        self.request_queue = {}  # Requêtes en attente par source
        self.lock = threading.Lock()
    
    def wait_if_needed(self, source: str):
        """Attend si nécessaire avant d'effectuer une requête
        
        Args:
            source: Nom de la source (prowlarr, ebdz, etc.)
        """
        with self.lock:
            current_time = time.time()
            
            if source not in self.last_request_time:
                self.last_request_time[source] = 0
            
            last_time = self.last_request_time[source]
            time_since_last = current_time - last_time
            
            if time_since_last < self.min_interval:
                wait_time = self.min_interval - time_since_last
                time.sleep(wait_time)
            
            self.last_request_time[source] = time.time()
    
    def can_request(self, source: str) -> bool:
        """Vérifie si on peut faire une requête sans throttling
        
        Args:
            source: Nom de la source
            
        Returns:
            True si on peut faire une requête
        """
        with self.lock:
            current_time = time.time()
            
            if source not in self.last_request_time:
                return True
            
            last_time = self.last_request_time[source]
            time_since_last = current_time - last_time
            
            return time_since_last >= self.min_interval
    
    def set_request_rate(self, source: str, requests_per_minute: int):
        """Configure le taux de requêtes pour une source spécifique
        
        Args:
            source: Nom de la source
            requests_per_minute: Taux pour cette source
        """
        with self.lock:
            if source not in self.request_queue:
                self.request_queue[source] = {
                    'rate': 60.0 / requests_per_minute,
                    'last_time': 0
                }
            else:
                self.request_queue[source]['rate'] = 60.0 / requests_per_minute


class SearchResultCache:
    """Cache simple pour les résultats de recherche"""
    
    def __init__(self, cache_duration_minutes: int = 60):
        """
        Initialise le cache
        
        Args:
            cache_duration_minutes: Durée de vie du cache en minutes
        """
        self.cache_duration = timedelta(minutes=cache_duration_minutes)
        self.cache = {}  # {cache_key: (results, timestamp)}
        self.lock = threading.Lock()
    
    def generate_key(self, source: str, title: str, volume_num: int) -> str:
        """Génère une clé de cache
        
        Args:
            source: Source de recherche
            title: Titre du manga
            volume_num: Numéro du volume
            
        Returns:
            Clé de cache
        """
        return f"{source}:{title.lower()}:vol{volume_num}"
    
    def get(self, key: str) -> Any:
        """Récupère une valeur du cache
        
        Args:
            key: Clé de cache
            
        Returns:
            Résultats ou None si expiré/non trouvé
        """
        with self.lock:
            if key not in self.cache:
                return None
            
            results, timestamp = self.cache[key]
            
            if datetime.now() - timestamp > self.cache_duration:
                del self.cache[key]
                return None
            
            return results
    
    def set(self, key: str, results: List[Dict]):
        """Stocke une valeur dans le cache
        
        Args:
            key: Clé de cache
            results: Résultats à cacher
        """
        with self.lock:
            self.cache[key] = (results, datetime.now())
    
    def clear(self):
        """Vide le cache"""
        with self.lock:
            self.cache.clear()
    
    def stats(self) -> Dict:
        """Retourne des stats sur le cache"""
        with self.lock:
            return {
                'total_entries': len(self.cache),
                'cache_size_bytes': sum(
                    len(str(results)) for results, _ in self.cache.values()
                )
            }


class SmartSearchOptimizer:
    """Optimise les requêtes de recherche en regroupant les termes similaires"""
    
    @staticmethod
    def should_prioritize_source(series_count: int, total_volumes: int, preferred_sources: List[str]) -> List[str]:
        """Détermine l'ordre optimal des sources selon la volumétrie
        
        Args:
            series_count: Nombre de séries à surveiller
            total_volumes: Nombre total de volumes manquants
            preferred_sources: Sources préférées
            
        Returns:
            Sources triées par priorité
        """
        # Si peu de requêtes, on peut utiliser toutes les sources
        if total_volumes < 20:
            return preferred_sources
        
        # Si beaucoup de requêtes, utiliser d'abord les sources locales (EBDZ)
        # puis Prowlarr, et éviter les surcharges sur les services externes
        priority = []
        
        # EBDZ : local, pas de limite
        if 'ebdz' in preferred_sources:
            priority.append('ebdz')
        
        # Nautiljon : confirmation rapide de l'existence
        if 'nautiljon' in preferred_sources:
            priority.append('nautiljon')
        
        # Prowlarr : rate-limited
        if 'prowlarr' in preferred_sources:
            priority.append('prowlarr')
        
        return priority
    
    @staticmethod
    def batch_search_queries(series_list: List[Dict]) -> Dict[str, List[Dict]]:
        """Regroupe les séries par rangées pour optimiser les requêtes
        
        Args:
            series_list: Liste des séries avec volumes manquants
            
        Returns:
            Dict: {source: [requêtes optimisées]}
        """
        batches = {
            'series_with_few_volumes': [],  # 1-2 volumes
            'series_with_many_volumes': [],  # 3+ volumes
            'series_missing_entire_range': []  # Bande manquante complète
        }
        
        for series in series_list:
            missing_count = len(series.get('missing_volumes', []))
            
            if missing_count == 0:
                continue
            elif missing_count <= 2:
                batches['series_with_few_volumes'].append(series)
            else:
                # Vérifier si c'est une bande continue
                missing_vols = sorted(series['missing_volumes'])
                is_continuous_range = (
                    missing_vols[-1] - missing_vols[0] + 1 == len(missing_vols)
                )
                
                if is_continuous_range and missing_count >= 3:
                    batches['series_missing_entire_range'].append(series)
                else:
                    batches['series_with_many_volumes'].append(series)
        
        return batches

