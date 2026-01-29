let currentResults = [];
let allResults = [];

function formatBytes(bytes) {
    if (!bytes) return 'N/A';
    const b = parseInt(bytes);
    if (b < 1024) return b + ' B';
    if (b < 1048576) return (b / 1024).toFixed(1) + ' KB';
    if (b < 1073741824) return (b / 1048576).toFixed(1) + ' MB';
    return (b / 1073741824).toFixed(2) + ' GB';
}

// Fonction pour décoder les caractères encodés (comme %20)
function decodeFilename(filename) {
    try {
        return decodeURIComponent(filename);
    } catch (e) {
        // Si le décodage échoue, retourner le nom original
        return filename;
    }
}

async function searchLinks() {
    const query = document.getElementById('searchInput').value;
    const volume = document.getElementById('volumeInput').value;
    const category = document.getElementById('categorySelect').value;
    
    if (!query && !volume && !category) {
        alert('Veuillez entrer au moins un critère de recherche');
        return;
    }

    const resultsDiv = document.getElementById('results');
    resultsDiv.innerHTML = '<div class="loading">⏳ Recherche en cours...</div>';
    
    // Cacher la barre de filtrage pendant la recherche
    document.getElementById('filterBox').style.display = 'none';

    try {
        const params = new URLSearchParams();
        if (query) params.append('query', query);
        if (volume) params.append('volume', volume);
        if (category) params.append('category', category);

        const response = await fetch(`/api/search?${params}`);
        const data = await response.json();

        allResults = data.results || [];
        currentResults = allResults;
        displayResults(currentResults);
        
        // Afficher la barre de filtrage si on a des résultats
        if (allResults.length > 0) {
            document.getElementById('filterBox').style.display = 'block';
            updateFilterStats();
        }
    } catch (error) {
        resultsDiv.innerHTML = '<div class="no-results"><h2>Erreur</h2><p>' + error + '</p></div>';
    }
}

function filterResults() {
    const filterText = document.getElementById('filterInput').value.toLowerCase();
    
    if (!filterText) {
        currentResults = allResults;
    } else {
        currentResults = allResults.filter(result => {
            const title = result.thread_title.toLowerCase();
            const filename = decodeFilename(result.filename).toLowerCase();
            const volume = result.volume ? result.volume.toString() : '';
            const category = result.forum_category ? result.forum_category.toLowerCase() : '';
            
            return title.includes(filterText) || 
                   filename.includes(filterText) || 
                   volume.includes(filterText) ||
                   category.includes(filterText);
        });
    }
    
    displayResults(currentResults);
    updateFilterStats();
}

function clearFilter() {
    document.getElementById('filterInput').value = '';
    currentResults = allResults;
    displayResults(currentResults);
    updateFilterStats();
}

function updateFilterStats() {
    document.getElementById('filteredCount').textContent = currentResults.length;
    document.getElementById('totalCount').textContent = allResults.length;
}

function displayResults(results) {
    const resultsDiv = document.getElementById('results');
    
    if (results.length === 0) {
        resultsDiv.innerHTML = `
            <div class="no-results">
                <h2>😕 Aucun résultat</h2>
                <p>Essayez avec d'autres mots-clés ou ajustez le filtre</p>
            </div>
        `;
        return;
    }

    // Groupe les résultats par thread
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

    let html = '';
    if (results.length > 1) {
        html += `<button class="copy-all-button" onclick="copyAllLinks()">📋 Copier tous les liens (${results.length})</button>`;
    }

    for (const threadId in grouped) {
        const thread = grouped[threadId];
        
        html += `
            <div class="result-card">
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
            // Décoder le nom de fichier pour l'affichage
            const decodedFilename = decodeFilename(link.filename);
            
            html += `
                <div class="file-item">
                    <div style="display: flex; align-items: center; gap: 10px; flex: 1;">
                        ${volumeDisplay}
                        <div class="file-name" title="${decodedFilename}">${decodedFilename}</div>
                    </div>
                    <div class="file-size">${formatBytes(link.filesize)}</div>
                    <button class="copy-button" onclick="copyLink('${escapeForAttribute(link.link)}', this)">📋 Copier</button>
                    <button class="add-button" onclick="addToEmule('${escapeForAttribute(link.link)}', this)" id="add-${threadId}-${index}">
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

    resultsDiv.innerHTML = html;
    
    // Vérifie si aMule est activé pour afficher/cacher les boutons
    checkEmuleStatus();
}

// Fonction pour échapper les caractères spéciaux dans les attributs HTML
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

async function copyAllLinks() {
    const links = currentResults.map(r => r.link).join('\n');
    try {
        await navigator.clipboard.writeText(links);
        alert(`✓ ${currentResults.length} liens copiés dans le presse-papier!`);
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

function openSettings() {
    document.getElementById('settingsModal').style.display = 'block';
    loadSettings();
}

function closeSettings() {
    document.getElementById('settingsModal').style.display = 'none';
}

async function loadSettings() {
    try {
        const response = await fetch('/api/emule/config');
        const config = await response.json();
        
        document.getElementById('emuleEnabled').checked = config.enabled;
        document.getElementById('emuleHost').value = config.host;
        document.getElementById('emuleEcPort').value = config.ec_port;
        document.getElementById('emulePassword').value = config.password;
    } catch (error) {
        showMessage('Erreur lors du chargement de la configuration', 'error');
    }
}

async function saveSettings() {
    const config = {
        enabled: document.getElementById('emuleEnabled').checked,
        type: 'amule',
        host: document.getElementById('emuleHost').value,
        ec_port: parseInt(document.getElementById('emuleEcPort').value),
        password: document.getElementById('emulePassword').value
    };

    try {
        const response = await fetch('/api/emule/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });

        const data = await response.json();
        
        if (data.success) {
            showMessage('✓ Configuration enregistrée avec succès!', 'success');
            checkEmuleStatus();
        } else {
            showMessage('✗ Erreur: ' + data.error, 'error');
        }
    } catch (error) {
        showMessage('✗ Erreur: ' + error, 'error');
    }
}

async function testConnection() {
    showMessage('⏳ Test de connexion...', 'success');
    
    try {
        const response = await fetch('/api/emule/test');
        const data = await response.json();
        
        if (data.success) {
            showMessage('✓ Connexion réussie à aMule!', 'success');
        } else {
            showMessage('✗ Échec de la connexion: ' + data.error, 'error');
        }
    } catch (error) {
        showMessage('✗ Erreur: ' + error, 'error');
    }
}

function showMessage(text, type) {
    const msg = document.getElementById('settingsMessage');
    msg.textContent = text;
    msg.className = 'message ' + type;
    msg.style.display = 'block';
    
    setTimeout(() => {
        msg.style.display = 'none';
    }, 5000);
}

// Ferme le modal si on clique en dehors
window.onclick = function(event) {
    const modal = document.getElementById('settingsModal');
    if (event.target == modal) {
        closeSettings();
    }
}

// Charge le statut au démarrage
checkEmuleStatus();
