#!/bin/bash
set -e

# Script de démarrage du container

# Vérifier que amulecmd est disponible
if ! command -v amulecmd &> /dev/null; then
    echo "⚠️ Avertissement : amulecmd n'a pas pu être installé"
    echo "L'intégration aMule ne sera pas disponible"
fi

# Démarrer l'application Flask
exec python3 run.py
