/**
 * Gestion de la surveillance des volumes manquants
 */

// Variables globales
let currentLibrariesData = [];
let currentSeriesData = [];
let currentSearchResults = [];
let currentHistoryData = [];
let selectedLibraries = [];

// Initialisation
document.addEventListener('DOMContentLoaded', function() {
    initializeTabs();
    loadStats();
    loadLibraries();
    loadDownloadHistory();
    loadConfig();
    
    // Événements de recherche
    document.getElementById('series-search').addEventListener('input', filterSeries);
    document.getElementById('series-status-filter').addEventListener('change', filterSeries);
    document.getElementById('history-filter').addEventListener('change', filterHistory);
});

// ========== TAB MANAGEMENT ==========

function initializeTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', function() {
            const tabName = this.getAttribute('data-tab');
            
            // Supprimer active de tous les boutons et panes
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabPanes.forEach(pane => pane.classList.remove('active'));
            
            // Ajouter active au bouton et pane cliqué
            this.classList.add('active');
            document.getElementById(tabName).classList.add('active');
        });
    });
}

// ========== STATS ==========

async function loadStats() {
    try {
        const response = await fetch('/api/missing-monitor/stats');
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('monitored-count').textContent = data.monitored_series || 0;
            document.getElementById('missing-count').textContent = data.total_missing_volumes || 0;
            document.getElementById('download-count').textContent = data.recent_downloads.length || 0;
            
            // Afficher les téléchargements récents
            displayRecentDownloads(data.recent_downloads);
        }
    } catch (error) {
        console.error('Erreur chargement stats:', error);
    }
}

function displayRecentDownloads(downloads) {
    const container = document.getElementById('recent-downloads');
    
    if (!downloads || downloads.length === 0) {
        container.innerHTML = '<p class="no-data">Aucun téléchargement pour le moment</p>';
        return;
    }
    
    container.innerHTML = downloads.map(dl => {
        const success = dl.success ? '✅' : '❌';
        const date = new Date(dl.created_at).toLocaleDateString('fr-FR');
        
        return `
            <div class="download-item ${dl.success ? 'success' : 'error'}">
                <div class="result-title">
                    ${success} ${dl.title} - Vol ${dl.volume_number}
                </div>
                <div class="result-meta">
                    <span>Client: ${dl.client}</span>
                    <span>${date}</span>
                </div>
                <div style="font-size: 12px; color: #6b7280; margin-top: 8px;">
                    ${dl.message || ''}
                </div>
            </div>
        `;
    }).join('');
}

function refreshStats() {
    showToast('Rafraîchissement en cours...', 'info');
    loadStats();
    loadLibraries();
    loadDownloadHistory();
}

// ========== LIBRARIES ==========

async function loadLibraries() {
    try {
        const response = await fetch('/api/missing-monitor/libraries');
        const data = await response.json();
        
        if (data.success) {
            currentLibrariesData = data.libraries;
            
            // Récupérer les bibliothèques sélectionnées
            selectedLibraries = data.libraries
                .filter(lib => lib.monitored === 1)
                .map(lib => lib.id);
            
            displayLibrariesSelection();
            
            // Charger les séries des bibliothèques sélectionnées
            await loadSeriesForSelectedLibraries();
        }
    } catch (error) {
        console.error('Erreur chargement bibliothèques:', error);
    }
}

function displayLibrariesSelection() {
    const container = document.getElementById('libraries-selection');
    
    if (currentLibrariesData.length === 0) {
        container.innerHTML = '<p class="no-data">Aucune bibliothèque trouvée</p>';
        return;
    }
    
    container.innerHTML = currentLibrariesData.map(lib => {
        const isSelected = selectedLibraries.includes(lib.id);
        const selectedClass = isSelected ? 'selected' : '';
        
        return `
            <label class="library-card ${selectedClass}">
                <input type="checkbox" class="library-checkbox" ${isSelected ? 'checked' : ''} 
                       onchange="toggleLibrarySelection(${lib.id})">
                <div class="library-name">${escapeHtml(lib.name)}</div>
                <div class="library-info">
                    📖 ${lib.total_series} série(s)
                </div>
                <div class="library-info">
                    ${isSelected ? '✅ Sélectionnée' : '❌ Non sélectionnée'}
                </div>
            </label>
        `;
    }).join('');
}

