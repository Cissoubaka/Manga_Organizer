//const libraryId = {{ library_id }};
let seriesData = [];
let showOnlyMissing = false;
let showOnlyUnenriched = false;
let seriesStatusFilter = 'all'; // 'all', 'completed', 'ongoing'
let currentSeriesTitle = '';

async function loadLibraryInfo() {
    try {
        const response = await fetch(`/api/libraries/${libraryId}`);
        const library = await response.json();
        
        document.getElementById('library-title').textContent = `📚 ${library.name}`;
        document.getElementById('library-path').textContent = library.path;
    } catch (error) {
        console.error('Erreur chargement bibliothèque:', error);
    }
}

async function loadLibraryData() {
    const grid = document.getElementById('series-grid');
    grid.innerHTML = '<div class="loading"><div class="spinner"></div><p>Chargement des données...</p></div>';

    try {
        const [seriesResponse, statsResponse] = await Promise.all([
            fetch(`/api/library/${libraryId}/series`),
            fetch(`/api/library/${libraryId}/stats`)
        ]);

        const series = await seriesResponse.json();
        const stats = await statsResponse.json();

        seriesData = series;
        updateStats(stats);
        displaySeries(series);
    } catch (error) {
        grid.innerHTML = `<div class="no-data"><h3>Erreur de chargement</h3><p>${error.message}</p></div>`;
    }
}

function updateStats(stats) {
    document.getElementById('series-count').textContent = stats.total_series;
    document.getElementById('volumes-count').textContent = stats.total_volumes;
    document.getElementById('total-size').textContent = formatBytes(stats.total_size);
    document.getElementById('avg-pages').textContent = stats.avg_pages;
}

function displaySeries(series) {
    const grid = document.getElementById('series-grid');
    
    if (series.length === 0) {
        grid.innerHTML = '<div class="no-data"><span class="no-data-icon">📚</span><h3>Aucune série trouvée</h3><p>Scannez votre bibliothèque pour commencer</p></div>';
        return;
    }

    grid.innerHTML = series.map(s => {
        // Calculer le badge en fonction de la logique complexe
        const badge = calculateSeriesBadge(s);
        
        return `
        <div class="series-card" onclick="viewSeries(${s.id})">
            <div style="display: flex; justify-content: space-between; align-items: flex-start; gap: 10px;">
                <div class="series-title">${escapeHtml(s.title)}</div>
                ${badge}
            </div>
            ${s.nautiljon_total_volumes ? `
                <div class="series-info" style="color: #667eea; font-weight: 500;">
                    🌊 ${s.nautiljon_total_volumes} volumes (Nautiljon)
                </div>
            ` : ''}
            <div class="series-info">📖 ${s.total_volumes} volume(s) local</div>
            <div class="series-info">📅 Dernier scan: ${new Date(s.last_scanned).toLocaleDateString('fr-FR')}</div>
            ${s.missing_volumes.length > 0 ? 
                `<div class="missing-volumes">⚠️ Volumes manquants: ${s.missing_volumes.join(', ')}</div>` :
                `<div class="complete">✅ Collection complète</div>`
            }
        </div>
    `;
    }).join('');
}

// Fonction pour calculer le badge d'une série
function calculateSeriesBadge(series) {
    // Récupérer les couleurs depuis le localStorage ou utiliser les défauts
    const colors = JSON.parse(localStorage.getItem('badgeColors')) || {
        complete: '#10b981',    // vert
        ongoing: '#ef4444',     // rouge
        incomplete: '#f59e0b',  // orange
        missing: '#3b82f6'      // bleu
    };
    
    const hasNautiljonInfo = series.nautiljon_total_volumes;
    const hasMissingVolumes = series.missing_volumes && series.missing_volumes.length > 0;
    const isNautiljonComplete = series.nautiljon_status && (
        series.nautiljon_status.toLowerCase().includes('terminé') || 
        series.nautiljon_status.toLowerCase().includes('termin')
    );
    
    // Logique des badges
    // 1. "Finie" : volumes locaux = volumes Nautiljon
    if (hasNautiljonInfo && series.total_volumes === series.nautiljon_total_volumes && !hasMissingVolumes) {
        return `<span class="series-badge" style="background: ${colors.complete}; color: white;">✅ Finie</span>`;
    }
    
    // 2. "Manquant" : série terminée sur Nautiljon ET volumes manquants
    if (isNautiljonComplete && hasMissingVolumes) {
        return `<span class="series-badge" style="background: ${colors.missing}; color: white;">📚 Manquant</span>`;
    }
    
    // 3. "Incomplet" : volumes manquants ET série pas terminée sur Nautiljon
    if (hasMissingVolumes && !isNautiljonComplete) {
        return `<span class="series-badge" style="background: ${colors.incomplete}; color: white;">⚠️ Incomplet</span>`;
    }
    
    // 4. "En cours" : volumes ne correspondent pas
    if (hasNautiljonInfo && series.total_volumes !== series.nautiljon_total_volumes) {
        return `<span class="series-badge" style="background: ${colors.ongoing}; color: white;">🔄 En cours</span>`;
    }
    
    // Pas de badge si pas d'info Nautiljon
    return '';
}

