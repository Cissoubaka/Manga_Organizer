/**
 * Script pour la page de découverte et d'ajout de séries
 */

// État global
let currentState = {
    selectedSeries: null,
    selectedLibrary: null,
    libraries: []
};

// ============================================
// ÉTAPE 1: Recherche sur Nautiljon
// ============================================

async function searchNautiljon() {
    const seriesName = document.getElementById('seriesNameInput').value.trim();
    
    if (!seriesName) {
        showError('step-1', 'Veuillez entrer un nom de série');
        return;
    }

    showLoading('step-1', true);
    hideError('step-1');
    hideElement('nautiljon-results');

    try {
        const response = await fetch(`/api/nautiljon/search?q=${encodeURIComponent(seriesName)}`);
        const data = await response.json();

        if (!data.success) {
            showError('step-1', data.error || 'Erreur lors de la recherche');
            return;
        }

        const results = data.results || [];
        
        if (results.length === 0) {
            showError('step-1', 'Aucune série trouvée. Essayez d\'autres mots-clés.');
            return;
        }

        displayNautiljonResults(results);
        showElement('nautiljon-results');

    } catch (error) {
        console.error('Erreur:', error);
        showError('step-1', 'Erreur lors de la recherche: ' + error.message);
    } finally {
        showLoading('step-1', false);
    }
}

function displayNautiljonResults(results) {
    const resultsList = document.getElementById('results-list');
    const resultsCount = document.getElementById('results-count');
    
    resultsList.innerHTML = '';
    resultsCount.textContent = results.length;

    results.forEach(result => {
        const div = document.createElement('div');
        div.className = 'result-item';
        div.innerHTML = `
            <p class="result-title">${escapeHtml(result.title)}</p>
            <p class="result-url">${escapeHtml(result.url)}</p>
            <div class="result-actions">
                <button class="btn-select" onclick="selectSeries('${escapeAttr(result.url)}', '${escapeAttr(result.title)}')">
                    ✓ Sélectionner
                </button>
            </div>
        `;
        resultsList.appendChild(div);
    });
}

function selectSeries(url, title) {
    currentState.selectedSeries = {
        title: title,
        url: url
    };

    // Afficher l'étape 2
    hideElement('step-1');
    showElement('step-2');
    loadLibraries();
    displaySelectedSeries();
}

function displaySelectedSeries() {
    const display = document.getElementById('selected-series-display');
    if (currentState.selectedSeries) {
        display.innerHTML = `
            <div style="display: flex; flex-direction: column; gap: 10px;">
                <p class="series-title">${escapeHtml(currentState.selectedSeries.title)}</p>
                <a href="${escapeAttr(currentState.selectedSeries.url)}" target="_blank" class="series-link">
                    🔗 Voir sur Nautiljon
                </a>
            </div>
        `;
    }
}

function resetToStep1() {
    currentState.selectedSeries = null;
    currentState.selectedLibrary = null;
    
    // Nettoyer les erreurs et loadings
    hideError('step-1');
    hideError('step-2');
    hideError('step-3');
    const verificationLoading = document.getElementById('series-verification-loading');
    if (verificationLoading) {
        verificationLoading.style.display = 'none';
    }
    
    showElement('step-1');
    hideElement('step-2');
    hideElement('step-3');
    
    document.getElementById('seriesNameInput').focus();
}

// ============================================
// ÉTAPE 2: Sélection de la bibliothèque
// ============================================

async function loadLibraries() {
    showLoading('step-2', true);
    hideError('step-2');

    try {
        const response = await fetch('/api/libraries');
        const libraries = await response.json();
        
        currentState.libraries = libraries;
        displayLibraries(libraries);

    } catch (error) {
        console.error('Erreur:', error);
        showError('step-2', 'Erreur lors du chargement des bibliothèques');
    } finally {
        showLoading('step-2', false);
    }
}

