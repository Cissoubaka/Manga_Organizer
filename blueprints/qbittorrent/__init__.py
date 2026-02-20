from flask import Blueprint

qbittorrent_bp = Blueprint(
    'qbittorrent',
    __name__,
    url_prefix='/api/qbittorrent'
)

from . import routes
