#!/usr/bin/env python3
"""
Script de migration pour chiffrer les identifiants existants
Exécuter une seule fois au démarrage du serveur actualisé
"""
import json
import os
from encryption import ensure_encryption_key, encrypt

CONFIG_FILE = './data/ebdz_config.json'

def migrate_ebdz_config():
    """Migrer la configuration ebdz en chiffrant les identifiants"""
    
    # S'assurer que la clé de chiffrement existe
    ensure_encryption_key()
    
    # Vérifier si le fichier de config existe
    if not os.path.exists(CONFIG_FILE):
        print("❌ Fichier de configuration introuvable")
        return False
    
    # Charger la configuration
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    
    # Vérifier si déjà chiffré (les mots de passe chiffrés commencent par 'gAAAAAA')
    password = config.get('password', '')
    
    if password and password.startswith('gAAAAAA'):
        print("✓ Le mot de passe est déjà chiffré")
        return True
    
    if password:
        print(f"Chiffrement du mot de passe pour l'utilisateur: {config.get('username')}")
        config['password'] = encrypt(password)
        
        # Sauvegarder la configuration chiffrée
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        
        print("✓ Configuration migrée avec succès - mot de passe chiffré")
        return True
    else:
        print("⚠ Aucun mot de passe trouvé dans la configuration")
        return False

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("Migration des identifiants EBDZ")
    print("=" * 60)
    
    if migrate_ebdz_config():
        print("✓ Migration réussie\n")
    else:
        print("✗ Erreur lors de la migration\n")
