/**
 * Gestion du transfert de séries entre bibliothèques
 */

let leftLibraryId = null;
let rightLibraryId = null;
let leftSelectedSeries = new Set();
let rightSelectedSeries = new Set();
let transferCount = 0;
let leftFilter = 'all';
let rightFilter = 'all';
let leftSeriesData = [];
let rightSeriesData = [];

// Initialisation au chargement de la page
document.addEventListener('DOMContentLoaded', () => {
    loadLibraries();
});

/**
 * Charge la liste des bibliothèques disponibles
 */
async function loadLibraries() {
    try {
        const response = await fetch('/api/libraries');
        const libraries = await response.json();

        const leftSelect = document.getElementById('left-library-select');
        const rightSelect = document.getElementById('right-library-select');

        // Remplir les sélecteurs
        libraries.forEach(lib => {
            const option1 = document.createElement('option');
            option1.value = lib.id;
            option1.textContent = `${lib.name} (${lib.series_count || 0} séries)`;
            leftSelect.appendChild(option1);

            const option2 = document.createElement('option');
            option2.value = lib.id;
            option2.textContent = `${lib.name} (${lib.series_count || 0} séries)`;
            rightSelect.appendChild(option2);
        });
    } catch (error) {
        console.error('Erreur lors du chargement des bibliothèques:', error);
        showNotification('Erreur lors du chargement des bibliothèques', 'error');
    }
}

/**
 * Charge les séries de la bibliothèque gauche
 */
async function loadLeftLibrary() {
    const select = document.getElementById('left-library-select');
    const libraryId = parseInt(select.value);

    if (!libraryId) {
        clearPanelLeft();
        return;
    }

    leftLibraryId = libraryId;
    leftSelectedSeries.clear();
    leftFilter = 'all';
    updateFilterButtons('left');
    await loadLibrarySeries(libraryId, 'left');
    updateMoveButtons();
}

/**
 * Charge les séries de la bibliothèque droite
 */
async function loadRightLibrary() {
    const select = document.getElementById('right-library-select');
    const libraryId = parseInt(select.value);

    if (!libraryId) {
        clearPanelRight();
        return;
    }

    rightLibraryId = libraryId;
    rightSelectedSeries.clear();
    rightFilter = 'all';
    updateFilterButtons('right');
    await loadLibrarySeries(libraryId, 'right');
    updateMoveButtons();
}

/**
 * Charge les séries d'une bibliothèque donnée
 */
async function loadLibrarySeries(libraryId, side) {
    try {
        const response = await fetch(`/api/transfer/series/${libraryId}`);
        const data = await response.json();

        // Ajouter la propriété isComplete à chaque série
        data.series.forEach(series => {
            series.isComplete = !series.missing_volumes || series.missing_volumes === '';
        });

        // Stocker les données brutes
        if (side === 'left') {
            leftSeriesData = data.series;
        } else {
            rightSeriesData = data.series;
        }

        // Afficher les séries filtrées
        displayFilteredSeries(side);
    } catch (error) {
        console.error(`Erreur lors du chargement des séries du côté ${side}:`, error);
        showNotification('Erreur lors du chargement des séries', 'error');
    }
}

/**
 * Affiche les séries filtrées pour un panneau donné
 */