function displayLibraries(libraries) {
    const list = document.getElementById('libraries-list');
    list.innerHTML = '';

    if (libraries.length === 0) {
        list.innerHTML = '<p style="text-align: center; color: #9ca3af;">Aucune bibliothèque trouvée</p>';
        return;
    }

    libraries.forEach(lib => {
        const div = document.createElement('div');
        div.className = 'library-item';
        div.onclick = () => selectLibrary(lib.id, lib, div);
        
        div.innerHTML = `
            <p class="library-name">${escapeHtml(lib.name)}</p>
            <p class="library-path">📂 ${escapeHtml(lib.path)}</p>
            <div class="library-stats">
                <span>📖 ${lib.series_count} série(s)</span>
                <span>📕 ${lib.volumes_count} volume(s)</span>
            </div>
        `;
        list.appendChild(div);
    });
}

function selectLibrary(libraryId, libraryData, element) {
    currentState.selectedLibrary = {
        id: libraryId,
        ...libraryData
    };

    // Mettre à jour la sélection visuelle
    document.querySelectorAll('.library-item').forEach(el => {
        el.classList.remove('selected');
    });
    
    if (element) {
        element.classList.add('selected');
    }

    // Créer le répertoire de la série
    createSeriesDirectory();
}

function createSeriesDirectory() {
    const libraryId = currentState.selectedLibrary.id;
    const seriesName = currentState.selectedSeries.title;
    
    // Afficher un message de chargement
    const verificationLoading = document.getElementById('series-verification-loading');
    if (verificationLoading) {
        verificationLoading.style.display = 'block';
    }
    
    fetch(`/api/libraries/${libraryId}/create-series`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        },
        body: JSON.stringify({
            series_name: seriesName
        })
    })
    .then(response => response.json())
    .then(data => {
        // Cacher le message de chargement
        if (verificationLoading) {
            verificationLoading.style.display = 'none';
        }
        
        if (data.success) {
            // Vérifier si la série existe déjà
            if (data.exists) {
                // Afficher un avertissement avec détails
                let warningMessage = '⚠️ La série existe déjà !\n\n';
                
                if (data.series_exists_in_db) {
                    warningMessage += '📚 La série est déjà enregistrée dans la base de données\n';
                }
                
                if (data.directory_exists) {
                    warningMessage += '📁 Le répertoire existe déjà sur le disque\n';
                }
                
                warningMessage += '\nContinuer quand même ?';
                
                if (confirm(warningMessage)) {
                    // L'utilisateur a confirmé, continuer vers l'étape 3
                    hideElement('step-2');
                    showElement('step-3');
                    displaySourceSelection();
                }
            } else {
                // Répertoire créé avec succès
                hideElement('step-2');
                showElement('step-3');
                displaySourceSelection();
            }
        } else {
            // Erreur lors de la création/vérification
            showError('step-2', 'Erreur lors de la vérification de la série : ' + (data.error || 'Erreur inconnue'));
        }
    })
    .catch(error => {
        console.error('Erreur:', error);
        // Cacher le message de chargement
        if (verificationLoading) {
            verificationLoading.style.display = 'none';
        }
        showError('step-2', 'Erreur lors de la vérification de la série : ' + error.message);
    });
}

function displaySourceSelection() {
    const summary = document.getElementById('selection-summary');
    
    if (currentState.selectedSeries && currentState.selectedLibrary) {
        summary.innerHTML = `
            <div class="summary-item">
                <div class="summary-label">📖 Série</div>
                <div class="summary-value">${escapeHtml(currentState.selectedSeries.title)}</div>
            </div>
            <div class="summary-item">
                <div class="summary-label">📚 Bibliothèque</div>
                <div class="summary-value">${escapeHtml(currentState.selectedLibrary.name)}</div>
            </div>
        `;
    }
}

