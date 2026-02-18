
let passwordVisible = false;
let ebdzPasswordVisible = false;

// ===== AMULE =====
async function loadSettings() {
    try {
        const response = await fetch('/api/emule/config');
        const config = await response.json();
        
        document.getElementById('emuleEnabled').checked = config.enabled;
        document.getElementById('emuleType').value = config.type || 'amule';
        document.getElementById('emuleHost').value = config.host;
        document.getElementById('emuleEcPort').value = config.ec_port;
        
        if (config.password && config.password !== '****') {
            document.getElementById('emulePassword').value = config.password;
        }
    } catch (error) {
        showMessage('settingsMessage', '❌ Erreur lors du chargement de la configuration', 'error');
    }
}

async function saveSettings() {
    const config = {
        enabled: document.getElementById('emuleEnabled').checked,
        type: document.getElementById('emuleType').value,
        host: document.getElementById('emuleHost').value,
        ec_port: parseInt(document.getElementById('emuleEcPort').value),
        password: document.getElementById('emulePassword').value
    };

    if (config.enabled && !config.password) {
        showMessage('settingsMessage', '⚠️ Veuillez entrer un mot de passe EC', 'warning');
        return;
    }

    try {
        const response = await fetch('/api/emule/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        const data = await response.json();
        
        if (data.success) {
            showMessage('settingsMessage', '✅ Configuration enregistrée avec succès !', 'success');
        } else {
            showMessage('settingsMessage', '❌ Erreur: ' + data.error, 'error');
        }
    } catch (error) {
        showMessage('settingsMessage', '❌ Erreur de connexion: ' + error.message, 'error');
    }
}

async function testConnection() {
    showMessage('settingsMessage', '⏳ Test de connexion en cours...', 'info');
    try {
        const response = await fetch('/api/emule/test');
        const data = await response.json();
        if (data.success) {
            showMessage('settingsMessage', '✅ Connexion réussie à aMule/eMule !', 'success');
        } else {
            showMessage('settingsMessage', '❌ Échec de la connexion: ' + data.error, 'error');
        }
    } catch (error) {
        showMessage('settingsMessage', '❌ Erreur: ' + error.message, 'error');
    }
}

function resetSettings() {
    if (!confirm('Voulez-vous réinitialiser la configuration aMule/eMule ?')) return;
    document.getElementById('emuleEnabled').checked = false;
    document.getElementById('emuleType').value = 'amule';
    document.getElementById('emuleHost').value = '127.0.0.1';
    document.getElementById('emuleEcPort').value = '4712';
    document.getElementById('emulePassword').value = '';
    showMessage('settingsMessage', '🔄 Configuration réinitialisée', 'info');
}

function togglePassword() {
    const passwordInput = document.getElementById('emulePassword');
    const toggleButton = passwordInput.closest('.password-input-group').querySelector('.btn-toggle-password');
    passwordVisible = !passwordVisible;
    passwordInput.type = passwordVisible ? 'text' : 'password';
    toggleButton.textContent = passwordVisible ? '🙈 Masquer' : '👁️ Afficher';
}

// ===== EBDZ.NET =====
async function loadEbdzConfig() {
    try {
        const response = await fetch('/api/ebdz/config');
        const config = await response.json();

        document.getElementById('ebdzUsername').value = config.username || '';

        // Le serveur retourne '****' si un mot de passe existe.
        // On ne touche au champ que si c'est vide (pas de mot de passe enregistré).
        // Sinon on laisse ce qui est déjà dans le champ (valeur tapée ou précédente).
        if (!config.password) {
            document.getElementById('ebdzPassword').value = '';
        }

        // Charger les forums
        renderForumsList(config.forums || []);
    } catch (error) {
        showMessage('ebdzMessage', '❌ Erreur lors du chargement de la config ebdz', 'error');
    }
}

function renderForumsList(forums) {
    const list = document.getElementById('forumsList');
    const emptyState = document.getElementById('forumsEmptyState');

    list.innerHTML = '';

    if (forums.length === 0) {
        emptyState.style.display = 'block';
        return;
    }
    emptyState.style.display = 'none';

    forums.forEach((forum, index) => {
        list.appendChild(createForumRow(forum, index));
    });
    updateSelectAllState();
}

function createForumRow(forum = {}, index = 0) {
    const row = document.createElement('div');
    row.className = 'forum-row';
    row.dataset.index = index;
    row.innerHTML = `
        <div class="forum-row-header">
            <div style="display:flex; align-items:center; gap:10px;">
                <input type="checkbox" class="forum-select" checked onchange="updateSelectAllState()">
                <span class="forum-row-label">Forum #${index + 1}</span>
            </div>
            <button class="btn-remove-forum" onclick="removeForumRow(this)">✕</button>
        </div>
        <div class="forum-row-fields">
            <div class="form-group" style="flex:0 0 120px;">
                <label>Code du forum (fid)</label>
                <input type="number" class="forum-fid" value="${forum.fid || ''}" placeholder="ex: 29" min="1">
            </div>
            <div class="form-group" style="flex:1;">
                <label>Nom de la catégorie</label>
                <input type="text" class="forum-category" value="${forum.category || ''}" placeholder="ex: Mangas">
            </div>
            <div class="form-group" style="flex:0 0 140px;">
                <label>Max pages (optionnel)</label>
                <input type="number" class="forum-max-pages" value="${forum.max_pages !== null && forum.max_pages !== undefined ? forum.max_pages : ''}" placeholder="Tout" min="1">
            </div>
        </div>
    `;
    return row;
}

function addForumRow() {
    const list = document.getElementById('forumsList');
    const emptyState = document.getElementById('forumsEmptyState');
    const currentCount = list.querySelectorAll('.forum-row').length;

    list.appendChild(createForumRow({}, currentCount));
    emptyState.style.display = 'none';
    updateSelectAllState();
}

function removeForumRow(btn) {
    const row = btn.closest('.forum-row');
    row.remove();

    // Re-numéroter
    const list = document.getElementById('forumsList');
    list.querySelectorAll('.forum-row').forEach((r, i) => {
        r.dataset.index = i;
        r.querySelector('.forum-row-label').textContent = `Forum #${i + 1}`;
    });

    if (list.querySelectorAll('.forum-row').length === 0) {
        document.getElementById('forumsEmptyState').style.display = 'block';
    }
    updateSelectAllState();
}

function collectForums() {
    const forums = [];
    document.querySelectorAll('.forum-row').forEach(row => {
        const fid = row.querySelector('.forum-fid').value.trim();
        const category = row.querySelector('.forum-category').value.trim();
        const maxPages = row.querySelector('.forum-max-pages').value.trim();

        if (fid) {
            forums.push({
                fid: parseInt(fid),
                category: category || `Forum ${fid}`,
                max_pages: maxPages ? parseInt(maxPages) : null
            });
        }
    });
    return forums;
}

async function saveEbdzConfig() {
    const username = document.getElementById('ebdzUsername').value.trim();
    const password = document.getElementById('ebdzPassword').value;
    const forums = collectForums();

    if (!username) {
        showMessage('ebdzMessage', '⚠️ Veuillez entrer un nom d\'utilisateur', 'warning');
        return;
    }

    // Validation des forums
    for (const f of forums) {
        if (!f.category || f.category.trim() === '') {
            showMessage('ebdzMessage', '⚠️ Chaque forum doit avoir un nom de catégorie', 'warning');
            return;
        }
    }

    try {
        const response = await fetch('/api/ebdz/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ username, password, forums })
        });
        const data = await response.json();

        if (data.success) {
            showMessage('ebdzMessage', '✅ Configuration ebdz.net enregistrée !', 'success');
            showMessage('ebdzMessage2', '✅ Configuration enregistrée !', 'success');
            loadEbdzConfig(); // Recharger depuis le serveur pour sync
        } else {
            showMessage('ebdzMessage', '❌ Erreur: ' + data.error, 'error');
        }
    } catch (error) {
        showMessage('ebdzMessage', '❌ Erreur: ' + error.message, 'error');
    }
}

