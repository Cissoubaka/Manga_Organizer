console.log('import.js chargé');
let importFiles = [];
let currentFileIndex = -1;
let allLibraries = [];
let librariesSeriesMap = {};

// ===== FONCTION UTILITAIRE POUR NORMALISER LES TITRES =====
function normalizeTitle(title) {
    // Normaliser un titre pour la comparaison
    return title
        .toLowerCase()
        .replace(/[._-]/g, ' ')  // Remplacer points, underscores, tirets par espaces
        .replace(/\s+/g, ' ')    // Réduire espaces multiples
        .trim();
}

// ===== FONCTION AMÉLIORÉE POUR TROUVER UNE SÉRIE EXISTANTE =====
function findExistingSeries(libraryId, seriesName) {
    const series = librariesSeriesMap[libraryId] || [];
    const normalizedInput = normalizeTitle(seriesName);
    
    // D'abord chercher une correspondance exacte (normalisée)
    let match = series.find(s => normalizeTitle(s.title) === normalizedInput);
    
    if (match) {
        return match;
    }
    
    // Sinon, chercher une correspondance partielle forte (>= 90%)
    let bestMatch = null;
    let bestScore = 0;
    
    for (const s of series) {
        const score = calculateSimilarity(normalizedInput, normalizeTitle(s.title));
        if (score >= 90 && score > bestScore) {
            bestMatch = s;
            bestScore = score;
        }
    }
    
    return bestMatch;
}

async function loadAllLibraries() {
    try {
        const response = await fetch('/api/libraries');
        allLibraries = await response.json();
        
        // Charger les séries pour chaque bibliothèque
        for (const lib of allLibraries) {
            const seriesResponse = await fetch(`/api/library/${lib.id}/series`);
            librariesSeriesMap[lib.id] = await seriesResponse.json();
        }
    } catch (error) {
        console.error('Erreur chargement bibliothèques:', error);
    }
}


function handleImportFolderSelect(event) {
    const files = event.target.files;
    if (files.length > 0) {
        const firstFile = files[0];
        let folderPath = firstFile.webkitRelativePath || firstFile.name;
        
        const pathParts = folderPath.split('/');
        if (pathParts.length > 1) {
            pathParts.pop();
            folderPath = pathParts.join('/');
        }
        
        if (firstFile.path) {
            const fullPath = firstFile.path;
            const fileName = firstFile.name;
            folderPath = fullPath.substring(0, fullPath.lastIndexOf(fileName.split('/').pop()));
            folderPath = folderPath.replace(/\\/g, '/').replace(/\/$/, '');
        }
        
        document.getElementById('import-path').value = folderPath;
        // Sauvegarder le chemin
        saveImportPath(folderPath);
    }
}

function saveImportPath(path) {
    try {
        localStorage.setItem('manga_import_path', path);
    } catch (e) {
        console.error('Impossible de sauvegarder le chemin:', e);
    }
}

function loadImportPath() {
    try {
        const savedPath = localStorage.getItem('manga_import_path');
        if (savedPath) {
            document.getElementById('import-path').value = savedPath;
        }
    } catch (e) {
        console.error('Impossible de charger le chemin:', e);
    }
}

