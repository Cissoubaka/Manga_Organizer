#!/usr/bin/env python3
"""
Script d'automatisation - Ajouter @login_required sur toutes les routes API
Phase 2: Protection des routes
"""
import re
import os

def add_login_required_to_file(filepath, skip_if_name=None):
    """
    Ajoute @login_required avant les routes API
    skip_if_name: nom de la fonction à sauter (ex: 'login', 'logout', 'current_user')
    """
    with open(filepath, 'r') as f:
        content = f.read()
    
    # Pattern pour chercher les routes @bp.route() ou @<nom>_bp.route()
    # qui commencent par /api/ et ne ont pas déjà @login_required
    pattern = r'(@\w+\.route\([\'"]\/api\/.*?[\'"].*?\))\ndef (\w+)\(:'
    
    # Récupérer tous les matches
    matches = list(re.finditer(pattern, content, re.DOTALL))
    
    if not matches:
        print(f"⚠️ Aucune route API trouvée dans {filepath}")
        return False
    
    # Process en reverse order pour ne pas perdre les indexes
    for match in reversed(matches):
        start = match.start()
        
        # Checker si @login_required est déjà là
        before_text = content[max(0,start-50):start]
        if '@login_required' in before_text:
            continue
        
        # Checker si la fonction est dans skip_list
        func_name = match.group(2)
        if skip_if_name and func_name in skip_if_name:
            print(f"  ⏭️ Skipping {func_name} (dans skip_list)")
            continue
        
        # Insérer @login_required après la route et avant la fonction
        route_end = match.end(1)
        content = content[:route_end] + '\n@login_required' + content[route_end:]
        print(f"  ✅ Ajout @login_required sur {func_name}")
    
    # Écrire le fichier modifié
    with open(filepath, 'w') as f:
        f.write(content)
    
    return True


# Fichiers à traiter
files_to_protect = [
    ('blueprints/library/routes.py', None),
    ('blueprints/ebdz/routes.py', ['ebdz_config', 'scrape', 'auto_scrape_config']),  # À adapter si besoin
    ('blueprints/emule/routes.py', None),
    ('blueprints/settings/routes.py', None),
    ('blueprints/prowlarr/routes.py', None),
    ('blueprints/qbittorrent/routes.py', None),
    ('blueprints/missing_monitor/routes.py', None),
    ('blueprints/search/routes.py', None),  # Optionnel
    ('blueprints/nautiljon/routes.py', None),  # Optionnel
]

print("=" * 60)
print("🔐 AJOUT @login_required - Phase 2a")
print("=" * 60)

for filepath, skip_list in files_to_protect:
    full_path = os.path.join(os.path.dirname(__file__), filepath)
    
    if not os.path.exists(full_path):
        print(f"\n❌ {filepath} - FICHIER NON TROUVÉ")
        continue
    
    print(f"\n📝 {filepath}")
    try:
        if add_login_required_to_file(full_path, skip_list):
            print(f"   ✅ Modifié avec succès")
        else:
            print(f"   ⚠️ Aucun changement")
    except Exception as e:
        print(f"   ❌ Erreur: {e}")

print("\n" + "=" * 60)
print("✅ TERMINÉ")
print("=" * 60)