// ===== SELECTION DES FORUMS =====
function toggleSelectAll(checkbox) {
    document.querySelectorAll('.forum-select').forEach(cb => {
        cb.checked = checkbox.checked;
    });
}

function updateSelectAllState() {
    const all = document.querySelectorAll('.forum-select');
    const selectAll = document.getElementById('selectAllCheckbox');
    const label = document.getElementById('selectAllLabel');

    // Cacher "Tout sélectionner" si moins de 2 forums
    label.style.display = all.length >= 2 ? 'flex' : 'none';

    // Mettre à jour la classe visuelle sur chaque ligne
    all.forEach(cb => {
        cb.closest('.forum-row').classList.toggle('forum-selected', cb.checked);
    });

    if (all.length === 0) {
        selectAll.checked = false;
        selectAll.indeterminate = false;
        return;
    }

    const checkedCount = [...all].filter(cb => cb.checked).length;
    if (checkedCount === all.length) {
        selectAll.checked = true;
        selectAll.indeterminate = false;
    } else if (checkedCount === 0) {
        selectAll.checked = false;
        selectAll.indeterminate = false;
    } else {
        selectAll.indeterminate = true;
    }
}

async function runScraper() {
    // Collecter uniquement les fid des forums cochés
    const selectedFids = [];
    document.querySelectorAll('.forum-row').forEach(row => {
        if (row.querySelector('.forum-select').checked) {
            const fid = row.querySelector('.forum-fid').value.trim();
            if (fid) selectedFids.push(parseInt(fid));
        }
    });

    if (selectedFids.length === 0) {
        showMessage('ebdzMessage2', '⚠️ Aucun forum sélectionné. Cochez au moins un forum.', 'warning');
        return;
    }

    const btn = document.getElementById('btnRunScraper');
    btn.disabled = true;
    btn.textContent = '⏳ Scraping...';
    showMessage('ebdzMessage2', `⏳ Scraping en cours pour ${selectedFids.length} forum(s)… cela peut prendre du temps.`, 'info');

    try {
        const response = await fetch('/api/ebdz/scrape', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ fids: selectedFids })
        });
        const data = await response.json();

        if (data.success) {
            showMessage('ebdzMessage2', `✅ Scraping terminé ! ${data.total_links} liens récupérés sur ${data.forums_scraped} forum(s).`, 'success');
        } else {
            showMessage('ebdzMessage2', '❌ Erreur: ' + data.error, 'error');
        }
    } catch (error) {
        showMessage('ebdzMessage2', '❌ Erreur: ' + error.message, 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '🚀 Lancer le scraper';
    }
}

