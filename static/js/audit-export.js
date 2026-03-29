/**
 * Export & Reporting JavaScript
 * Handle filtering, preview, and export functionality
 */

// State
const exportState = {
    filters: {
        date_from: '',
        date_to: '',
        username: '',
        action: '',
        ip_address: '',
        level: ''
    },
    previewData: [],
    recentExports: []
};

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎯 Initializing export page...');
    
    checkAuth();
    loadFilters();
    loadRecentExports();
    setDefaultDates();
});

/**
 * Check authentication
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
        
    document.getElementById('logout-btn').addEventListener('click', logout);
}

/**
 * Set default dates (last 7 days)
 */
function setDefaultDates() {
    const to = new Date();
    const from = new Date(to.getTime() - 7 * 24 * 60 * 60 * 1000);
    
    document.getElementById('date-from').valueAsDate = from;
    document.getElementById('date-to').valueAsDate = to;
}

/**
 * Load available filters from server
 */
function loadFilters() {
    fetch('/audit/filters')
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                populateFilterSelects(data.filters);
            }
        })
        .catch(error => console.error('Filter load error:', error));
}

/**
 * Populate filter dropdown selects
 */
function populateFilterSelects(filters) {
    // Users
    const userSelect = document.getElementById('user-filter');
    filters.usernames.forEach(user => {
        const option = document.createElement('option');
        option.value = user;
        option.textContent = user;
        userSelect.appendChild(option);
    });
    
    // IPs
    const ipSelect = document.getElementById('ip-filter');
    filters.ips.forEach(ip => {
        const option = document.createElement('option');
        option.value = ip;
        option.textContent = ip;
        ipSelect.appendChild(option);
    });
    
    // Actions
    const actionSelect = document.getElementById('action-filter');
    filters.actions.forEach(action => {
        const option = document.createElement('option');
        option.value = action;
        option.textContent = action.substring(0, 50);
        actionSelect.appendChild(option);
    });
}

/**
 * Collect current filters
 */
function collectFilters() {
    exportState.filters = {
        date_from: document.getElementById('date-from').value,
        date_to: document.getElementById('date-to').value,
        username: document.getElementById('user-filter').value,
        action: document.getElementById('action-filter').value,
        ip_address: document.getElementById('ip-filter').value,
        level: document.getElementById('level-filter').value
    };
    
    return exportState.filters;
}

/**
 * Preview data with current filters
 */
function previewData() {
    const filters = collectFilters();
    
    showLoadingSpinner(true);
    
    fetch('/audit/export/preview', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filters: filters, limit: 100 })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            exportState.previewData = data.data;
            displayPreview(data);
        } else {
            alert(`Erreur: ${data.error}`);
        }
    })
    .catch(error => console.error('Preview error:', error))
    .finally(() => showLoadingSpinner(false));
}

/**
 * Display preview
 */
function displayPreview(data) {
    const previewSection = document.getElementById('preview-section');
    const tbody = document.getElementById('preview-body');
    
    document.getElementById('record-count').textContent = data.total_records;
    document.getElementById('preview-count').textContent = data.preview_count;
    
    tbody.innerHTML = data.data.map(record => `
        <tr>
            <td>${escapeHtml(record.timestamp.substring(0, 19))}</td>
            <td>${escapeHtml(record.username || '-')}</td>
            <td>${escapeHtml(record.action || '-')}</td>
            <td><code>${escapeHtml(record.ip_address || '-')}</code></td>
            <td><span class="level-badge">${record.level || 'INFO'}</span></td>
        </tr>
    `).join('');
    
    previewSection.classList.remove('hidden');
    updateStatsDisplay(data);
}

/**
 * Update stats display
 */