async function scanImportDirectory() {
    const importPath = document.getElementById('import-path').value;
    
    if (!importPath) {
        alert('⚠️ Veuillez sélectionner un répertoire d\'import');
        return;
    }

    // Sauvegarder le chemin
    saveImportPath(importPath);

    const resultsSection = document.getElementById('scan-results');
    const container = document.getElementById('import-files-container');
    
    resultsSection.style.display = 'block';
    container.innerHTML = '<div class="loading"><div class="spinner"></div><p>Scan en cours...</p></div>';

    try {
        const response = await fetch('/api/import/scan', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path: importPath })
        });

        const data = await response.json();

        if (data.success) {
            importFiles = data.files;
            updateImportStats();
            displayImportFiles();
        } else {
            container.innerHTML = `
                <div class="no-data">
                    <h3>Erreur</h3>
                    <p>${data.error || 'Erreur inconnue'}</p>
                </div>
            `;
        }
    } catch (error) {
        container.innerHTML = `
            <div class="no-data">
                <h3>Erreur de connexion</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

function updateImportStats() {
    document.getElementById('files-found').textContent = importFiles.length;
    
    const assignedCount = importFiles.filter(f => f.destination).length;
    document.getElementById('matches-found').textContent = assignedCount;
    document.getElementById('unassigned-count').textContent = importFiles.length - assignedCount;
    
    const importBtn = document.getElementById('import-btn');
    importBtn.disabled = assignedCount === 0;
}

function displayImportFiles() {
    const container = document.getElementById('import-files-container');

    if (importFiles.length === 0) {
        container.innerHTML = `
            <div class="no-data">
                <h3>Aucun fichier trouvé</h3>
                <p>Le répertoire ne contient aucun fichier manga supporté</p>
            </div>
        `;
        return;
    }

    // Regrouper les fichiers par titre détecté
    const groupedFiles = {};
    importFiles.forEach((file, index) => {
        const seriesKey = file.parsed.title || 'Sans titre';
        if (!groupedFiles[seriesKey]) {
            groupedFiles[seriesKey] = [];
        }
        groupedFiles[seriesKey].push({ file, index });
    });

    // Créer le HTML pour chaque groupe
    const groupsHtml = Object.entries(groupedFiles).map(([seriesTitle, items]) => {
        const allAssigned = items.every(item => item.file.destination);
        const someAssigned = items.some(item => item.file.destination);
        const noneAssigned = !someAssigned;

        let groupStatusClass = 'group-mixed';
        if (allAssigned) groupStatusClass = 'group-assigned';
        else if (noneAssigned) groupStatusClass = 'group-unassigned';

        const totalSize = items.reduce((sum, item) => sum + item.file.file_size, 0);
        const volumes = items.map(item => item.file.parsed.volume).filter(v => v).sort((a, b) => a - b);

        // Générer des identifiants sûrs
        const idSuffix = seriesTitle.replace(/\s+/g, '-').replace(/[^a-zA-Z0-9-_]/g, '');
        const safeGroupId = `group-${idSuffix}`;
        // JSON.stringify may include unicode line separators U+2028/U+2029 which break
        // inline JS string literals in some browsers. Escape them explicitly.
        const safeJsTitle = JSON.stringify(seriesTitle)
            .replace(/\u2028/g, '\\u2028')
            .replace(/\u2029/g, '\\u2029');

        // Vérifier si tous les fichiers du groupe ont la même destination
        const firstDestination = items.find(item => item.file.destination)?.file.destination;
        const sameDestination = allAssigned && items.every(item =>
            item.file.destination?.library_id === firstDestination?.library_id &&
            item.file.destination?.series_title === firstDestination?.series_title
        );

        return `
            <div class="import-group ${groupStatusClass}">
                <div class="import-group-header" onclick="toggleGroup(this,'${safeGroupId}')">
                    <div class="import-group-info">
                        <div class="import-group-title">
                            <span class="group-toggle">▼</span>
                            📚 ${escapeHtml(seriesTitle)}
                        </div>
                        <div class="import-group-meta">
                            <span class="badge">${items.length} fichier${items.length > 1 ? 's' : ''}</span>
                            ${volumes.length > 0 ? `<span class="badge">📗 Vol. ${volumes.join(', ')}</span>` : ''}
                            <span class="badge">💾 ${formatBytes(totalSize)}</span>
                            ${allAssigned ? '<span class="badge badge-success">✅ Tous assignés</span>' :
                                someAssigned ? '<span class="badge" style="background: #fbbf24;">⚠️ Partiellement assigné</span>' :
                                '<span class="badge" style="background: #f87171; color: white;">❌ Non assigné</span>'}
                        </div>
                    </div>
                </div>

                ${!allAssigned ? `
                    <div class="import-group-quick-assign">
                        <div class="quick-assign-header">⚡ Assigner tous les fichiers de cette série :</div>
                        <div class="quick-assign-form">
                            <div class="quick-assign-row">
                                <label>Bibliothèque:</label>
                                <select id="group-lib-${idSuffix}" class="quick-select"
                                        onchange="updateGroupSeriesOptions('${idSuffix}')">
                                    <option value="">-- Sélectionner --</option>
                                    ${allLibraries.map(lib => `<option value="${lib.id}">${escapeHtml(lib.name)}</option>`).join('')}
                                </select>
                            </div>
                            <div class="quick-assign-row">
                                <label>Série:</label>
                                <input type="text"
                                        id="group-series-${idSuffix}"
                                        class="quick-input"
                                        placeholder="Nom de la série"
                                        value="${escapeHtml(seriesTitle)}"
                                        list="group-series-list-${idSuffix}">
                                <datalist id="group-series-list-${idSuffix}"></datalist>
                            </div>
                            <div class="quick-assign-row quick-assign-buttons">
                                <button class="btn btn-success quick-assign-btn" data-series-title="${encodeURIComponent(seriesTitle)}">
                                    ✅ Assigner tous (${items.filter(item => !item.file.destination).length} fichier${items.filter(item => !item.file.destination).length > 1 ? 's' : ''})
                                </button>
                            </div>
                        </div>
                    </div>
                ` : sameDestination ? `
                    <div class="import-group-destination">
                        <div class="destination-info">
                            <div class="destination-label">📍 Destination commune:</div>
                            <div class="destination-details">
                                <strong>${escapeHtml(firstDestination.library_name)}</strong> →
                                <strong>${escapeHtml(firstDestination.series_title)}</strong>
                                ${firstDestination.is_new_series ? '<span class="badge badge-success">Nouvelle série</span>' : '<span class="badge" style="background: #10b981;">Série existante</span>'}
                            </div>
                        </div>
                        <button class="btn btn-danger remove-group-btn" data-series-title="${encodeURIComponent(seriesTitle)}">
                            ❌ Retirer tous
                        </button>
                    </div>
                ` : ''}

                <div class="import-group-files" id="${safeGroupId}" style="display: none;">
                    ${items.map(({ file, index }) => {
                        const hasDestination = file.destination;
                        const statusClass = hasDestination ? 'assigned' : 'unassigned';

                        return `
                            <div class="import-file-card ${statusClass}">
                                <div class="import-file-info">
                                    <div class="import-file-name" title="${escapeHtml(file.filename)}">
                                        📄 ${escapeHtml(file.filename)}
                                    </div>
                                    <div class="import-file-meta">
                                        ${file.parsed.volume ? `<span class="badge">Vol. ${file.parsed.volume}</span>` : ''}
                                        <span class="badge">💾 ${formatBytes(file.file_size)}</span>
                                        <span class="badge">📁 ${escapeHtml(file.relative_path)}</span>
                                    </div>
                                    ${hasDestination ? `
                                        <div class="import-file-destination">
                                            <div class="destination-label">📍 Destination:</div>
                                            <div class="destination-details">
                                                <strong>${escapeHtml(file.destination.library_name)}</strong> →
                                                <strong>${escapeHtml(file.destination.series_title)}</strong>
                                                ${file.destination.is_new_series ?
                                                    '<span class="badge badge-success">Nouvelle série</span>' :
                                                    '<span class="badge" style="background: #10b981;">Série existante</span>'}
                                            </div>
                                        </div>
                                    ` : ''}
                                </div>
                                <div class="import-file-actions">
                                    ${!hasDestination ? `
                                        <button class="btn" onclick="openDestinationModal(${index})">
                                            📌 Assigner
                                        </button>
                                    ` : `
                                        <button class="btn" onclick="openDestinationModal(${index})">
                                            ✏️ Modifier
                                        </button>
                                        <button class="btn btn-danger" onclick="removeDestination(${index})">
                                            ❌
                                        </button>
                                    `}
                                </div>
                            </div>
                        `;
                    }).join('')}
                </div>
            </div>
        `;
    }).join('');

    container.innerHTML = groupsHtml;

    // Attacher les écouteurs aux boutons créés dynamiquement (évite les handlers inline)
    container.querySelectorAll('.quick-assign-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const title = decodeURIComponent(btn.getAttribute('data-series-title'));
            quickAssignGroup(title);
        });
    });

    container.querySelectorAll('.remove-group-btn').forEach(btn => {
        btn.addEventListener('click', (e) => {
            const title = decodeURIComponent(btn.getAttribute('data-series-title'));
            removeGroupDestination(title);
        });
    });
}

function toggleGroup(el, groupId) {
    const group = document.getElementById(groupId);
    const toggle = el.querySelector('.group-toggle');

    if (group.style.display === 'none') {
        group.style.display = 'block';
        toggle.textContent = '▲';
    } else {
        group.style.display = 'none';
        toggle.textContent = '▼';
    }
}

function updateGroupSeriesOptions(groupKey) {
    const libraryId = parseInt(document.getElementById(`group-lib-${groupKey}`).value);
    const datalist = document.getElementById(`group-series-list-${groupKey}`);
    
    if (!libraryId) {
        datalist.innerHTML = '';
        return;
    }
    
    const series = librariesSeriesMap[libraryId] || [];
    datalist.innerHTML = series.map(s => `<option value="${escapeHtml(s.title)}"></option>`).join('');
}

function quickAssignGroup(seriesTitle) {
    const groupKey = seriesTitle.replace(/\s+/g, '-').replace(/[^a-zA-Z0-9-_]/g, '');
    const libraryId = parseInt(document.getElementById(`group-lib-${groupKey}`).value);
    const seriesName = document.getElementById(`group-series-${groupKey}`).value.trim();
    
    if (!libraryId) {
        alert('⚠️ Veuillez sélectionner une bibliothèque');
        return;
    }
    
    if (!seriesName) {
        alert('⚠️ Veuillez entrer un nom de série');
        return;
    }
    
    const library = allLibraries.find(l => l.id === libraryId);
    
    // ===== UTILISATION DE LA FONCTION AMÉLIORÉE =====
    const existingSeries = findExistingSeries(libraryId, seriesName);
    
    let destination;
    if (existingSeries) {
        console.log(`✅ Série existante trouvée: "${existingSeries.title}" (ID: ${existingSeries.id})`);
        destination = {
            library_id: libraryId,
            library_name: library.name,
            library_path: library.path,
            series_id: existingSeries.id,
            series_title: existingSeries.title,
            is_new_series: false
        };
    } else {
        console.log(`➕ Nouvelle série: "${seriesName}"`);
        destination = {
            library_id: libraryId,
            library_name: library.name,
            library_path: library.path,
            series_id: null,
            series_title: seriesName,
            is_new_series: true
        };
    }
    
    // Assigner tous les fichiers du groupe qui n'ont pas encore de destination
    let assignedCount = 0;
    importFiles.forEach((file, index) => {
        if ((file.parsed.title || 'Sans titre') === seriesTitle && !file.destination) {
            importFiles[index].destination = { ...destination };
            assignedCount++;
        }
    });
    
    alert(`✅ ${assignedCount} fichier(s) assigné(s) à "${seriesName}"${existingSeries ? ' (série existante)' : ' (nouvelle série)'}`);
    updateImportStats();
    displayImportFiles();
}

function removeGroupDestination(seriesTitle) {
    if (!confirm(`Retirer l'assignation de tous les fichiers de "${seriesTitle}" ?`)) {
        return;
    }
    
    const groupKey = seriesTitle.replace(/\s+/g, '-').replace(/[^a-zA-Z0-9-_]/g, '');
    importFiles.forEach((file, index) => {
        if ((file.parsed.title || 'Sans titre') === seriesTitle) {
            delete importFiles[index].destination;
        }
    });
    
    updateImportStats();
    displayImportFiles();
}