function toggleEbdzPassword() {
    const input = document.getElementById('ebdzPassword');
    const btn = input.closest('.password-input-group').querySelector('.btn-toggle-password');
    ebdzPasswordVisible = !ebdzPasswordVisible;
    input.type = ebdzPasswordVisible ? 'text' : 'password';
    btn.textContent = ebdzPasswordVisible ? '🙈 Masquer' : '👁️ Afficher';
}

// ===== PROWLARR =====
let prowlarrPasswordVisible = false;

async function loadProwlarrSettings() {
    try {
        const response = await fetch('/api/prowlarr/config');
        const config = await response.json();
        
        document.getElementById('prowlarrEnabled').checked = config.enabled;
        document.getElementById('prowlarrUrl').value = config.url || '';
        document.getElementById('prowlarrPort').value = config.port || 9696;
        
        if (config.api_key && config.api_key !== '****') {
            document.getElementById('prowlarrApiKey').value = config.api_key;
        }
    } catch (error) {
        showMessage('prowlarrMessage', '❌ Erreur lors du chargement de la configuration Prowlarr', 'error');
    }
}

async function saveProwlarrSettings() {
    const config = {
        enabled: document.getElementById('prowlarrEnabled').checked,
        url: document.getElementById('prowlarrUrl').value.trim(),
        port: parseInt(document.getElementById('prowlarrPort').value),
        api_key: document.getElementById('prowlarrApiKey').value
    };

    if (config.enabled && !config.url) {
        showMessage('prowlarrMessage', '⚠️ Veuillez entrer l\'URL du serveur Prowlarr', 'warning');
        return;
    }

    if (config.enabled && !config.api_key) {
        showMessage('prowlarrMessage', '⚠️ Veuillez entrer la clé API Prowlarr', 'warning');
        return;
    }

    try {
        const response = await fetch('/api/prowlarr/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        const data = await response.json();
        
        if (data.success) {
            showMessage('prowlarrMessage', '✅ Configuration Prowlarr enregistrée avec succès !', 'success');
        } else {
            showMessage('prowlarrMessage', '❌ Erreur: ' + data.error, 'error');
        }
    } catch (error) {
        showMessage('prowlarrMessage', '❌ Erreur de connexion: ' + error.message, 'error');
    }
}

async function testProwlarrConnection() {
    showMessage('prowlarrMessage', '⏳ Test de connexion en cours...', 'info');
    try {
        const response = await fetch('/api/prowlarr/test');
        const data = await response.json();
        if (data.success) {
            showMessage('prowlarrMessage', '✅ Connexion réussie à Prowlarr !', 'success');
        } else {
            showMessage('prowlarrMessage', '❌ Échec de la connexion: ' + data.error, 'error');
        }
    } catch (error) {
        showMessage('prowlarrMessage', '❌ Erreur: ' + error.message, 'error');
    }
}

function resetProwlarrSettings() {
    if (!confirm('Voulez-vous réinitialiser la configuration Prowlarr ?')) return;
    document.getElementById('prowlarrEnabled').checked = false;
    document.getElementById('prowlarrUrl').value = '';
    document.getElementById('prowlarrPort').value = '9696';
    document.getElementById('prowlarrApiKey').value = '';
    showMessage('prowlarrMessage', '🔄 Configuration réinitialisée', 'info');
}

function toggleProwlarrPassword() {
    const input = document.getElementById('prowlarrApiKey');
    const btn = input.closest('.password-input-group').querySelector('.btn-toggle-password');
    prowlarrPasswordVisible = !prowlarrPasswordVisible;
    input.type = prowlarrPasswordVisible ? 'text' : 'password';
    btn.textContent = prowlarrPasswordVisible ? '🙈 Masquer' : '👁️ Afficher';
}

// ===== PROWLARR INDEXERS =====
async function loadProwlarrIndexers() {
    showMessage('indexersMessage', '⏳ Récupération des indexeurs en cours...', 'info');
    try {
        const response = await fetch('/api/prowlarr/indexers');
        const data = await response.json();
        
        if (!data.success) {
            // Afficher le message d'erreur de manière lisible
            let errorMsg = data.error || 'Erreur inconnue';
            if (errorMsg.includes('URLs essayées')) {
                // Le message contient des infos de debug, l'afficher complètement
                showMessage('indexersMessage', '❌ ' + errorMsg, 'error');
            } else {
                showMessage('indexersMessage', '❌ Erreur: ' + errorMsg, 'error');
            }
            return;
        }
        
        if (!data.indexers || data.indexers.length === 0) {
            showMessage('indexersMessage', '⚠️ Aucun indexeur trouvé dans Prowlarr', 'warning');
        }
        
        displayIndexers(data.indexers || []);
        showMessage('indexersMessage', '✅ Indexeurs chargés avec succès !', 'success');
    } catch (error) {
        showMessage('indexersMessage', '❌ Erreur de connexion: ' + error.message, 'error');
    }
}

function displayIndexers(indexers) {
    const list = document.getElementById('indexersList');
    
    if (indexers.length === 0) {
        list.innerHTML = '<p style="color: #999;">Aucun indexeur trouvé</p>';
        return;
    }
    
    let html = '';
    indexers.forEach(indexer => {
        let categoriesHtml = '';
        
        if (indexer.categories && indexer.categories.length > 0) {
            categoriesHtml = '<div style="margin-top: 12px; padding-top: 12px; border-top: 1px solid #e0e0e0;">';
            categoriesHtml += '<strong style="display: block; margin-bottom: 8px; font-size: 0.9em;">Catégories:</strong>';
            categoriesHtml += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(180px, 1fr)); gap: 8px;">';
            
            indexer.categories.forEach(category => {
                const isSubcategory = category.name.startsWith('  ↳');
                categoriesHtml += `
                    <label style="display: flex; align-items: center; gap: 8px; cursor: pointer; font-size: 0.85em; padding: ${isSubcategory ? '2px 0 2px 10px' : '0'};">
                        <input type="checkbox" class="category-checkbox" data-indexer-id="${indexer.id}" data-category-id="${category.id}" ${category.selected ? 'checked' : ''}>
                        <span>${category.name}</span>
                    </label>
                `;
            });
            
            categoriesHtml += '</div></div>';
        } else {
            categoriesHtml = '<div style="margin-top: 10px; padding: 10px; background: #f9f9f9; border-radius: 3px; border-left: 3px solid #ffc107; font-size: 0.85em; color: #666;">⚠️ Pas de catégories trouvées pour cet indexeur</div>';
        }
        
        html += `
            <div style="padding: 15px; border: 1px solid #e0e0e0; border-radius: 5px; margin-bottom: 15px; background: #fafafa;">
                <div style="display: flex; align-items: center; gap: 15px; margin-bottom: 8px;">
                    <input type="checkbox" id="indexer-${indexer.id}" class="indexer-checkbox" value="${indexer.id}" ${indexer.selected ? 'checked' : ''}>
                    <div style="flex: 1;">
                        <label for="indexer-${indexer.id}" style="cursor: pointer; margin: 0;">
                            <strong>${indexer.name}</strong>
                            <span style="color: #999; font-size: 0.9em; margin-left: 10px;">(ID: ${indexer.id})</span>
                        </label>
                        ${indexer.language ? `<div style="font-size: 0.85em; color: #666;">🌐 ${indexer.language}</div>` : ''}
                    </div>
                </div>
                ${categoriesHtml}
            </div>
        `;
    });
    
    list.innerHTML = html;
}

