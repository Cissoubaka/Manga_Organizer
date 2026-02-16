"""
Blueprint pour Nautiljon - Source d'infos sur les mangas
"""
from flask import Blueprint

nautiljon_bp = Blueprint('nautiljon', __name__)

from . import routes
