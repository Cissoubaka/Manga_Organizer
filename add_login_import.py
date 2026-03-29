#!/usr/bin/env python3
"""
Ajoute l'import Flask-Login aux fichiers blueprints qui en ont besoin
"""
import os
import re

files_needing_import = [
    'blueprints/ebdz/routes.py',
    'blueprints/emule/routes.py',
    'blueprints/missing_monitor/routes.py',
    'blueprints/nautiljon/routes.py',
    'blueprints/prowlarr/routes.py',
    'blueprints/qbittorrent/routes.py',
    'blueprints/search/routes.py',
    'blueprints/settings/routes.py',
]

for filepath in files_needing_import:
    if not os.path.exists(filepath):
        print(f"❌ {filepath}: fichier non trouvé")
        continue
    
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Vérifier si l'import existe déjà
    if 'from flask_login import login_required' in content:
        print(f"✓ {filepath}: import existe déjà")
        continue
    
    # Trouver le endroit où ajouter l'import (après les autres imports flask)
    lines = content.split('\n')
    insert_pos = -1
    
    # Trouver la dernière ligne de import 'from flask'
    for i, line in enumerate(lines):
        if line.startswith('from flask'):
            insert_pos = i
    
    if insert_pos == -1:
        print(f"⚠️ {filepath}: pas d'imports Flask trouvés")
        continue
    
    # Ajouter l'import après la dernière ligne de 'from flask'
    lines.insert(insert_pos + 1, 'from flask_login import login_required')
    
    with open(filepath, 'w') as f:
        f.write('\n'.join(lines))
    
    print(f"✅ {filepath}: import ajouté")

print("\n✅ Imports ajoutés!")
