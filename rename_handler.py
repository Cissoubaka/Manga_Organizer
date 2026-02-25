"""
Module pour gérer le renommage de fichiers avec tags personnalisés
Tags supportés:
  [C] - Compteur (Ex: [C:01:3] pour compteur de 01 avec 3 chiffres)
  [E] - Extension du fichier (Ex: [E] -> .pdf)
  [T] - Titre de la série
  [V] - Numéro de volume
  [P] - Numéro de partie (si applicable)
  [N] - Nom du fichier original (sans extension)
"""
import re
from pathlib import Path
from typing import List, Dict, Tuple
import logging

logger = logging.getLogger(__name__)


class RenamePattern:
    """Classe pour gérer les patterns de renommage avec tags"""
    
    def __init__(self, pattern: str):
        """
        Initialise un pattern de renommage
        
        Args:
            pattern: Pattern avec tags. Ex: "[T] - Vol [V] [E]"
        """
        self.pattern = pattern
        self.tags = self._extract_tags()
    
    def _extract_tags(self) -> List[str]:
        """Extrait tous les tags du pattern"""
        # Match [TAG] ou [TAG:param1:param2:...]
        return re.findall(r'\[([^\]]+)\]', self.pattern)
    
    def validate(self) -> Tuple[bool, str]:
        """
        Valide le pattern
        
        Returns:
            Tuple (is_valid, error_message)
        """
        for tag in self.tags:
            tag_name = tag.split(':')[0].upper()
            
            # Vérifier que le tag est supporté
            if tag_name not in ['C', 'E', 'T', 'V', 'P', 'N']:
                return False, f"Tag non supporté: [{tag}]"
            
            # Validations spécifiques par tag
            if tag_name == 'C':
                parts = tag.split(':')
                if len(parts) < 3:
                    return False, "Format incorrect pour [C]: utilisez [C:départ:longueur]"
                try:
                    int(parts[1])  # départ
                    int(parts[2])  # longueur
                except ValueError:
                    return False, "[C] doit avoir des paramètres numériques"
        
        return True, ""
    
    def apply(self, 
              series_title: str,
              volume_number: int = None,
              part_number: int = None,
              original_filename: str = None,
              counter: int = None) -> str:
        """
        Applique le pattern au fichier
        
        Args:
            series_title: Titre de la série
            volume_number: Numéro de volume
            part_number: Numéro de partie (optionnel)
            original_filename: Nom du fichier original avec extension
            counter: Valeur du compteur (pour tag [C])
        
        Returns:
            Nouveau nom de fichier avec extension
        """
        result = self.pattern
        
        # Extraire l'extension du fichier original
        if original_filename:
            ext = Path(original_filename).suffix
            # Retirer le point de l'extension
            ext_clean = ext.lstrip('.')
        else:
            ext_clean = ""
        
        # Extraire le nom du fichier sans extension
        if original_filename:
            name_only = Path(original_filename).stem
        else:
            name_only = ""
        
        # Remplacer les tags
        for tag in self.tags:
            tag_full = tag
            tag_name = tag.split(':')[0].upper()
            
            if tag_name == 'T':
                # Titre de la série
                result = result.replace(f'[{tag_full}]', series_title)
            
            elif tag_name == 'V':
                # Numéro de volume
                if volume_number is not None:
                    result = result.replace(f'[{tag_full}]', str(volume_number))
            
            elif tag_name == 'P':
                # Numéro de partie
                if part_number is not None:
                    result = result.replace(f'[{tag_full}]', str(part_number))
            
            elif tag_name == 'N':
                # Nom du fichier original
                result = result.replace(f'[{tag_full}]', name_only)
            
            elif tag_name == 'E':
                # Extension
                result = result.replace(f'[{tag_full}]', ext_clean)
            
            elif tag_name == 'C':
                # Compteur: [C:départ:longueur]
                parts = tag.split(':')
                if len(parts) >= 3 and counter is not None:
                    try:
                        start = int(parts[1])
                        length = int(parts[2])
                        counter_value = start + counter
                        formatted = str(counter_value).zfill(length)
                        result = result.replace(f'[{tag_full}]', formatted)
                    except (ValueError, IndexError):
                        pass
        
        return result
    
    def preview(self,
                files_info: List[Dict]) -> List[Dict]:
        """
        Génère un aperçu du renommage pour une liste de fichiers
        
        Args:
            files_info: Liste de dicts avec au moins: 
                       'filename', 'volume_number', 'part_number', 'series_title'
        
        Returns:
            Liste de dicts avec 'old_name', 'new_name', 'volume_number'
        """
        preview = []
        for idx, file_info in enumerate(files_info):
            new_name = self.apply(
                series_title=file_info.get('series_title', ''),
                volume_number=file_info.get('volume_number'),
                part_number=file_info.get('part_number'),
                original_filename=file_info.get('filename'),
                counter=idx
            )
            
            preview.append({
                'old_name': file_info.get('filename'),
                'new_name': new_name,
                'volume_number': file_info.get('volume_number'),
                'counter': idx
            })
        
        return preview