async function saveProwlarrIndexers() {
    const selected = [];
    const selectedCategories = {};
    
    // Récupérer les indexeurs sélectionnés
    document.querySelectorAll('.indexer-checkbox:checked').forEach(checkbox => {
        selected.push(parseInt(checkbox.value));
        selectedCategories[checkbox.value.toString()] = [];
    });
    
    // Récupérer les catégories sélectionnées pour chaque indexeur
    document.querySelectorAll('.category-checkbox:checked').forEach(checkbox => {
        const indexerId = checkbox.getAttribute('data-indexer-id');
        const categoryId = parseInt(checkbox.getAttribute('data-category-id'));
        
        if (selectedCategories[indexerId]) {
            if (!Array.isArray(selectedCategories[indexerId])) {
                selectedCategories[indexerId] = [];
            }
            selectedCategories[indexerId].push(categoryId);
        }
    });
    
    try {
        const response = await fetch('/api/prowlarr/indexers', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({ 
                selected_indexers: selected,
                selected_categories: selectedCategories
            })
        });
        const data = await response.json();
        
        if (data.success) {
            showMessage('indexersMessage', '✅ Indexeurs et catégories enregistrés !', 'success');
        } else {
            showMessage('indexersMessage', '❌ Erreur: ' + data.error, 'error');
        }
    } catch (error) {
        showMessage('indexersMessage', '❌ Erreur de connexion: ' + error.message, 'error');
    }
}


