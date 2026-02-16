"""
Scraper pour Nautiljon.com - Récupère les infos sur les mangas
"""
import requests
from bs4 import BeautifulSoup
import re
import sqlite3
from urllib.parse import urljoin, quote
import time
import logging

logger = logging.getLogger(__name__)


class NautiljonScraper:
    """Scraper pour récupérer les infos des mangas sur Nautiljon"""
    
    def __init__(self):
        self.base_url = "https://www.nautiljon.com"
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'fr-FR,fr;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer': 'https://www.nautiljon.com/'
        })
        self.cache = {}  # Cache pour éviter les rechutes
    
    def search_manga(self, manga_title):
        """
        Recherche un manga sur Nautiljon
        Retourne une liste de résultats avec titre et URL
        """
        try:
            results = []
            
            # Nautiljon utilise la page /mangas/ avec un paramètre GET 'q'
            search_url = f"{self.base_url}/mangas/"
            params = {'q': manga_title}
            
            logger.info(f"Recherche Nautiljon: {manga_title}")
            
            response = self.session.get(search_url, params=params, timeout=10)
            response.encoding = 'utf-8'
            
            if response.status_code == 200:
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Chercher tous les liens vers des fiches de mangas
                # Les fiches sont dans /mangas/titre.html
                links = soup.find_all('a', href=True)
                
                for link in links:
                    href = link.get('href')
                    text = link.get_text(strip=True)
                    
                    # Vérifier que c'est un lien de manga (format /mangas/...html)
                    # et pas un lien de filtrage (contenant ?)
                    if (href.startswith('/mangas/') and 
                        href.endswith('.html') and 
                        '?' not in href and 
                        text and 
                        len(text) > 2):
                        
                        url = urljoin(self.base_url, href)
                        
                        # Éviter les doublons
                        if not any(r['url'] == url for r in results):
                            results.append({
                                'title': text,
                                'url': url
                            })
                            logger.debug(f"✓ Trouvé: {text} ({url})")
                            
                            # Limiter à 10 résultats
                            if len(results) >= 10:
                                break
            else:
                logger.warning(f"Erreur HTTP {response.status_code} pour la recherche")
            
            return results
        
        except Exception as e:
            logger.error(f"Erreur lors de la recherche Nautiljon: {e}")
            return []
    
    def get_manga_info(self, manga_url_or_title):
        """
        Récupère les infos détaillées d'un manga
        Accepte soit une URL complète, soit un titre (va chercher d'abord)
        
        Retourne:
        {
            'title': str,
            'url': str,
            'total_volumes': int or None,
            'french_volumes': int or None,
            'editor': str,
            'status': str (En cours / Terminé / Pausé),
            'mangaka': str,
            'year_start': int,
            'year_end': int or None
        }
        """
        try:
            # Si c'est un titre, chercher l'URL d'abord
            if not manga_url_or_title.startswith('http'):
                results = self.search_manga(manga_url_or_title)
                if not results:
                    logger.warning(f"Aucun résultat trouvé pour: {manga_url_or_title}")
                    return None
                # Prendre le premier résultat
                manga_url = results[0]['url']
            else:
                manga_url = manga_url_or_title
            
            # Vérifier le cache
            if manga_url in self.cache:
                return self.cache[manga_url]
            
            logger.info(f"Récupération des infos: {manga_url}")
            
            response = self.session.get(manga_url, timeout=10)
            response.encoding = 'utf-8'
            
            if response.status_code != 200:
                logger.warning(f"Erreur HTTP: {response.status_code} pour {manga_url}")
                return None
            
            soup = BeautifulSoup(response.content, 'html.parser')
            text = soup.get_text()
            
            info = {
                'title': None,
                'url': manga_url,
                'total_volumes': None,
                'french_volumes': None,
                'editor': None,
                'status': None,
                'mangaka': None,
                'year_start': None,
                'year_end': None
            }
            
            # Récupère le titre principal (en enlevant "Modifier" qui est présent)
            title_tag = soup.find('h1')
            if title_tag:
                title_text = title_tag.get_text(strip=True)
                # Enlever "Modifier" du début si présent
                if title_text.startswith('Modifier'):
                    title_text = title_text[8:].strip()
                info['title'] = title_text
            
            # Extraction du texte pour les regex
            # Format: "Nb volumes VO : 113 (En cours)"
            vol_vo_match = re.search(r'Nb volumes VO\s*:\s*(\d+)', text, re.IGNORECASE)
            if vol_vo_match:
                info['total_volumes'] = int(vol_vo_match.group(1))
            
            # Format: "Nb volumes VF : 111 (En cours)"
            vol_vf_match = re.search(r'Nb volumes VF\s*:\s*(\d+)', text, re.IGNORECASE)
            if vol_vf_match:
                info['french_volumes'] = int(vol_vf_match.group(1))
            
            # Éditeur VF: "Éditeur VF : Glénat (Shonen)"
            editor_match = re.search(r'Éditeur VF\s*:\s*([^\n\(]+)', text, re.IGNORECASE)
            if editor_match:
                info['editor'] = editor_match.group(1).strip()
            
            # Mangaka: "Eiichiro Oda" - arrêter au prochain champ (Traducteur, Éditeur, etc.)
            mangaka_match = re.search(
                r'(?:Mangaka|Auteur|Créateur)\s*:\s*([A-Za-zÀ-ÿ\s\-\.]+?)(?=\n|Traducteur|Éditeur|Groupes|Années|Prix|Statut|Prépublié)',
                text, 
                re.IGNORECASE
            )
            if mangaka_match:
                mangaka_text = mangaka_match.group(1).strip()
                # Nettoyer: enlever les espaces supplémentaires et caractères indésirables
                mangaka_text = re.sub(r'\s+', ' ', mangaka_text)
                # Enlever les informations entre parenthèses
                mangaka_text = re.sub(r'\([^)]*\)', '', mangaka_text).strip()
                if mangaka_text:
                    info['mangaka'] = mangaka_text
            
            # Années de publication: chercher le format "1997 - 2024" ou juste "1997"
            # Généralement après "années" ou dans les infos
            year_match = re.search(
                r'(?:Année|Date) (?:début|de début|de publication|VO|VF)\s*:\s*(\d{4})(?:\s*-\s*(\d{4}))?',
                text,
                re.IGNORECASE
            )
            if year_match:
                info['year_start'] = int(year_match.group(1))
                if year_match.group(2):
                    info['year_end'] = int(year_match.group(2))
            else:
                # Fallback: chercher simplement les années à proximité du titre
                early_years = re.findall(r'(\d{4})', text[:500])
                if early_years:
                    info['year_start'] = int(early_years[0])
            
            # Statut: "En cours", "Terminé", etc.
            status_match = re.search(
                r'(?:Statut|État)\s*:\s*([^\n\)]+)',
                text,
                re.IGNORECASE
            )
            if status_match:
                info['status'] = status_match.group(1).strip()
            else:
                # Chercher dans les parenthèses après le nombre de volumes
                status_in_parens = re.search(r'volumes?.+?\(([^)]+)\)', text, re.IGNORECASE)
                if status_in_parens:
                    info['status'] = status_in_parens.group(1).strip()
            
            # Cache le résultat
            self.cache[manga_url] = info
            
            logger.debug(f"Infos extraites: {info['title']} - {info['total_volumes']} tomes - {info['editor']}")
            
            return info
        
        except Exception as e:
            logger.error(f"Erreur lors de la récupération des infos: {e}")
            return None
    
    def search_and_get_best_match(self, title):
        """
        Cherche un manga et retourne les infos du meilleur résultat
        """
        results = self.search_manga(title)
        
        if not results:
            return None
        
        # Essayer le premier résultat
        for result in results:
            info = self.get_manga_info(result['url'])
            if info:
                return info
        
        return None


