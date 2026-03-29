#!/usr/bin/env python3
"""
Nettoie les @login_required en double
Garde seulement celui DIRECTEMENT avant la def
"""
import os
import glob
import re

def clean_duplicates(filepath):
    """Supprime les @login_required en double"""
    
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    new_lines = []
    i = 0
    removed = 0
    
    while i < len(lines):
        line = lines[i]
        
        # Si on trouve @login_required
        if '@login_required' in line:
            # Vérifier si la proche ligne suivante est aussi @login_required
            if i + 1 < len(lines) and '@login_required' in lines[i+1]:
                # Supprimer le doublon (garder le plus proche de def)
                removed += 1
                i += 1  # Sauter la ligne
                continue
            
            # Vérifier si c'est suivi d'une autre décorateur route
            if i + 1 < len(lines) and '.route(' in lines[i+1]:
                # C'est OK - @login_required avant la route
                new_lines.append(line)
            elif i + 1 < len(lines) and 'def ' in lines[i+1]:
                # C'est OK - @login_required avant def
                new_lines.append(line)
            # Sinon on saute les autres cas (par ex toutes les autres déco)
            else:
                new_lines.append(line)
        else:
            new_lines.append(line)
        
        i += 1
    
    if removed > 0:
        with open(filepath, 'w') as f:
            f.writelines(new_lines)
    
    return removed

# Nettoyer tous les fichiers
print("=" * 70)
print("🧹 NETTOYAGE - Suppression des @login_required en double")
print("=" * 70)

total_removed = 0
for filepath in sorted(glob.glob('blueprints/*/routes.py')):
    count = clean_duplicates(filepath)
    if count > 0:
        blueprint_name = filepath.split('/')[-2]
        print(f"✅ {blueprint_name:20} → -{count} doublons supprimés")
        total_removed += count

print(f"\n{total_removed} doublons supprimés au total")
print("=" * 70)