function resetToStep2() {
    currentState.selectedLibrary = null;
    
    // Cacher les messages d'erreur et chargement de l'étape 2
    const verificationLoading = document.getElementById('series-verification-loading');
    if (verificationLoading) {
        verificationLoading.style.display = 'none';
    }
    hideError('step-2');
    
    showElement('step-2');
    hideElement('step-3');
    
    // Riche afficher la série sélectionnée avec le lien
    displaySelectedSeries();
    
    // Retirer la sélection visuelle
    document.querySelectorAll('.library-item').forEach(el => {
        el.classList.remove('selected');
    });
}

// ============================================
// ÉTAPE 3: Recherche dans les sources
// ============================================

async function searchSources() {
    if (!currentState.selectedSeries) {
        showError('step-3', 'Pas de série sélectionnée');
        return;
    }

    const searchEbdz = document.getElementById('search-ebdz').checked;
    const searchProwlarr = document.getElementById('search-prowlarr').checked;
    const volumeOverride = document.getElementById('volume-override').value;

    if (!searchEbdz && !searchProwlarr) {
        showError('step-3', 'Sélectionnez au moins une source');
        return;
    }

    showLoading('step-3', true);
    hideError('step-3');
    hideElement('sources-results');

    try {
        const seriesTitle = currentState.selectedSeries.title;
        let hasResults = false;

        // Rechercher sur EBDZ
        if (searchEbdz) {
            const ebdzResults = await searchEbdzSources(seriesTitle, volumeOverride);
            if (ebdzResults && ebdzResults.length > 0) {
                displayEbdzResults(ebdzResults);
                showElement('ebdz-results');
                hasResults = true;
            }
        }

        // Rechercher sur Prowlarr
        if (searchProwlarr) {
            const prowlarrResults = await searchProwlarrSources(seriesTitle, volumeOverride);
            if (prowlarrResults && prowlarrResults.length > 0) {
                displayProwlarrResults(prowlarrResults);
                showElement('prowlarr-results');
                hasResults = true;
            }
        }

        if (hasResults) {
            showElement('sources-results');
        } else {
            showError('step-3', 'Aucun résultat trouvé dans les sources');
        }

    } catch (error) {
        console.error('Erreur:', error);
        showError('step-3', 'Erreur lors de la recherche: ' + error.message);
    } finally {
        showLoading('step-3', false);
    }
}