async function toggleLibrarySelection(libraryId) {
    const index = selectedLibraries.indexOf(libraryId);
    const isCurrentlySelected = index !== -1;
    const newState = !isCurrentlySelected;
    
    try {
        // Appeler l'API pour mettre à jour l'état de surveillance
        const response = await fetch(`/api/missing-monitor/libraries/${libraryId}/monitor`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ enabled: newState })
        });
        
        const result = await response.json();
        if (result.success) {
            // Mettre à jour la liste locale
            if (newState) {
                if (!selectedLibraries.includes(libraryId)) {
                    selectedLibraries.push(libraryId);
                }
            } else {
                if (index !== -1) {
                    selectedLibraries.splice(index, 1);
                }
            }
            
            // Recharger les séries
            await loadSeriesForSelectedLibraries();
            
            // Rafraîchir l'affichage des bibliothèques
            displayLibrariesSelection();
            
            showToast(`Bibliothèque ${newState ? 'sélectionnée' : 'désélectionnée'}`, 'success');
        }
    } catch (error) {
        console.error('Erreur modification bibliothèque:', error);
        showToast('Erreur lors de la mise à jour', 'error');
    }
}

async function loadSeriesForSelectedLibraries() {
    if (selectedLibraries.length === 0) {
        currentSeriesData = [];
        filterSeries();
        return;
    }
    
    try {
        let allSeries = [];
        
        for (const libraryId of selectedLibraries) {
            const response = await fetch(`/api/missing-monitor/libraries/${libraryId}/series`);
            const data = await response.json();
            
            if (data.success) {
                allSeries = allSeries.concat(data.series);
            }
        }
        
        currentSeriesData = allSeries;
        filterSeries();
    } catch (error) {
        console.error('Erreur chargement séries:', error);
    }
}

// ========== MONITORED SERIES ==========

async function loadMonitoredSeries() {
    // Fonction héritée - maintenant remplacée par loadLibraries() et selectiveloading
    // Garder pour la compatibilité
    await loadLibraries();
}

function filterSeries() {
    const searchTerm = document.getElementById('series-search').value.toLowerCase();
    const statusFilter = document.getElementById('series-status-filter').value;
    
    let filtered = currentSeriesData;
    
    // Filtre par recherche
    if (searchTerm) {
        filtered = filtered.filter(s => 
            s.title.toLowerCase().includes(searchTerm)
        );
    }
    
    // Filtre par statut
    if (statusFilter === 'missing') {
        filtered = filtered.filter(s => 
            s.nautiljon_status && 
            s.nautiljon_status.toLowerCase().startsWith('termin')
        );
    } else if (statusFilter === 'incomplete') {
        filtered = filtered.filter(s => 
            s.nautiljon_status && 
            !s.nautiljon_status.toLowerCase().startsWith('termin')
        );
    }
    
    displaySeriesGrid(filtered);
}

