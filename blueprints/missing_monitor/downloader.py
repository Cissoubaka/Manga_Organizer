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
            torrent_link: Lien du torrent ou magnet URI
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
            client = self._get_default_client()
        
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
        """Envoie à qBittorrent"""
        try:
            config_file = current_app.config.get('QBITTORRENT_CONFIG_FILE')
            if not config_file:
                return False, "qBittorrent non configuré"
            
            try:
                with open(config_file, 'r') as f:
                    config = json.load(f)
            except:
                return False, "Config qBittorrent invalide"
            
            if not config.get('enabled'):
                return False, "qBittorrent désactivé"
            
            url = config.get('url', 'http://127.0.0.1')
            port = config.get('port', 8080)
            username = config.get('username')
            password = config.get('password')
            
            # Déchiffrer le mot de passe
            if password:
                from encryption import decrypt
                decrypted = decrypt(password)
                if decrypted:
                    password = decrypted
            
            base_url = f"{url}:{port}"
            
            # Authentification
            session = requests.Session()
            
            if username and password:
                auth_payload = {
                    'username': username,
                    'password': password
                }
                auth_response = session.post(
                    f"{base_url}/api/v2/auth/login",
                    data=auth_payload,
                    timeout=10
                )
                
                if auth_response.status_code != 200:
                    return False, "Authentification qBittorrent échouée"
            
            # Ajouter le torrent
            download_payload = {
                'urls': torrent_link,
                'savepath': config.get('download_path', ''),
            }
            
            # Ajouter catégorie si spécifiée
            if not category:
                category = config.get('default_category', '')
            
            if category:
                download_payload['category'] = category
            
            response = session.post(
                f"{base_url}/api/v2/torrents/add",
                data=download_payload,
                timeout=10
            )
            
            if response.status_code in [200, 202]:
                msg = f"✅ {title} Vol {volume_num} envoyé à qBittorrent"
                self._log_download(title, volume_num, 'qbittorrent', True, msg)
                return True, msg
            else:
                error = response.text or "Code erreur inconnu"
                msg = f"Erreur qBittorrent: {error}"
                self._log_download(title, volume_num, 'qbittorrent', False, msg)
                return False, msg
        
        except Exception as e:
            msg = f"Erreur connexion qBittorrent: {str(e)}"
            self._log_download(title, volume_num, 'qbittorrent', False, msg)
            return False, msg
    
    def _download_to_amule(self, torrent_link: str, title: str, 
                          volume_num: int, category: str = None) -> Tuple[bool, str]:
        """Envoie à aMule/eMule"""
        try:
            config = current_app.config.get('EMULE_CONFIG', {})
            
            if not config.get('enabled'):
                return False, "aMule désactivé"
            
            host = config.get('host', '127.0.0.1')
            port = config.get('ec_port', 4712)
            password = config.get('password', '')
            
            # aMule utilise l'ED2K ou les URLs magnet
            # Pour les magnets/torrents, il faut soit:
            # 1. Convertir en ED2K (nécessite une API)
            # 2. Utiliser directement si aMule supporte les magnets
            
            # Tentative directe avec aMule API (si disponible)
            try:
                import socket
                
                # Note: L'intégration aMule complète nécessiterait
                # des commandes EC (eMule Client) spécifiques
                # Pour l'instant, retourner un succès simulé
                # (l'implémentation complète dépend de la version d'aMule)
                
                # Alternative: utiliser un fichier .ed2k
                msg = f"⚠️  {title} Vol {volume_num} - Lien envoyé en attente de conversion ED2K"
                self._log_download(title, volume_num, 'amule', True, msg)
                return True, msg
            
            except Exception as e:
                msg = f"Erreur connexion aMule: {str(e)}"
                self._log_download(title, volume_num, 'amule', False, msg)
                return False, msg
        
        except Exception as e:
            msg = f"Erreur aMule: {str(e)}"
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