function filterSeries() {
    const searchTerm = document.getElementById('search').value.toLowerCase();
    let filtered = seriesData.filter(s => 
        s.title.toLowerCase().includes(searchTerm)
    );
    
    if (showOnlyMissing) {
        filtered = filtered.filter(s => s.missing_volumes.length > 0);
    }
    
    if (showOnlyUnenriched) {
        filtered = filtered.filter(s => !s.nautiljon_url);
    }
    
    if (seriesStatusFilter === 'completed') {
        filtered = filtered.filter(s => 
            s.nautiljon_status && 
            (s.nautiljon_status.toLowerCase().includes('terminé') || s.nautiljon_status.toLowerCase().includes('termin'))
        );
    } else if (seriesStatusFilter === 'ongoing') {
        filtered = filtered.filter(s => 
            s.nautiljon_status && 
            s.nautiljon_status.toLowerCase().includes('cours')
        );
    }
    
    displaySeries(filtered);
}

function toggleStatusFilter() {
    const btn = document.getElementById('filter-status-btn');
    
    if (seriesStatusFilter === 'all') {
        seriesStatusFilter = 'completed';
        btn.textContent = '✅ Séries terminées uniquement';
        btn.style.background = '#10b981';
    } else if (seriesStatusFilter === 'completed') {
        seriesStatusFilter = 'ongoing';
        btn.textContent = '📖 Séries en cours uniquement';
        btn.style.background = '#f59e0b';
    } else {
        seriesStatusFilter = 'all';
        btn.textContent = '📚 Toutes les séries';
        btn.style.background = '#667eea';
    }
    
    filterSeries();
}

function toggleMissingFilter() {
    showOnlyMissing = !showOnlyMissing;
    const btn = document.getElementById('filter-btn');
    
    if (showOnlyMissing) {
        btn.textContent = '✅ Afficher toutes les séries';
        btn.style.background = '#10b981';
    } else {
        btn.textContent = '⚠️ Volumes manquants uniquement';
        btn.style.background = '#667eea';
    }
    
    filterSeries();
}

function toggleUnenrichedFilter() {
    showOnlyUnenriched = !showOnlyUnenriched;
    const btn = document.getElementById('filter-unenriched-btn');
    
    if (showOnlyUnenriched) {
        btn.textContent = '✅ Afficher toutes les séries';
        btn.style.background = '#10b981';
    } else {
        btn.textContent = '🔍 Séries non enrichies';
        btn.style.background = '#667eea';
    }
    
    filterSeries();
}

async function scanLibrary() {
    const button = event.target;
    button.disabled = true;
    button.textContent = '⏳ Scan en cours...';

    try {
        const response = await fetch(`/api/scan/${libraryId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ Scan terminé !\n${data.series_count} séries trouvées.\n\n💡 Utilisez le bouton "Enrichir la bibliothèque" pour récupérer les infos Nautiljon`);
            await loadLibraryData();
            await loadLibraryData();
        } else {
            alert('❌ Erreur: ' + (data.error || 'Erreur inconnue'));
        }
    } catch (error) {
        alert('❌ Erreur de connexion: ' + error.message);
    } finally {
        button.disabled = false;
        button.textContent = '🔄 Scanner la bibliothèque';
    }
}

async function scanSeries(seriesId) {
    try {
        const response = await fetch(`/api/scan/series/${seriesId}`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ Scan de la série terminé !\n${data.volumes_count} volume(s) détecté(s).`);
            // Recharger les détails de la série
            const seriesData = await fetch(`/api/series/${seriesId}`);
            if (seriesData.ok) {
                closeModal();
                // Recharger la page pour voir les changements
                await loadLibraryData();
            }
        } else {
            alert('❌ Erreur: ' + (data.error || 'Erreur inconnue'));
        }
    } catch (error) {
        alert('❌ Erreur de connexion: ' + error.message);
    }
}

async function enrichAllSeries() {
    if (!confirm('Enrichir toutes les séries sans infos Nautiljon?\n\nCette opération peut prendre du temps...')) {
        return;
    }
    
    const button = event.target;
    button.disabled = true;
    button.textContent = '⏳ Enrichissement en cours...';

    try {
        const response = await fetch(`/api/library/${libraryId}/enrich`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ Enrichissement terminé!\n${data.enriched_count} séries enrichies\n${data.failed_count} non trouvées`);
            await loadLibraryData();
        } else {
            alert('❌ Erreur: ' + (data.error || 'Erreur inconnue'));
        }
    } catch (error) {
        alert('❌ Erreur de connexion: ' + error.message);
    } finally {
        button.disabled = false;
        button.textContent = '✨ Enrichir la bibliothèque';
    }
}

