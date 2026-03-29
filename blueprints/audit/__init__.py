"""
Audit Blueprint - Dashboard, analytics, and reporting
"""
from flask import Blueprint

audit_bp = Blueprint('audit', __name__, url_prefix='/audit')

# Import routes to register them
from .routes import *