function displayFilteredSeries(side) {
    const seriesData = side === 'left' ? leftSeriesData : rightSeriesData;
    const currentFilter = side === 'left' ? leftFilter : rightFilter;
    const containerId = `${side}-series-container`;
    const container = document.getElementById(containerId);

    if (seriesData.length === 0) {
        container.innerHTML = '<p class="placeholder">Aucune série dans cette bibliothèque</p>';
        return;
    }

    // Appliquer le filtre
    let filteredSeries = seriesData;
    if (currentFilter === 'complete') {
        filteredSeries = seriesData.filter(s => s.isComplete);
    } else if (currentFilter === 'incomplete') {
        filteredSeries = seriesData.filter(s => !s.isComplete);
    }

    if (filteredSeries.length === 0) {
        container.innerHTML = '<p class="placeholder">Aucune série matching le filtre</p>';
        return;
    }

    // Créer la liste des séries
    const list = document.createElement('ul');
    list.className = 'series-list';

    filteredSeries.forEach(series => {
        const item = document.createElement('li');
        item.className = 'series-item';
        item.id = `${side}-series-${series.id}`;

        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.value = series.id;
        checkbox.checked = (side === 'left' ? leftSelectedSeries : rightSelectedSeries).has(series.id);
        checkbox.onchange = (e) => handleSeriesSelection(series.id, side, e.target.checked);

        const info = document.createElement('div');
        info.className = 'series-info';

        const title = document.createElement('div');
        title.className = 'series-title';
        const statusIcon = series.isComplete ? '✅' : '⚠️';
        title.textContent = `${statusIcon} ${series.title}`;

        const details = document.createElement('div');
        details.className = 'series-details';
        const volumes = series.total_volumes || '?';
        const missing = series.missing_volumes ? ` • Manquants: ${series.missing_volumes}` : '';
        details.textContent = `Volumes: ${volumes}${missing}`;

        info.appendChild(title);
        info.appendChild(details);

        item.appendChild(checkbox);
        item.appendChild(info);

        list.appendChild(item);
    });

    container.innerHTML = '';
    container.appendChild(list);
}

/**
 * Gère la sélection/déselection d'une série
 */
function handleSeriesSelection(seriesId, side, isSelected) {
    const selectedSet = side === 'left' ? leftSelectedSeries : rightSelectedSeries;
    const itemId = `${side}-series-${seriesId}`;
    const item = document.getElementById(itemId);

    if (isSelected) {
        selectedSet.add(seriesId);
        if (item) item.classList.add('selected');
    } else {
        selectedSet.delete(seriesId);
        if (item) item.classList.remove('selected');
    }

    updateSelectionCount(side);
    updateMoveButtons();
}

/**
 * Met à jour le compteur de séries sélectionnées
 */
function updateSelectionCount(side) {
    const selectedSet = side === 'left' ? leftSelectedSeries : rightSelectedSeries;
    const countId = side === 'left' ? 'left-selected-count' : 'right-selected-count';
    document.getElementById(countId).textContent = selectedSet.size;
}

/**
 * Met à jour l'état des boutons de transfert
 */
function updateMoveButtons() {
    const rightBtn = document.getElementById('move-right-btn');
    const leftBtn = document.getElementById('move-left-btn');

    rightBtn.disabled = leftSelectedSeries.size === 0 || !rightLibraryId;
    leftBtn.disabled = rightSelectedSeries.size === 0 || !leftLibraryId;
}

/**
 * Déplace les séries sélectionnées de gauche à droite
 */
async function moveSelectedRight() {
    if (leftSelectedSeries.size === 0 || !rightLibraryId) return;

    const seriesIds = Array.from(leftSelectedSeries);
    await transferSeries(seriesIds, leftLibraryId, rightLibraryId, 'left', 'right');
}

/**
 * Déplace les séries sélectionnées de droite à gauche
 */
async function moveSelectedLeft() {
    if (rightSelectedSeries.size === 0 || !leftLibraryId) return;

    const seriesIds = Array.from(rightSelectedSeries);
    await transferSeries(seriesIds, rightLibraryId, leftLibraryId, 'right', 'left');
}

/**
 * Effectue le transfert d'une ou plusieurs séries
 */