function displaySeriesGrid(series) {
    const grid = document.getElementById('series-grid');
    
    if (series.length === 0) {
        grid.innerHTML = '<p class="no-data">Aucune série trouvée</p>';
        return;
    }
    
    grid.innerHTML = series.map(s => {
        // Parser missing_volumes si c'est une chaîne JSON
        let missingVols = s.missing_volumes;
        if (typeof missingVols === 'string') {
            try {
                missingVols = JSON.parse(missingVols);
            } catch (e) {
                missingVols = [];
            }
        }
        
        const missingVolsStr = Array.isArray(missingVols) ? missingVols.join(', ') : '';
        const missingCount = Array.isArray(missingVols) ? missingVols.length : 0;
        const isMonitored = s.enabled !== 0; // 0 = non suivi, 1 = suivi
        const badgeClass = isMonitored ? 'badge-monitored' : 'badge-not-monitored';
        const badgeText = isMonitored ? '✅ Suivi' : '❌ Non suivi';
        const buttonText = isMonitored ? '✅ Suivi' : '❌ Non suivi';
        const buttonClass = isMonitored ? 'btn-success' : 'btn-danger';
        
        return `
            <div class="series-card">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px; margin-bottom: 10px;">
                    <div class="series-title" style="flex: 1;">${escapeHtml(s.title)}</div>
                    <span class="series-badge ${badgeClass}">${badgeText}</span>
                </div>
                <div class="series-info">
                    📚 ${s.total_local} volume(s) local
                </div>
                ${s.nautiljon_total_volumes ? `
                    <div class="series-info">
                        🌊 ${s.nautiljon_total_volumes} volumes (Nautiljon)
                    </div>
                ` : ''}
                ${missingCount > 0 ? `
                    <div class="series-info series-missing">
                        ⚠️  ${missingCount} manquant(s): ${missingVolsStr}
                    </div>
                ` : ''}
                <div class="result-actions" style="margin-top: 10px;">
                    <button class="btn ${buttonClass}" style="flex: 1; font-size: 13px;" 
                            onclick="configureSeriesMonitor(${s.id})">
                        ${buttonText}
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

async function configureSeriesMonitor(seriesId) {
    const series = currentSeriesData.find(s => s.id === seriesId);
    if (!series) return;
    
    // Déterminer le nouvel état (toggle)
    const isCurrentlyMonitored = series.enabled !== 0; // 0 = non suivi
    const newState = !isCurrentlyMonitored;
    
    // Message de confirmation
    const action = newState ? 'activer' : 'désactiver';
    const confirmed = confirm(`${newState ? '✅' : '❌'} ${action.charAt(0).toUpperCase() + action.slice(1)} la surveillance pour "${series.title}"?`);
    
    if (!confirmed) return;
    
    const autoDownload = false; // Pour l'instant, désactivé par défaut
    
    try {
        const response = await fetch(`/api/missing-monitor/series/${seriesId}/monitor`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                enabled: newState,
                search_sources: ['ebdz', 'prowlarr'],
                auto_download_enabled: autoDownload
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(
                `✅ Surveillance ${newState ? 'activée' : 'désactivée'} pour ${series.title}`, 
                'success'
            );
            loadMonitoredSeries();
        } else {
            showToast('Erreur: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Erreur:', error);
        showToast('Erreur de configuration', 'error');
    }
}

// ========== SEARCH ==========

async function searchVolume() {
    const title = document.getElementById('search-title').value.trim();
    const volume = document.getElementById('search-volume').value;
    
    if (!title || !volume) {
        showToast('Veuillez remplir tous les champs', 'error');
        return;
    }
    
    const sources = Array.from(document.querySelectorAll('input[name="search-source"]:checked'))
        .map(el => el.value);
    
    if (sources.length === 0) {
        showToast('Sélectionnez au moins une source', 'error');
        return;
    }
    
    showToast('Recherche en cours...', 'info');
    
    try {
        const response = await fetch('/api/missing-monitor/search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                title: title,
                volume_num: parseInt(volume),
                sources: sources
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            currentSearchResults = data.results;
            displaySearchResults(data.results, data.query);
            showToast(`${data.results_count} résultat(s) trouvé(s)`, 'success');
        } else {
            showToast('Erreur: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Erreur recherche:', error);
        showToast('Erreur de recherche', 'error');
    }
}

function displaySearchResults(results, query) {
    const section = document.getElementById('search-results-section');
    const container = document.getElementById('search-results');
    
    if (!results || results.length === 0) {
        section.style.display = 'none';
        showToast('Aucun résultat trouvé', 'info');
        return;
    }
    
    section.style.display = 'block';
    
    container.innerHTML = results.map(result => {
        const seeders = result.seeders ? `👥 ${result.seeders} seeders` : '';
        const size = result.size ? `${(result.size / 1073741824).toFixed(2)} GB` : '';
        
        return `
            <div class="result-item">
                <div class="result-title">
                    ${escapeHtml(result.title)}
                </div>
                <div class="result-meta">
                    ${result.source ? `<span>🔗 ${result.source}</span>` : ''}
                    ${result.indexer ? `<span>${result.indexer}</span>` : ''}
                    ${seeders ? `<span>${seeders}</span>` : ''}
                    ${size ? `<span>💾 ${size}</span>` : ''}
                </div>
                <div class="result-actions">
                    <button class="btn btn-primary" onclick="openDownloadModal('${escapeHtml(result.link)}', '${escapeHtml(currentSearchResults[0].title || '')}', '')">
                        📥 Télécharger
                    </button>
                </div>
            </div>
        `;
    }).join('');
}

// ========== DOWNLOAD MODAL ==========

function openDownloadModal(link, title, volume) {
    document.getElementById('modal-link').value = link;
    document.getElementById('modal-title').value = title || '';
    document.getElementById('modal-volume').value = volume || '';
    document.getElementById('download-modal').classList.add('show');
}

function closeDownloadModal() {
    document.getElementById('download-modal').classList.remove('show');
}

async function confirmDownload() {
    const link = document.getElementById('modal-link').value.trim();
    const title = document.getElementById('modal-title').value.trim();
    const volume = document.getElementById('modal-volume').value;
    
    if (!link) {
        showToast('Veuillez fournir un lien', 'error');
        return;
    }
    
    showToast('Envoi du téléchargement...', 'info');
    
    try {
        const response = await fetch('/api/missing-monitor/download', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                link: link,
                title: title,
                volume_num: parseInt(volume) || 0
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast(data.message || 'Téléchargement envoyé', 'success');
            closeDownloadModal();
            loadStats();
        } else {
            showToast('Erreur: ' + data.message, 'error');
        }
    } catch (error) {
        console.error('Erreur:', error);
        showToast('Erreur envoi téléchargement', 'error');
    }
}

// ========== HISTORY ==========

async function loadDownloadHistory() {
    try {
        const response = await fetch('/api/missing-monitor/history?limit=50');
        const data = await response.json();
        
        if (data.success) {
            currentHistoryData = data.history;
            filterHistory();
        }
    } catch (error) {
        console.error('Erreur chargement historique:', error);
    }
}

function filterHistory() {
    const filter = document.getElementById('history-filter').value;
    
    let filtered = currentHistoryData;
    
    if (filter === 'success') {
        filtered = filtered.filter(h => h.success);
    } else if (filter === 'error') {
        filtered = filtered.filter(h => !h.success);
    }
    
    displayHistory(filtered);
}

function displayHistory(history) {
    const container = document.getElementById('history-list');
    
    if (!history || history.length === 0) {
        container.innerHTML = '<p class="no-data">Aucun historique disponible</p>';
        return;
    }
    
    container.innerHTML = history.map(item => {
        const date = new Date(item.created_at).toLocaleDateString('fr-FR', {
            year: 'numeric',
            month: 'long',
            day: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        return `
            <div class="history-item ${item.success ? 'success' : 'error'}">
                <div class="history-info">
                    <div class="history-title">
                        ${item.success ? '✅' : '❌'} ${escapeHtml(item.title)} - Vol ${item.volume_number}
                    </div>
                    <div class="history-meta">
                        ${item.client} • ${item.message}
                    </div>
                </div>
                <div class="history-date">${date}</div>
            </div>
        `;
    }).join('');
}

// ========== CONFIGURATION ==========

async function loadConfig() {
    try {
        const response = await fetch('/api/missing-monitor/config');
        const config = await response.json();
        
        document.getElementById('config-enabled').checked = config.enabled || false;
        document.getElementById('config-auto-check').checked = config.auto_check_enabled || false;
        document.getElementById('config-interval').value = config.auto_check_interval || 60;
        document.getElementById('config-interval-unit').value = config.auto_check_interval_unit || 'minutes';
        document.getElementById('config-search').checked = config.search_enabled !== false;
        document.getElementById('config-auto-download').checked = config.auto_download_enabled || false;
        document.getElementById('config-client').value = config.preferred_client || 'qbittorrent';
        
        // Cocher les sources
        (config.search_sources || ['ebdz', 'prowlarr']).forEach(source => {
            const el = document.querySelector(`input[name="source"][value="${source}"]`);
            if (el) el.checked = true;
        });
        
        updateAutoCheckUI();
    } catch (error) {
        console.error('Erreur chargement config:', error);
    }
}

function updateAutoCheckUI() {
    const enabled = document.getElementById('config-auto-check').checked;
    const settings = document.getElementById('auto-check-settings');
    settings.style.display = enabled ? 'block' : 'none';
}

async function saveConfig() {
    const sources = Array.from(document.querySelectorAll('input[name="source"]:checked'))
        .map(el => el.value);
    
    const config = {
        enabled: document.getElementById('config-enabled').checked,
        auto_check_enabled: document.getElementById('config-auto-check').checked,
        auto_check_interval: parseInt(document.getElementById('config-interval').value) || 60,
        auto_check_interval_unit: document.getElementById('config-interval-unit').value,
        search_enabled: document.getElementById('config-search').checked,
        search_sources: sources,
        auto_download_enabled: document.getElementById('config-auto-download').checked,
        preferred_client: document.getElementById('config-client').value
    };
    
    try {
        const response = await fetch('/api/missing-monitor/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });
        
        const data = await response.json();
        
        if (data.success) {
            showToast('Configuration sauvegardée', 'success');
        } else {
            showToast('Erreur: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Erreur sauvegarde config:', error);
        showToast('Erreur sauvegarde configuration', 'error');
    }
}

// ========== MANUAL CHECK ==========

async function runManualCheck() {
    showToast('Vérification en cours...', 'info');
    
    try {
        const response = await fetch('/api/missing-monitor/run-check', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                search_enabled: true,
                auto_download: false
            })
        });
        
        const data = await response.json();
        
        if (data.success) {
            const stats = data.stats;
            showToast(
                `Vérification terminée:\n` +
                `• ${stats.total_series} séries analysées\n` +
                `• ${stats.total_missing} volumes manquants trouvés\n` +
                `• ${stats.searches_performed} recherches effectuées\n` +
                `• ${stats.results_found} résultats trouvés`,
                'success'
            );
            loadStats();
            loadDownloadHistory();
        } else {
            showToast('Erreur: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Erreur vérification:', error);
        showToast('Erreur lors de la vérification', 'error');
    }
}

// ========== UTILITIES ==========

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    
    document.getElementById('toast-container').appendChild(toast);
    
    setTimeout(() => {
        toast.style.animation = 'slideOut 0.3s ease';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

// Fermer modal en cliquant à l'extérieur
window.addEventListener('click', function(event) {
    const modal = document.getElementById('download-modal');
    if (event.target === modal) {
        closeDownloadModal();
    }
});

// Maj perodique des stats
setInterval(() => {
    // Refresh stats silencieusement toutes les minutes
    fetch('/api/missing-monitor/stats')
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                document.getElementById('monitored-count').textContent = data.monitored_series || 0;
                document.getElementById('missing-count').textContent = data.total_missing_volumes || 0;
            }
        })
        .catch(() => {}); // Ignorer les erreurs silencieusement
}, 60000);