async function searchEbdzSources(title, volume) {
    try {
        let url = `/api/search/ebdz?q=${encodeURIComponent(title)}`;
        if (volume) {
            url += `&volume=${encodeURIComponent(volume)}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.success) {
            return data.results || [];
        }
        return [];

    } catch (error) {
        console.error('Erreur EBDZ:', error);
        return [];
    }
}

async function searchProwlarrSources(title, volume) {
    try {
        let url = `/api/search/prowlarr?q=${encodeURIComponent(title)}`;
        if (volume) {
            url += `&volume=${encodeURIComponent(volume)}`;
        }
        
        const response = await fetch(url);
        const data = await response.json();
        
        if (data.success) {
            return data.results || [];
        }
        return [];

    } catch (error) {
        console.error('Erreur Prowlarr:', error);
        return [];
    }
}

function displayEbdzResults(results) {
    const list = document.getElementById('ebdz-list');
    list.innerHTML = '';

    results.forEach((result, index) => {
        const div = document.createElement('div');
        div.className = 'ebdz-result-item';
        
        let metaHtml = '';
        if (result.forum) metaHtml += `<span>📂 ${escapeHtml(result.forum)}</span>`;
        if (result.size) metaHtml += `<span>📦 ${formatFileSize(parseInt(result.size))}</span>`;
        if (result.volume !== undefined && result.volume !== null) metaHtml += `<span>📕 Vol. ${result.volume}</span>`;
        
        div.innerHTML = `
            <div class="result-name">${escapeHtml(result.title || result.name)}</div>
            <div class="result-meta">${metaHtml}</div>
            ${result.filename ? `<div class="result-meta"><small>📄 ${escapeHtml(result.filename)}</small></div>` : ''}
            <div class="result-actions">
                <button class="btn-download btn-download-ed2k" onclick="addToEmule('${escapeHtml(result.ed2k_link || '').replace(/'/g, "\\'")}', this)" id="ebdz-btn-${index}">
                    ⬇️ Ajouter à eMule
                </button>
            </div>
        `;
        list.appendChild(div);
    });
}

function displayProwlarrResults(results) {
    const list = document.getElementById('prowlarr-list');
    list.innerHTML = '';

    results.forEach((result, index) => {
        const div = document.createElement('div');
        div.className = 'prowlarr-result-item';
        
        let metaHtml = '';
        if (result.indexer) metaHtml += `<span>🔗 ${escapeHtml(result.indexer)}</span>`;
        if (result.seeders !== undefined) metaHtml += `<span>👥 ${result.seeders} seeds</span>`;
        if (result.leechers !== undefined) metaHtml += `<span>👤 ${result.leechers} peers</span>`;
        if (result.size) metaHtml += `<span>📦 ${formatFileSize(result.size)}</span>`;

        const downloadUrl = escapeHtml(result.download_url || result.link || '');
        
        div.innerHTML = `
            <div class="result-name">${escapeHtml(result.title)}</div>
            <div class="result-meta">${metaHtml}</div>
            <div class="result-actions">
                ${downloadUrl ? `
                    <button class="btn-download btn-download-torrent" onclick="addTorrentToQbittorrent('${downloadUrl.replace(/'/g, "\\'")}', this)" id="prowlarr-btn-${index}">
                        ⚡ Ajouter à qBittorrent
                    </button>
                ` : ''}
            </div>
        `;
        list.appendChild(div);
    });
}

// ============================================
// Utilitaires d'interface
// ============================================

function showLoading(stepNum, show) {
    let loadingId;
    if (stepNum === 'step-1' || stepNum === 1) {
        loadingId = 'nautiljon-loading';
    } else if (stepNum === 'step-2' || stepNum === 2) {
        loadingId = 'library-loading';
    } else if (stepNum === 'step-3' || stepNum === 3) {
        loadingId = 'sources-loading';
    }
    
    if (loadingId) {
        const el = document.getElementById(loadingId);
        if (el) {
            el.style.display = show ? 'block' : 'none';
        }
    }
}

function showError(step, message) {
    let errorId;
    if (step === 'step-1' || step === 1) {
        errorId = 'nautiljon-error';
    } else if (step === 'step-2' || step === 2) {
        errorId = 'library-error';
    } else if (step === 'step-3' || step === 3) {
        errorId = 'sources-error';
    }
    
    if (errorId) {
        const el = document.getElementById(errorId);
        if (el) {
            el.textContent = '❌ ' + message;
            el.style.display = 'block';
        }
    }
}

function hideError(step) {
    let errorId;
    if (step === 'step-1' || step === 1) {
        errorId = 'nautiljon-error';
    } else if (step === 'step-2' || step === 2) {
        errorId = 'library-error';
    } else if (step === 'step-3' || step === 3) {
        errorId = 'sources-error';
    }
    
    if (errorId) {
        const el = document.getElementById(errorId);
        if (el) {
            el.style.display = 'none';
        }
    }
}

function showElement(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'block';
}

function hideElement(id) {
    const el = document.getElementById(id);
    if (el) el.style.display = 'none';
}

function escapeHtml(text) {
    if (!text) return '';
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return text.replace(/[&<>"']/g, m => map[m]);
}

function escapeAttr(text) {
    if (!text) return '';
    return text.replace(/'/g, "\\'").replace(/"/g, '\\"');
}

function formatFileSize(bytes) {
    if (!bytes) return '?';
    const units = ['B', 'KB', 'MB', 'GB'];
    let size = bytes;
    let unitIndex = 0;
    while (size >= 1024 && unitIndex < units.length - 1) {
        size /= 1024;
        unitIndex++;
    }
    return size.toFixed(2) + ' ' + units[unitIndex];
}


