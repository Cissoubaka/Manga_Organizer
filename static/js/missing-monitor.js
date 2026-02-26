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
    console.log('🚀 DOMContentLoaded triggered - Initializing missing-monitor page');
    
    try {
        initializeTabs();
        console.log('✅ Tabs initialized');
    } catch (e) {
        console.error('❌ Erreur initializeTabs:', e);
    }
    
    try {
        loadStats();
        console.log('✅ Stats loaded');
    } catch (e) {
        console.error('❌ Erreur loadStats:', e);
    }
    
    try {
        loadLibraries();
        // Initialiser le filtre par défaut
        document.getElementById('filter-all-series')?.classList.add('active');
        console.log('✅ Libraries loaded');
    } catch (e) {
        console.error('❌ Erreur loadLibraries:', e);
    }
    
    try {
        loadDownloadHistory();
        console.log('✅ Download history loaded');
    } catch (e) {
        console.error('❌ Erreur loadDownloadHistory:', e);
    }
    
    // Configuration moved to /settings - no longer loading here
    console.log('✅ Configuration is now managed in /settings');
    
    // Événements de recherche avec vérifications
    const seriesSearch = document.getElementById('series-search');
    if (seriesSearch) {
        seriesSearch.addEventListener('input', filterSeries);
        console.log('✅ Series search listener added');
    } else {
        console.warn('⚠️ series-search element not found');
    }
    
    const seriesStatusFilter = document.getElementById('series-status-filter');
    if (seriesStatusFilter) {
        seriesStatusFilter.addEventListener('change', filterSeries);
        console.log('✅ Series status filter listener added');
    } else {
        console.warn('⚠️ series-status-filter element not found');
    }
    
    const seriesBadgesFilter = document.getElementById('series-badges-filter');
    if (seriesBadgesFilter) {
        seriesBadgesFilter.addEventListener('change', filterSeries);
        console.log('✅ Series badges filter listener added');
    } else {
        console.warn('⚠️ series-badges-filter element not found');
    }
    
    const historyFilter = document.getElementById('history-filter');
    if (historyFilter) {
        historyFilter.addEventListener('change', filterHistory);
        console.log('✅ History filter listener added');
    } else {
        console.warn('⚠️ history-filter element not found');
    }
    
    console.log('🎉 Page initialization complete');
});

// ========== TAB MANAGEMENT ==========

