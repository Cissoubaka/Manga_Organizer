"""
Module de chiffrement pour les données sensibles
"""
import os
from cryptography.fernet import Fernet
import base64

# Fichier où stocker la clé de chiffrement
ENCRYPTION_KEY_FILE = './data/.encryption_key'


def ensure_encryption_key():
    """Assure qu'une clé de chiffrement existe, la crée sinon"""
    os.makedirs('./data', exist_ok=True)
    
    if not os.path.exists(ENCRYPTION_KEY_FILE):
        key = Fernet.generate_key()
        with open(ENCRYPTION_KEY_FILE, 'wb') as f:
            f.write(key)
        print("✓ Clé de chiffrement générée et sauvegardée")
    else:
        print("✓ Clé de chiffrement existante trouvée")


def load_encryption_key():
    """Charge la clé de chiffrement"""
    if not os.path.exists(ENCRYPTION_KEY_FILE):
        raise FileNotFoundError(f"Clé de chiffrement non trouvée. Exécutez ensure_encryption_key()")
    
    with open(ENCRYPTION_KEY_FILE, 'rb') as f:
        return f.read()


def encrypt(plaintext):
    """Chiffre une chaîne de caractères"""
    if not plaintext:
        return None
    
    key = load_encryption_key()
    cipher = Fernet(key)
    encrypted = cipher.encrypt(plaintext.encode())
    return encrypted.decode()


def decrypt(ciphertext):
    """Déchiffre une chaîne de caractères"""
    if not ciphertext:
        return None
    
    try:
        key = load_encryption_key()
        cipher = Fernet(key)
        decrypted = cipher.decrypt(ciphertext.encode())
        return decrypted.decode()
    except Exception as e:
        print(f"Erreur déchiffrement: {e}")
        return None
