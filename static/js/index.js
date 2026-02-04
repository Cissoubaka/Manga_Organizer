let libraries = [];

async function loadLibraries() {
    const container = document.getElementById('libraries-container');
    
    try {
        const response = await fetch('/api/libraries');
        libraries = await response.json();

        if (libraries.length === 0) {
            container.innerHTML = `
                <div class="no-data">
                    <div class="no-data-icon">📚</div>
                    <h3>Aucune bibliothèque</h3>
                    <p>Créez votre première bibliothèque pour commencer</p>
                </div>
            `;
            return;
        }

        displayLibraries(libraries);
    } catch (error) {
        container.innerHTML = `
            <div class="no-data">
                <h3>Erreur de chargement</h3>
                <p>${error.message}</p>
            </div>
        `;
    }
}

function displayLibraries(libs) {
    const container = document.getElementById('libraries-container');
    
    const cardsHtml = libs.map(lib => {
        return `
            <div class="library-card">
                <div class="library-header">
                    <div style="flex: 1;">
                        <div class="library-name">${escapeHtml(lib.name)}</div>
                        ${lib.description ? `<div class="library-description">${escapeHtml(lib.description)}</div>` : ''}
                    </div>
                </div>
                
                <div class="library-path">${escapeHtml(lib.path)}</div>
                
                <div class="library-stats">
                    <div class="stat-item">
                        <div class="stat-value">${lib.series_count}</div>
                        <div class="stat-label">Séries</div>
                    </div>
                    <div class="stat-item">
                        <div class="stat-value">${lib.volumes_count}</div>
                        <div class="stat-label">Volumes</div>
                    </div>
                </div>

                <div class="library-actions">
                    <button class="btn" onclick="window.location.href='/library/${lib.id}'">
                        📖 Ouvrir
                    </button>
                    <button class="btn" onclick="scanLibrary(${lib.id})">
                        🔄 Scanner
                    </button>
                    <button class="btn btn-danger" onclick="deleteLibraryConfirm(${lib.id})">
                        🗑️ Supprimer
                    </button>
                </div>

                <div class="library-footer">
                    ${lib.last_scanned ? 
                        `<span class="badge badge-success">Dernière analyse: ${new Date(lib.last_scanned).toLocaleString('fr-FR')}</span>` :
                        `<span class="badge badge-warning">Jamais analysée</span>`
                    }
                </div>
            </div>
        `;
    }).join('');
    
    container.innerHTML = `<div class="libraries-grid">${cardsHtml}</div>`;
}

function openCreateModal() {
    document.getElementById('create-modal').classList.add('active');
}

function closeCreateModal() {
    document.getElementById('create-modal').classList.remove('active');
    document.getElementById('create-form').reset();
}

async function createLibrary(event) {
    event.preventDefault();

    const name = document.getElementById('library-name').value;
    const path = document.getElementById('library-path').value;
    const description = document.getElementById('library-description').value;

    try {
        const response = await fetch('/api/libraries', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ name, path, description })
        });

        const data = await response.json();

        if (data.success) {
            alert('✅ Bibliothèque créée avec succès !');
            closeCreateModal();
            loadLibraries();
        } else {
            alert('❌ Erreur: ' + (data.error || 'Erreur inconnue'));
        }
    } catch (error) {
        alert('❌ Erreur de connexion: ' + error.message);
    }
}

async function scanLibrary(libraryId) {
    if (!confirm('Voulez-vous scanner cette bibliothèque ? Cela peut prendre du temps.')) {
        return;
    }

    try {
        const response = await fetch(`/api/scan/${libraryId}`);
        const data = await response.json();

        if (data.success) {
            alert(`✅ Scan terminé ! ${data.series_count} séries trouvées.`);
            loadLibraries();
        } else {
            alert('❌ Erreur: ' + (data.error || 'Erreur inconnue'));
        }
    } catch (error) {
        alert('❌ Erreur: ' + error.message);
    }
}

async function deleteLibraryConfirm(libraryId) {
    const library = libraries.find(lib => lib.id === libraryId);
    if (!library) return;
    
    const libraryName = library.name;
    
    if (!confirm(`Voulez-vous vraiment supprimer la bibliothèque "${libraryName}" ?\n\nCela supprimera toutes les données associées (séries et volumes scannés).\nLes fichiers sur votre disque ne seront PAS supprimés.`)) {
        return;
    }

    try {
        const response = await fetch(`/api/libraries/${libraryId}`, {
            method: 'DELETE'
        });

        const data = await response.json();

        if (data.success) {
            alert('✅ Bibliothèque supprimée avec succès !');
            loadLibraries();
        } else {
            alert('❌ Erreur: ' + (data.error || 'Erreur inconnue'));
        }
    } catch (error) {
        alert('❌ Erreur: ' + error.message);
    }
}


function handleFolderSelect(event) {
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
        
        document.getElementById('library-path').value = folderPath;
    }
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
    const modal = document.getElementById('create-modal');
    if (event.target == modal) {
        closeCreateModal();
    }
}

window.addEventListener('load', loadLibraries);