async function viewSeries(seriesId) {
    const modal = document.getElementById('series-modal');
    const modalBody = document.getElementById('modal-body');
    
    modal.classList.add('active');
    modalBody.innerHTML = '<div class="loading"><div class="spinner"></div><p>Chargement des détails...</p></div>';

    try {
        const response = await fetch(`/api/series/${seriesId}`);
        
        if (!response.ok) {
            const text = await response.text();
            throw new Error(`Erreur serveur ${response.status}: ${text.substring(0, 200)}`);
        }
        
        const data = await response.json();
        
        console.log('Données reçues:', data);
        
        // Sauvegarder le titre de la série pour la recherche
        currentSeriesTitle = data.title;

        // ===== SECTION NAUTILJON =====
        let nautiljonHtml = '';
        if (data.nautiljon && data.nautiljon.url) {
            nautiljonHtml = `
                <div style="background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 20px; border-radius: 8px; margin-bottom: 20px;">
                    <div style="display: flex; justify-content: space-between; align-items: start; gap: 20px;">
                        ${data.nautiljon.cover_path ? `
                            <div style="flex-shrink: 0;">
                                <img src="/${data.nautiljon.cover_path}" alt="${data.title}" style="max-width: 120px; border-radius: 6px; box-shadow: 0 4px 12px rgba(0,0,0,0.3);">
                            </div>
                        ` : ''}
                        <div>
                            <h3 style="margin: 0 0 15px 0;">🌊 Informations Nautiljon</h3>
                            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; font-size: 0.95em;">
                                ${data.nautiljon.total_volumes ? `
                                    <div>
                                        <strong>Volumes Totaux:</strong>
                                        <div>${data.nautiljon.total_volumes}</div>
                                    </div>
                                ` : ''}
                                ${data.nautiljon.french_volumes ? `
                                    <div>
                                        <strong>Tomes Français:</strong>
                                        <div>${data.nautiljon.french_volumes}</div>
                                    </div>
                                ` : ''}
                                ${data.nautiljon.editor ? `
                                    <div style="grid-column: 1/-1;">
                                        <strong>Éditeur:</strong>
                                        <div>${data.nautiljon.editor}</div>
                                    </div>
                                ` : ''}
                                ${data.nautiljon.mangaka ? `
                                    <div style="grid-column: 1/-1;">
                                        <strong>Mangaka:</strong>
                                        <div>${data.nautiljon.mangaka}</div>
                                    </div>
                                ` : ''}
                                ${data.nautiljon.status ? `
                                    <div>
                                        <strong>Statut:</strong>
                                        <div>${data.nautiljon.status}</div>
                                    </div>
                                ` : ''}
                                ${data.nautiljon.year_start ? `
                                    <div>
                                        <strong>Années:</strong>
                                        <div>${data.nautiljon.year_start}${data.nautiljon.year_end ? ` - ${data.nautiljon.year_end}` : ''}</div>
                                    </div>
                                ` : ''}
                            </div>
                        </div>
                        <div style="display: flex; flex-direction: column; gap: 8px;">
                            <a href="${data.nautiljon.url}" target="_blank" class="btn" style="background: white; color: #667eea; white-space: nowrap;">
                                ↗️ Nautiljon
                            </a>
                            <button class="btn" onclick="searchNautiljonManually(${seriesId})" style="background: rgba(255,255,255,0.2); white-space: nowrap; font-size: 0.9em;">
                                🔍 Chercher un autre titre
                            </button>
                            <button class="btn" onclick="scanSeries(${seriesId})" style="background: rgba(255,255,255,0.2); white-space: nowrap; font-size: 0.9em;">
                                🔄 Scanner cette série
                            </button>
                            <button class="btn" onclick="openRenameModal(${seriesId}, '${data.title.replace(/'/g, "\\'")}')\" style="background: rgba(255,255,255,0.2); white-space: nowrap; font-size: 0.9em;">
                                ✏️ Renommer fichiers
                            </button>
                        </div>
                    </div>
                </div>
            `;
        } else {
            nautiljonHtml = `
                <div style="background: #f3f4f6; padding: 15px; border-radius: 8px; margin-bottom: 20px; text-align: center;">
                    <p style="margin: 0;">
                        ⚠️ Pas d'informations Nautiljon
                        <button class="btn" onclick="enrichSeriesFromModal(${seriesId}, '${data.title.replace(/'/g, "\\'")}')">
                            ✨ Enrichir
                        </button>
                        <button class="btn" onclick="searchNautiljonManually(${seriesId})" style="background: #f59e0b;">
                            🔍 Chercher manuellement
                        </button>
                        <button class="btn" onclick="scanSeries(${seriesId})" style="background: #10b981;">
                            🔄 Scanner cette série
                        </button>
                        <button class="btn" onclick="openRenameModal(${seriesId}, '${data.title.replace(/'/g, "\\'")}')" style="background: #8b5cf6;">
                            ✏️ Renommer fichiers
                        </button>
                    </p>
                </div>
            `;
        }

        let volumesHtml = '';
        
        if (data.has_parts && data.parts) {
            const partNumbers = Object.keys(data.parts).sort((a, b) => parseInt(a) - parseInt(b));
            
            volumesHtml = partNumbers.map(partNum => {
                const part = data.parts[partNum];
                return `
                    <div class="part-section">
                        <div class="part-header">
                            <h3>📖 ${escapeHtml(part.name)}</h3>
                            <span class="part-count">${part.volumes.length} volume(s)</span>
                        </div>
                        <div class="volume-list">
                            ${part.volumes.map(v => `
                                <div class="volume-item">
                                    <div class="volume-number">${v.volume_number || '?'}</div>
                                    <div class="volume-details">
                                        <div class="volume-filename">${escapeHtml(v.filename)}</div>
                                        <div class="volume-meta">
                                            ${v.author ? `<span class="badge">👤 ${escapeHtml(v.author)}</span>` : ''}
                                            ${v.year ? `<span class="badge">📅 ${v.year}</span>` : ''}
                                            ${v.resolution ? `<span class="badge">🖼️ ${v.resolution}</span>` : ''}
                                            <span class="badge">📄 ${v.page_count} pages</span>
                                            <span class="badge">💾 ${formatBytes(v.file_size)}</span>
                                            <span class="badge">.${v.format.toUpperCase()}</span>
                                        </div>
                                    </div>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            }).join('');
        } else {
            volumesHtml = `
                <div class="volume-list">
                    ${(data.volumes || []).map(v => `
                        <div class="volume-item">
                            <div class="volume-number">${v.volume_number || '?'}</div>
                            <div class="volume-details">
                                <div class="volume-filename">${escapeHtml(v.filename)}</div>
                                <div class="volume-meta">
                                    ${v.author ? `<span class="badge">👤 ${escapeHtml(v.author)}</span>` : ''}
                                    ${v.year ? `<span class="badge">📅 ${v.year}</span>` : ''}
                                    ${v.resolution ? `<span class="badge">🖼️ ${v.resolution}</span>` : ''}
                                    <span class="badge">📄 ${v.page_count} pages</span>
                                    <span class="badge">💾 ${formatBytes(v.file_size)}</span>
                                    <span class="badge">.${v.format.toUpperCase()}</span>
                                </div>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        }

        modalBody.innerHTML = `
            ${nautiljonHtml}
            <div class="modal-header">
                <h2 class="modal-title">${escapeHtml(data.title)}</h2>
                <p class="modal-subtitle">
                    ${data.total_volumes} volume(s) dans la collection
                    ${data.has_parts ? ' • Série avec arcs/parties' : ''}
                </p>
                <!-- Tags Management Section -->
                <div style="margin-top: 15px; padding: 15px; background: #f9fafb; border-radius: 6px;">
                    <h4 style="margin: 0 0 10px 0; font-size: 0.95em;">🏷️ Tags</h4>
                    <div id="tags-list-${seriesId}" style="display: flex; flex-wrap: wrap; gap: 5px; margin-bottom: 10px;">
                        <!-- Les tags seront chargés ici -->
                    </div>
                    <div style="display: flex; gap: 5px;">
                        <input type="text" id="new-tag-input-${seriesId}" placeholder="Ajouter un tag..." style="flex: 1; padding: 6px 10px; border: 1px solid #d1d5db; border-radius: 4px; font-size: 0.9em;">
                        <button onclick="addTagToSeries(${seriesId})" class="btn" style="padding: 6px 12px; font-size: 0.9em;">Ajouter</button>
                    </div>
                </div>
                ${data.missing_volumes.length > 0 ? 
                    `<div class="missing-volumes-section" style="margin-top: 20px;">
                        <h3 class="missing-volumes-title">⚠️ Volumes manquants</h3>
                        <div class="missing-volumes-grid">
                            ${data.missing_volumes.map(volNum => `
                                <div class="missing-volume-card" data-series-title="${encodeURIComponent(data.title)}" data-volume-number="${volNum}" style="cursor: pointer;">
                                    <div class="missing-volume-number">${volNum}</div>
                                    <div class="missing-volume-label">Vol. ${volNum}</div>
                                    <div style="font-size: 0.7em; color: #667eea; margin-top: 5px;">🔍 Rechercher</div>
                                </div>
                            `).join('')}
                        </div>
                    </div>` : 
                    `<div class="complete" style="margin-top: 15px;">
                        ✅ Collection complète
                    </div>`
                }
            </div>
            ${volumesHtml}
        `;
        
        // Charger et afficher les tags
        await loadAndDisplayTags(seriesId);
        
        // Attacher écouteurs aux cartes de volumes manquants (évite handlers inline cassés par apostrophes)
        modalBody.querySelectorAll('.missing-volume-card').forEach(card => {
            card.addEventListener('click', (e) => {
                e.stopPropagation();
                const title = decodeURIComponent(card.getAttribute('data-series-title'));
                const vol = parseInt(card.getAttribute('data-volume-number'));
                searchMissingVolume(title, vol);
            });
        });
    } catch (error) {
        modalBody.innerHTML = `<div class="no-data"><h3>Erreur</h3><p>${error.message}</p></div>`;
    }
}

