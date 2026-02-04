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
        // Affiche '****' dans le champ pour indiquer qu'un mot de passe est enregistré,
        // sinon vide le champ s'il n'y a pas de mot de passe.
        if (config.password && config.password === '****') {
            document.getElementById('ebdzPassword').value = '****';
        } else if (!config.password) {
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

// ===== TABS =====
function switchTab(tabName) {
    document.querySelectorAll('.tab-button').forEach(btn => btn.classList.remove('active'));
    document.querySelectorAll('.tab-content').forEach(content => content.classList.remove('active'));
    event.target.classList.add('active');
    document.getElementById('tab-' + tabName).classList.add('active');
}

// ===== MESSAGES =====
function showMessage(elementId, text, type) {
    const msg = document.getElementById(elementId);
    msg.textContent = text;
    msg.className = 'message ' + type;
    msg.style.display = 'block';
    setTimeout(() => { msg.style.display = 'none'; }, 6000);
}

// ===== INIT =====
window.addEventListener('load', () => {
    loadSettings();
    loadEbdzConfig();
});
