"""
Recherche de volumes manquants sur les sources configurées
"""
import json
import requests
from typing import List, Dict, Optional
from flask import current_app
from datetime import datetime


class MissingVolumeSearcher:
    """Recherche les volumes manquants sur les sources disponibles"""
    
    def __init__(self):
        self.sources = {
            'ebdz': self._search_ebdz,
            'prowlarr': self._search_prowlarr,
            'nautiljon': self._search_nautiljon,
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
        
        all_results = []
        
        for source in sources:
            if source not in self.sources:
                continue
            
            try:
                results = self.sources[source](title, volume_num)
                if results:
                    all_results.extend(results)
            except Exception as e:
                print(f"⚠️  Erreur recherche {source}: {e}")
        
        # Dédupliquer et trier par score de pertinence
        return self._deduplicate_and_rank(all_results, title, volume_num)
    
    def _search_ebdz(self, title: str, volume_num: int) -> List[Dict]:
        """Recherche sur EBDZ via l'API existante"""
        try:
            # Utiliser l'API EBDZ existante
            from blueprints.ebdz.scraper import MyBBScraper
            
            # Charger la configuration EBDZ
            config_file = current_app.config.get('EBDZ_CONFIG_FILE', 'data/ebdz_config.json')
            if not config_file:
                return []
            
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
            except:
                return []
            
            from encryption import decrypt
            username = config.get('username', '')
            password = decrypt(config.get('password', ''))
            
            if not username or not password:
                return []
            
            # Essayer plusieurs variations de recherche
            search_terms = [
                f"{title} vol {volume_num}",
                f"{title} volume {volume_num}",
                f"{title} {volume_num}",
            ]
            
            results = []
            for search_term in search_terms:
                try:
                    # Effectuer une recherche sur EBDZ
                    # Cette fonctionnalité dépend de la structure du scraper EBDZ
                    response = self._search_ebdz_forum(search_term, username, password)
                    if response:
                        results.extend(response)
                except:
                    continue
            
            return results
        except Exception as e:
            print(f"Erreur EBDZ search: {e}")
            return []
    
    def _search_ebdz_forum(self, search_term: str, username: str, password: str) -> List[Dict]:
        """Recherche sur EBDZ forum"""
        try:
            # Note: Cette implémentation dépend de l'API EBDZ
            # Pour l'instant, retourner une liste vide
            # L'intégration complète nécessiterait une API de recherche EBDZ
            return []
        except:
            return []
    
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
            
            url = f"http://{config.get('url', '127.0.0.1')}:{config.get('port', 9696)}"
            api_key = config.get('api_key')
            
            # Recherche via Prowlarr API
            response = requests.get(
                f"{url}/api/v1/search",
                params={
                    'query': f"{title} vol {volume_num}",
                    'apikey': api_key
                },
                timeout=10
            )
            
            if response.status_code == 200:
                data = response.json()
                results = []
                for item in data.get('results', [])[:10]:  # Limiter à 10 résultats
                    results.append({
                        'source': 'prowlarr',
                        'title': item.get('title', ''),
                        'link': item.get('downloadUrl', ''),
                        'size': item.get('size', 0),
                        'seeders': item.get('seeders', 0),
                        'indexer': item.get('indexerName', ''),
                        'score': self._calculate_relevance_score(
                            item.get('title', ''), title, volume_num
                        )
                    })
                return results
        except Exception as e:
            print(f"Erreur Prowlarr search: {e}")
        
        return []
    
    def _search_nautiljon(self, title: str, volume_num: int) -> List[Dict]:
        """Recherche info Nautiljon pour confirmer l'existence du volume"""
        try:
            from blueprints.nautiljon.scraper import NautiljonScraper
            
            scraper = NautiljonScraper()
            info = scraper.get_manga_info(title)
            
            if info and info.get('total_volumes'):
                total = info['total_volumes']
                if volume_num <= total:
                    return [{
                        'source': 'nautiljon',
                        'title': f"{title} - Vol {volume_num}",
                        'link': info.get('url', ''),
                        'status': info.get('status', ''),
                        'score': 100  # Confirmé par Nautiljon
                    }]
        except Exception as e:
            print(f"Erreur Nautiljon search: {e}")
        
        return []
    
    def _calculate_relevance_score(self, result_title: str, manga_title: str, volume_num: int) -> int:
        """Calcule un score de pertinence pour un résultat
        
        Returns:
            Score entre 0 et 100
        """
        score = 0
        result_lower = result_title.lower()
        manga_lower = manga_title.lower()
        
        # Titre du manga présent
        if manga_lower in result_lower:
            score += 40
        
        # Numéro de volume présent
        if str(volume_num) in result_title:
            score += 30
        
        # Contient "vol" ou "tome"
        if 'vol' in result_lower or 'tome' in result_lower:
            score += 15
        
        # Pas de caractères spéciaux suspects
        if '[' not in result_title and '{' not in result_title:
            score += 15
        
        return min(score, 100)
    
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
            elif not link:
                # Garder les résultats sans lien (Nautiljon par exemple)
                unique_results.append(result)
        
        # Trier par score (décroissant) puis par source (priorité)
        source_priority = {'nautiljon': 100, 'prowlarr': 50, 'ebdz': 40}
        
        def sort_key(item):
            source_score = source_priority.get(item.get('source', ''), 10)
            relevance = item.get('score', 0)
            seeders = item.get('seeders', 0)
            return (-relevance, -source_score, -seeders)
        
        return sorted(unique_results, key=sort_key)
