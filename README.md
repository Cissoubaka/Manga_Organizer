# Manga_Organizer
Permet de gerer sa collection de manga, importation, volumes manquants,.....

## A installer
- amulecmd ``sudo apt install amule-utils``
- module python : voir le fichier requirement.txt :
  ```pip install -r requirements.txt```
- un crontab, comme par exemple une fois par semaine pour scraper.py
  


## app.py
- ajouter des bibliothèques de mangas,
- importer des nouveaux mangas dans les series deja dispo (remplacement si taille plus grande) ou de nouvelle serie (choix de la bibliotèque)
- afficher les volumes manquants dans les séries et les rechercher directement
- rechercher les séries/volumes dans la base de données obtenu par scraper.py
- configuration de amule directement sur la page web
- ajouter des volumes a télécharger directement dans aMule



## scraper.py
- permet de scraper les liens ed2k du forum ebdz.net dans une base de données avec covers et descriptions pour la plupart des mangas.
- identification du forum a mettre vers la fin du fichier.

### Correction a venir
- détection correcte des volumes par scraper.py (beaucoup de cas particulier du a un formalisme totalement absent)
- suppression des bouton parcourir qui ne fonctionnent pas
- il faut rescanner la bibliotheque apres l'import de nouveaux volumes/séries
