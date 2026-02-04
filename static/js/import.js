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

window.onclick = function(event) {
    const modal = document.getElementById('select-destination-modal');
    if (event.target == modal) {
        closeDestinationModal();
    }
}

window.addEventListener('load', function() {
    loadAllLibraries();
    loadImportPath();
});