// Fonction pour enrichir une série depuis le modal
async function enrichSeriesFromModal(seriesId, seriesTitle) {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '⏳ Enrichissement...';

    try {
        // Importe l'API Nautiljon si disponible
        if (typeof NautiljonAPI !== 'undefined') {
            const result = await NautiljonAPI.enrichSeries(seriesId, seriesTitle, 'title');
            
            if (result.success) {
                btn.textContent = '✅ Enrichi!';
                // Recharger le modal
                setTimeout(() => {
                    viewSeries(seriesId);
                    btn.disabled = false;
                }, 1000);
            } else {
                btn.textContent = '❌ Erreur';
                btn.disabled = false;
            }
        }
    } catch (error) {
        btn.textContent = '❌ Erreur';
        btn.disabled = false;
        console.error('Erreur enrichissement:', error);
    }
}

// Fonction pour rechercher manuellement une série sur Nautiljon
async function searchNautiljonManually(seriesId) {
    // Naviguer vers la page Nautiljon avec la bibliothèque et la série pré-sélectionnées
    window.location.href = `/nautiljon?libraryId=${libraryId}&seriesId=${seriesId}`;
}

async function searchMissingVolume(seriesTitle, volumeNumber) {
    const searchModal = document.getElementById('search-ed2k-modal');
    const searchModalBody = document.getElementById('search-modal-body');
    
    searchModal.classList.add('active');
    searchModalBody.innerHTML = '<div class="loading"><div class="spinner"></div><p>Recherche en cours...</p></div>';

    try {
        const params = new URLSearchParams();
        params.append('query', seriesTitle);
        params.append('volume', volumeNumber);

        const response = await fetch(`/api/search?${params}`);
        const data = await response.json();

        if (data.results && data.results.length > 0) {
            displaySearchResults(seriesTitle, volumeNumber, data.results);
        } else {
            searchModalBody.innerHTML = `
                <div class="search-header">
                    <h2>🔍 Recherche: ${escapeHtml(seriesTitle)} - Volume ${volumeNumber}</h2>
                </div>
                <div class="no-data">
                    <h3>😕 Aucun résultat</h3>
                    <p>Aucun lien ED2K trouvé pour ce volume dans la base de données</p>
                    <button class="btn" onclick="closeSearchModal()" style="margin-top: 20px;">Fermer</button>
                </div>
            `;
        }
    } catch (error) {
        searchModalBody.innerHTML = `
            <div class="no-data">
                <h3>❌ Erreur</h3>
                <p>${error.message}</p>
                <button class="btn" onclick="closeSearchModal()" style="margin-top: 20px;">Fermer</button>
            </div>
        `;
    }
}