function updateQuickSeriesOptions(fileIndex) {
    const libraryId = parseInt(document.getElementById(`quick-lib-${fileIndex}`).value);
    const datalist = document.getElementById(`series-list-${fileIndex}`);
    
    if (!libraryId) {
        datalist.innerHTML = '';
        return;
    }
    
    const series = librariesSeriesMap[libraryId] || [];
    datalist.innerHTML = series.map(s => `<option value="${escapeHtml(s.title)}"></option>`).join('');
}

function quickAssign(fileIndex) {
    const libraryId = parseInt(document.getElementById(`quick-lib-${fileIndex}`).value);
    const seriesName = document.getElementById(`quick-series-${fileIndex}`).value.trim();
    
    if (!libraryId) {
        alert('⚠️ Veuillez sélectionner une bibliothèque');
        return;
    }
    
    if (!seriesName) {
        alert('⚠️ Veuillez entrer un nom de série');
        return;
    }
    
    const library = allLibraries.find(l => l.id === libraryId);
    
    // ===== UTILISATION DE LA FONCTION AMÉLIORÉE =====
    const existingSeries = findExistingSeries(libraryId, seriesName);
    
    if (existingSeries) {
        // Série existante
        importFiles[fileIndex].destination = {
            library_id: libraryId,
            library_name: library.name,
            library_path: library.path,
            series_id: existingSeries.id,
            series_title: existingSeries.title,
            is_new_series: false
        };
    } else {
        // Nouvelle série
        importFiles[fileIndex].destination = {
            library_id: libraryId,
            library_name: library.name,
            library_path: library.path,
            series_id: null,
            series_title: seriesName,
            is_new_series: true
        };
    }
    
    updateImportStats();
    displayImportFiles();
}

