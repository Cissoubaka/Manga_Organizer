"""
Blueprint pour l'intégration eMule/aMule
"""
from flask import Blueprint

emule_bp = Blueprint('emule', __name__)

from . import routes
