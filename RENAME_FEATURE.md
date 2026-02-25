# Fonctionnalité de Renommage de Fichiers

## Description

Vous pouvez maintenant renommer les fichiers d'une série directement depuis sa fiche. Cette fonctionnalité vous permet d'utiliser des **tags personnalisables** (similaire au renommeur de Total Commander) pour créer des patterns de renommage flexibles.

## Accès

1. Ouvrez une **fiche série** depuis la bibliothèque
2. Cliquez sur le bouton **✏️ Renommer fichiers** (visible dans la section Nautiljon ou en haut du modal)

## Tags disponibles

| Tag | Description | Exemple |
|-----|-------------|---------|
| `[T]` | Titre de la série | `[T]` → "Naruto" |
| `[V]` | Numéro de volume | `[V]` → "1", "2", etc. |
| `[C:départ:longueur]` | Compteur avec paramètres | `[C:01:3]` → "001", "002", "003" |
| `[E]` | Extension du fichier | `[E]` → "pdf", "cbz", "zip" |
| `[N]` | Nom du fichier original (sans extension) | `[N]` → "Chapitre 1" |
| `[P]` | Numéro de partie (si applicable) | `[P]` → "1", "2" |

## Paramètres du tag Compteur `[C]`

Format: `[C:départ:longueur]`

- **départ** : Numéro de départ du compteur (ex: 01, 1, 100)
- **longueur** : Nombre de chiffres avec zéros à gauche (ex: 1, 2, 3)

**Exemples:**
- `[C:01:3]` → 001, 002, 003, 010, 100
- `[C:1:2]` → 01, 02, 03, 10, 99
- `[C:100:3]` → 100, 101, 102

## Exemples de patterns

### Pattern simple avec titre et volume
```
[T] - Vol [V].[E]
```
**Résultat :** `Naruto - Vol 1.pdf`, `Naruto - Vol 2.pdf`

### Pattern avec compteur
```
[T] [C:01:3].[E]
```
**Résultat :** `Naruto 001.pdf`, `Naruto 002.pdf`, `Naruto 003.pdf`

### Pattern avec compteur au début
```
[C:01:2] - [N].[E]
```
**Résultat :** `01 - Chapter 1.pdf`, `02 - Chapter 2.pdf`

### Garder le nom original avec extension
```
[T] - [N].[E]
```
**Résultat :** `Naruto - Chapitre 1.pdf`, `Naruto - Chapitre 2.pdf`

## Fonctionnement

1. **Entrez votre pattern** dans le champ de renommage
2. **Visualisez l'aperçu** : le système affiche immédiatement comment chaque fichier sera renommé
3. **Validez les changements** : cliquez sur "Appliquer le renommage"
4. **Confirmation** : un message de confirmation s'affichera avant d'effectuer les changements
5. **Résultat** : les fichiers sont renommés et la série est automatiquement re-scannée

## Points importants

⚠️ **Le renommage est irréversible** - Assurez-vous de vérifier l'aperçu avant de valider !

✅ **Validation automatique** - Si votre pattern n'est pas valide, un message d'erreur s'affichera

✅ **Gestion des doublons** - Le système refuse de renommer si le nouveau nom existe déjà

✅ **Re-scan automatique** - Après le renommage, la série est automatiquement re-scannée pour mettre à jour la base de données

## Résolution des problèmes

**"Tag non supporté"** → Utilisez uniquement les tags listés ci-dessus

**"Format incorrect pour [C]"** → Utilisez le format correct : `[C:départ:longueur]`

**"Aucun fichier trouvé"** → La série doit avoir des fichiers dans sa bibliothèque

**"Fichier destination existe déjà"** → Votre pattern génère des doublons, modifiez-le
