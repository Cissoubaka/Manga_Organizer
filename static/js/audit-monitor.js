/**
 * Live Monitoring JavaScript
 * WebSocket for real-time event monitoring
 */

// Configuration
const CONFIG = {
    MAX_FEED_ITEMS: 500,
    AUTO_SCROLL: true,
    PAUSED: false
};

// State tracking
const state = {
    eventCount: 0,
    loginCount: 0,
    alerts: [],
    userStats: {},
    actionStats: {},
    feed: []
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎯 Initializing monitor...');
    
    // Check authentication
    checkAuth();
    
    // Setup event listeners
    setupEventListeners();
    
    // Try to establish WebSocket connection
    setupWebSocketConnection();
    
    // Load initial data
    loadInitialAlerts();
});

/**
 * Check if user is authenticated
 */
function checkAuth() {
    fetch('/auth/current-user')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.user) {
                document.getElementById('current-user').textContent = `👤 ${data.user.username}`;
            } else {
                window.location.href = '/auth/login';
            }
        })
        .catch(() => window.location.href = '/auth/login');
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    document.getElementById('logout-btn').addEventListener('click', logout);
}

/**
 * Setup WebSocket connection
 */
function setupWebSocketConnection() {
    console.log('🔌 Establishing WebSocket connection...');
    
    try {
        // For now, use polling instead of true WebSocket
        // In a full implementation, use Flask-SocketIO
        setInterval(pollForNewEvents, 5000);
        updateConnectionStatus(true);
    } catch (e) {
        console.error('❌ WebSocket error:', e);
        updateConnectionStatus(false);
    }
}

/**
 * Poll for new events every 5 seconds
 */
function pollForNewEvents() {
    if (CONFIG.PAUSED) return;
    
    fetch('/audit/recent-activity?limit=20')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Add new events to feed (reverse chronological)
                data.data.forEach(activity => {
                    addEventToFeed(activity);
                });
                
                // Check for alerts
                checkForAlerts();
                
                // Update live stats
                updateLiveStats();
            }
        })
        .catch(error => console.error('Poll error:', error));
}

/**
 * Add event to live feed
 */
function addEventToFeed(activity) {
    // Check if event already exists
    if (state.feed.some(e => e.timestamp === activity.timestamp)) {
        return;
    }
    
    state.feed.unshift(activity);
    state.eventCount++;
    
    if (activity.action && activity.action.includes('connexion')) {
        state.loginCount++;
    }
    
    // Update user stats
    if (activity.username) {
        state.userStats[activity.username] = (state.userStats[activity.username] || 0) + 1;
    }
    
    // Update action stats
    if (activity.action) {
        const actionType = simplifyAction(activity.action);
        state.actionStats[actionType] = (state.actionStats[actionType] || 0) + 1;
    }
    
    // Render feed
    rerenderFeed();
    updateLiveStats();
    
    // Show toast notification
    showNotification(activity);
}

/**
 * Render live feed
 */
function rerenderFeed() {
    const feedContainer = document.getElementById('live-feed');
    
    if (state.feed.length === 0) {
        feedContainer.innerHTML = `
            <div class="feed-placeholder">
                <p>En attente des événements...</p>
                <p style="font-size: 24px;">👀</p>
            </div>
        `;
        return;
    }
    
    const limit = CONFIG.MAX_FEED_ITEMS;
    const displayFeed = state.feed.slice(0, limit);
    
    feedContainer.innerHTML = displayFeed.map((activity, index) => {
        const timestamp = new Date(activity.timestamp).toLocaleTimeString('fr-FR');
        const level = activity.level || 'INFO';
        const levelIcon = getLevelIcon(level);
        const actionEmoji = getActionEmoji(activity.action);
        
        return `
            <div class="feed-item ${level.toLowerCase()}" data-index="${index}">
                <div class="feed-item-time">${timestamp}</div>
                <div class="feed-item-content">
                    <div class="feed-item-header">
                        <span class="feed-item-emoji">${levelIcon}</span>
                        <span class="feed-item-action">${actionEmoji} ${escapeHtml(activity.action || 'Unknown')}</span>
                        <span class="feed-item-user">@${escapeHtml(activity.username || 'system')}</span>
                    </div>
                    <div class="feed-item-meta">
                        <code>${escapeHtml(activity.ip_address || '-')}</code>
                        <span class="level-badge ${level.toLowerCase()}">${level}</span>
                    </div>
                </div>
            </div>
        `;
    }).join('');
    
    // Auto-scroll to top if enabled
    if (CONFIG.AUTO_SCROLL) {
        feedContainer.scrollTop = 0;
    }
}

/**
 * Update live statistics
 */
