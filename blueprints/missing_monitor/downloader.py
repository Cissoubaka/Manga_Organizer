"""
Envoi automatique des téléchargements aux clients (qBittorrent, aMule)
"""
import requests
import json
from typing import Dict, List, Optional, Tuple
from flask import current_app
from datetime import datetime
import sqlite3


class MissingVolumeDownloader:
    """Envoie les téléchargements aux clients configurés"""
    
    def __init__(self):
        self.clients = {
            'qbittorrent': self._download_to_qbittorrent,
            'amule': self._download_to_amule
        }
    
    def send_torrent_download(self, torrent_link: str, title: str, volume_num: int, 
                             client: str = None, category: str = None) -> Tuple[bool, str]:
        """Envoie un torrent au client de téléchargement
        
        Args:
            torrent_link: Lien du torrent ou magnet URI ou ED2K
            title: Titre du manga
            volume_num: Numéro du volume
            client: Client à utiliser ('qbittorrent', 'amule') ou auto-détection
            category: Catégorie (pour qBittorrent)
            
        Returns:
            Tuple (succès, message)
        """
        if not torrent_link:
            return False, "Lien vide"
        
        # Auto-détection du client si non spécifié
        if not client:
            # Déterminer le client selon le type de lien
            if torrent_link.startswith('ed2k://'):
                client = 'amule'
            else:
                # magnet:, http://, https://, etc. → qBittorrent
                client = 'qbittorrent'
        
        if client not in self.clients:
            return False, f"Client inconnu: {client}"
        
        try:
            return self.clients[client](torrent_link, title, volume_num, category)
        except Exception as e:
            return False, f"Erreur {client}: {str(e)}"
    
    def _get_default_client(self) -> str:
        """Détermine le client par défaut (le premier actif)"""
        try:
            config_file = current_app.config.get('QBITTORRENT_CONFIG_FILE')
            if config_file:
                with open(config_file, 'r') as f:
                    config = json.load(f)
                    if config.get('enabled'):
                        return 'qbittorrent'
        except:
            pass
        
        try:
            config = current_app.config.get('EMULE_CONFIG', {})
            if config.get('enabled'):
                return 'amule'
        except:
            pass
        
        return 'qbittorrent'  # Par défaut
    
    def _download_to_qbittorrent(self, torrent_link: str, title: str, 
                                volume_num: int, category: str = None) -> Tuple[bool, str]:
        """Envoie à qBittorrent en utilisant l'endpoint /api/qbittorrent/add"""
        try:
            import sys
            
            # Charger la catégorie par défaut si non fournie
            if not category:
                from ..qbittorrent.routes import load_qbittorrent_config
                config = load_qbittorrent_config()
                category = config.get('default_category', '')
            
            # Utiliser l'endpoint qBittorrent existant qui fonctionne déjà
            payload = {
                'torrent_url': torrent_link,
            }
            
            # Ajouter la catégorie si configurée
            if category:
                payload['category'] = category
            
            print(f"[qBittorrent Download] Envoi à qBittorrent: {title} Vol {volume_num}", file=sys.stderr)
            print(f"[qBittorrent Download] URL: {torrent_link[:80]}...", file=sys.stderr)
            if category:
                print(f"[qBittorrent Download] Catégorie: {category}", file=sys.stderr)
            
            response = requests.post(
                'http://127.0.0.1:5000/api/qbittorrent/add',
                json=payload,
                timeout=30
            )
            
            print(f"[qBittorrent Download] Réponse HTTP: {response.status_code}", file=sys.stderr)
            
            if response.status_code == 200:
                result = response.json()
                print(f"[qBittorrent Download] Résultat: {result}", file=sys.stderr)
                
                if result.get('success'):
                    msg = f"✅ {title} Vol {volume_num} envoyé à qBittorrent"
                    self._log_download(title, volume_num, 'qbittorrent', True, msg)
                    print(f"[qBittorrent Download] ✅ Succès", file=sys.stderr)
                    return True, msg
                else:
                    error_msg = result.get('error', 'Erreur inconnue')
                    msg = f"Erreur qBittorrent: {error_msg}"
                    self._log_download(title, volume_num, 'qbittorrent', False, msg)
                    print(f"[qBittorrent Download] ❌ {error_msg}", file=sys.stderr)
                    return False, msg
            else:
                msg = f"Erreur qBittorrent: HTTP {response.status_code}"
                self._log_download(title, volume_num, 'qbittorrent', False, msg)
                print(f"[qBittorrent Download] ❌ HTTP {response.status_code}: {response.text[:200]}", file=sys.stderr)
                return False, msg
        
        except Exception as e:
            import sys
            msg = f"Erreur connexion qBittorrent: {str(e)}"
            self._log_download(title, volume_num, 'qbittorrent', False, msg)
            print(f"[qBittorrent Download] ❌ Exception: {str(e)}", file=sys.stderr)
            return False, msg

    
    def _download_to_amule(self, torrent_link: str, title: str, 
                          volume_num: int, category: str = None) -> Tuple[bool, str]:
        """Envoie à aMule/eMule en utilisant l'endpoint /api/emule/add"""
        try:
            # Utiliser l'endpoint eMule existant qui fonctionne déjà
            payload = {
                'link': torrent_link,
            }
            
            # Si on a une catégorie, on peut la passer (bien que aMule ne l'utilise pas)
            if category:
                payload['category'] = category
            
            response = requests.post(
                'http://127.0.0.1:5000/api/emule/add',
                json=payload,
                timeout=30
            )
            
            if response.status_code == 200:
                result = response.json()
                if result.get('success'):
                    msg = f"✅ {title} Vol {volume_num} envoyé à aMule"
                    self._log_download(title, volume_num, 'amule', True, msg)
                    return True, msg
                else:
                    error_msg = result.get('error', 'Erreur inconnue')
                    msg = f"Erreur aMule: {error_msg}"
                    self._log_download(title, volume_num, 'amule', False, msg)
                    return False, msg
            else:
                msg = f"Erreur aMule: HTTP {response.status_code}"
                self._log_download(title, volume_num, 'amule', False, msg)
                return False, msg
        
        except Exception as e:
            msg = f"Erreur connexion aMule: {str(e)}"
            self._log_download(title, volume_num, 'amule', False, msg)
            return False, msg
    
    def _log_download(self, title: str, volume_num: int, client: str, 
                     success: bool, message: str) -> bool:
        """Enregistre un événement de téléchargement dans la base de données
        
        Args:
            title: Titre du manga
            volume_num: Numéro du volume
            client: Client utilisé
            success: Si succès ou erreur
            message: Message de détail
            
        Returns:
            True si enregistré
        """
        try:
            db_path = current_app.config.get('DATABASE')
            if not db_path:
                return False
            
            conn = sqlite3.connect(db_path, timeout=30.0)
            cursor = conn.cursor()
            
            cursor.execute('''
                INSERT INTO missing_volume_downloads 
                (title, volume_number, client, success, message, created_at)
                VALUES (?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
            ''', (title, volume_num, client, 1 if success else 0, message))
            
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"Erreur log download: {e}")
            return False
    
    def get_download_history(self, limit: int = 50) -> List[Dict]:
        """Récupère l'historique des téléchargements
        
        Args:
            limit: Nombre maximum de records à retourner
            
        Returns:
            Liste historique
        """
        try:
            db_path = current_app.config.get('DATABASE')
            if not db_path:
                return []
            
            conn = sqlite3.connect(db_path, timeout=30.0)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            
            cursor.execute('''
                SELECT id, title, volume_number, client, success, message, created_at
                FROM missing_volume_downloads
                ORDER BY created_at DESC
                LIMIT ?
            ''', (limit,))
            
            history = []
            for row in cursor.fetchall():
                history.append({
                    'id': row[0],
                    'title': row[1],
                    'volume_number': row[2],
                    'client': row[3],
                    'success': bool(row[4]),
                    'message': row[5],
                    'created_at': row[6]
                })
            
            conn.close()
            return history
        except Exception as e:
            print(f"Erreur récupération historique: {e}")
            return []
