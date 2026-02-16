"""
Blueprint pour l'intégration Prowlarr
"""
from flask import Blueprint

prowlarr_bp = Blueprint('prowlarr', __name__)

from . import routes