async function transferSeries(seriesIds, fromLibraryId, toLibraryId, fromSide, toSide) {
    try {
        let successCount = 0;
        let failureCount = 0;

        for (const seriesId of seriesIds) {
            try {
                const response = await fetch('/api/transfer/move', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        series_id: seriesId,
                        from_library_id: fromLibraryId,
                        to_library_id: toLibraryId
                    })
                });

                if (response.ok) {
                    successCount++;
                    transferCount++;
                    
                    // Retirer l'élément de l'affichage
                    const itemId = `${fromSide}-series-${seriesId}`;
                    const item = document.getElementById(itemId);
                    if (item) {
                        item.style.animation = 'slideOut 0.3s ease-out';
                        setTimeout(() => item.remove(), 300);
                    }
                    
                    // Mettre à jour les sélections
                    if (fromSide === 'left') {
                        leftSelectedSeries.delete(seriesId);
                    } else {
                        rightSelectedSeries.delete(seriesId);
                    }
                } else {
                    failureCount++;
                    const errorData = await response.json();
                    console.error(`Erreur transfert série ${seriesId}:`, errorData.error);
                }
            } catch (error) {
                failureCount++;
                console.error(`Erreur lors du transfert de la série ${seriesId}:`, error);
            }
        }

        // Afficher le résultat
        if (successCount > 0) {
            showNotification(
                `${successCount} série(s) transférée(s) avec succès!`,
                'success'
            );
            updateCompletionStat();
        }

        if (failureCount > 0) {
            showNotification(
                `${failureCount} série(s) n'ont pas pu être transférée(s)`,
                'error'
            );
        }

        // Mettre à jour l'affichage
        updateSelectionCount(fromSide);
        updateMoveButtons();

        // Recharger les deux bibliothèques pour synchroniser
        if (leftLibraryId) {
            await loadLibrarySeries(leftLibraryId, 'left');
        }
        if (rightLibraryId) {
            await loadLibrarySeries(rightLibraryId, 'right');
        }
    } catch (error) {
        console.error('Erreur lors du transfert:', error);
        showNotification('Erreur lors du transfert de séries', 'error');
    }
}

/**
 * Met à jour le compteur de transferts réussis
 */
function updateCompletionStat() {
    document.getElementById('transfer-success-count').textContent = transferCount;
}

/**
 * Bascule le filtre du panneau gauche
 */
function toggleLeftFilter(filterType) {
    leftFilter = filterType;
    updateFilterButtons('left');
    displayFilteredSeries('left');
}

/**
 * Bascule le filtre du panneau droite
 */
function toggleRightFilter(filterType) {
    rightFilter = filterType;
    updateFilterButtons('right');
    displayFilteredSeries('right');
}

/**
 * Met à jour l'état visuel des boutons de filtre
 */
function updateFilterButtons(side) {
    const currentFilter = side === 'left' ? leftFilter : rightFilter;
    const panel = side === 'left' ? document.querySelector('.left-panel') : document.querySelector('.right-panel');
    const buttons = panel.querySelectorAll('.filter-btn');
    
    buttons.forEach(btn => {
        const filterType = btn.getAttribute('data-filter');
        if (filterType === currentFilter) {
            btn.classList.add('active');
        } else {
            btn.classList.remove('active');
        }
    });
}

/**
 * Affiche une notification temporaire
 */
function showNotification(message, type = 'info') {
    const notification = document.createElement('div');
    notification.className = `notification ${type}`;
    notification.textContent = message;
    document.body.appendChild(notification);

    setTimeout(() => {
        notification.style.animation = 'slideOut 0.3s ease-out';
        setTimeout(() => notification.remove(), 300);
    }, 3000);
}

/**
 * Efface le contenu du panneau gauche
 */
function clearPanelLeft() {
    document.getElementById('left-series-container').innerHTML = 
        '<p class="placeholder">Sélectionnez une bibliothèque source</p>';
    leftLibraryId = null;
    leftSelectedSeries.clear();
    leftSeriesData = [];
    leftFilter = 'all';
    updateSelectionCount('left');
    updateFilterButtons('left');
    updateMoveButtons();
}

/**
 * Efface le contenu du panneau droit
 */
function clearPanelRight() {
    document.getElementById('right-series-container').innerHTML = 
        '<p class="placeholder">Sélectionnez une bibliothèque destination</p>';
    rightLibraryId = null;
    rightSelectedSeries.clear();
    rightSeriesData = [];
    rightFilter = 'all';
    updateSelectionCount('right');
    updateFilterButtons('right');
    updateMoveButtons();
}

// Animation de sortie
const style = document.createElement('style');
style.textContent = `
    @keyframes slideOut {
        from {
            opacity: 1;
            transform: translateX(0);
        }
        to {
            opacity: 0;
            transform: translateX(-20px);
        }
    }
`;
document.head.appendChild(style);