function openDestinationModal(fileIndex) {
    console.debug('openDestinationModal called with index=', fileIndex);
    currentFileIndex = fileIndex;
    const file = importFiles[fileIndex];
    
    document.getElementById('file-to-assign').textContent = `Fichier: ${file.filename}`;
    
    // Remplir la liste des bibliothèques
    const librarySelect = document.getElementById('destination-library');
    librarySelect.innerHTML = '<option value="">-- Sélectionner une bibliothèque --</option>' +
        allLibraries.map(lib => `<option value="${lib.id}">${escapeHtml(lib.name)}</option>`).join('');
    
    // Si déjà assigné, pré-remplir
    if (file.destination) {
        librarySelect.value = file.destination.library_id;
        loadLibrarySeries();
        setTimeout(() => {
            document.getElementById('destination-series').value = file.destination.series_id || '__new__';
            if (file.destination.is_new_series) {
                document.getElementById('new-series-name-group').style.display = 'block';
                document.getElementById('new-series-name').value = file.destination.series_title;
            }
        }, 100);
    }
    
    document.getElementById('select-destination-modal').classList.add('active');
}

function closeDestinationModal() {
    document.getElementById('select-destination-modal').classList.remove('active');
    document.getElementById('destination-library').value = '';
    document.getElementById('destination-series').value = '';
    document.getElementById('new-series-name-group').style.display = 'none';
    document.getElementById('new-series-name').value = '';
    currentFileIndex = -1;
}

function loadLibrarySeries() {
    const libraryId = document.getElementById('destination-library').value;
    const seriesSelect = document.getElementById('destination-series');
    
    if (!libraryId) {
        seriesSelect.innerHTML = '<option value="">-- Sélectionner une série --</option>';
        return;
    }
    
    const series = librariesSeriesMap[libraryId] || [];
    seriesSelect.innerHTML = '<option value="">-- Sélectionner une série --</option>' +
        '<option value="__new__">➕ Créer une nouvelle série</option>' +
        series.map(s => `<option value="${s.id}">${escapeHtml(s.title)}</option>`).join('');
    
    seriesSelect.onchange = function() {
        const newSeriesGroup = document.getElementById('new-series-name-group');
        if (this.value === '__new__') {
            newSeriesGroup.style.display = 'block';
            // Pré-remplir avec le titre parsé
            const file = importFiles[currentFileIndex];
            document.getElementById('new-series-name').value = file.parsed.title || '';
        } else {
            newSeriesGroup.style.display = 'none';
        }
    };
}

function assignDestination() {
    console.debug('assignDestination called, currentFileIndex=', currentFileIndex);
    const libraryId = parseInt(document.getElementById('destination-library').value);
    const seriesValue = document.getElementById('destination-series').value;
    
    if (!libraryId || !seriesValue) {
        alert('⚠️ Veuillez sélectionner une bibliothèque et une série');
        return;
    }
    
    let library = allLibraries.find(l => l.id === libraryId);
    if (!library) {
        // tolerate string ids
        library = allLibraries.find(l => parseInt(l.id) === libraryId);
    }
    console.debug('assignDestination: libraryId=', libraryId, 'seriesValue=', seriesValue, 'library=', library);
    let destination;
    
    if (seriesValue === '__new__') {
        const newSeriesName = document.getElementById('new-series-name').value.trim();
        if (!newSeriesName) {
            alert('⚠️ Veuillez entrer un nom pour la nouvelle série');
            return;
        }
        
        destination = {
            library_id: libraryId,
            library_name: library.name,
            library_path: library.path,
            series_id: null,
            series_title: newSeriesName,
            is_new_series: true
        };
    } else {
        const seriesId = parseInt(seriesValue);
        const seriesList = librariesSeriesMap[libraryId] || librariesSeriesMap[String(libraryId)] || [];
        const series = seriesList.find(s => parseInt(s.id) === seriesId);

        if (!series) {
            alert('⚠️ Série introuvable dans la bibliothèque sélectionnée. Vérifiez la bibliothèque choisie.');
            console.warn('assignDestination: series not found', { libraryId, seriesId, seriesList });
            return;
        }

        destination = {
            library_id: libraryId,
            library_name: library.name,
            library_path: library.path,
            series_id: seriesId,
            series_title: series.title,
            is_new_series: false
        };
    }
    
    importFiles[currentFileIndex].destination = destination;
    
    updateImportStats();
    displayImportFiles();
    closeDestinationModal();
}

