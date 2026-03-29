/**
 * 🔐 CSRF Token & Auth Helper
 * Gère les tokens CSRF et les appels API sécurisés
 */

// ============================================================================
// CSRF TOKEN MANAGEMENT
// ============================================================================

/**
 * Récupère le token CSRF depuis la meta tag
 * @returns {string} Le token CSRF ou vide si absent
 */
function getCsrfToken() {
    try {
        // Chercher la meta tag csrf-token
        const csrfMeta = document.querySelector('meta[name="csrf-token"]')
        if (csrfMeta && csrfMeta.content) {
            return csrfMeta.content
        }
        // Alternative: chercher dans les données du DOM
        const csrfDiv = document.getElementById('csrf-token')
        if (csrfDiv && csrfDiv.textContent) {
            return csrfDiv.textContent
        }
        return ''
    } catch (e) {
        console.warn('Could not get CSRF token:', e)
        return ''
    }
}

// ============================================================================
// AUTH STATE MANAGEMENT  
// ============================================================================

let currentUser = null

/**
 * Récupère l'utilisateur actuellement connecté
 * @returns {Promise<Object|null>} Les infos de l'utilisateur ou null
 */
async function getCurrentUser() {
    try {
        const response = await fetch('/auth/current-user')
        const data = await response.json()
        if (data.success && data.user) {
            currentUser = data.user
            return currentUser
        }
        currentUser = null
        return null
    } catch (e) {
        console.error('Error fetching current user:', e)
        currentUser = null
        return null
    }
}

/**
 * Vérifie si l'utilisateur est connecté
 * @returns {Promise<boolean>}
 */
async function isAuthenticated() {
    const user = await getCurrentUser()
    return user !== null
}

// ============================================================================
// SECURE API CALLS WITH CSRF
// ============================================================================

/**
 * Effectue un appel API sécurisé avec gestion CSRF et 401
 * @param {string} url - L'URL à appeler
 * @param {Object} options - Options fetch (method, body, etc.)
 * @returns {Promise<Response>}
 */
async function apiCall(url, options = {}) {
    // Fusionner avec les options par défaut
    const config = {
        method: 'GET',
        headers: {
            'Content-Type': 'application/json',
            ...options.headers
        },
        ...options
    }

    // Ajouter le token CSRF pour les requêtes non-GET
    if (config.method !== 'GET') {
        const csrfToken = getCsrfToken()
        if (csrfToken) {
            config.headers['X-CSRFToken'] = csrfToken
        }
    }

    // Effectuer la requête
    const response = await fetch(url, config)

    // Gérer les erreurs d'authentification
    if (response.status === 401) {
        console.warn('Authentification requise!')
        handleUnauthorized()
        throw new Error('Authentification requise')
    }

    return response
}

/**
 * Appelé quand l'utilisateur n'est pas authentifié (401)
 */
function handleUnauthorized() {
    showMessage(
        'Votre session a expiré. Veuillez vous reconnecter.',
        'warning'
    )
    // Rediriger vers la page de login après 2s
    setTimeout(() => {
        window.location.href = '/auth/login?next=' + encodeURIComponent(window.location.pathname)
    }, 2000)
}

// ============================================================================
// UTILITY FUNCTIONS
// ============================================================================

/**
 * Affiche un message temporaire à l'utilisateur
 * @param {string} message - Le message to afficher
 * @param {string} type - Type: 'success', 'error', 'warning', 'info'
 * @param {number} duration - Durée en millisecondes (0 = permanent)
 */
