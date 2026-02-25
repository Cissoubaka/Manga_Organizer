"""
Module de surveillance des volumes manquants et envoi automatique aux clients de téléchargement
"""
from flask import Blueprint

missing_monitor_bp = Blueprint('missing_monitor', __name__)

# Import des routes
from . import routes
