"""
Routes pour la page de configuration
"""
from flask import render_template
from . import settings_bp


@settings_bp.route('/settings')
def settings_page():
    """Page de configuration"""
    return render_template('settings.html')