class FileRenamer:
    """Classe pour effectuer le renommage réel des fichiers"""
    
    @staticmethod
    def rename_series_files(series_path: str, 
                          pattern: str,
                          files_to_rename: List[str],
                          series_title: str,
                          dry_run: bool = True) -> Tuple[bool, List[Dict], str]:
        """
        Renomme les fichiers d'une série
        
        Args:
            series_path: Chemin du répertoire de la série
            pattern: Pattern de renommage
            files_to_rename: Liste des fichiers à renommer (noms ou chemins)
            series_title: Titre de la série
            dry_run: Si True, ne fait qu'un aperçu
        
        Returns:
            Tuple (succès, liste des changements, message d'erreur)
        """
        try:
            # Valider le pattern
            rename_pattern = RenamePattern(pattern)
            is_valid, error = rename_pattern.validate()
            if not is_valid:
                return False, [], error
            
            # Préparer les infos des fichiers
            files_info = []
            series_path_obj = Path(series_path)
            
            for file_item in files_to_rename:
                file_path = series_path_obj / file_item if not file_item.startswith('/') else Path(file_item)
                
                if not file_path.exists():
                    continue
                
                # Extraire le numéro de volume du nom du fichier
                volume_number = extract_volume_number(file_path.stem)
                
                files_info.append({
                    'filename': file_path.name,
                    'filepath': str(file_path),
                    'volume_number': volume_number,
                    'series_title': series_title
                })
            
            if not files_info:
                return False, [], "Aucun fichier trouvé à renommer"
            
            # Générer l'aperçu
            preview = rename_pattern.preview(files_info)
            
            if dry_run:
                return True, preview, ""
            
            # Effectuer le renommage réel
            results = []
            for item in preview:
                old_path = series_path_obj / item['old_name']
                new_path = series_path_obj / item['new_name']
                
                if old_path.exists():
                    # Vérifier que le nouveau nom n'existe pas déjà
                    if new_path.exists() and old_path != new_path:
                        logger.warning(f"Fichier destination existe déjà: {new_path}")
                        results.append({
                            'old_name': item['old_name'],
                            'new_name': item['new_name'],
                            'success': False,
                            'error': 'Fichier destination existe déjà'
                        })
                        continue
                    
                    try:
                        old_path.rename(new_path)
                        results.append({
                            'old_name': item['old_name'],
                            'new_name': item['new_name'],
                            'success': True
                        })
                        logger.info(f"Fichier renommé: {item['old_name']} -> {item['new_name']}")
                    except Exception as e:
                        results.append({
                            'old_name': item['old_name'],
                            'new_name': item['new_name'],
                            'success': False,
                            'error': str(e)
                        })
                        logger.error(f"Erreur renommage: {e}")
            
            return True, results, ""
        
        except Exception as e:
            logger.error(f"Erreur lors du renommage: {e}")
            return False, [], str(e)


def extract_volume_number(filename: str) -> int:
    """
    Extrait le numéro de volume d'un nom de fichier
    
    Args:
        filename: Nom du fichier (sans extension)
    
    Returns:
        Numéro de volume ou None
    """
    # Chercher un pattern comme "Vol 1", "Volume 1", "V1", etc.
    patterns = [
        r'[Vv](?:ol(?:ume)?)?\.?\s*(\d+)',  # V1, Vol 1, Volume 1
        r'(\d+)\s*(?:tomes?|volumes?)',      # 1 tome, 2 volumes
        r'^(\d+)',                            # Commence par un nombre
    ]
    
    for pattern in patterns:
        match = re.search(pattern, filename, re.IGNORECASE)
        if match:
            try:
                return int(match.group(1))
            except (ValueError, IndexError):
                pass
    
    return None