function removeDestination(fileIndex) {
    delete importFiles[fileIndex].destination;
    updateImportStats();
    displayImportFiles();
}

function calculateSimilarity(str1, str2) {
    // Calculer la similarité entre deux chaînes
    if (str1 === str2) return 100;
    
    // Si une chaîne contient l'autre
    const shorter = str1.length < str2.length ? str1 : str2;
    const longer = str1.length >= str2.length ? str1 : str2;
    
    if (longer.includes(shorter)) {
        return (shorter.length / longer.length) * 90;
    }
    
    // Calcul de distance basique (nombre de mots en commun)
    const words1 = str1.split(' ').filter(w => w.length > 2);
    const words2 = str2.split(' ').filter(w => w.length > 2);
    
    let commonWords = 0;
    for (const word of words1) {
        if (words2.includes(word)) {
            commonWords++;
        }
    }
    
    if (words1.length === 0 || words2.length === 0) return 0;
    
    // Score basé sur le ratio de mots communs
    const ratio = commonWords / Math.max(words1.length, words2.length);
    return ratio * 100;
}

async function autoMatchAll() {
    if (allLibraries.length === 0) {
        alert('⚠️ Aucune bibliothèque disponible');
        return;
    }

    let matchCount = 0;

    for (let file of importFiles) {
        if (file.destination) continue; // Déjà assigné
        
        const parsedTitle = normalizeTitle(file.parsed.title);
        
        // Chercher une correspondance dans toutes les bibliothèques
        let bestMatch = null;
        let bestScore = 0;
        
        for (const lib of allLibraries) {
            const series = librariesSeriesMap[lib.id] || [];
            
            for (const s of series) {
                const seriesTitle = normalizeTitle(s.title);
                
                // Calculer le score de similarité
                const score = calculateSimilarity(parsedTitle, seriesTitle);
                
                if (score > bestScore) {
                    bestMatch = { library: lib, series: s };
                    bestScore = score;
                }
                
                // Si correspondance parfaite, arrêter
                if (score === 100) break;
            }
            
            if (bestScore === 100) break;
        }
        
        // Assigner si correspondance >= 70%
        if (bestMatch && bestScore >= 70) {
            file.destination = {
                library_id: bestMatch.library.id,
                library_name: bestMatch.library.name,
                library_path: bestMatch.library.path,
                series_id: bestMatch.series.id,
                series_title: bestMatch.series.title,
                is_new_series: false
            };
            matchCount++;
        }
    }

    alert(`✅ ${matchCount} fichier(s) assigné(s) automatiquement`);
    updateImportStats();
    displayImportFiles();
}

async function executeImport() {
    const filesToImport = importFiles.filter(f => f.destination);
    
    if (filesToImport.length === 0) {
        alert('⚠️ Aucun fichier à importer');
        return;
    }

    const importPath = document.getElementById('import-path').value;

    if (!confirm(`Voulez-vous importer ${filesToImport.length} fichier(s) ?\n\nLes fichiers seront déplacés vers leurs destinations.\n\nRègles de gestion des doublons :\n- Si le nouveau fichier est plus gros : remplacement (ancien → _old_files)\n- Si le nouveau fichier est plus petit : ignoré (→ _doublons)`)) {
        return;
    }

    const importBtn = document.getElementById('import-btn');
    importBtn.disabled = true;
    importBtn.textContent = '⏳ Import en cours...';

    try {
        const response = await fetch('/api/import/execute', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ 
                files: filesToImport,
                import_path: importPath
            })
        });

        const data = await response.json();

        if (data.success) {
            let message = `✅ Import terminé !\n\n`;
            message += `📥 Importés : ${data.imported_count}\n`;
            if (data.replaced_count > 0) {
                message += `🔄 Remplacés : ${data.replaced_count} (anciens → _old_files)\n`;
            }
            if (data.skipped_count > 0) {
                message += `⏭️ Ignorés : ${data.skipped_count} (doublons → _doublons)\n`;
            }
            if (data.failed_count > 0) {
                message += `❌ Échecs : ${data.failed_count}\n`;
            }
            if (data.cleaned_directories > 0) {
                message += `🧹 Répertoires vides nettoyés : ${data.cleaned_directories}\n`;
            }
            
            alert(message);
            
            if (data.failed_count > 0) {
                console.log('Échecs:', data.failures);
            }
            
            // Recharger le scan
            await scanImportDirectory();
        } else {
            alert('❌ Erreur: ' + (data.error || 'Erreur inconnue'));
        }
    } catch (error) {
        alert('❌ Erreur de connexion: ' + error.message);
    } finally {
        importBtn.disabled = false;
        importBtn.textContent = '✅ Importer les fichiers sélectionnés';
    }
}

