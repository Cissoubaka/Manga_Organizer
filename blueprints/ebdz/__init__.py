"""
Blueprint pour le scraper ebdz.net
"""
from flask import Blueprint

ebdz_bp = Blueprint('ebdz', __name__)

from . import routes
