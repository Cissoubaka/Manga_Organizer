# Manga_Organizer
Permet de gerer sa collection de manga, importation, volumes manquants,.....



## app.py
ajouter des bibliothèques de mangas,
importer des nouveaux mangas dans les series deja dispo (remplacement si taille plus grande) ou de nouvelle serie (choix de la bibliotèque)
afficher les volumes manquants dans les séries
rechercher les séries/volumes dans la base de données obtenu par scraper.py


## scraper.py
permet de scraper les liens ed2k du forum ebdz.net dans une base de données avec covers et descriptions pour la plupart des mangas.
identification du forum a mettre vers la fin du fichier.

### Correction a venir
- détection correcte des volumes par scraper.py
- cliquer sur le volume manquant le recherche dans la bdd edbz
- ...