function initializeTabs() {
    const tabButtons = document.querySelectorAll('.tab-button');
    const tabPanes = document.querySelectorAll('.tab-pane');
    
    console.log('initializeTabs called - found', tabButtons.length, 'buttons and', tabPanes.length, 'panes');
    
    tabButtons.forEach(button => {
        button.addEventListener('click', function(e) {
            // Skip if not a real tab button (e.g., configuration link)
            if (!this.hasAttribute('data-tab')) {
                console.log('Skipping non-tab button');
                return;
            }
            
            e.preventDefault();
            const tabName = this.getAttribute('data-tab');
            console.log('Tab clicked:', tabName);
            
            // Supprimer active de tous les boutons et panes
            tabButtons.forEach(btn => btn.classList.remove('active'));
            tabPanes.forEach(pane => pane.classList.remove('active'));
            
            // Ajouter active au bouton et pane cliqué
            this.classList.add('active');
            const targetPane = document.getElementById(tabName);
            console.log('Target pane:', targetPane ? 'Found' : 'Not found');
            if (targetPane) {
                targetPane.classList.add('active');
            }
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
    const monitoredFilter = sessionStorage.getItem('monitoredFilter') || 'all';
    
    let filtered = currentSeriesData;
    
    // Filtre par recherche
    if (searchTerm) {
        filtered = filtered.filter(s => 
            s.title.toLowerCase().includes(searchTerm)
        );
    }
    
    // Filtre par statut (manquant/complète)
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
    
    // Filtre par statut monitored
    if (monitoredFilter === 'monitored') {
        filtered = filtered.filter(s => s.enabled !== 0);
    } else if (monitoredFilter === 'not-monitored') {
        filtered = filtered.filter(s => s.enabled === 0);
    }
    
    displaySeriesGrid(filtered);
}

function filterByMonitoredStatus(status) {
    sessionStorage.setItem('monitoredFilter', status);
    
    // Mettre à jour les styles des boutons
    document.getElementById('filter-all-series')?.classList.remove('active');
    document.getElementById('filter-monitored')?.classList.remove('active');
    document.getElementById('filter-not-monitored')?.classList.remove('active');
    
    if (status === 'monitored') {
        document.getElementById('filter-monitored')?.classList.add('active');
    } else if (status === 'not-monitored') {
        document.getElementById('filter-not-monitored')?.classList.add('active');
    } else {
        document.getElementById('filter-all-series')?.classList.add('active');
    }
    
    filterSeries();
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
    
    const autoDownload = true; // Activé par défaut
    
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
    const noResults = document.getElementById('no-search-yet');
    
    if (!results || results.length === 0) {
        section.style.display = 'none';
        if (noResults) noResults.style.display = 'block';
        showToast('Aucun résultat trouvé', 'info');
        return;
    }
    
    if (noResults) noResults.style.display = 'none';
    section.style.display = 'block';
    
    // Charger la configuration pour respecter l'ordre des sources
    fetch('/api/missing-monitor/config')
        .then(r => r.json())
        .then(config => {
            // Déterminer l'ordre des sources à partir de la requête
            // Pour maintenant, on teste les deux configurations possibles
            let sources = [];
            
            // Essayer de déterminer quelle configuration a été utilisée
            const hasEBDZ = results.some(r => r.source === 'ebdz');
            const hasProwlarr = results.some(r => r.source === 'prowlarr');
            
            if (hasEBDZ && hasProwlarr) {
                // Sa vient de search_for_volume qui utilise la config manquant_volume ou new_volume
                // On va supposer que c'est missing_volume par défaut
                sources = config.monitor_missing_volumes?.search_sources || ['ebdz', 'prowlarr'];
            } else if (hasProwlarr) {
                sources = config.monitor_missing_volumes?.search_sources || ['ebdz', 'prowlarr'];
            } else {
                sources = config.monitor_missing_volumes?.search_sources || ['ebdz', 'prowlarr'];
            }
            
            // Trier les résultats par l'ordre des sources
            const sortedResults = results.sort((a, b) => {
                const indexA = sources.indexOf(a.source);
                const indexB = sources.indexOf(b.source);
                return indexA - indexB;
            });
            
            displaySortedResults(sortedResults);
        })
        .catch(() => {
            // En cas d'erreur, afficher simplement en groupant par source
            displaySortedResults(results);
        });
    
    // Vérifier le statut aMule pour afficher/cacher les boutons
    checkEmuleStatus();
}

function displaySortedResults(results) {
    const container = document.getElementById('search-results');
    
    // Grouper par source
    const grouped = {};
    results.forEach(result => {
        const source = result.source || 'autre';
        if (!grouped[source]) {
            grouped[source] = [];
        }
        grouped[source].push(result);
    });
    
    // Ordre de priorité standard
    const sourceOrder = ['ebdz', 'prowlarr'];
    
    let html = '';
    
    // Afficher en ordre de priorité
    sourceOrder.forEach(source => {
        if (!grouped[source] || grouped[source].length === 0) return;
        
        const sourceResults = grouped[source];
        const sourceTitle = source.toUpperCase();
        const sourceBadge = source === 'ebdz' ? '📦 EBDZ' : '⚡ PROWLARR';
        
        html += `<div style="margin-bottom: 20px;">
                    <h4 style="margin: 0 0 10px 0; padding: 10px; background: ${source === 'ebdz' ? '#e3f2fd' : '#fff3e0'}; border-radius: 5px; color: ${source === 'ebdz' ? '#1976d2' : '#ff9800'};">
                        ${sourceBadge}
                    </h4>`;
        
        sourceResults.forEach((result, index) => {
            const seeders = result.seeders ? `👥 ${result.seeders} seeders` : '';
            const size = result.size ? `${(result.size / 1073741824).toFixed(2)} GB` : '';
            
            // Différencier les boutons selon le type de lien
            let actionButtons = '';
            
            if (result.source === 'ebdz') {
                // Pour ED2K, utiliser aMule
                actionButtons = `
                    <button class="btn btn-primary" onclick="addToEmule('${escapeHtml(result.link)}', this)" style="background: #8b5cf6;">
                        ⬇️ Ajouter à aMule
                    </button>
                `;
            } else if (result.source === 'prowlarr') {
                // Pour Prowlarr, utiliser qBittorrent
                actionButtons = `
                    <a href="${result.link}" target="_blank" class="btn btn-primary" style="text-decoration: none; background: #28a745;">
                        📥 Télécharger torrent
                    </a>
                    <button class="btn btn-primary" onclick="addTorrentToQbittorrent('${escapeHtml(result.link)}', this)" style="background: #f5576c;">
                        ⚡ qBittorrent
                    </button>
                `;
            }
            
            html += `
                <div class="result-item">
                    <div class="result-title">
                        ${escapeHtml(result.title)}
                    </div>
                    <div class="result-meta">
                        ${result.indexer ? `<span>${result.indexer}</span>` : ''}
                        ${seeders ? `<span>${seeders}</span>` : ''}
                        ${size ? `<span>💾 ${size}</span>` : ''}
                    </div>
                    <div class="result-actions">
                        ${actionButtons}
                    </div>
                </div>
            `;
        });
        
        html += '</div>';
    });
    
    // Afficher les autres sources si elles existent
    Object.keys(grouped).forEach(source => {
        if (!sourceOrder.includes(source)) {
            html += `<h4>${source.toUpperCase()}</h4>`;
            grouped[source].forEach(result => {
                html += `<div class="result-item">${escapeHtml(result.title)}</div>`;
            });
        }
    });
    
    const container_el = document.getElementById('search-results');
    if (container_el) {
        container_el.innerHTML = html;
    }
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
        
        // Vérifications de sécurité avant d'accéder aux éléments
        const configEnabled = document.getElementById('config-enabled');
        const configAutoCheck = document.getElementById('config-auto-check');
        const configInterval = document.getElementById('config-interval');
        const configIntervalUnit = document.getElementById('config-interval-unit');
        const configClient = document.getElementById('config-client');
        const configMonitorMissing = document.getElementById('config-monitor-missing');
        const configMissingSearch = document.getElementById('config-missing-search');
        const configMissingAutoDownload = document.getElementById('config-missing-auto-download');
        const configMonitorNew = document.getElementById('config-monitor-new');
        const configNewSearch = document.getElementById('config-new-search');
        const configNewAutoDownload = document.getElementById('config-new-auto-download');
        const configNautiljonCheck = document.getElementById('config-nautiljon-check');
        
        // Configuration générale
        if (configEnabled) configEnabled.checked = config.enabled || false;
        if (configAutoCheck) configAutoCheck.checked = config.auto_check_enabled || false;
        if (configInterval) configInterval.value = config.auto_check_interval || 60;
        if (configIntervalUnit) configIntervalUnit.value = config.auto_check_interval_unit || 'minutes';
        if (configClient) configClient.value = config.preferred_client || 'qbittorrent';
        
        // Cocher les sources
        (config.search_sources || ['ebdz', 'prowlarr']).forEach(source => {
            const el = document.querySelector(`input[name="source"][value="${source}"]`);
            if (el) el.checked = true;
        });

        // Configuration des volumes manquants
        const missingVolumeConfig = config.monitor_missing_volumes || {};
        if (configMonitorMissing) configMonitorMissing.checked = missingVolumeConfig.enabled !== false;
        if (configMissingSearch) configMissingSearch.checked = missingVolumeConfig.search_enabled !== false;
        if (configMissingAutoDownload) configMissingAutoDownload.checked = missingVolumeConfig.auto_download_enabled || false;

        // Configuration des nouveaux volumes
        const newVolumeConfig = config.monitor_new_volumes || {};
        if (configMonitorNew) configMonitorNew.checked = newVolumeConfig.enabled || false;
        if (configNewSearch) configNewSearch.checked = newVolumeConfig.search_enabled !== false;
        if (configNewAutoDownload) configNewAutoDownload.checked = newVolumeConfig.auto_download_enabled || false;
        if (configNautiljonCheck) configNautiljonCheck.checked = newVolumeConfig.check_nautiljon_updates !== false;

        // Mettre à jour l'affichage des sections
        updateAutoCheckUI();
        updateNewVolumesUI();
    } catch (error) {
        console.error('Erreur chargement config:', error);
    }
}

function updateAutoCheckUI() {
    const enabled = document.getElementById('config-auto-check');
    const settings = document.getElementById('auto-check-settings');
    if (enabled && settings) {
        settings.style.display = enabled.checked ? 'block' : 'none';
    }
}

function updateNewVolumesUI() {
    const enabled = document.getElementById('config-monitor-new');
    const settings = document.getElementById('new-volumes-settings');
    if (enabled && settings) {
        settings.style.display = enabled.checked ? 'block' : 'none';
    }
}

async function saveConfig() {
    try {
        const sources = Array.from(document.querySelectorAll('input[name="source"]:checked'))
            .map(el => el.value);
        
        const configEnabled = document.getElementById('config-enabled');
        const configAutoCheck = document.getElementById('config-auto-check');
        const configInterval = document.getElementById('config-interval');
        const configIntervalUnit = document.getElementById('config-interval-unit');
        const configClient = document.getElementById('config-client');
        const configMonitorMissing = document.getElementById('config-monitor-missing');
        const configMissingSearch = document.getElementById('config-missing-search');
        const configMissingAutoDownload = document.getElementById('config-missing-auto-download');
        const configMonitorNew = document.getElementById('config-monitor-new');
        const configNewSearch = document.getElementById('config-new-search');
        const configNewAutoDownload = document.getElementById('config-new-auto-download');
        const configNautiljonCheck = document.getElementById('config-nautiljon-check');

        const config = {
            enabled: configEnabled?.checked || false,
            auto_check_enabled: configAutoCheck?.checked || false,
            auto_check_interval: parseInt(configInterval?.value) || 60,
            auto_check_interval_unit: configIntervalUnit?.value || 'minutes',
            search_sources: sources,
            preferred_client: configClient?.value || 'qbittorrent',
            monitor_missing_volumes: {
                enabled: configMonitorMissing?.checked !== false,
                search_enabled: configMissingSearch?.checked !== false,
                auto_download_enabled: configMissingAutoDownload?.checked || false
            },
            monitor_new_volumes: {
                enabled: configMonitorNew?.checked || false,
                search_enabled: configNewSearch?.checked !== false,
                auto_download_enabled: configNewAutoDownload?.checked || false,
                check_nautiljon_updates: configNautiljonCheck?.checked !== false
            }
        };
        
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

// ========== DOWNLOAD FUNCTIONS ==========

async function addToEmule(link, button) {
    const originalText = button.textContent;
    button.textContent = '⏳ Envoi...';
    button.disabled = true;

    try {
        const response = await fetch('/api/emule/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({link: link})
        });

        const data = await response.json();
        
        if (data.success) {
            button.textContent = '✓ Ajouté!';
            button.style.background = '#28a745';
            showToast('Lien ajouté à aMule', 'success');
            setTimeout(() => {
                button.textContent = originalText;
                button.disabled = false;
                button.style.background = '';
            }, 3000);
        } else {
            throw new Error(data.error || 'Erreur inconnue');
        }
    } catch (error) {
        button.textContent = '✗ Erreur';
        button.style.background = '#dc3545';
        showToast('Erreur: ' + error.message, 'error');
        setTimeout(() => {
            button.textContent = originalText;
            button.disabled = false;
            button.style.background = '';
        }, 3000);
    }
}

async function addTorrentToQbittorrent(torrentUrl, button) {
    const originalText = button.textContent;
    button.textContent = '⏳ Envoi...';
    button.disabled = true;

    try {
        // Charger la config pour obtenir la catégorie par défaut
        const configResponse = await fetch('/api/qbittorrent/config');
        const config = await configResponse.json();
        
        const payload = {
            torrent_url: torrentUrl
        };
        
        // Ajouter la catégorie par défaut si elle est configurée
        if (config.default_category) {
            payload.category = config.default_category;
        }
        
        const response = await fetch('/api/qbittorrent/add', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(payload)
        });

        const data = await response.json();
        
        if (data.success) {
            button.textContent = '✓ Ajouté!';
            button.style.background = '#10b981';
            showToast('Torrent ajouté à qBittorrent', 'success');
            setTimeout(() => {
                button.textContent = originalText;
                button.disabled = false;
                button.style.background = '';
            }, 3000);
        } else {
            throw new Error(data.error || 'Erreur inconnue');
        }
    } catch (error) {
        button.textContent = '✗ Erreur';
        button.style.background = '#dc3545';
        showToast('Erreur: ' + error.message, 'error');
        setTimeout(() => {
            button.textContent = originalText;
            button.disabled = false;
            button.style.background = '';
        }, 3000);
    }
}

async function checkEmuleStatus() {
    try {
        const response = await fetch('/api/emule/config');
        const config = await response.json();
        
        const addButtons = document.querySelectorAll('button[onclick*="addToEmule"]');
        addButtons.forEach(button => {
            button.style.display = config.enabled ? 'inline-block' : 'none';
        });
    } catch (error) {
        console.error('Erreur lors de la vérification du statut aMule:', error);
    }
}

// ========== UTILITIES ==========

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
