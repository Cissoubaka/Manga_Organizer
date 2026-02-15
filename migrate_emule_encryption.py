#!/usr/bin/env python3
"""
Script de migration pour unifier le chiffrement eMule 
Exécuter une seule fois pour migrer eMule vers encryption.py unifié
"""
import json
import os
from encryption import encrypt, decrypt

CONFIG_FILE = './data/emule_config.json'
OLD_KEY_FILE = './data/.emule_key'

def migrate_emule_config():
    """Migrer la configuration eMule vers le système de chiffrement unifié"""
    
    # Vérifier si le fichier de config existe
    if not os.path.exists(CONFIG_FILE):
        print("❌ Fichier de configuration eMule introuvable")
        return False
    
    # Charger la configuration
    with open(CONFIG_FILE, 'r') as f:
        config = json.load(f)
    
    password = config.get('password', '')
    
    if not password:
        print("⚠ Aucun mot de passe trouvé dans la configuration eMule")
        return False
    
    # Essayer de déchiffrer avec l'ancienne clé
    try:
        if os.path.exists(OLD_KEY_FILE):
            print(f"Ancien mot de passe trouvé, migration en cours...")
            
            # Charger l'ancienne clé
            from cryptography.fernet import Fernet
            with open(OLD_KEY_FILE, 'rb') as f:
                old_key = f.read()
            
            # Déchiffrer avec l'ancienne clé
            try:
                old_cipher = Fernet(old_key)
                decrypted = old_cipher.decrypt(password.encode()).decode()
                print(f"✓ Mot de passe déchiffré avec l'ancienne clé")
                
                # Le remchiffrer avec la nouvelle clé
                config['password'] = encrypt(decrypted)
                
                # Sauvegarder
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(config, f, indent=4)
                
                print(f"✓ Mot de passe rechiffré avec la nouvelle clé")
                
                # Nettoyer l'ancienne clé
                os.remove(OLD_KEY_FILE)
                print(f"✓ Ancienne clé supprimée")
                
                return True
            except Exception as e:
                print(f"⚠ Impossible de déchiffrer avec l'ancienne clé: {e}")
                print(f"Tentative de déchiffrement avec la nouvelle clé...")
                
                # Le mot de passe est peut-être déjà chiffré avec la nouvelle clé
                decrypted = decrypt(password)
                if decrypted and decrypted != password:
                    print(f"✓ Mot de passe compatible avec la nouvelle clé - aucune migration nécessaire")
                    return True
                else:
                    print(f"✗ Impossible de migrer le mot de passe eMule")
                    return False
        else:
            # Pas d'ancienne clé - vérifier si le password est déjà chiffré avec la nouvelle
            decrypted = decrypt(password)
            if decrypted and decrypted != password:
                print(f"✓ Mot de passe eMule est déjà chiffré avec la nouvelle clé")
                return True
            else:
                # Le password est en clair, le chiffrer
                config['password'] = encrypt(password)
                with open(CONFIG_FILE, 'w') as f:
                    json.dump(config, f, indent=4)
                print(f"✓ Mot de passe eMule chiffré avec la nouvelle clé")
                return True
    
    except Exception as e:
        print(f"✗ Erreur lors de la migration: {e}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == '__main__':
    print("\n" + "=" * 60)
    print("Migration du chiffrement eMule vers système unifié")
    print("=" * 60)
    
    if migrate_emule_config():
        print("✓ Migration réussie\n")
    else:
        print("✗ Erreur lors de la migration\n")