function clearImport() {
    if (!confirm('Voulez-vous effacer tous les résultats du scan ?')) {
        return;
    }
    
    importFiles = [];
    document.getElementById('scan-results').style.display = 'none';
    document.getElementById('import-path').value = '';
}

async function cleanupEmptyDirectories() {
    const importPath = document.getElementById('import-path').value;
    
    if (!importPath) {
        alert('⚠️ Veuillez d\'abord sélectionner un répertoire d\'import');
        return;
    }

    if (!confirm('Nettoyer les répertoires vides du répertoire d\'import ?\n\nLes répertoires _old_files et _doublons ne seront pas touchés.')) {
        return;
    }

    try {
        const response = await fetch('/api/import/cleanup', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ path: importPath })
        });

        const data = await response.json();

        if (data.success) {
            if (data.cleaned_directories > 0) {
                alert(`🧹 Nettoyage terminé !\n\n${data.cleaned_directories} répertoire(s) vide(s) supprimé(s)`);
            } else {
                alert('✅ Aucun répertoire vide à nettoyer');
            }
        } else {
            alert('❌ Erreur: ' + (data.error || 'Erreur inconnue'));
        }
    } catch (error) {
        alert('❌ Erreur de connexion: ' + error.message);
    }
}

function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB', 'TB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return Math.round(bytes / Math.pow(k, i) * 100) / 100 + ' ' + sizes[i];
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

// ===== FONCTIONS D'IMPORT AUTOMATIQUE =====

async function loadAutoImportConfig() {
    try {
        const response = await fetch('/api/import/config');
        const config = await response.json();
        
        document.getElementById('auto-import-enabled').checked = config.auto_import_enabled;
        document.getElementById('auto-assign-enabled').checked = config.auto_assign_enabled;
        document.getElementById('auto-import-path').value = config.import_path || '';
        document.getElementById('auto-import-interval').value = config.auto_import_interval || 60;
        document.getElementById('auto-import-interval-unit').value = config.auto_import_interval_unit || 'minutes';
        
        showAutoImportStatus('Configuration chargée', 'success');
    } catch (error) {
        console.error('Erreur lors du chargement de la configuration:', error);
        showAutoImportStatus('Erreur lors du chargement', 'error');
    }
}

async function saveAutoImportConfig() {
    try {
        const config = {
            auto_import_enabled: document.getElementById('auto-import-enabled').checked,
            auto_assign_enabled: document.getElementById('auto-assign-enabled').checked,
            import_path: document.getElementById('auto-import-path').value,
            auto_import_interval: parseInt(document.getElementById('auto-import-interval').value),
            auto_import_interval_unit: document.getElementById('auto-import-interval-unit').value
        };
        
        const response = await fetch('/api/import/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        if (!response.ok) {
            throw new Error('Erreur lors de la sauvegarde');
        }
        
        const result = await response.json();
        if (result.success) {
            showAutoImportStatus(
                'Configuration sauvegardée avec succès' + 
                (config.auto_import_enabled ? '. Import automatique activé ✓' : ''),
                'success'
            );
        } else {
            showAutoImportStatus('Erreur: ' + result.error, 'error');
        }
    } catch (error) {
        console.error('Erreur lors de la sauvegarde:', error);
        showAutoImportStatus('Erreur lors de la sauvegarde', 'error');
    }
}

async function testAutoImport() {
    try {
        const btn = document.getElementById('test-auto-import-btn');
        btn.disabled = true;
        btn.textContent = '🔄 Import en cours...';
        
        const config = {
            auto_import_enabled: document.getElementById('auto-import-enabled').checked,
            auto_assign_enabled: document.getElementById('auto-assign-enabled').checked,
            import_path: document.getElementById('auto-import-path').value,
            auto_import_interval: parseInt(document.getElementById('auto-import-interval').value),
            auto_import_interval_unit: document.getElementById('auto-import-interval-unit').value
        };
        
        if (!config.import_path) {
            throw new Error('Veuillez spécifier un chemin d\'import');
        }
        
        // Sauvegarder la config
        let response = await fetch('/api/import/config', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify(config)
        });
        
        if (!response.ok) {
            throw new Error('Erreur lors de la sauvegarde de la configuration');
        }
        
        // Utiliser le chemin du config pour scanner au lieu du chemin manuel
        document.getElementById('import-path').value = config.import_path;
        
        // Scanner le répertoire (utilise la fonction existante)
        showAutoImportStatus('Scan en cours...', 'info');
        await scanImportDirectory();
        
        // Vérifier si des fichiers ont été trouvés
        if (importFiles.length === 0) {
            showAutoImportStatus('✓ Aucun fichier trouvé à importer', 'success');
            return;
        }
        
        // Auto-assigner les fichiers (utilise la fonction existante)
        if (config.auto_assign_enabled) {
            showAutoImportStatus('Auto-assignation en cours...', 'info');
            await autoMatchAll();
        }
        
        // Vérifier s'il y a des fichiers assignés
        const assignedFiles = importFiles.filter(f => f.destination);
        if (assignedFiles.length === 0) {
            showAutoImportStatus(
                `⚠️ Aucun fichier auto-assignable (${importFiles.length} détecté(s), 0 assigné(s))`,
                'error'
            );
            return;
        }
        
        // Exécuter l'import (utilise la fonction existante)
        showAutoImportStatus('Import en cours...', 'info');
        await executeImport();
        
        showAutoImportStatus(
            `✅ Import automatique terminé!`,
            'success'
        );
        
    } catch (error) {
        console.error('Erreur lors du test:', error);
        showAutoImportStatus('Erreur: ' + error.message, 'error');
    } finally {
        const btn = document.getElementById('test-auto-import-btn');
        btn.disabled = false;
        btn.textContent = '▶️ Testez l\'import maintenant';
    }
}

