#!/usr/bin/env python3
"""
Script d'entrée pour l'application Manga Organizer
"""
from app import create_app

if __name__ == '__main__':
    app = create_app('production')
    app.run(host='0.0.0.0', port=5000)