// ===== TABS =====
function switchTab(tabName) {
    // Supprimer les classes active de tous les boutons et contenus
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    
    // Ajouter la classe active au bouton cliqué
    if (event && event.currentTarget) {
        event.currentTarget.classList.add('active');
    } else {
        // Fallback : chercher le bouton par son onclick
        document.querySelectorAll('.tab-button').forEach(btn => {
            if (btn.getAttribute('onclick').includes(`'${tabName}'`)) {
                btn.classList.add('active');
            }
        });
    }
    
    // Afficher le contenu de l'onglet
    const tabElement = document.getElementById('tab-' + tabName);
    if (tabElement) {
        tabElement.classList.add('active');
    }
    
    // Charger les données spécifiques à chaque onglet
    if (tabName === 'amule') {
        loadSettings();
    } else if (tabName === 'ebdz') {
        loadEbdzConfig();
    } else if (tabName === 'prowlarr') {
        loadProwlarrSettings();
    } else if (tabName === 'badges') {
        initBadgeColorPickers();
    }
}

// ===== BADGES =====
function initBadgeColorPickers() {
    // Charger les couleurs sauvegardées ou utiliser les défauts
    const savedColors = JSON.parse(localStorage.getItem('badgeColors')) || {
        complete: '#10b981',
        ongoing: '#ef4444',
        incomplete: '#f59e0b',
        missing: '#3b82f6'
    };
    
    // Appliquer les couleurs aux pickers
    document.getElementById('badgeColorComplete').value = savedColors.complete;
    document.getElementById('badgeColorOngoing').value = savedColors.ongoing;
    document.getElementById('badgeColorIncomplete').value = savedColors.incomplete;
    document.getElementById('badgeColorMissing').value = savedColors.missing;
    
    // Initialiser les textes
    const badges = ['Complete', 'Ongoing', 'Incomplete', 'Missing'];
    
    badges.forEach(badge => {
        const colorInput = document.getElementById(`badgeColor${badge}`);
        const textInput = document.getElementById(`badgeColor${badge}Text`);
        
        if (colorInput && textInput) {
            // Initialiser le texte avec la couleur
            textInput.value = colorInput.value;
            
            // Mettre à jour le texte quand la couleur change
            colorInput.addEventListener('input', () => {
                textInput.value = colorInput.value;
            });
        }
    });
}

