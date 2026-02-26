"""
Recherche de volumes manquants sur les sources configurées
"""
import json
import requests
import os
from typing import List, Dict, Optional
from flask import current_app
from datetime import datetime
from .request_throttler import RequestThrottler, SearchResultCache, SmartSearchOptimizer


class MissingVolumeSearcher:
    """Recherche les volumes manquants sur les sources disponibles"""
    
    # Instance partagée du throttler et du cache (global)
    _throttler = RequestThrottler(requests_per_minute=30)
    _cache = SearchResultCache(cache_duration_minutes=60)
    _optimizer = SmartSearchOptimizer()
    
    def __init__(self):
        self.sources = {
            'ebdz': self._search_ebdz,
            'prowlarr': self._search_prowlarr,
        }
    
    def search_for_volume(self, title: str, volume_num: int, sources: List[str] = None) -> List[Dict]:
        """Recherche un volume spécifique sur les sources
        
        Args:
            title: Titre du manga
            volume_num: Numéro du volume
            sources: Liste des sources à utiliser (par défaut toutes)
            
        Returns:
            Liste des résultats trouvés
        """
        if sources is None:
            sources = list(self.sources.keys())
        
        # Retirer Nautiljon des sources pour la recherche de volumes manquants
        # (Nautiljon ne retourne que des URLs sans liens de DL)
        sources = [s for s in sources if s != 'nautiljon']
        
        all_results = []
        
        for source in sources:
            if source not in self.sources:
                continue
            
            try:
                # Vérifier le cache d'abord
                cache_key = self._cache.generate_key(source, title, volume_num)
                cached_results = self._cache.get(cache_key)
                
                if cached_results is not None:
                    print(f"📦 Cache hit: {title} vol {volume_num} from {source}")
                    all_results.extend(cached_results)
                    continue
                
                # Throttle Prowlarr pour éviter les surcharges
                if source == 'prowlarr':
                    self._throttler.wait_if_needed('prowlarr')
                
                results = self.sources[source](title, volume_num)
                
                if results:
                    # Mettre en cache les résultats
                    self._cache.set(cache_key, results)
                    all_results.extend(results)
            except Exception as e:
                print(f"⚠️  Erreur recherche {source}: {e}")
        
        # Dédupliquer et trier par score de pertinence
        return self._deduplicate_and_rank(all_results, title, volume_num)
    
    def check_new_volume_on_nautiljon(self, title: str, current_total: int) -> tuple[bool, int]:
        """Vérifie s'il y a un nouveau volume sur Nautiljon
        
        Args:
            title: Titre du manga
            current_total: Nombre de volumes actuellement connus
            
        Returns:
            (has_new_volume: bool, nautiljon_total: int)
        """
        try:
            from blueprints.nautiljon.scraper import NautiljonScraper
            
            scraper = NautiljonScraper()
            info = scraper.get_manga_info(title)
            
            if info and info.get('total_volumes'):
                nautiljon_total = int(info['total_volumes'])
                has_new = nautiljon_total > current_total
                
                return (has_new, nautiljon_total)
        except Exception as e:
            print(f"⚠️  Erreur vérification Nautiljon: {e}")
        
        return (False, current_total)
    
    def search_for_new_volumes(self, title: str, new_volume_num: int, sources: List[str] = None) -> List[Dict]:
        """Recherche les nouveaux volumes détectés sur Nautiljon
        
        Args:
            title: Titre du manga
            new_volume_num: Numéro du nouveau volume détecté
            sources: Sources à utiliser (par défaut EBDZ + Prowlarr)
            
        Returns:
            Résultats de recherche pour le nouveau volume
        """
        if sources is None:
            sources = ['ebdz', 'prowlarr']  # EBDZ et Prowlarr seulement
        
        # S'assurer que Nautiljon n'est pas inclus
        sources = [s for s in sources if s != 'nautiljon']
        
        return self.search_for_volume(title, new_volume_num, sources)
    
    def _search_ebdz(self, title: str, volume_num: int) -> List[Dict]:
        """Recherche dans la base de données EBDZ (ed2k_links)"""
        try:
            import sqlite3
            
            # Utiliser la même base de données que la page search
            db_path = current_app.config.get('DB_FILE', 'data/ebdz.db')
            
            if not db_path or not os.path.exists(db_path):
                return []
            
            conn = sqlite3.connect(db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            # Vérifier si la table ed2k_links existe
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ed2k_links'")
            if not cursor.fetchone():
                conn.close()
                return []
            
            # Nettoyer la requête
            clean_title = self._clean_series_name(title)
            
            # Recherche dans la base de données
            sql = '''
                SELECT DISTINCT thread_id, thread_title, thread_url, forum_category, 
                       link, filename, filesize, volume
                FROM ed2k_links
                WHERE 1=1
                AND (thread_title LIKE ? OR filename LIKE ? OR thread_title LIKE ? OR filename LIKE ?)
                AND volume = ?
                ORDER BY thread_id DESC
                LIMIT 10
            '''
            
            search_term_clean = f'%{clean_title}%'
            search_term_orig = f'%{title}%'
            
            cursor.execute(sql, [search_term_clean, search_term_clean, search_term_orig, search_term_orig, volume_num])
            rows = cursor.fetchall()
            
            results = []
            for row in rows:
                results.append({
                    'source': 'ebdz',
                    'title': row[1],  # thread_title
                    'link': row[4],   # ed2k_link
                    'filename': row[5],
                    'size': row[6],
                    'volume': row[7],
                    'forum': row[3],
                    'score': 100  # Score de pertinence maximal pour EBDZ
                })
            
            conn.close()
            return results
            
        except Exception as e:
            print(f"Erreur EBDZ search: {e}")
            return []
    
    def _clean_series_name(self, name: str) -> str:
        """Nettoie le nom d'une série pour la recherche"""
        if not name:
            return ""
        
        import re
        
        # Convertir en minuscules
        cleaned = name.lower().strip()
        
        # Enlever les ponctuations
        chars_to_remove = ',;:\'"' + '`'
        for char in chars_to_remove:
            cleaned = cleaned.replace(char, '')
        
        cleaned = cleaned.replace('.', '')
        
        # Normaliser les espaces
        cleaned = re.sub(r'\s+', ' ', cleaned)
        cleaned = cleaned.strip()
        
        return cleaned
    
    def _search_prowlarr(self, title: str, volume_num: int) -> List[Dict]:
        """Recherche via Prowlarr"""
        try:
            config_file = current_app.config.get('PROWLARR_CONFIG_FILE', 'data/prowlarr_config.json')
            if not config_file:
                return []
            
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
            except:
                return []
            
            if not config.get('enabled') or not config.get('api_key'):
                return []
            
            # Construire l'URL en gérant les schémas (http://, https://)
            url_base = config.get('url', '127.0.0.1').strip()
            
            # Enlever le schéma s'il est présent
            if url_base.startswith('http://'):
                url_base = url_base[7:]
                scheme = 'http'
            elif url_base.startswith('https://'):
                url_base = url_base[8:]
                scheme = 'https'
            else:
                scheme = 'http'
            
            # Enlever le port s'il est dans l'URL
            url_base = url_base.split(':')[0]
            
            port = config.get('port', 9696)
            url = f"{scheme}://{url_base}:{port}"
            
            # Déchiffrer la clé API si nécessaire
            api_key = config.get('api_key')
            if api_key:
                from encryption import decrypt
                decrypted = decrypt(api_key)
                if decrypted:
                    api_key = decrypted
            
            if not api_key:
                return []
            
            # Nettoyer le titre comme dans la recherche standard
            clean_title = self._clean_series_name(title)
            search_title = clean_title
            if volume_num:
                search_title += f' {volume_num}'
            
            # Construire les paramètres de la requête
            params = {
                'query': search_title,
                'type': 'search'
            }
            
            # Ajouter les indexeurs sélectionnés s'il y en a
            selected_indexers = config.get('selected_indexers', [])
            if selected_indexers:
                params['indexerIds'] = selected_indexers
            
            # Ajouter les catégories sélectionnées
            selected_categories_config = config.get('selected_categories', {})
            all_categories = set()
            for indexer_id in selected_indexers:
                indexer_id_str = str(indexer_id)
                if indexer_id_str in selected_categories_config:
                    all_categories.update(selected_categories_config[indexer_id_str])
            
            if all_categories:
                params['categories'] = list(all_categories)
            
            # Recherche via Prowlarr API avec les headers corrects
            headers = {'X-Api-Key': api_key}
            response = requests.get(
                f"{url}/api/v1/search",
                headers=headers,
                params=params,
                timeout=10
            )
            
            if response.status_code == 200:
                raw_data = response.json()
                data = raw_data if isinstance(raw_data, list) else raw_data.get('results', [])
                
                results = []
                query_lower = title.lower()
                query_words = query_lower.split()
                
                for item in data[:10]:  # Limiter à 10 résultats
                    item_title = item.get('title', '').lower()
                    
                    # Calculer un score de pertinence
                    score = 0
                    if query_lower in item_title:
                        score += 100
                    for word in query_words:
                        if len(word) > 2:
                            if word in item_title:
                                score += 50
                            elif item_title.startswith(word):
                                score += 75
                    
                    # Ajouter à la liste si score > 0
                    if score > 0:
                        results.append({
                            'source': 'prowlarr',
                            'title': item.get('title', ''),
                            'link': item.get('downloadUrl', '') or item.get('link', ''),
                            'guid': item.get('guid', ''),
                            'size': item.get('size', 0),
                            'seeders': item.get('seeders', 0),
                            'peers': item.get('peers', 0),
                            'publish_date': item.get('publishDate', ''),
                            'indexer': item.get('indexer', 'Prowlarr'),
                            'score': score
                        })
                
                # Trier par score puis par seeders
                results.sort(key=lambda x: (-x['score'], -(x.get('seeders', 0) or 0)))
                for result in results:
                    del result['score']
                
                return results
        except Exception as e:
            print(f"Erreur Prowlarr search: {e}")
        
        return []
    
    
    def _deduplicate_and_rank(self, results: List[Dict], title: str, volume_num: int) -> List[Dict]:
        """Déduplique et trie les résultats par pertinence
        
        Args:
            results: Liste des résultats bruts
            title: Titre du manga (pour calcul de score)
            volume_num: Numéro du volume
            
        Returns:
            Résultats dédupliqués et triés
        """
        # Dédupliquer par lien
        seen_links = set()
        unique_results = []
        
        for result in results:
            link = result.get('link', '').lower()
            if link and link not in seen_links:
                seen_links.add(link)
                unique_results.append(result)
        
        # Trier par score (décroissant) puis par source (priorité)
        # Note: Nautiljon n'est plus utilisé pour la recherche des volumes manquants
        source_priority = {'prowlarr': 50, 'ebdz': 40}
        
        def sort_key(item):
            source_score = source_priority.get(item.get('source', ''), 10)
            relevance = item.get('score', 0)
            seeders = item.get('seeders', 0)
            return (-relevance, -source_score, -seeders)
        
        return sorted(unique_results, key=sort_key)