function updateStatsDisplay(data) {
    document.getElementById('stat-records').textContent = data.total_records;
    
    // Count unique users and IPs
    const uniqueUsers = new Set(data.data.map(d => d.username));
    const uniqueIPs = new Set(data.data.map(d => d.ip_address));
    
    document.getElementById('stat-users').textContent = uniqueUsers.size;
    document.getElementById('stat-ips').textContent = uniqueIPs.size;
    
    // Calculate timespan
    if (data.data.length > 0) {
        const timestamps = data.data.map(d => new Date(d.timestamp));
        const oldest = new Date(Math.min(...timestamps));
        const newest = new Date(Math.max(...timestamps));
        const hours = Math.ceil((newest - oldest) / (1000 * 60 * 60));
        
        document.getElementById('stat-duration').textContent = 
            hours > 24 ? `${Math.ceil(hours / 24)} jours` : `${hours} heures`;
    }
}

/**
 * Close preview
 */
function closePreview() {
    document.getElementById('preview-section').classList.add('hidden');
}

/**
 * Download report
 */
function downloadReport() {
    const filters = collectFilters();
    const format = document.querySelector('input[name="format"]:checked').value;
    
    showLoadingSpinner(true);
    
    const endpoint = `/audit/export/${format}`;
    
    fetch(endpoint, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ filters: filters })
    })
    .then(response => response.json())
    .then(data => {
        if (data.success) {
            if (format === 'csv' || format === 'json') {
                downloadTextFile(data.data, data.filename, format);
            } else if (format === 'pdf') {
                alert('✓ PDF généré avec succès!\n\nFichier: ' + data.filename);
            }
            
            addToRecentExports(format, data.filename);
        } else {
            alert(`Erreur: ${data.error}`);
        }
    })
    .catch(error => {
        console.error('Download error:', error);
        alert('Erreur lors du téléchargement');
    })
    .finally(() => showLoadingSpinner(false));
}

/**
 * Download text file (CSV/JSON)
 */
function downloadTextFile(content, filename, format) {
    const mimeType = format === 'csv' ? 'text/csv' : 'application/json';
    const blob = new Blob([content], { type: mimeType });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    
    link.href = url;
    link.download = filename;
    document.body.appendChild(link);
    link.click();
    document.body.removeChild(link);
    URL.revokeObjectURL(url);
}

/**
 * Add to recent exports list
 */
function addToRecentExports(format, filename) {
    const export_item = {
        format: format,
        filename: filename,
        timestamp: new Date().toLocaleString('fr-FR'),
        size: '~2.5 MB'
    };
    
    exportState.recentExports.unshift(export_item);
    if (exportState.recentExports.length > 10) {
        exportState.recentExports.pop();
    }
    
    // Save to localStorage
    try {
        localStorage.setItem('recentExports', JSON.stringify(exportState.recentExports));
    } catch (e) {
        console.error('localStorage save error:', e);
    }
    
    renderRecentExports();
}

/**
 * Render recent exports
 */
function renderRecentExports() {
    const container = document.getElementById('downloads-list');
    
    if (exportState.recentExports.length === 0) {
        container.innerHTML = '<p style="color: #999;">Aucun export récent</p>';
        return;
    }
    
    container.innerHTML = exportState.recentExports.map((item, index) => `
        <div class="export-item">
            <div class="export-info">
                <span class="export-format badge-${item.format}">${item.format.toUpperCase()}</span>
                <span class="export-name">${escapeHtml(item.filename.substring(0, 40))}</span>
            </div>
            <div class="export-meta">
                <span>${item.timestamp}</span>
            </div>
        </div>
    `).join('');
}

/**
 * Load recent exports from localStorage
 */
function loadRecentExports() {
    const saved = localStorage.getItem('recentExports');
    if (saved) {
        try {
            exportState.recentExports = JSON.parse(saved);
            renderRecentExports();
        } catch (e) {
            console.error('Load recent exports error:', e);
        }
    }
}

/**
 * Show/hide loading spinner
 */
function showLoadingSpinner(show) {
    const spinner = document.getElementById('loading-spinner');
    if (spinner) {
        spinner.classList.toggle('hidden', !show);
    }
}

/**
 * Escape HTML
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
