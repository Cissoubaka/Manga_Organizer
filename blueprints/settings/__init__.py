"""
Blueprint pour les paramètres de l'application
"""
from flask import Blueprint

settings_bp = Blueprint('settings', __name__)

from . import routes
