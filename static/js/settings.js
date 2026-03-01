
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
    
    // Ajouter la classe active au bouton cliqué en utilisant data-tab
    const activeBtn = document.querySelector(`.tab-button[data-tab="${tabName}"]`);
    if (activeBtn) {
        activeBtn.classList.add('active');
    }
    
    // Afficher le contenu de l'onglet
    const tabElement = document.getElementById('tab-' + tabName);
    if (tabElement) {
        tabElement.classList.add('active');
        // Mettre à jour l'URL avec le hash
        window.history.replaceState(null, null, '#' + tabName);
    }
    
    // Charger les données spécifiques à chaque onglet
    if (tabName === 'amule') {
        loadSettings();
    } else if (tabName === 'ebdz') {
        loadEbdzConfig();
    } else if (tabName === 'prowlarr') {
        loadProwlarrSettings();
    } else if (tabName === 'qbittorrent') {
        loadQbittorrentSettings();
    } else if (tabName === 'badges') {
        initBadgeColorPickers();
    } else if (tabName === 'monitoring') {
        loadMonitoringConfig();
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

// ===== QBITTORRENT =====
let qbittorrentPasswordVisible = false;

async function loadQbittorrentSettings() {
    try {
        const response = await fetch('/api/qbittorrent/config');
        const config = await response.json();
        
        document.getElementById('qbittorrentEnabled').checked = config.enabled;
        document.getElementById('qbittorrentUrl').value = config.url || '';
        document.getElementById('qbittorrentPort').value = config.port || 8080;
        document.getElementById('qbittorrentUsername').value = config.username || '';
        
        // Charger le mot de passe déchiffré
        if (config.password) {
            document.getElementById('qbittorrentPassword').value = config.password;
        }
        
        // Charger les catégories disponibles D'ABORD
        await loadQbittorrentCategories();
        
        // PUIS mettre la catégorie sauvegardée après que les options soient chargées
        if (config.default_category) {
            document.getElementById('qbittorrentDefaultCategory').value = config.default_category;
        }
    } catch (error) {
        showMessage('qbittorrentMessage', '❌ Erreur lors du chargement de la configuration', 'error');
    }
}

async function loadQbittorrentCategories() {
    try {
        const response = await fetch('/api/qbittorrent/categories_and_tags');
        const data = await response.json();
        
        if (data.success && data.categories.length > 0) {
            const select = document.getElementById('qbittorrentDefaultCategory');
            const currentValue = select.value;
            
            // Ajouter les catégories
            const optionsHtml = data.categories
                .map(cat => `<option value="${cat}">${cat}</option>`)
                .join('');
            
            select.innerHTML = `<option value="">-- Aucune catégorie --</option>` + optionsHtml;
            select.value = currentValue;
        }
    } catch (error) {
        console.warn('Erreur lors du chargement des catégories:', error);
    }
}

async function saveQbittorrentSettings() {
    const config = {
        enabled: document.getElementById('qbittorrentEnabled').checked,
        url: document.getElementById('qbittorrentUrl').value.trim(),
        port: parseInt(document.getElementById('qbittorrentPort').value),
        username: document.getElementById('qbittorrentUsername').value.trim(),
        password: document.getElementById('qbittorrentPassword').value,
        default_category: document.getElementById('qbittorrentDefaultCategory').value.trim()
    };

    try {
        const response = await fetch('/api/qbittorrent/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        const data = await response.json();
        
        if (data.success) {
            showMessage('qbittorrentMessage', '✅ Configuration qBittorrent enregistrée !', 'success');
        } else {
            showMessage('qbittorrentMessage', '❌ Erreur: ' + data.error, 'error');
        }
    } catch (error) {
        showMessage('qbittorrentMessage', '❌ Erreur de connexion: ' + error.message, 'error');
    }
}

async function testQbittorrentConnection() {
    showMessage('qbittorrentMessage', '⏳ Test de connexion en cours...', 'info');
    
    // Préparer la configuration du formulaire
    const config = {
        enabled: true,  // Forcer enabled à true pour le test
        url: document.getElementById('qbittorrentUrl').value.trim(),
        port: parseInt(document.getElementById('qbittorrentPort').value),
        username: document.getElementById('qbittorrentUsername').value.trim(),
        password_decrypted: document.getElementById('qbittorrentPassword').value  // Texte clair du formulaire
    };
    
    // Vérifier que l'URL est remplie
    if (!config.url) {
        showMessage('qbittorrentMessage', '❌ Veuillez entrer une URL', 'error');
        return;
    }
    
    try {
        const response = await fetch('/api/qbittorrent/test', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify(config)
        });
        const data = await response.json();
        if (data.success) {
            showMessage('qbittorrentMessage', '✅ ' + data.message, 'success');
            // Charger les catégories disponibles après un test réussi
            setTimeout(() => loadQbittorrentCategories(), 500);
        } else {
            showMessage('qbittorrentMessage', '❌ Échec: ' + data.error, 'error');
        }
    } catch (error) {
        showMessage('qbittorrentMessage', '❌ Erreur: ' + error.message, 'error');
    }
}

function resetQbittorrentSettings() {
    if (!confirm('Voulez-vous réinitialiser la configuration qBittorrent ?')) return;
    document.getElementById('qbittorrentEnabled').checked = false;
    document.getElementById('qbittorrentUrl').value = 'http://localhost';
    document.getElementById('qbittorrentPort').value = '8080';
    document.getElementById('qbittorrentUsername').value = '';
    document.getElementById('qbittorrentPassword').value = '';
    showMessage('qbittorrentMessage', '🔄 Configuration réinitialisée', 'info');
}

function toggleQbittorrentPassword() {
    const passwordInput = document.getElementById('qbittorrentPassword');
    const toggleButton = passwordInput.closest('.password-input-group').querySelector('.btn-toggle-password');
    qbittorrentPasswordVisible = !qbittorrentPasswordVisible;
    passwordInput.type = qbittorrentPasswordVisible ? 'text' : 'password';
    toggleButton.textContent = qbittorrentPasswordVisible ? '🙈 Masquer' : '👁️ Afficher';
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

// ===== EBDZ AUTO SCRAPE =====
async function loadAutoScrapeConfig() {
    try {
        const response = await fetch('/api/ebdz/auto-scrape/config');
        const config = await response.json();

        document.getElementById('ebdzAutoScrapeEnabled').checked = config.auto_scrape_enabled;
        document.getElementById('ebdzAutoScrapeInterval').value = config.auto_scrape_interval;
        document.getElementById('ebdzAutoScrapeUnit').value = config.auto_scrape_interval_unit;

        updateAutoScrapeUI();
        checkAutoScrapeStatus();
    } catch (error) {
        console.error('Erreur lors du chargement de la config auto scrape:', error);
    }
}

function updateAutoScrapeUI() {
    const enabled = document.getElementById('ebdzAutoScrapeEnabled').checked;
    const controlsDiv = document.getElementById('autoScrapeControlsDiv');
    const statusDiv = document.getElementById('autoScrapeStatusDiv');

    if (enabled) {
        controlsDiv.style.display = 'flex';
        statusDiv.style.display = 'block';
    } else {
        controlsDiv.style.display = 'none';
        statusDiv.style.display = 'none';
    }
}

async function saveAutoScrapeConfig() {
    try {
        const enabled = document.getElementById('ebdzAutoScrapeEnabled').checked;
        const interval = parseInt(document.getElementById('ebdzAutoScrapeInterval').value);
        const unit = document.getElementById('ebdzAutoScrapeUnit').value;

        if (enabled && interval < 1) {
            showMessage('ebdzAutoMessage', '⚠️ L\'intervalle doit être >= 1', 'warning');
            return;
        }

        const response = await fetch('/api/ebdz/auto-scrape/config', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({
                auto_scrape_enabled: enabled,
                auto_scrape_interval: interval,
                auto_scrape_interval_unit: unit
            })
        });
        const data = await response.json();

        if (data.success) {
            showMessage('ebdzAutoMessage', 
                enabled ? `✅ Scraping automatique activé: tous les ${interval} ${unit}` : '✅ Scraping automatique désactivé', 
                'success');
            updateAutoScrapeUI();
            checkAutoScrapeStatus();
        } else {
            showMessage('ebdzAutoMessage', '❌ Erreur: ' + data.error, 'error');
        }
    } catch (error) {
        showMessage('ebdzAutoMessage', '❌ Erreur: ' + error.message, 'error');
    }
}

async function checkAutoScrapeStatus() {
    try {
        const response = await fetch('/api/ebdz/auto-scrape/status');
        const data = await response.json();

        if (data.success) {
            const statusText = document.getElementById('autoScrapeStatusText');
            const nextRunText = document.getElementById('autoScrapeNextRunText');

            if (data.is_running) {
                statusText.textContent = '🟢 Actif';
                statusText.style.color = '#4CAF50';
                
                if (data.next_run) {
                    const nextRun = new Date(data.next_run);
                    nextRunText.textContent = nextRun.toLocaleString('fr-FR');
                } else {
                    nextRunText.textContent = 'Calcul en cours...';
                }
            } else {
                statusText.textContent = '🔴 Inactif';
                statusText.style.color = '#f44336';
                nextRunText.textContent = '-';
            }
        }
    } catch (error) {
        console.error('Erreur lors du vérification du statut:', error);
    }
}

// Ajouter l'event listener pour le checkbox auto scrape
document.addEventListener('DOMContentLoaded', function() {
    const checkbox = document.getElementById('ebdzAutoScrapeEnabled');
    if (checkbox) {
        checkbox.addEventListener('change', updateAutoScrapeUI);
    }
});

// ===== INIT =====
window.addEventListener('load', () => {
    // Vérifier si une tab est spécifiée dans l'URL (ex: #monitoring)
    if (window.location.hash) {
        const tabName = window.location.hash.substring(1); // Enlever le '#'
        console.log('Hash détecté au load:', tabName);
        switchTab(tabName);
        console.log('switchTab exécuté pour:', tabName);
    } else {
        console.log('Pas de hash dans l\'URL');
    }
    
    try {
        loadSettings();
    } catch (e) {
        console.error('Erreur loadSettings:', e);
    }
});

// Gérer les changements de hash (navigation sans rechargement)
window.addEventListener('hashchange', () => {
    if (window.location.hash) {
        const tabName = window.location.hash.substring(1);
        console.log('Hash changé vers:', tabName);
        switchTab(tabName);
    }
});

// ===== SURVEILLANCE =====

async function loadMonitoringConfig() {
    try {
        const response = await fetch('/api/missing-monitor/config');
        const config = await response.json();
        
        // Configuration des volumes manquants
        const missingConfig = config.monitor_missing_volumes || {};
        
        const settingsMonitorMissing = document.getElementById('settingsMonitorMissing');
        const settingsMissingSearch = document.getElementById('settingsMissingSearch');
        const settingsMissingAutoDownload = document.getElementById('settingsMissingAutoDownload');
        const settingsMissingEbdz = document.getElementById('settingsMissingEbdz');
        const settingsMissingProwlarr = document.getElementById('settingsMissingProwlarr');
        const missingCheckInterval = document.getElementById('missingCheckInterval');
        const missingCheckUnit = document.getElementById('missingCheckUnit');
        
        if (settingsMonitorMissing) settingsMonitorMissing.checked = missingConfig.enabled !== false;
        if (settingsMissingSearch) settingsMissingSearch.checked = missingConfig.search_enabled !== false;
        if (settingsMissingAutoDownload) settingsMissingAutoDownload.checked = missingConfig.auto_download_enabled || false;
        
        // Charger les fréquences pour les volumes manquants
        if (missingCheckInterval) missingCheckInterval.value = missingConfig.check_interval || 12;
        if (missingCheckUnit) missingCheckUnit.value = missingConfig.check_interval_unit || 'hours';
        
        // Charger les sources de recherche AVEC l'ordre de priorité
        const missingSources = missingConfig.search_sources || ['ebdz', 'prowlarr'];
        if (settingsMissingEbdz) settingsMissingEbdz.checked = missingSources.includes('ebdz');
        if (settingsMissingProwlarr) settingsMissingProwlarr.checked = missingSources.includes('prowlarr');
        
        // Afficher l'ordre de priorité
        const missingSources1stEl = document.getElementById('missingSources1st');
        const missingSources2ndEl = document.getElementById('missingSources2nd');
        if (missingSources1stEl && missingSources.length > 0) {
            missingSources1stEl.textContent = missingSources[0].toUpperCase();
        }
        if (missingSources2ndEl && missingSources.length > 1) {
            missingSources2ndEl.textContent = missingSources[1].toUpperCase();
        }

        // Configuration des nouveaux volumes
        const newConfig = config.monitor_new_volumes || {};
        
        const settingsMonitorNew = document.getElementById('settingsMonitorNew');
        const settingsNewSearch = document.getElementById('settingsNewSearch');
        const settingsNewAutoDownload = document.getElementById('settingsNewAutoDownload');
        const settingsNautiljonCheck = document.getElementById('settingsNautiljonCheck');
        const settingsNewEbdz = document.getElementById('settingsNewEbdz');
        const settingsNewProwlarr = document.getElementById('settingsNewProwlarr');
        const newVolumesSettings = document.getElementById('newVolumesSettings');
        const newCheckInterval = document.getElementById('newCheckInterval');
        const newCheckUnit = document.getElementById('newCheckUnit');
        
        if (settingsMonitorNew) settingsMonitorNew.checked = newConfig.enabled || false;
        if (settingsNewSearch) settingsNewSearch.checked = newConfig.search_enabled !== false;
        if (settingsNewAutoDownload) settingsNewAutoDownload.checked = newConfig.auto_download_enabled || false;
        if (settingsNautiljonCheck) settingsNautiljonCheck.checked = newConfig.check_nautiljon_updates !== false;
        
        // Charger les fréquences pour les nouveaux volumes
        if (newCheckInterval) newCheckInterval.value = newConfig.check_interval || 6;
        if (newCheckUnit) newCheckUnit.value = newConfig.check_interval_unit || 'hours';
        
        // Charger les sources de recherche AVEC l'ordre de priorité
        const newSources = newConfig.search_sources || ['ebdz', 'prowlarr'];
        if (settingsNewEbdz) settingsNewEbdz.checked = newSources.includes('ebdz');
        if (settingsNewProwlarr) settingsNewProwlarr.checked = newSources.includes('prowlarr');
        
        // Afficher l'ordre de priorité
        const newSources1stEl = document.getElementById('newSources1st');
        const newSources2ndEl = document.getElementById('newSources2nd');
        if (newSources1stEl && newSources.length > 0) {
            newSources1stEl.textContent = newSources[0].toUpperCase();
        }
        if (newSources2ndEl && newSources.length > 1) {
            newSources2ndEl.textContent = newSources[1].toUpperCase();
        }

        // Ajouter les événements pour afficher/masquer les sections
        if (settingsMonitorNew) {
            settingsMonitorNew.addEventListener('change', function() {
                if (newVolumesSettings) {
                    newVolumesSettings.style.display = this.checked ? 'block' : 'none';
                }
            });
        }

        // Initialiser l'affichage
        if (newVolumesSettings && settingsMonitorNew) {
            newVolumesSettings.style.display = settingsMonitorNew.checked ? 'block' : 'none';
        }
        
        // Calculer et afficher la prochaine vérification
        updateNextMissingCheck();
        updateNextNewCheck();
    } catch (error) {
        console.error('Erreur chargement config surveillance:', error);
    }
}

async function saveMonitoringConfig() {
    try {
        // Vérifier que tous les éléments existent avant d'accéder à leurs valeurs
        const settingsMonitorMissing = document.getElementById('settingsMonitorMissing');
        const settingsMissingSearch = document.getElementById('settingsMissingSearch');
        const settingsMissingAutoDownload = document.getElementById('settingsMissingAutoDownload');
        const settingsMissingEbdz = document.getElementById('settingsMissingEbdz');
        const settingsMissingProwlarr = document.getElementById('settingsMissingProwlarr');
        const missingCheckInterval = document.getElementById('missingCheckInterval');
        const missingCheckUnit = document.getElementById('missingCheckUnit');
        
        const settingsMonitorNew = document.getElementById('settingsMonitorNew');
        const settingsNewSearch = document.getElementById('settingsNewSearch');
        const settingsNewAutoDownload = document.getElementById('settingsNewAutoDownload');
        const settingsNautiljonCheck = document.getElementById('settingsNautiljonCheck');
        const settingsNewEbdz = document.getElementById('settingsNewEbdz');
        const settingsNewProwlarr = document.getElementById('settingsNewProwlarr');
        const newCheckInterval = document.getElementById('newCheckInterval');
        const newCheckUnit = document.getElementById('newCheckUnit');
        
        if (!settingsMonitorMissing || !settingsMissingSearch || !settingsMissingAutoDownload) {
            console.error('Éléments manquants pour la section volumes manquants');
            return;
        }
        
        if (!settingsMonitorNew || !settingsNewSearch || !settingsNewAutoDownload || !settingsNautiljonCheck) {
            console.error('Éléments manquants pour la section nouveaux volumes');
            return;
        }
        
        // Construire la liste des sources pour les volumes manquants (respecter l'ordre)
        let missingSources = [];
        const missingSources1st = document.getElementById('missingSources1st')?.textContent || '';
        const missingSources2nd = document.getElementById('missingSources2nd')?.textContent || '';
        
        if (missingSources1st && missingSources1st !== '-') {
            missingSources.push(missingSources1st.toLowerCase());
        }
        if (missingSources2nd && missingSources2nd !== '-') {
            missingSources.push(missingSources2nd.toLowerCase());
        }
        
        // Fallback: si pas de priorisation, utiliser les checkboxes
        if (missingSources.length === 0) {
            if (settingsMissingEbdz && settingsMissingEbdz.checked) missingSources.push('ebdz');
            if (settingsMissingProwlarr && settingsMissingProwlarr.checked) missingSources.push('prowlarr');
        }
        
        // Construire la liste des sources pour les nouveaux volumes (respecter l'ordre)
        let newSources = [];
        const newSources1st = document.getElementById('newSources1st')?.textContent || '';
        const newSources2nd = document.getElementById('newSources2nd')?.textContent || '';
        
        if (newSources1st && newSources1st !== '-') {
            newSources.push(newSources1st.toLowerCase());
        }
        if (newSources2nd && newSources2nd !== '-') {
            newSources.push(newSources2nd.toLowerCase());
        }
        
        // Fallback: si pas de priorisation, utiliser les checkboxes
        if (newSources.length === 0) {
            if (settingsNewEbdz && settingsNewEbdz.checked) newSources.push('ebdz');
            if (settingsNewProwlarr && settingsNewProwlarr.checked) newSources.push('prowlarr');
        }
        
        // Récupérer les fréquences
        const missingInterval = parseInt(missingCheckInterval?.value || 12) || 12;
        const missingUnit = missingCheckUnit?.value || 'hours';
        const newInterval = parseInt(newCheckInterval?.value || 6) || 6;
        const newUnit = newCheckUnit?.value || 'hours';
        
        const config = {
            monitor_missing_volumes: {
                enabled: settingsMonitorMissing.checked,
                search_enabled: settingsMissingSearch.checked,
                auto_download_enabled: settingsMissingAutoDownload.checked,
                search_sources: missingSources,
                check_interval: missingInterval,
                check_interval_unit: missingUnit
            },
            monitor_new_volumes: {
                enabled: settingsMonitorNew.checked,
                search_enabled: settingsNewSearch.checked,
                auto_download_enabled: settingsNewAutoDownload.checked,
                check_nautiljon_updates: settingsNautiljonCheck.checked,
                search_sources: newSources,
                check_interval: newInterval,
                check_interval_unit: newUnit
            }
        };

        const response = await fetch('/api/missing-monitor/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(config)
        });

        const data = await response.json();

        if (data.success) {
            showSettingsMessage('monitoringMessage', '✅ Configuration de surveillance sauvegardée avec succès !', 'success');
        } else {
            showSettingsMessage('monitoringMessage', '❌ Erreur: ' + data.error, 'error');
        }
    } catch (error) {
        console.error('Erreur sauvegarde config surveillance:', error);
        showSettingsMessage('monitoringMessage', '❌ Erreur de connexion', 'error');
    }
}

