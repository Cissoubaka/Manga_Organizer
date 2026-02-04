const libraryId = { library_id };
let seriesData = [];
let showOnlyMissing = false;
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

    grid.innerHTML = series.map(s => `
        <div class="series-card" onclick="viewSeries(${s.id})">
            <div class="series-title">${escapeHtml(s.title)}</div>
            <div class="series-info">📖 ${s.total_volumes} volume(s)</div>
            <div class="series-info">📅 Dernier scan: ${new Date(s.last_scanned).toLocaleDateString('fr-FR')}</div>
            ${s.missing_volumes.length > 0 ? 
                `<div class="missing-volumes">⚠️ Volumes manquants: ${s.missing_volumes.join(', ')}</div>` :
                `<div class="complete">✅ Collection complète</div>`
            }
        </div>
    `).join('');
}

function filterSeries() {
    const searchTerm = document.getElementById('search').value.toLowerCase();
    let filtered = seriesData.filter(s => 
        s.title.toLowerCase().includes(searchTerm)
    );
    
    if (showOnlyMissing) {
        filtered = filtered.filter(s => s.missing_volumes.length > 0);
    }
    
    displaySeries(filtered);
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

async function scanLibrary() {
    if (!confirm('Voulez-vous scanner cette bibliothèque ? Cela peut prendre du temps.')) {
        return;
    }

    const button = event.target;
    button.disabled = true;
    button.textContent = '⏳ Scan en cours...';

    try {
        const response = await fetch(`/api/scan/${libraryId}`);
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ Scan terminé ! ${data.series_count} séries trouvées.`);
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

async function viewSeries(seriesId) {
    const modal = document.getElementById('series-modal');
    const modalBody = document.getElementById('modal-body');
    
    modal.classList.add('active');
    modalBody.innerHTML = '<div class="loading"><div class="spinner"></div><p>Chargement des détails...</p></div>';

    try {
        const response = await fetch(`/api/series/${seriesId}`);
        const data = await response.json();
        
        console.log('Données reçues:', data);
        
        // Sauvegarder le titre de la série pour la recherche
        currentSeriesTitle = data.title;

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
            <div class="modal-header">
                <h2 class="modal-title">${escapeHtml(data.title)}</h2>
                <p class="modal-subtitle">
                    ${data.total_volumes} volume(s) dans la collection
                    ${data.has_parts ? ' • Série avec arcs/parties' : ''}
                </p>
                ${data.missing_volumes.length > 0 ? 
                    `<div class="missing-volumes-section" style="margin-top: 20px;">
                        <h3 class="missing-volumes-title">⚠️ Volumes manquants</h3>
                        <div class="missing-volumes-grid">
                            ${data.missing_volumes.map(volNum => `
                                <div class="missing-volume-card" onclick="searchMissingVolume('${escapeHtml(data.title)}', ${volNum}); event.stopPropagation();" style="cursor: pointer;">
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
    } catch (error) {
        modalBody.innerHTML = `<div class="no-data"><h3>Erreur</h3><p>${error.message}</p></div>`;
    }
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
    
    // Regrouper par thread
    const grouped = {};
    results.forEach(result => {
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

    let html = `
        <div class="search-header">
            <h2>🔍 ${escapeHtml(seriesTitle)} - Volume ${volumeNumber}</h2>
            <p style="color: #666; margin-top: 10px;">${results.length} résultat(s) trouvé(s)</p>
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

window.addEventListener('load', function() {
    loadLibraryInfo();
    loadLibraryData();
});
