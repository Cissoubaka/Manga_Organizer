# 🎯 Page de Découverte et d'Ajout de Séries

## Vue d'ensemble

Une nouvelle page interactive a été créée pour permettre de découvrir et ajouter des séries à votre bibliothèque en trois étapes simples :

1. **Rechercher une série sur Nautiljon**
2. **Choisir une bibliothèque de destination**
3. **Chercher les sources dans EBDZ et Prowlarr**

## Accès à la page

La page est accessible depuis :
- 🏠 Page d'accueil : bouton **🎯 Découvrir et ajouter**
- 📚 Page de bibliothèque : bouton **🎯 Découvrir**
- 🔍 Page de recherche : bouton **🎯 Découvrir**

URL directe : `http://votre-serveur:5000/discover`

## Flux d'utilisation

### Étape 1️⃣ : Rechercher une série

1. Entrez le nom de la série que vous cherchez (ex: "One Piece", "Naruto", etc.)
2. Cliquez sur **🔍 Chercher sur Nautiljon**
3. Attendez les résultats (cela peut prendre quelques secondes, Nautiljon met du temps pour recharger)
4. Cliquez sur **✓ Sélectionner** pour la série souhaitée

### Étape 2️⃣ : Choisir une bibliothèque

1. La page affiche la série sélectionnée et la liste de vos bibliothèques
2. Cliquez sur la bibliothèque où vous voulez ranger cette série
3. Elle sera mise en surbrillance pour confirmer votre choix

### Étape 3️⃣ : Chercher les sources

1. Vous pouvez modifier le numéro de volume spécifique à chercher (optionnel)
2. Sélectionnez les sources à chercher :
   - ✅ **EBDZ (EdZ)** : Base de données locale des liens ED2K
   - ✅ **Prowlarr** : Indexeurs torrents configurés
3. Cliquez sur **🔎 Chercher les sources**
4. Les résultats s'affichent en bas avec détails :
   - Pour EBDZ : forum, taille, numéro de volume
   - Pour Prowlarr : indexeur, seeders, taille du fichier

## Caractéristiques

### Recherche Nautiljon
- Affiche jusqu'à 10 résultats
- Permet de trouver des séries exactes ou proches
- Récupère les informations officielles sur Nautiljon

### Recherche EBDZ
- Cherche dans la base de données de liens ED2K
- Affiche les 50 meilleurs résultats
- Filtre par nombre de volume et catégorie optionnels
- Affiche le lien ED2K pour chaque fichier

### Recherche Prowlarr
- Cherche dans tous les indexeurs configurés
- Affiche seeders et pairs pour chaque résultat
- Propose des liens cliquables vers les sources
- Classement par pertinence

## Données affichées

### Résultats Nautiljon
- Titre de la série
- URL directe vers Nautiljon

### Résultats EBDZ
- Titre du thread
- Nom du fichier
- Taille du fichier
- Numéro de volume identifié
- Forum source

### Résultats Prowlarr
- Titre du fichier/torrent
- Nombre de seeders et peers
- Taille du fichier
- Lien vers la source
- Indexeur
- Date de publication

## Fichiers créés/modifiés

### Fichiers créés
- `templates/discover.html` - Page HTML principale
- `static/css/style-discover.css` - Styles personnalisés
- `static/js/discover.js` - Logique JavaScript interactive

### Fichiers modifiés
- `blueprints/search/routes.py` - Ajout des routes Flask :
  - `GET /discover` - Page de découverte
  - `GET /api/search/ebdz` - Recherche EBDZ
  - `GET /api/search/prowlarr` - Recherche Prowlarr
- `templates/index.html` - Ajout du bouton de navigation
- `templates/library.html` - Ajout du bouton de navigation
- `templates/search.html` - Ajout du bouton de navigation

## API disponibles

### Recherche Nautiljon
```
GET /api/nautiljon/search?q=<nom_serie>
```
Retourne : Liste de séries avec titre et URL

### Recherche EBDZ
```
GET /api/search/ebdz?q=<nom_serie>&volume=<numéro>&category=<catégorie>
```
Paramètres optionnels : volume, category

### Recherche Prowlarr
```
GET /api/search/prowlarr?q=<nom_serie>&volume=<numéro>
```
Paramètre optionnel : volume

### Lister les bibliothèques
```
GET /api/libraries
```
Retourne : Liste complète des bibliothèques avec statistiques

## Notes techniques

- La page utilise des requêtes AJAX asynchrones pour une meilleure expérience
- Les erreurs sont affichées de façon claire et visible
- Les états de chargement sont indiqués par des messages animés
- La navigation entre les étapes est fluide et réversible
- Tous les appels API gèrent les erreurs gracieusement

## Prochaines étapes optionnelles

Si vous souhaitez améliorer cette fonctionnalité, voici des idées :
- Ajouter la création automatique d'une série dans la bibliothèque
- Intégrer un téléchargement automatique via eMule/aMule
- Ajouter un historique de recherche
- Permettre l'enregistrement de favoris
- Ajouter des filtres avancés pour les résultats
