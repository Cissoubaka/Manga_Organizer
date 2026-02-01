# Manga_Organizer
Permet de gerer sa collection de manga, importation, volumes manquants,.....

## A installer
- amulecmd ``sudo apt install amule-utils``
- module python : voir le fichier requirement.txt :
  ```pip install -r requirements.txt```

## Fonctionnement
#### Bibliothèque
- Ajouter une biliothèque,
- Scanner une bibliothèque
- Ouvrir la bibliothèque, pour consulter les séries
- Cliquer sur une série pour voir les volumes possédés, les manquants (en cliquant sur le volume manquant, cela cherche dans la base de données ebdz.net si configuré)
  
#### Import
A faire apres avoir au moins créer et scanner une bibliothèque
- choisir un chemin d'import,
- scanner le chemin
- cliquer sur auto-assigner
- modifier les assignation auto
- cliquer sur importer les fichiers assignés

#### Recherche
- rechercher dans la base de données de liens ed2k de ebdz.net
- cliquer sur ajouter permet d'envoyer directement a amule si amulecmd est installé, et si aMule est configuré 

#### Configuration
- configuration de aMule
- configuration des identifiants de ebdz.net et des sous-forums a scraper
- lancer le scrap des forums sélectionnés