function saveBadgeColors() {
    const colors = {
        complete: document.getElementById('badgeColorComplete')?.value || '#10b981',
        ongoing: document.getElementById('badgeColorOngoing')?.value || '#ef4444',
        incomplete: document.getElementById('badgeColorIncomplete')?.value || '#f59e0b',
        missing: document.getElementById('badgeColorMissing')?.value || '#3b82f6'
    };
    
    // Sauvegarder dans le localStorage
    localStorage.setItem('badgeColors', JSON.stringify(colors));
    
    // Afficher un message de confirmation
    try {
        if (document.getElementById('settingsMessage')) {
            showMessage('settingsMessage', '✅ Couleurs des badges sauvegardées !', 'success');
        } else {
            alert('✅ Couleurs des badges sauvegardées !');
        }
    } catch (e) {
        alert('✅ Couleurs des badges sauvegardées !');
    }
    
    // Rafraîchir la page pour appliquer les changements
    setTimeout(() => {
        window.location.reload();
    }, 1000);
}

function resetBadgeColors() {
    if (!confirm('Êtes-vous sûr de vouloir réinitialiser les couleurs aux valeurs par défaut ?')) {
        return;
    }
    
    const defaultColors = {
        complete: '#10b981',
        ongoing: '#ef4444',
        incomplete: '#f59e0b',
        missing: '#3b82f6'
    };
    
    document.getElementById('badgeColorComplete').value = defaultColors.complete;
    document.getElementById('badgeColorOngoing').value = defaultColors.ongoing;
    document.getElementById('badgeColorIncomplete').value = defaultColors.incomplete;
    document.getElementById('badgeColorMissing').value = defaultColors.missing;
    
    // Mettre à jour les textes
    document.getElementById('badgeColorCompleteText').value = defaultColors.complete;
    document.getElementById('badgeColorOngoingText').value = defaultColors.ongoing;
    document.getElementById('badgeColorIncompleteText').value = defaultColors.incomplete;
    document.getElementById('badgeColorMissingText').value = defaultColors.missing;
    
    // Sauvegarder
    saveBadgeColors();
}

// ===== MESSAGES =====
function showMessage(elementId, text, type) {
    try {
        const msg = document.getElementById(elementId);
        if (msg) {
            msg.textContent = text;
            msg.className = 'message ' + type;
            msg.style.display = 'block';
            setTimeout(() => { msg.style.display = 'none'; }, 6000);
        }
    } catch (error) {
        console.error('Erreur showMessage:', error);
    }
}

// ===== INIT =====
window.addEventListener('load', () => {
    try {
        loadSettings();
    } catch (e) {
        console.error('Erreur loadSettings:', e);
    }
    
    try {
        loadEbdzConfig();
    } catch (e) {
        console.error('Erreur loadEbdzConfig:', e);
    }
    
    try {
        loadProwlarrSettings();
    } catch (e) {
        console.error('Erreur loadProwlarrSettings:', e);
    }
    
    try {
        initBadgeColorPickers();
    } catch (e) {
        console.error('Erreur initBadgeColorPickers:', e);
    }
});
