"""
Routes pour la page de configuration
"""
from flask import render_template, jsonify
from flask_login import login_required, current_user
from . import settings_bp


@settings_bp.route('/settings')
@login_required
def settings_page():
    """Page de configuration"""
    return render_template('settings.html')


@settings_bp.route('/users')
@login_required
def users_page():
    """Page de gestion des utilisateurs (admin only)"""
    # Vérifier que l'utilisateur est admin
    if current_user.id != '1':
        return jsonify({'error': 'Accès refusé - admin requis'}), 403
    
    return render_template('users.html')