function showSettingsMessage(elementId, message, type) {
    const element = document.getElementById(elementId);
    if (element) {
        element.className = 'message ' + type;
        element.textContent = message;
        element.style.display = 'block';
        
        // Masquer après 5 secondes
        if (type === 'success') {
            setTimeout(() => {
                element.style.display = 'none';
            }, 5000);
        }
    }
}

function swapMissingSources() {
    const sources1st = document.getElementById('missingSources1st');
    const sources2nd = document.getElementById('missingSources2nd');
    
    if (sources1st && sources2nd) {
        const temp = sources1st.textContent;
        sources1st.textContent = sources2nd.textContent;
        sources2nd.textContent = temp;
    }
}

function swapNewSources() {
    const sources1st = document.getElementById('newSources1st');
    const sources2nd = document.getElementById('newSources2nd');
    
    if (sources1st && sources2nd) {
        const temp = sources1st.textContent;
        sources1st.textContent = sources2nd.textContent;
        sources2nd.textContent = temp;
    }
}

function updateNextMissingCheck() {
    const interval = parseInt(document.getElementById('missingCheckInterval')?.value || 12) || 12;
    const unit = document.getElementById('missingCheckUnit')?.value || 'hours';
    
    const nextDate = new Date();
    if (unit === 'hours') {
        nextDate.setHours(nextDate.getHours() + interval);
    } else if (unit === 'days') {
        nextDate.setDate(nextDate.getDate() + interval);
    }
    
    const displayText = formatNextCheck(nextDate);
    const elem = document.getElementById('nextMissingCheck');
    if (elem) {
        elem.textContent = displayText;
    }
}