function showAutoImportStatus(message, type) {
    const statusDiv = document.getElementById('auto-import-status');
    statusDiv.textContent = message;
    statusDiv.style.display = 'block';
    
    if (type === 'success') {
        statusDiv.style.background = '#d1fae5';
        statusDiv.style.color = '#065f46';
        statusDiv.style.borderLeft = '4px solid #10b981';
    } else if (type === 'info') {
        statusDiv.style.background = '#dbeafe';
        statusDiv.style.color = '#0c4a6e';
        statusDiv.style.borderLeft = '4px solid #3b82f6';
    } else {
        statusDiv.style.background = '#fee2e2';
        statusDiv.style.color = '#7f1d1d';
        statusDiv.style.borderLeft = '4px solid #ef4444';
    }
    
    // Masquer après 10 secondes (plus de temps pour lire les résultats d'import)
    // Mais pas pour 'info' car c'est temporaire
    if (type !== 'info') {
        setTimeout(() => {
            statusDiv.style.display = 'none';
        }, 10000);
    }
}

window.onclick = function(event) {
    const modal = document.getElementById('select-destination-modal');
    if (event.target == modal) {
        closeDestinationModal();
    }
}

// ===== HISTORIQUE DES IMPORTS =====
async function loadImportHistory() {
    try {
        const container = document.getElementById('history-container');
        const loading = document.getElementById('history-loading');
        
        loading.style.display = 'block';
        container.style.display = 'none';
        
        const response = await fetch('/api/import/history?limit=50');
        const data = await response.json();
        
        if (data.success && data.history && data.history.length > 0) {
            displayImportHistory(data.history);
            container.style.display = 'block';
            loading.style.display = 'none';
        } else {
            document.getElementById('history-empty').style.display = 'block';
            document.getElementById('history-table-wrapper').style.display = 'none';
            container.style.display = 'block';
            loading.style.display = 'none';
        }
    } catch (error) {
        console.error('Erreur chargement historique:', error);
        document.getElementById('history-loading').innerHTML = `<p style="color: red;">Erreur: ${error.message}</p>`;
    }
}

