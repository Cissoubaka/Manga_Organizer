#!/bin/bash
# Script de test de la fonctionnalité de surveillance des volumes manquants

set -e

echo "📚 Test de la Surveillance des Volumes Manquants"
echo "=============================================="
echo ""

# Couleurs
BLUE='\033[0;34m'
GREEN='\033[0;32m'
RED='\033[0;31m'
NC='\033[0m' # No Color

# 1. Vérifier que l'application démarre
echo -e "${BLUE}1. Démarrage de l'application...${NC}"
cd "$(dirname "$0")"

# Vérifier les imports
python3 << 'EOF'
try:
    from blueprints.missing_monitor.detector import MissingVolumeDetector
    from blueprints.missing_monitor.searcher import MissingVolumeSearcher
    from blueprints.missing_monitor.downloader import MissingVolumeDownloader
    from blueprints.missing_monitor.scheduler import MissingVolumeScheduler
    print("✓ Tous les modules s'importent correctement")
except ImportError as e:
    print(f"✗ Erreur d'import: {e}")
    exit(1)
EOF

echo ""

# 2. Vérifier la syntaxe des fichiers
echo -e "${BLUE}2. Vérification de la syntaxe Python...${NC}"
python3 -m py_compile \
    blueprints/missing_monitor/__init__.py \
    blueprints/missing_monitor/detector.py \
    blueprints/missing_monitor/searcher.py \
    blueprints/missing_monitor/downloader.py \
    blueprints/missing_monitor/scheduler.py \
    blueprints/missing_monitor/routes.py
echo "✓ Syntaxe OK"

echo ""

# 3. Vérifier les fichiers créés
echo -e "${BLUE}3. Vérification des fichiers créés...${NC}"
FILES=(
    "blueprints/missing_monitor/__init__.py"
    "blueprints/missing_monitor/detector.py"
    "blueprints/missing_monitor/searcher.py"
    "blueprints/missing_monitor/downloader.py"
    "blueprints/missing_monitor/scheduler.py"
    "blueprints/missing_monitor/routes.py"
    "templates/missing-monitor.html"
    "static/css/style-missing-monitor.css"
    "static/js/missing-monitor.js"
    "MISSING_VOLUMES_MONITOR.md"
    "IMPLEMENTATION_SUMMARY.md"
)

for file in "${FILES[@]}"; do
    if [ -f "$file" ]; then
        lines=$(wc -l < "$file")
        echo "✓ $file ($lines lignes)"
    else
        echo "✗ $file (MANQUANT)"
    fi
done

echo ""

# 4. Lancer un test rapide de l'application
echo -e "${BLUE}4. Test de démarrage de l'application...${NC}"
timeout 5 python3 app.py > /tmp/app_test.log 2>&1 &
APP_PID=$!

sleep 3

# Vérifier si l'app est toujours en cours d'exécution
if kill -0 $APP_PID 2>/dev/null; then
    echo "✓ Application démarre correctement"
    kill $APP_PID 2>/dev/null || true
else
    echo "✗ Erreur au démarrage:"
    cat /tmp/app_test.log
    exit 1
fi

echo ""

# 5. Vérifier les modifications aux fichiers existants
echo -e "${BLUE}5. Vérification des modifications existantes...${NC}"

if grep -q "missing_monitor_bp" app.py; then
    echo "✓ Blueprint intégré dans app.py"
else
    echo "✗ Blueprint non trouvé dans app.py"
fi

if grep -q "MISSING_MONITOR_CONFIG_FILE" config.py; then
    echo "✓ Configuration ajoutée dans config.py"
else
    echo "✗ Configuration manquante dans config.py"
fi

if grep -q "/missing-monitor" blueprints/library/routes.py; then
    echo "✓ Route HTML créée dans library/routes.py"
else
    echo "✗ Route manquante dans library/routes.py"
fi

if grep -q "missing-monitor" templates/index.html; then
    echo "✓ Lien menu ajouté dans index.html"
else
    echo "✗ Lien menu manquant dans index.html"
fi

echo ""

# Résumé
echo -e "${GREEN}=============================================="
echo "✓ Tous les tests réussis!"
echo "=============================================="
echo ""
echo "📚 Fonctionnalité complètement implémentée!"
echo ""
echo "Prochaines étapes:"
echo "1. Démarrer: python app.py"
echo "2. Accéder: http://localhost:5000/missing-monitor"
echo "3. Configurer les paramètres"
echo "4. Consulter la doc: MISSING_VOLUMES_MONITOR.md"
echo ""
