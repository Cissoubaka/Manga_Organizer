# Chiffrement unifié des identifiants

## 🔐 Modifications apportées

Un système de chiffrement unifié a été implémenté pour tous les identifiants sensibles (EBDZ et eMule).

### Fichiers créés/modifiés :

1. **[encryption.py](encryption.py)** - Module de chiffrement unifié
   - Gestion centralisée de la clé de chiffrement Fernet
   - Fonctions `encrypt()` et `decrypt()` réutilisables
   - La clé est générée automatiquement et stockée dans `./data/.encryption_key`

2. **[blueprints/ebdz/routes.py](blueprints/ebdz/routes.py)** - Routes EBDZ mises à jour
   - Import du module de chiffrement unifié
   - `load_ebdz_config()` déchiffre automatiquement le mot de passe
   - `save_ebdz_config()` chiffre automatiquement le mot de passe

3. **[blueprints/emule/routes.py](blueprints/emule/routes.py)** - Routes eMule mises à jour
   - Import du module de chiffrement unifié
   - Suppression du code de chiffrement dupliqué
   - `load_emule_config()` déchiffre automatiquement le mot de passe
   - `save_emule_config()` chiffre automatiquement le mot de passe
   - Les appels `amulecmd` utilisent le mot de passe déchiffré

4. **[app.py](app.py)** - Point d'entrée mis à jour
   - Initialisation automatique de la clé de chiffrement au démarrage

5. **[config.py](config.py)** - Configuration nettoyée
   - Suppression de `KEY_FILE` (utilise une clé unique maintenant)

## ✅ Étapes de migration

### Migration EBDZ (effectuée)
```bash
✓ Clé de chiffrement générée et sauvegardée
✓ Mot de passe chiffré pour l'utilisateur: Cissou
✓ Configuration migrée avec succès
```

### Migration eMule (effectuée)
```bash
✓ Ancien mot de passe trouvé, migration en cours...
✓ Mot de passe déchiffré avec l'ancienne clé
✓ Mot de passe rechiffré avec la nouvelle clé
✓ Ancienne clé supprimée
```

## 📋 Résumé des changements

### Avant (2 systèmes indépendants)
```
📁 data/
├── .encryption_key (clé EBDZ)
├── .emule_key (clé eMule)
├── ebdz_config.json (password chiffré)
└── emule_config.json (password chiffré)
```

### Après (système unifié)
```
📁 data/
├── .encryption_key (clé unique)
├── ebdz_config.json (password chiffré avec la même clé)
└── emule_config.json (password chiffré avec la même clé)
```

## 🔑 Sécurité de la clé

- **Une seule clé** `./data/.encryption_key` pour tous les services
- Elle est **automatiquement ignorée par Git** (dossier `data/` dans .gitignore)
- Chaque installation a sa propre clé unique
- Les mots de passe restent masqués en "****" dans les réponses API

## 🚀 Utilisation

Aucun changement requis côté utilisateur final. Le chiffrement/déchiffrement se fait automatiquement :

1. **Au chargement de la configuration** : les mots de passe sont déchiffrés automatiquement
2. **À la sauvegarde** : les nouveaux mots de passe sont chiffrés automatiquement
3. **Lors de la connexion** : les mots de passe déchiffrés sont utilisés

## 🧪 Test du système

Pour vérifier le fonctionnement :
```bash
python3 -c "
from encryption import decrypt, encrypt
# Tester le chiffrement
password = 'mon_mot_de_passe'
encrypted = encrypt(password)
decrypted = decrypt(encrypted)
print(f'Original: {password}')
print(f'Déchiffré: {decrypted}')
print(f'✓ OK' if password == decrypted else '✗ Erreur')
"
```

## ⚠️ Important

- **Ne commitez pas** `./data/.encryption_key` (elle est ignorée par git)
- **Gardez** la clé en sécurité - la perdre rendra les mots de passe illisibles
- **Sauvegardez** votre `.encryption_key` si vous changez de machine
- Les deux services (EBDZ et eMule) utilisent maintenant la **même clé**

---

**Date de migration** : 15 février 2026  
**Algorithme** : Fernet (AES-128 CTR + HMAC)  
**Services protégés** : EBDZ, eMule/aMule