class NautiljonDatabase:
    """Gère la sauvegarde des infos Nautiljon dans la BDD"""
    
    NAUTILJON_SCHEMA = """
        ALTER TABLE series ADD COLUMN IF NOT EXISTS nautiljon_url TEXT;
        ALTER TABLE series ADD COLUMN IF NOT EXISTS nautiljon_total_volumes INTEGER;
        ALTER TABLE series ADD COLUMN IF NOT EXISTS nautiljon_french_volumes INTEGER;
        ALTER TABLE series ADD COLUMN IF NOT EXISTS nautiljon_editor TEXT;
        ALTER TABLE series ADD COLUMN IF NOT EXISTS nautiljon_status TEXT;
        ALTER TABLE series ADD COLUMN IF NOT EXISTS nautiljon_mangaka TEXT;
        ALTER TABLE series ADD COLUMN IF NOT EXISTS nautiljon_year_start INTEGER;
        ALTER TABLE series ADD COLUMN IF NOT EXISTS nautiljon_year_end INTEGER;
        ALTER TABLE series ADD COLUMN IF NOT EXISTS nautiljon_updated_at TIMESTAMP;
    """
    
    def __init__(self, db_path):
        self.db_path = db_path
        self.init_database()
    
    def init_database(self):
        """Initialise le schéma Nautiljon dans la BDD"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            
            # Exécute chaque ajout de colonne séparément pour éviter les erreurs
            statements = self.NAUTILJON_SCHEMA.strip().split(';')
            for statement in statements:
                if statement.strip():
                    try:
                        cursor.execute(statement.strip())
                    except sqlite3.OperationalError as e:
                        if 'already exists' not in str(e):
                            logger.warning(f"Attention lors de l'init schema: {e}")
            
            conn.commit()
            conn.close()
            logger.info("Base de données Nautiljon initialisée")
        
        except Exception as e:
            logger.error(f"Erreur lors de l'initialisation de la BDD: {e}")
    
    def update_series_nautiljon_info(self, series_id, nautiljon_info):
        """Met à jour les infos Nautiljon d'une série"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            cursor = conn.cursor()
            
            cursor.execute('''
                UPDATE series SET
                    nautiljon_url = ?,
                    nautiljon_total_volumes = ?,
                    nautiljon_french_volumes = ?,
                    nautiljon_editor = ?,
                    nautiljon_status = ?,
                    nautiljon_mangaka = ?,
                    nautiljon_year_start = ?,
                    nautiljon_year_end = ?,
                    nautiljon_updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            ''', (
                nautiljon_info.get('url'),
                nautiljon_info.get('total_volumes'),
                nautiljon_info.get('french_volumes'),
                nautiljon_info.get('editor'),
                nautiljon_info.get('status'),
                nautiljon_info.get('mangaka'),
                nautiljon_info.get('year_start'),
                nautiljon_info.get('year_end'),
                series_id
            ))
            
            conn.commit()
            conn.close()
            
            logger.info(f"Infos Nautiljon mises à jour pour série #{series_id}")
            return True
        
        except Exception as e:
            logger.error(f"Erreur lors de la mise à jour: {e}")
            return False
    
    def get_series_nautiljon_info(self, series_id):
        """Récupère les infos Nautiljon d'une série"""
        try:
            conn = sqlite3.connect(self.db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT 
                    nautiljon_url,
                    nautiljon_total_volumes,
                    nautiljon_french_volumes,
                    nautiljon_editor,
                    nautiljon_status,
                    nautiljon_mangaka,
                    nautiljon_year_start,
                    nautiljon_year_end,
                    nautiljon_updated_at
                FROM series
                WHERE id = ?
            ''', (series_id,))
            
            row = cursor.fetchone()
            conn.close()
            
            if row:
                return dict(row)
            return None
        
        except Exception as e:
            logger.error(f"Erreur lors de la récupération: {e}")
            return None
