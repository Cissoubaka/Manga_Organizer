#!/bin/bash
set -e

# Script de démarrage du container

# Vérifier que amulecmd est disponible
if ! command -v amulecmd &> /dev/null; then
    echo "⚠️ Avertissement : amulecmd n'a pas pu être installé"
    echo "L'intégration aMule ne sera pas disponible"
fi

# Démarrer l'application Flask
exec python3 -c "from app import create_app; app = create_app('production'); app.run(host='0.0.0.0', port=5000)"
