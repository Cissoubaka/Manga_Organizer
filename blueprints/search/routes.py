"""
Routes pour la recherche de liens ED2K
"""
from flask import render_template, request, jsonify, current_app
from . import search_bp
import sqlite3


def get_db_connection():
    """Retourne une connexion à la base ED2K"""
    conn = sqlite3.connect(current_app.config['DB_FILE'], timeout=30.0)
    conn.row_factory = sqlite3.Row
    return conn


@search_bp.route('/search')
def search_page():
    """Page de recherche ED2K"""
    
    # Récupérer les catégories et statistiques
    conn = get_db_connection()
    cursor = conn.cursor()
    
    cursor.execute('SELECT DISTINCT forum_category FROM ed2k_links ORDER BY forum_category')
    categories = [row[0] for row in cursor.fetchall()]
    
    cursor.execute('SELECT COUNT(*) FROM ed2k_links')
    total_links = cursor.fetchone()[0]
    
    cursor.execute('SELECT COUNT(DISTINCT thread_id) FROM ed2k_links')
    total_threads = cursor.fetchone()[0]
    
    conn.close()
    
    return render_template('search.html', 
                          categories=categories, 
                          total_links=total_links,
                          total_threads=total_threads)


@search_bp.route('/api/search', methods=['GET'])
def search_links():
    """Recherche de liens ED2K"""
    
    query = request.args.get('query', '').strip()
    volume = request.args.get('volume', '').strip()
    category = request.args.get('category', '').strip()
    
    conn = get_db_connection()
    cursor = conn.cursor()
    
    sql = 'SELECT * FROM ed2k_links WHERE 1=1'
    params = []
    
    if query:
        sql += ' AND (thread_title LIKE ? OR filename LIKE ?)'
        params.extend([f'%{query}%', f'%{query}%'])
    
    if volume:
        sql += ' AND volume = ?'
        params.append(int(volume))
    
    if category:
        sql += ' AND forum_category = ?'
        params.append(category)
    
    sql += ' ORDER BY thread_title, volume'
    
    cursor.execute(sql, params)
    
    results = []
    for row in cursor.fetchall():
        results.append(dict(row))
    
    conn.close()
    
    return jsonify({'results': results})

@search_bp.route('/api/search')
def search_ed2k():
    query = request.args.get('query', '').strip()
    volume = request.args.get('volume', '').strip()
    category = request.args.get('category', '').strip()

    try:
        conn = sqlite3.connect(current_app.config['DB_FILE'], timeout=30.0)
        cursor = conn.cursor()

        sql = '''
            SELECT thread_id, thread_title, thread_url, forum_category, cover_image,
                   link, filename, filesize, volume, description
            FROM ed2k_links
            WHERE 1=1
        '''
        params = []

        if query:
            sql += ' AND (thread_title LIKE ? OR filename LIKE ?)'
            search_term = f'%{query}%'
            params.extend([search_term, search_term])

        if volume:
            sql += ' AND volume = ?'
            params.append(int(volume))

        if category:
            sql += ' AND forum_category = ?'
            params.append(category)

        sql += ' ORDER BY thread_id, volume'

        cursor.execute(sql, params)
        results = cursor.fetchall()

        links = []
        for row in results:
            links.append({
                'thread_id': row[0],
                'thread_title': row[1],
                'thread_url': row[2],
                'forum_category': row[3],
                'cover_image': row[4],
                'link': row[5],
                'filename': row[6],
                'filesize': row[7],
                'volume': row[8],
                'description': row[9]
            })

        conn.close()

        return jsonify({'results': links})

    except Exception as e:
        return jsonify({'error': str(e)}), 500