function displayImportHistory(history) {
    const tbody = document.getElementById('history-body');
    tbody.innerHTML = '';
    
    const tableWrapper = document.getElementById('history-table-wrapper');
    tableWrapper.style.display = 'table';
    document.getElementById('history-empty').style.display = 'none';
    
    history.forEach(operation => {
        const row = document.createElement('tr');
        row.style.borderBottom = '1px solid #e5e7eb';
        row.style.cursor = 'pointer';
        row.style.transition = 'background-color 0.2s';
        
        // Au survol, changer la couleur de fond
        row.onmouseover = () => row.style.background = '#fafafa';
        row.onmouseout = () => row.style.background = '';
        
        // Cliquer sur la ligne pour voir les détails
        row.onclick = () => showHistoryDetails(operation.operation_id);
        
        // Formater la date
        const date = new Date(operation.created_at);
        const dateStr = date.toLocaleString('fr-FR', {
            year: 'numeric',
            month: '2-digit',
            day: '2-digit',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        // Déterminer la couleur du badge de statut
        let statusColor = '#8b5cf6';
        let statusText = operation.status;
        
        if (operation.status === 'completed') {
            statusColor = '#10b981';
            statusText = '✅ Complété';
        } else if (operation.status === 'started') {
            statusColor = '#f59e0b';
            statusText = '⏳ En cours';
        } else if (operation.status === 'undone') {
            statusColor = '#6b7280';
            statusText = '↩️ Annulé';
        } else if (operation.status === 'failed') {
            statusColor = '#ef4444';
            statusText = '❌ Échoué';
        }
        
        const statusBadge = `<span style="background: ${statusColor}; color: white; padding: 4px 8px; border-radius: 4px; font-size: 12px; font-weight: 600;">${statusText}</span>`;
        
        row.innerHTML = `
            <td style="padding: 10px;">${dateStr}</td>
            <td style="padding: 10px;">${statusBadge}</td>
            <td style="padding: 10px; text-align: center; font-weight: 500;">${operation.files_imported || 0}</td>
            <td style="padding: 10px; text-align: center; font-weight: 500;">${operation.files_replaced || 0}</td>
            <td style="padding: 10px; text-align: center; font-weight: 500;">${operation.files_skipped || 0}</td>
            <td style="padding: 10px; text-align: center; font-weight: 500;" style="color: ${operation.files_failed > 0 ? '#ef4444' : '#666'};">${operation.files_failed || 0}</td>
            <td style="padding: 10px; text-align: center;">
                <button class="btn" style="padding: 4px 8px; font-size: 12px; background: #8b5cf6; margin-right: 5px;" onclick="event.stopPropagation(); showHistoryDetails('${operation.operation_id}');">
                    📋 Détails
                </button>
                ${operation.status === 'completed' ? `
                    <button class="btn" style="padding: 4px 8px; font-size: 12px; background: #ef4444;" onclick="event.stopPropagation(); undoImportOperation('${operation.operation_id}');">
                        ↩️ Annuler
                    </button>
                ` : ''}
            </td>
        `;
        
        tbody.appendChild(row);
    });
}

async function showHistoryDetails(operationId) {
    try {
        const response = await fetch(`/api/import/history/${operationId}`);
        const data = await response.json();
        
        if (data.success && data.details) {
            const { operation, files } = data.details;
            
            let detailsHtml = `
                <div style="background: white; padding: 20px; border-radius: 8px; margin-top: 15px; border: 2px solid #8b5cf6;">
                    <button style="float: right; background: none; border: none; font-size: 20px; cursor: pointer;" onclick="this.parentElement.style.display='none';">×</button>
                    <h3 style="color: #8b5cf6; margin-top: 0;">Détails de l'opération</h3>
                    <p><strong>ID:</strong> ${operation.operation_id}</p>
                    <p><strong>Date:</strong> ${new Date(operation.created_at).toLocaleString('fr-FR')}</p>
                    <p><strong>Status:</strong> ${operation.status}</p>
                    <p><strong>Chemin:</strong> ${operation.import_path}</p>
                    
                    <div style="margin-top: 15px; padding: 15px; background: #f0f4ff; border-radius: 4px;">
                        <h4 style="margin-top: 0;">Résumé</h4>
                        <p>📥 Importés: <strong>${operation.files_imported}</strong></p>
                        <p>🔄 Remplacés: <strong>${operation.files_replaced}</strong></p>
                        <p>⏭️ Ignorés: <strong>${operation.files_skipped}</strong></p>
                        <p>❌ Erreurs: <strong>${operation.files_failed}</strong></p>
                    </div>
                    
                    ${files && files.length > 0 ? `
                        <h4 style="margin-top: 20px;">Fichiers (${files.length})</h4>
                        <table style="width: 100%; border-collapse: collapse; font-size: 13px;">
                            <thead>
                                <tr style="background: #e9d5ff; border-bottom: 1px solid #8b5cf6;">
                                    <th style="padding: 8px; text-align: left;">Fichier</th>
                                    <th style="padding: 8px; text-align: left;">Série</th>
                                    <th style="padding: 8px; text-align: left;">Action</th>
                                    <th style="padding: 8px; text-align: left;">Status</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${files.map(f => `
                                    <tr style="border-bottom: 2px solid #e5e7eb;">
                                        <td style="padding: 8px; font-weight: 500;">${f.filename}</td>
                                        <td style="padding: 8px;">${f.series_title || '-'}</td>
                                        <td style="padding: 8px;">
                                            <span style="background: #dbeafe; color: #0c4a6e; padding: 4px 8px; border-radius: 3px; font-size: 11px; font-weight: 500;">${f.action || '-'}</span>
                                        </td>
                                        <td style="padding: 8px;">
                                            <span style="background: ${f.status === 'success' ? '#d1fae5' : '#fee2e2'}; color: ${f.status === 'success' ? '#065f46' : '#7f1d1d'}; padding: 4px 8px; border-radius: 3px; font-size: 11px; font-weight: 500;">${f.status || '-'}</span>
                                        </td>
                                    </tr>
                                    <tr style="background: #fafafa; border-bottom: 1px solid #e5e7eb;">
                                        <td colspan="4" style="padding: 10px;">
                                            <div style="font-size: 12px; color: #666;">
                                                <div><strong>Source:</strong> ${f.source_path || '-'}</div>
                                                <div><strong>Destination:</strong> ${f.destination_path || '-'}</div>
                                                ${f.message ? `<div style="color: #ef4444; margin-top: 5px;"><strong>Message:</strong> ${f.message}</div>` : ''}
                                            </div>
                                        </td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    ` : '<p style="color: #999;">Aucun fichier enregistré</p>'}
                </div>
            `;
            
            // Insérer après la table d'historique ou au début du container
            let detailsDiv = document.getElementById('history-details');
            if (!detailsDiv) {
                detailsDiv = document.createElement('div');
                detailsDiv.id = 'history-details';
                document.getElementById('history-container').appendChild(detailsDiv);
            }
            
            detailsDiv.innerHTML = detailsHtml;
            
            // Scroll vers les détails
            detailsDiv.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        } else {
            alert('Erreur: Impossible de charger les détails');
        }
    } catch (error) {
        console.error('Erreur:', error);
        alert('Erreur: ' + error.message);
    }
}

async function undoImportOperation(operationId) {
    if (!confirm('Êtes-vous sûr de vouloir annuler cette opération d\'import ?\n\nLes fichiers importés seront déplacés vers un dossier _undo.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/import/history/${operationId}/undo`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        const data = await response.json();
        
        if (data.success) {
            alert(`✅ Annulation réussie!\n\n${data.message}`);
            loadImportHistory(); // Recharger l'historique
        } else {
            alert(`❌ Erreur: ${data.error}`);
        }
    } catch (error) {
        console.error('Erreur:', error);
        alert('Erreur: ' + error.message);
    }
}

window.addEventListener('load', function() {
    loadAllLibraries();
    loadImportPath();
    loadAutoImportConfig();
    loadImportHistory();
});