function updateNextNewCheck() {
    const interval = parseInt(document.getElementById('newCheckInterval')?.value || 6) || 6;
    const unit = document.getElementById('newCheckUnit')?.value || 'hours';
    
    const nextDate = new Date();
    if (unit === 'hours') {
        nextDate.setHours(nextDate.getHours() + interval);
    } else if (unit === 'days') {
        nextDate.setDate(nextDate.getDate() + interval);
    }
    
    const displayText = formatNextCheck(nextDate);
    const elem = document.getElementById('nextNewCheck');
    if (elem) {
        elem.textContent = displayText;
    }
}

function formatNextCheck(date) {
    const today = new Date();
    today.setHours(0, 0, 0, 0);
    
    const checkDate = new Date(date);
    checkDate.setHours(0, 0, 0, 0);
    
    const diffTime = checkDate - today;
    const diffDays = Math.floor(diffTime / (1000 * 60 * 60 * 24));
    
    const dayOptions = { weekday: 'long', month: 'long', day: 'numeric' };
    const timeOptions = { hour: '2-digit', minute: '2-digit' };
    
    const dayName = date.toLocaleDateString('fr-FR', dayOptions);
    const timeName = date.toLocaleTimeString('fr-FR', timeOptions);
    
    let prefix = '';
    if (diffDays === 0) {
        prefix = 'Aujourd\'hui';
    } else if (diffDays === 1) {
        prefix = 'Demain';
    } else if (diffDays > 1 && diffDays <= 7) {
        prefix = `Dans ${diffDays} jours`;
    } else {
        return `Prochaine vérification: ${dayName} à ${timeName}`;
    }
    
    return `Prochaine vérification: ${prefix} à ${timeName}`;
}