function showMessage(message, type = 'info', duration = 3000) {
    // Créer un conteneur s'il n'existe pas
    let container = document.getElementById('message-container-auth')
    if (!container) {
        container = document.createElement('div')
        container.id = 'message-container-auth'
        container.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            z-index: 10000;
            max-width: 400px;
            font-family: sans-serif;
        `
        document.body.appendChild(container)
    }

    // Créer l'élément du message
    const messageEl = document.createElement('div')
    const colors = {
        'success': '#10b981',
        'error': '#ef4444',
        'warning': '#f59e0b',
        'info': '#3b82f6'
    }
    const bg = colors[type] || colors['info']

    messageEl.style.cssText = `
        background-color: ${bg};
        color: white;
        padding: 16px 20px;
        border-radius: 6px;
        margin-bottom: 10px;
        box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        animation: slideIn 0.3s ease-out;
    `
    messageEl.textContent = message

    container.appendChild(messageEl)

    // Retirer le message après la durée
    if (duration > 0) {
        setTimeout(() => {
            messageEl.style.animation = 'slideOut 0.3s ease-in forwards'
            setTimeout(() => messageEl.remove(), 300)
        }, duration)
    }
}

// ============================================================================
// USER MENU DISPLAY
// ============================================================================

/**
 * Affiche le menu utilisateur dans le header
 * @param {Object} user - Objet utilisateur avec propriété 'username'
 */
function showUserMenu(user) {
    try {
        // Créer ou récupérer le conteneur du menu utilisateur
        let userMenu = document.getElementById('user-menu-container')
        
        if (!userMenu) {
            // Chercher un header ou créer un conteneur
            const header = document.querySelector('header') || document.querySelector('.header-content')
            if (!header) return
            
            userMenu = document.createElement('div')
            userMenu.id = 'user-menu-container'
            userMenu.style.cssText = `
                display: flex;
                align-items: center;
                gap: 12px;
                position: absolute;
                right: 20px;
                top: 50%;
                transform: translateY(-50%);
            `
            
            // Insérer dans le header
            header.style.position = 'relative'
            header.appendChild(userMenu)
        }
        
        // Créer le contenu du menu
        userMenu.innerHTML = `
            <span style="color: #666; font-size: 14px;">
                👤 ${escapeHtml(user.username)}
            </span>
            <button id="logout-btn" style="
                background: #ef4444;
                color: white;
                border: none;
                padding: 8px 16px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 500;
            ">
                Déconnexion
            </button>
        `
        
        // Ajouter l'événement de déconnexion
        const logoutBtn = document.getElementById('logout-btn')
        if (logoutBtn) {
            logoutBtn.addEventListener('click', logout)
        }
        
    } catch (error) {
        console.warn('Erreur lors de l\'affichage du menu utilisateur:', error)
    }
}

/**
 * Effectue la déconnexion
 */
async function logout() {
    try {
        const response = await apiCall('/auth/logout', {
            method: 'POST'
        })
        
        if (response.ok) {
            console.log('✓ Déconnexion réussie')
            showMessage('Vous avez été déconnecté', 'success', 2000)
            
            // Rediriger vers la page de login après 1s
            setTimeout(() => {
                window.location.href = '/auth/login'
            }, 1000)
        } else {
            showMessage('Erreur lors de la déconnexion', 'error')
        }
    } catch (error) {
        console.error('Erreur lors de la déconnexion:', error)
        showMessage('Erreur serveur', 'error')
    }
}

/**
 * Échappe les caractères HTML pour éviter les injections XSS
 * @param {string} text - Texte à échapper
 * @returns {string} Texte échappé
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    }
    return text.replace(/[&<>"']/g, m => map[m])
}

// ============================================================================
// CSRF TOKEN SETUP (À l'initialisation de la page)
// ============================================================================

/**
 * Initialise le système CSRF et affiche le user connecté
 * À appeler au chargement de la page
 */
async function initAuthSystem() {
    try {
        // Vérifier l'authentification
        const user = await getCurrentUser()
        
        if (user) {
            console.log('✓ Utilisateur connecté:', user.username)
            // Afficher le menu utilisateur si la fonction existe
            if (typeof showUserMenu === 'function') {
                showUserMenu(user)
            }
        } else {
            console.log('Aucun utilisateur connecté')
        }
    } catch (error) {
        console.error('Erreur lors de l\'initialisation du système d\'auth:', error)
    }
}

// JS CSS pour les animations
function addAuthStyles() {
    const style = document.createElement('style')
    style.textContent = `
        @keyframes slideIn {
            from {
                transform: translateX(400px);
                opacity: 0;
            }
            to {
                transform: translateX(0);
                opacity: 1;
            }
        }
        
        @keyframes slideOut {
            from {
                transform: translateX(0);
                opacity: 1;
            }
            to {
                transform: translateX(400px);
                opacity: 0;
            }
        }
    `
    document.head.appendChild(style)
}

// Initialiser les styles dès que le script est chargé
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', addAuthStyles)
} else {
    addAuthStyles()
}
