import requests
from bs4 import BeautifulSoup
import re
import sqlite3
from urllib.parse import urljoin
import time
import os
import hashlib

class MyBBScraper:
    def __init__(self, base_url, db_file, username, password, forum_category=""):
        self.base_url = base_url
        self.db_file = db_file
        self.username = username
        self.password = password
        self.forum_category = forum_category
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
        self.logged_in = False
        
        # Créer les répertoires nécessaires
        os.makedirs('./data/covers', exist_ok=True)
        
    def connect_db(self):
        """Connexion à la base SQLite"""
        try:
            connection = sqlite3.connect(self.db_file)
            return connection
        except Exception as e:
            print(f"Erreur de connexion SQLite: {e}")
            return None
    
    def login(self):
        """Se connecter au forum myBB"""
        try:
            # Récupère la page principale pour obtenir les cookies et le my_post_key
            home_url = "https://ebdz.net/forum/index.php"
            response = self.session.get(home_url)
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extrait le my_post_key du HTML
            my_post_key = None
            for script in soup.find_all('script'):
                if script.string and 'my_post_key' in script.string:
                    match = re.search(r'my_post_key = "([^"]+)"', script.string)
                    if match:
                        my_post_key = match.group(1)
                        break
            
            # Prépare les données de connexion selon le formulaire myBB
            login_data = {
                'action': 'do_login',
                'url': home_url,
                'quick_login': '1',
                'my_post_key': my_post_key,
                'quick_username': self.username,
                'quick_password': self.password,
                'quick_remember': 'yes',
                'submit': 'Se connecter'
            }
            
            # Envoie le formulaire de login
            login_url = "https://ebdz.net/forum/member.php"
            response = self.session.post(login_url, data=login_data, allow_redirects=True)
            
            # Vérifie si connecté
            if 'action=logout' in response.text or 'Déconnexion' in response.text:
                print(f"✓ Connecté en tant que {self.username}")
                self.logged_in = True
                return True
            else:
                print("✗ Échec de connexion - vérifie tes identifiants")
                return False
                
        except Exception as e:
            print(f"Erreur lors de la connexion: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def extract_volume_number(self, filename):
        """Extrait le numéro de volume depuis le nom de fichier"""
        if not filename:
            return None
        
        # Patterns pour détecter les numéros de volume
        patterns = [
            r'[Tt](\d{1,3})',           # T01, t12, T123
            r'[Vv]ol\.?\s*(\d{1,3})',   # Vol.01, vol 12, Vol.123
            r'[Vv](\d{1,3})',           # V01, v12
            r'Volume\s*(\d{1,3})',      # Volume 01
            r'Tome\s*(\d{1,3})',        # Tome 01
            r'\s-\s(\d{1,3})\s',        # - 01 -
            r'#(\d{1,3})',              # #01
        ]
        
        for pattern in patterns:
            match = re.search(pattern, filename, re.IGNORECASE)
            if match:
                volume = int(match.group(1))
                return volume
        
        return None
    
    def create_table(self):
        """Crée la table pour stocker les liens ed2k avec colonne volume"""
        connection = self.connect_db()
        if connection:
            cursor = connection.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS ed2k_links (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    link TEXT NOT NULL UNIQUE,
                    filename TEXT,
                    filesize TEXT,
                    volume INTEGER,
                    thread_title TEXT,
                    thread_url TEXT,
                    thread_id TEXT,
                    forum_category TEXT,
                    cover_image TEXT,
                    description TEXT,
                    date_scraped TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            connection.commit()
            cursor.close()
            connection.close()
            print("✓ Table créée/vérifiée dans edbz.db (avec colonne volume)")
    
    def extract_ed2k_links(self, html):
        """Extrait les liens ed2k du HTML"""
        ed2k_pattern = r'ed2k://\|file\|[^\s<>"]+'
        links = re.findall(ed2k_pattern, html)
        return links
    
    def parse_ed2k_link(self, link):
        """Parse un lien ed2k pour extraire infos"""
        parts = link.split('|')
        filename = parts[2] if len(parts) > 2 else None
        filesize = parts[3] if len(parts) > 3 else None
        return filename, filesize
    
    def get_thread_links(self, forum_url, max_pages=None):
        """Récupère tous les liens de threads du forum"""
        thread_links = []
        seen_urls = set()
        page = 1
        
        try:
            while True:
                # Construit l'URL de la page du forum (liste des threads)
                if page == 1:
                    page_url = forum_url
                else:
                    # Format myBB pour la pagination du forum
                    if '?' in forum_url:
                        page_url = f"{forum_url}&page={page}"
                    else:
                        page_url = f"{forum_url}?page={page}"
                
                print(f"  Lecture page {page} du forum...")
                response = self.session.get(page_url)
                soup = BeautifulSoup(response.content, 'html.parser')
                
                # Trouve TOUS les liens qui contiennent showthread
                all_thread_links = soup.find_all('a', href=re.compile(r'showthread\.php'))
                
                # Trouve les liens de threads myBB dans cette page
                page_threads = []
                for link in all_thread_links:
                    href = link.get('href', '')
                    if 'tid=' in href:
                        thread_url = urljoin(forum_url.split('forumdisplay.php')[0], href)
                        # Nettoie l'URL (enlève les ancres et paramètres inutiles)
                        thread_url = thread_url.split('#')[0].split('&page=')[0]
                        thread_title = link.get_text(strip=True)
                        
                        if thread_url not in seen_urls and thread_title:
                            seen_urls.add(thread_url)
                            page_threads.append((thread_url, thread_title))
                
                if not page_threads:
                    break
                
                print(f"  → {len(page_threads)} threads trouvés sur cette page")
                thread_links.extend(page_threads)
                
                # Limite de pages pour les tests
                if max_pages and page >= max_pages:
                    print(f"  Limite de {max_pages} page(s) atteinte")
                    break
                
                # Vérifie s'il y a une page suivante - cherche plusieurs patterns
                pagination = soup.find_all('a', class_='pagination_page')
                
                # Cherche le lien "next" ou le numéro de page suivant
                has_next = False
                for link in pagination:
                    if str(page + 1) in link.get_text():
                        has_next = True
                        break
                
                if not has_next:
                    break
                
                page += 1
                time.sleep(0.5)  # Petite pause entre les pages
            
            print(f"✓ {len(thread_links)} threads trouvés au total")
        except Exception as e:
            print(f"Erreur lors du scraping du forum: {e}")
            import traceback
            traceback.print_exc()
        
        return thread_links
    
    def download_cover(self, image_url):
        """Télécharge une couverture et retourne le chemin local"""
        if not image_url:
            return None
        
        try:
            # Génère un nom de fichier unique basé sur l'URL
            url_hash = hashlib.md5(image_url.encode()).hexdigest()
            ext = os.path.splitext(image_url)[1] or '.jpg'
            filename = f"{url_hash}{ext}"
            filepath = os.path.join('./data/covers', filename)
            
            # Télécharge seulement si pas déjà présent
            if not os.path.exists(filepath):
                print(f"    Téléchargement de la couverture...")
                response = self.session.get(image_url, timeout=10)
                if response.status_code == 200:
                    with open(filepath, 'wb') as f:
                        f.write(response.content)
                    print(f"    ✓ Couverture sauvegardée: {filename}")
                    return f"covers/{filename}"
                else:
                    print(f"    ✗ Échec du téléchargement: HTTP {response.status_code}")
                    return None
            else:
                print(f"    ✓ Couverture existe déjà: {filename}")
                return f"covers/{filename}"
        except Exception as e:
            print(f"    ✗ Erreur téléchargement couverture: {e}")
            return None
    
    def scrape_thread(self, thread_url, thread_title):
        """Scrappe la première page d'un thread pour extraire les liens ed2k"""
        ed2k_data = []
        try:
            # Assure qu'on est sur la première page (pas de paramètre &page=)
            if '&page=' in thread_url:
                thread_url = thread_url.split('&page=')[0]
            
            # Extrait le thread_id de l'URL
            thread_id = ""
            tid_match = re.search(r'tid=(\d+)', thread_url)
            if tid_match:
                thread_id = tid_match.group(1)
            
            response = self.session.get(thread_url)
            html = response.text
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Récupère la couverture
            cover_image = None
            couv_li = soup.find('li', class_='couv')
            if couv_li:
                img_tag = couv_li.find('img')
                if img_tag and img_tag.get('src'):
                    cover_url = img_tag['src']
                    print(f"  → Couverture trouvée: {cover_url[:60]}...")
                    cover_image = self.download_cover(cover_url)
            
            # Récupère la description
            description = None
            desc_p = soup.find('p', class_='indent')
            if desc_p:
                # Nettoie la description (enlève les balises <br />)
                description = desc_p.get_text(separator=' ', strip=True)
                print(f"  → Description trouvée ({len(description)} caractères)")
            
            links = self.extract_ed2k_links(html)
            for link in links:
                filename, filesize = self.parse_ed2k_link(link)
                
                # Extrait le numéro de volume du nom de fichier
                volume = self.extract_volume_number(filename)
                
                ed2k_data.append({
                    'link': link,
                    'filename': filename,
                    'filesize': filesize,
                    'volume': volume,
                    'thread_title': thread_title,
                    'thread_url': thread_url,
                    'thread_id': thread_id,
                    'forum_category': self.forum_category,
                    'cover_image': cover_image,
                    'description': description
                })
            
            if links:
                volumes_found = [str(d['volume']) for d in ed2k_data if d['volume'] is not None]
                volumes_info = f" (volumes: {', '.join(volumes_found)})" if volumes_found else ""
                print(f"  → {len(links)} liens ed2k trouvés{volumes_info} dans: {thread_title[:50]}")
                
        except Exception as e:
            print(f"Erreur lors du scraping du thread: {e}")
        
        return ed2k_data
    
    def save_to_db(self, ed2k_data):
        """Sauvegarde les liens ed2k dans SQLite"""
        connection = self.connect_db()
        if not connection:
            return
        
        cursor = connection.cursor()
        saved = 0
        duplicates = 0
        
        for data in ed2k_data:
            try:
                cursor.execute("""
                    INSERT INTO ed2k_links (link, filename, filesize, volume, thread_title, thread_url, thread_id, forum_category, cover_image, description)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (data['link'], data['filename'], data['filesize'], data['volume'],
                      data['thread_title'], data['thread_url'], data['thread_id'], 
                      data['forum_category'], data['cover_image'], data['description']))
                saved += 1
            except sqlite3.IntegrityError:
                duplicates += 1
        
        connection.commit()
        cursor.close()
        connection.close()
        
        print(f"✓ {saved} nouveaux liens sauvegardés, {duplicates} doublons ignorés")
    
    def run(self, max_pages=None):
        """Lance le scraping complet"""
        print("=== Démarrage du scraper myBB ===\n")
        
        # Connexion au forum
        print("Connexion au forum...")
        if not self.login():
            print("Impossible de continuer sans connexion.")
            return
        
        # Crée la table
        self.create_table()
        
        # Récupère les threads
        if max_pages:
            print(f"\nScraping du forum (limité à {max_pages} page(s)): {self.base_url}")
        else:
            print(f"\nScraping du forum: {self.base_url}")
        
        thread_links = self.get_thread_links(self.base_url, max_pages)
        
        # Scrappe chaque thread
        print(f"\nScraping des threads...\n")
        all_ed2k_data = []
        
        for i, (thread_url, thread_title) in enumerate(thread_links, 1):
            print(f"[{i}/{len(thread_links)}] {thread_title[:60]}...")
            ed2k_data = self.scrape_thread(thread_url, thread_title)
            all_ed2k_data.extend(ed2k_data)
            time.sleep(1)  # Politesse envers le serveur
        
        # Sauvegarde dans la base
        if all_ed2k_data:
            print(f"\n=== Sauvegarde de {len(all_ed2k_data)} liens ===")
            self.save_to_db(all_ed2k_data)
        else:
            print("\nAucun lien ed2k trouvé.")
        
        print("\n=== Scraping terminé ===")


# Configuration
if __name__ == "__main__":
    # Fichier de base de données SQLite dans ./data
    DB_FILE = "./data/edbz.db"
    
    # Créer le répertoire data si nécessaire
    os.makedirs('./data', exist_ok=True)
    
    # Identifiants forum - À PERSONNALISER
    USERNAME = ""
    PASSWORD = ""
   
    # ======= CONFIGURATION DES FORUMS À SCRAPER =======
    # Change facilement l'URL et le nom de catégorie ici
    
    FORUMS_TO_SCRAPE = [
        {
            'url': 'https://ebdz.net/forum/forumdisplay.php?fid=29',
            'category': 'Mangas',  # Nom pour identifier cette catégorie
            'max_pages': 71  # Limite de pages (None pour tout scraper)
        },
        # Ajoute d'autres forums ici :
        # {
        #     'url': 'https://ebdz.net/forum/forumdisplay.php?fid=30',
        #     'category': 'Films',
        #     'max_pages': None
        # },
    ]
    
    # ================================================
    
    print("\n" + "=" * 60)
    print("🚀 SCRAPER ED2K - EmuleBDZ")
    print("=" * 60)
    
    for forum_config in FORUMS_TO_SCRAPE:
        print(f"\n📂 Catégorie : {forum_config['category']}")
        print(f"🔗 URL : {forum_config['url']}")
        
        scraper = MyBBScraper(
            forum_config['url'], 
            DB_FILE, 
            USERNAME, 
            PASSWORD,
            forum_config['category']
        )
        
        scraper.run(max_pages=forum_config['max_pages'])
        
        print("\n" + "-" * 60)
    
    print("\n✅ Scraping terminé pour toutes les catégories !")
    print("=" * 60) 
    