function updateLiveStats() {
    // Update counters
    document.getElementById('event-count').textContent = state.eventCount;
    document.getElementById('login-count').textContent = state.loginCount;
    document.getElementById('alert-count').textContent = state.alerts.length;
    
    // Update user stats
    const userStatsContainer = document.getElementById('user-stats');
    const topUsers = Object.entries(state.userStats)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);
    
    userStatsContainer.innerHTML = topUsers.map(([user, count]) => `
        <div class="stat-item">
            <span>${escapeHtml(user)}</span>
            <span class="count">${count}</span>
        </div>
    `).join('');
    
    // Update action stats
    const actionStatsContainer = document.getElementById('action-stats');
    const topActions = Object.entries(state.actionStats)
        .sort((a, b) => b[1] - a[1])
        .slice(0, 5);
    
    actionStatsContainer.innerHTML = topActions.map(([action, count]) => `
        <div class="stat-item">
            <span>${escapeHtml(action)}</span>
            <span class="count">${count}</span>
        </div>
    `).join('');
}

/**
 * Check for alerts
 */
function checkForAlerts() {
    fetch('/audit/alerts/check')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.has_alerts) {
                state.alerts = data.alerts;
                displayAlerts(data.alerts);
            } else {
                state.alerts = [];
                document.getElementById('alerts-section').classList.add('hidden');
            }
        })
        .catch(error => console.error('Alert check error:', error));
}

/**
 * Display alerts
 */
function displayAlerts(alerts) {
    const section = document.getElementById('alerts-section');
    const container = document.getElementById('alerts-container');
    
    if (alerts.length === 0) {
        section.classList.add('hidden');
        return;
    }
    
    section.classList.remove('hidden');
    
    container.innerHTML = alerts.map(alert => `
        <div class="alert-box ${alert.severity.toLowerCase()}">
            <div class="alert-header">
                <span class="alert-type">${alert.type}</span>
                <span class="alert-severity">${alert.severity}</span>
            </div>
            <div class="alert-body">
                <p>${escapeHtml(alert.message)}</p>
            </div>
        </div>
    `).join('');
}

/**
 * Load initial alerts
 */
function loadInitialAlerts() {
    checkForAlerts();
    setInterval(checkForAlerts, 10000); // Check every 10 seconds
}

/**
 * Show notification toast
 */
function showNotification(activity) {
    const toast = document.getElementById('toast');
    const level = activity.level || 'INFO';
    
    toast.textContent = `${getActionEmoji(activity.action)} ${activity.action}`;
    toast.className = `toast ${level.toLowerCase()}`;
    toast.classList.remove('hidden');
    
    setTimeout(() => toast.classList.add('hidden'), 3000);
}

/**
 * Toggle auto-scroll
 */
function toggleAutoScroll() {
    CONFIG.AUTO_SCROLL = !CONFIG.AUTO_SCROLL;
    document.getElementById('auto-scroll-btn').textContent = 
        CONFIG.AUTO_SCROLL ? '📌 Auto-scroll ON' : '📌 Auto-scroll OFF';
}

/**
 * Clear live feed
 */
function clearFeed() {
    if (confirm('Êtes-vous sûr de vouloir effacer le flux?')) {
        state.feed = [];
        state.eventCount = 0;
        state.loginCount = 0;
        state.userStats = {};
        state.actionStats = {};
        rerenderFeed();
        updateLiveStats();
    }
}

/**
 * Pause monitoring
 */
function pauseMonitoring() {
    CONFIG.PAUSED = !CONFIG.PAUSED;
    const btn = document.getElementById('pause-btn');
    btn.textContent = CONFIG.PAUSED ? '▶️ Reprendre' : '⏸️ Pause';
}

/**
 * Update connection status
 */
function updateConnectionStatus(connected) {
    const status = document.getElementById('connection-status');
    if (connected) {
        status.classList.remove('disconnected');
        status.classList.add('connected');
        status.textContent = '● Connecté';
    } else {
        status.classList.add('disconnected');
        status.classList.remove('connected');
        status.textContent = '● Déconnecté';
    }
}

/**
 * Get emoji for action level
 */
function getLevelIcon(level) {
    const icons = {
        'INFO': 'ℹ️',
        'WARNING': '⚠️',
        'ERROR': '🔴'
    };
    return icons[level] || 'ℹ️';
}

/**
 * Get emoji for action type
 */
function getActionEmoji(action) {
    if (!action) return '🎯';
    const lower = action.toLowerCase();
    
    if (lower.includes('connexion')) return action.includes('échouée') ? '🔐❌' : '🔐✓';
    if (lower.includes('déconnexion')) return '🚪';
    if (lower.includes('utilisateur')) return '👤';
    if (lower.includes('mot de passe')) return '🔑';
    if (lower.includes('permission')) return '⚙️';
    
    return '🎯';
}

/**
 * Simplify action name
 */
function simplifyAction(action) {
    if (!action) return 'Unknown';
    
    if (action.includes('connexion')) return 'Tentative connexion';
    if (action.includes('déconnexion')) return 'Déconnexion';
    if (action.includes('Utilisateur')) return 'Gestion utilisateur';
    if (action.includes('mot de passe')) return 'Changement mot de passe';
    
    return action.substring(0, 30);
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}

/**
 * Logout
 */
function logout() {
    if (confirm('Êtes-vous sûr de vouloir vous déconnecter?')) {
        fetch('/auth/logout', { method: 'POST' })
            .then(() => window.location.href = '/auth/login')
            .catch(error => console.error('Logout error:', error));
    }
}