function displaySearchResults(seriesTitle, volumeNumber, results) {
    const searchModalBody = document.getElementById('search-modal-body');
    
    // Séparer les résultats ED2K et Prowlarr
    const ed2kResults = results.filter(r => r.source === 'ebdz');
    const prowlarrResults = results.filter(r => r.source === 'prowlarr');
    
    let html = `
        <div class="search-header">
            <h2>🔍 ${escapeHtml(seriesTitle)} - Volume ${volumeNumber}</h2>
            <p style="color: #666; margin-top: 10px;">${results.length} résultat(s) trouvé(s)</p>
        </div>
    `;

    // ===== SECTION ED2K =====
    if (ed2kResults.length > 0) {
        // Regrouper par thread
        const grouped = {};
        ed2kResults.forEach(result => {
            if (!grouped[result.thread_id]) {
                grouped[result.thread_id] = {
                    title: result.thread_title,
                    url: result.thread_url,
                    category: result.forum_category,
                    cover_image: result.cover_image,
                    description: result.description,
                    links: []
                };
            }
            grouped[result.thread_id].links.push(result);
        });

        html += `
            <div style="margin-top: 30px; padding: 20px; background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; border-radius: 8px; margin-bottom: 20px;">
                <h3 style="margin: 0 0 15px 0;">📚 Résultats eMule (${ed2kResults.length})</h3>
            </div>
        `;

        for (const threadId in grouped) {
            const thread = grouped[threadId];
            
            html += `
                <div class="result-card" style="margin-top: 20px;">
                    <div class="cover-container">
                        ${thread.cover_image ? 
                            `<img src="/covers/${thread.cover_image.replace('covers/', '')}" class="cover-image" alt="Couverture">` 
                            : '<div class="cover-image" style="background: #e0e0e0; display: flex; align-items: center; justify-content: center; color: #999;">Pas de couverture</div>'
                        }
                    </div>
                    <div class="result-content">
                        <div class="result-title">${thread.title}</div>
                        <span class="result-category">${thread.category || 'Non catégorisé'}</span>
                        
                        ${thread.description ? 
                            `<div class="description">${thread.description}</div>` 
                            : ''
                        }
                        
                        <div class="file-info">
            `;

            thread.links.forEach((link, index) => {
                const volumeDisplay = link.volume ? `<div class="volume-badge">Vol. ${link.volume}</div>` : '';
                const decodedFilename = decodeFilename(link.filename);
                
                html += `
                    <div class="file-item">
                        <div style="display: flex; align-items: center; gap: 10px; flex: 1;">
                            ${volumeDisplay}
                            <div class="file-name" title="${decodedFilename}">${decodedFilename}</div>
                        </div>
                        <div class="file-size">${formatBytes(link.filesize)}</div>
                        <button class="copy-button" onclick="copyLink('${escapeForAttribute(link.link)}', this)">📋 Copier</button>
                        <button class="add-button" onclick="addToEmule('${escapeForAttribute(link.link)}', this)" id="add-search-${threadId}-${index}">
                            ⬇️ Ajouter
                        </button>
                    </div>
                `;
            });

            html += `
                        </div>
                    </div>
                </div>
            `;
        }
    }

    // ===== SECTION PROWLARR =====
    if (prowlarrResults.length > 0) {
        html += `
            <div style="margin-top: 30px; padding: 20px; background: linear-gradient(135deg, #f093fb 0%, #f5576c 100%); color: white; border-radius: 8px; margin-bottom: 20px;">
                <h3 style="margin: 0 0 15px 0;">🔍 Résultats Prowlarr (${prowlarrResults.length})</h3>
            </div>
        `;

        prowlarrResults.forEach((result, index) => {
            const publishDate = result.publish_date ? new Date(result.publish_date).toLocaleDateString('fr-FR') : 'N/A';
            const seeders = result.seeders !== null ? result.seeders : 'N/A';
            const peers = result.peers !== null ? result.peers : 'N/A';
            
            html += `
                <div class="result-card" style="margin-top: 20px;">
                    <div class="result-content" style="width: 100%;">
                        <div class="result-title">${escapeHtml(result.title)}</div>
                        <span class="result-category">${result.indexer || 'Prowlarr'}</span>
                        
                        <div style="margin-top: 10px; font-size: 0.9em;">
                            <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 10px; margin-bottom: 10px;">
                                <div>
                                    <strong>Taille:</strong> ${formatBytes(result.size)}
                                </div>
                                <div>
                                    <strong>Date:</strong> ${publishDate}
                                </div>
                                <div>
                                    <strong>Seeders:</strong> ${seeders}
                                </div>
                                <div>
                                    <strong>Peers:</strong> ${peers}
                                </div>
                            </div>
                        </div>
                        
                        ${result.description ? 
                            `<div class="description">${escapeHtml(result.description)}</div>` 
                            : ''
                        }
                        
                        <div class="file-info" style="margin-top: 15px;">
                            <div class="file-item">
                                <div style="display: flex; align-items: center; gap: 10px; flex: 1;">
                                    <div class="file-name">${escapeHtml(result.title)}</div>
                                </div>
                                <button class="copy-button" onclick="copyLink('${escapeForAttribute(result.link || result.download_url)}', this)">📋 Copier lien</button>
                                ${result.download_url ? `
                                    <button class="add-button" style="background: #f5576c;" onclick="addTorrentToQbittorrent('${escapeForAttribute(result.download_url)}', this)">
                                        ⚡ qBittorrent
                                    </button>
                                ` : ''}
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });
    }

    // Si aucun résultat
    if (results.length === 0) {
        html += `
            <div class="no-data">
                <h3>😕 Aucun résultat</h3>
                <p>Aucun lien trouvé pour ce volume dans ED2K ou Prowlarr</p>
            </div>
        `;
    }

    html += `
        <div style="text-align: center; margin-top: 30px;">
            <button class="btn" onclick="closeSearchModal()">Fermer</button>
        </div>
    `;

    searchModalBody.innerHTML = html;
    
    // Vérifier si aMule est activé pour afficher/cacher les boutons
    checkEmuleStatus();
}

function decodeFilename(filename) {
    try {
        return decodeURIComponent(filename);
    } catch (e) {
        return filename;
    }
}

function escapeForAttribute(text) {
    return text.replace(/'/g, "\\'").replace(/"/g, '&quot;');
}

async function copyLink(link, button) {
    try {
        await navigator.clipboard.writeText(link);
        button.textContent = '✓ Copié!';
        button.classList.add('copied');
        setTimeout(() => {
            button.textContent = '📋 Copier';
            button.classList.remove('copied');
        }, 2000);
    } catch (error) {
        alert('Erreur lors de la copie: ' + error);
    }
}

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
        alert('Erreur: ' + error.message);
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
        
        const addButtons = document.querySelectorAll('.add-button');
        addButtons.forEach(button => {
            button.style.display = config.enabled ? 'inline-block' : 'none';
        });
    } catch (error) {
        console.error('Erreur lors de la vérification du statut aMule:', error);
    }
}

function closeModal() {
    document.getElementById('series-modal').classList.remove('active');
}

function closeSearchModal() {
    document.getElementById('search-ed2k-modal').classList.remove('active');
}

function formatBytes(bytes) {
    if (!bytes) return 'N/A';
    const b = parseInt(bytes);
    if (b === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(b) / Math.log(k));
    return Math.round(b / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
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

/**
 * Charge et affiche les tags d'une série
 */
async function loadAndDisplayTags(seriesId) {
    try {
        const response = await fetch(`/api/series/${seriesId}/tags`);
        
        if (!response.ok) {
            console.warn(`Erreur chargement tags: ${response.status}`);
            return;
        }
        
        const data = await response.json();
        
        const tagsList = document.getElementById(`tags-list-${seriesId}`);
        if (!tagsList) return;
        
        tagsList.innerHTML = '';
        
        if (data.tags && data.tags.length > 0) {
            data.tags.forEach(tag => {
                const tagElement = document.createElement('span');
                tagElement.className = 'tag-badge';
                tagElement.style.cssText = 'display: inline-flex; align-items: center; gap: 5px; padding: 4px 10px; background: #dbeafe; color: #1e40af; border-radius: 12px; font-size: 0.85em; font-weight: 500; border: 1px solid #93c5fd;';
                tagElement.innerHTML = `
                    ${escapeHtml(tag)}
                    <button onclick="removeTagFromSeries(${seriesId}, '${tag.replace(/'/g, "\\'")}', event)" style="background: none; border: none; color: #1e40af; cursor: pointer; font-weight: bold; padding: 0; margin-left: 3px;">×</button>
                `;
                tagsList.appendChild(tagElement);
            });
        } else {
            tagsList.innerHTML = '<p style="margin: 0; color: #6b7280; font-size: 0.9em;">Aucun tag</p>';
        }
    } catch (error) {
        console.error('Erreur lors du chargement des tags:', error);
    }
}

/**
 * Ajoute un tag à une série
 */
async function addTagToSeries(seriesId) {
    const input = document.getElementById(`new-tag-input-${seriesId}`);
    const tagText = input.value.trim();
    
    if (!tagText) {
        alert('Veuillez entrer un tag');
        return;
    }
    
    try {
        // Charger les tags actuels
        const response = await fetch(`/api/series/${seriesId}/tags`);
        const data = await response.json();
        
        let tags = data.tags || [];
        
        // Vérifier que le tag n'existe pas déjà
        if (tags.includes(tagText)) {
            alert('Ce tag existe déjà');
            input.value = '';
            return;
        }
        
        // Ajouter le nouveau tag
        tags.push(tagText);
        
        // Sauvegarder
        const updateResponse = await fetch(`/api/series/${seriesId}/tags`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ tags: tags })
        });
        
        if (updateResponse.ok) {
            input.value = '';
            await loadAndDisplayTags(seriesId);
            // Recharger les données de la bibliothèque pour mettre à jour les filtres
            loadLibraryData();
        } else {
            alert('Erreur lors de l\'ajout du tag');
        }
    } catch (error) {
        console.error('Erreur:', error);
        alert('Erreur lors de l\'ajout du tag');
    }
}

/**
 * Supprime un tag d'une série
 */
async function removeTagFromSeries(seriesId, tag, event) {
    event.preventDefault();
    event.stopPropagation();
    
    try {
        // Charger les tags actuels
        const response = await fetch(`/api/series/${seriesId}/tags`);
        const data = await response.json();
        
        let tags = data.tags || [];
        
        // Supprimer le tag
        tags = tags.filter(t => t !== tag);
        
        // Sauvegarder
        const updateResponse = await fetch(`/api/series/${seriesId}/tags`, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ tags: tags })
        });
        
        if (updateResponse.ok) {
            await loadAndDisplayTags(seriesId);
            // Recharger les données de la bibliothèque pour mettre à jour les filtres
            loadLibraryData();
        } else {
            alert('Erreur lors de la suppression du tag');
        }
    } catch (error) {
        console.error('Erreur:', error);
        alert('Erreur lors de la suppression du tag');
    }
}

// ===== qBITTORRENT =====
// Ajouter un torrent à qBittorrent avec la catégorie par défaut
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
        alert('Erreur: ' + error.message);
        setTimeout(() => {
            button.textContent = originalText;
            button.disabled = false;
            button.style.background = '';
        }, 3000);
    }
}

window.onclick = function(event) {
    const modal = document.getElementById('series-modal');
    const searchModal = document.getElementById('search-ed2k-modal');
    if (event.target == modal) {
        closeModal();
    }
    if (event.target == searchModal) {
        closeSearchModal();
    }
}

// ========== RENOMMAGE DE FICHIERS ==========

let currentRenameSeriesId = null;
let currentRenameSeries = null;

async function openRenameModal(seriesId, seriesTitle) {
    currentRenameSeriesId = seriesId;
    currentRenameSeries = {
        id: seriesId,
        title: seriesTitle
    };
    
    // Créer le modal de renommage s'il n'existe pas
    let renameModal = document.getElementById('rename-modal');
    if (!renameModal) {
        renameModal = document.createElement('div');
        renameModal.id = 'rename-modal';
        renameModal.className = 'modal rename-modal';
        document.body.appendChild(renameModal);
    }
    
    renameModal.innerHTML = `
        <div class="modal-content rename-modal-content">
            <span class="close-modal" onclick="closeRenameModal()">×</span>
            <div class="rename-modal-header">
                <h2>✏️ Renommer les fichiers</h2>
                <p class="rename-modal-subtitle">Série: <strong>${escapeHtml(seriesTitle)}</strong></p>
            </div>
            
            <div class="rename-modal-body">
                <div class="rename-section">
                    <h3>Pattern de renommage</h3>
                    <p class="rename-help-text">Utilisez des tags pour personnaliser les noms de fichiers:</p>
                    
                    <div class="tags-reference">
                        <div class="tag-info">
                            <code>[T]</code> - Titre de la série
                        </div>
                        <div class="tag-info">
                            <code>[V]</code> - Numéro de volume
                        </div>
                        <div class="tag-info">
                            <code>[C:départ:longueur]</code> - Compteur (Ex: [C:01:3] = 001, 002, ...)
                        </div>
                        <div class="tag-info">
                            <code>[E]</code> - Extension du fichier (Ex: pdf, cbz)
                        </div>
                        <div class="tag-info">
                            <code>[N]</code> - Nom du fichier original
                        </div>
                        <div class="tag-info">
                            <code>[P]</code> - Numéro de partie (si applicable)
                        </div>
                    </div>
                    
                    <label>Exemple de patterns:</label>
                    <ul style="margin: 10px 0; font-size: 0.9em; color: #666;">
                        <li><code>[T] - Vol [V].[E]</code> → "Mon Manga - Vol 1.pdf"</li>
                        <li><code>[T] [C:01:3].[E]</code> → "Mon Manga 001.pdf"</li>
                        <li><code>[C:01:2] - [N].[E]</code> → "01 - Original Name.pdf"</li>
                    </ul>
                    
                    <div style="margin-top: 15px;">
                        <label for="rename-pattern-input">Votre pattern:</label>
                        <input 
                            type="text" 
                            id="rename-pattern-input" 
                            class="rename-pattern-input"
                            placeholder="Ex: [T] - Vol [V].[E]"
                            onkeyup="updateRenamePreview()">
                    </div>
                </div>
                
                <div class="rename-section">
                    <h3>Aperçu du renommage</h3>
                    <div id="rename-preview-container" class="rename-preview-container">
                        <p style="color: #999; text-align: center; padding: 20px;">
                            Entrez un pattern pour voir l'aperçu du renommage
                        </p>
                    </div>
                </div>
                
                <div style="display: flex; gap: 10px; justify-content: flex-end; margin-top: 20px;">
                    <button onclick="closeRenameModal()" class="btn" style="background: #e5e7eb; color: #333;">Annuler</button>
                    <button onclick="executeRename()" class="btn" style="background: #10b981;">✅ Appliquer le renommage</button>
                </div>
            </div>
        </div>
    `;
    
    renameModal.classList.add('active');
}

function closeRenameModal() {
    const modal = document.getElementById('rename-modal');
    if (modal) {
        modal.classList.remove('active');
    }
    currentRenameSeriesId = null;
    currentRenameSeries = null;
}

async function updateRenamePreview() {
    const pattern = document.getElementById('rename-pattern-input').value;
    const previewContainer = document.getElementById('rename-preview-container');
    
    if (!pattern.trim()) {
        previewContainer.innerHTML = `
            <p style="color: #999; text-align: center; padding: 20px;">
                Entrez un pattern pour voir l'aperçu du renommage
            </p>
        `;
        return;
    }
    
    previewContainer.innerHTML = `
        <div class="loading" style="padding: 20px;">
            <div class="spinner"></div>
            <p>Calcul de l'aperçu...</p>
        </div>
    `;
    
    try {
        const response = await fetch(`/api/series/${currentRenameSeriesId}/rename/preview`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                pattern: pattern
            })
        });
        
        if (!response.ok) {
            const text = await response.text();
            throw new Error(`Erreur serveur ${response.status}: ${text.substring(0, 100)}`);
        }
        
        const data = await response.json();
        
        if (data.error) {
            previewContainer.innerHTML = `
                <div class="error-message" style="padding: 15px; background: #fee; border: 1px solid #f99; border-radius: 4px; color: #c33;">
                    ❌ ${escapeHtml(data.error)}
                </div>
            `;
            return;
        }
        
        if (data.preview && data.preview.length > 0) {
            previewContainer.innerHTML = `
                <div class="rename-preview-list">
                    ${data.preview.map((item, idx) => `
                        <div class="rename-preview-item">
                            <div class="rename-preview-old">
                                <span class="rename-preview-label">Avant:</span>
                                <code>${escapeHtml(item.old_name)}</code>
                            </div>
                            <div class="rename-preview-arrow">→</div>
                            <div class="rename-preview-new">
                                <span class="rename-preview-label">Après:</span>
                                <code>${escapeHtml(item.new_name)}</code>
                            </div>
                        </div>
                    `).join('')}
                </div>
            `;
        } else {
            previewContainer.innerHTML = `
                <p style="color: #999; text-align: center; padding: 20px;">
                    Aucun fichier à renommer
                </p>
            `;
        }
    } catch (error) {
        previewContainer.innerHTML = `
            <div class="error-message" style="padding: 15px; background: #fee; border: 1px solid #f99; border-radius: 4px; color: #c33;">
                ❌ Erreur: ${escapeHtml(error.message)}
            </div>
        `;
    }
}

async function executeRename() {
    const pattern = document.getElementById('rename-pattern-input').value;
    
    if (!pattern.trim()) {
        alert('Veuillez entrer un pattern de renommage');
        return;
    }
    
    if (!confirm('Êtes-vous sûr de vouloir renommer tous les fichiers de cette série?\n\nCette action ne peut pas être annulée.')) {
        return;
    }
    
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '⏳ Renommage en cours...';
    
    try {
        // D'abord récupérer les fichiers via l'aperçu
        const previewResponse = await fetch(`/api/series/${currentRenameSeriesId}/rename/preview`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                pattern: pattern
            })
        });
        
        if (!previewResponse.ok) {
            const text = await previewResponse.text();
            throw new Error(`Erreur serveur ${previewResponse.status}: ${text.substring(0, 200)}`);
        }
        
        const previewData = await previewResponse.json();
        
        if (previewData.error) {
            alert(`Erreur: ${previewData.error}`);
            btn.disabled = false;
            btn.textContent = '✅ Appliquer le renommage';
            return;
        }
        
        // Extraire les noms de fichiers
        const filesToRename = previewData.preview.map(item => item.old_name);
        
        // Exécuter le renommage
        const executeResponse = await fetch(`/api/series/${currentRenameSeriesId}/rename/execute`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                pattern: pattern,
                files: filesToRename
            })
        });
        
        if (!executeResponse.ok) {
            const text = await executeResponse.text();
            throw new Error(`Erreur serveur ${executeResponse.status}: ${text.substring(0, 200)}`);
        }
        
        const executeData = await executeResponse.json();
        
        if (executeData.error) {
            alert(`Erreur: ${executeData.error}`);
            btn.disabled = false;
            btn.textContent = '✅ Appliquer le renommage';
            return;
        }
        
        // Afficher le résultat
        const successful = executeData.results.filter(r => r.success).length;
        const failed = executeData.results.filter(r => !r.success).length;
        
        let resultMessage = `✅ Renommage terminé!\n\n${successful} fichier(s) renommé(s)`;
        if (failed > 0) {
            resultMessage += `\n⚠️ ${failed} erreur(s)`;
        }
        
        alert(resultMessage);
        
        // Fermer les modals et recharger la liste des séries
        closeRenameModal();
        closeModal();
        loadLibraryData();
        
    } catch (error) {
        alert(`Erreur: ${error.message}`);
        btn.disabled = false;
        btn.textContent = '✅ Appliquer le renommage';
    }
}

// Fermer le modal de renommage quand on clique en dehors
document.addEventListener('click', function(event) {
    const renameModal = document.getElementById('rename-modal');
    if (renameModal && event.target == renameModal) {
        closeRenameModal();
    }
});

window.addEventListener('load', function() {
    loadLibraryInfo();
    loadLibraryData();
});