/**
 * Nautiljon API Integration
 * Functions to interact with Nautiljon API endpoints
 */

const NautiljonAPI = {
    /**
     * Search for a manga on Nautiljon
     * @param {string} query - Manga title to search
     * @returns {Promise<Array>} Array of search results
     */
    async searchManga(query) {
        try {
            const response = await fetch(`/api/nautiljon/search?q=${encodeURIComponent(query)}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            return data.results || [];
        } catch (error) {
            console.error('Nautiljon search error:', error);
            return [];
        }
    },

    /**
     * Get detailed info for a manga
     * @param {string} urlOrTitle - Nautiljon URL or manga title
     * @param {boolean} byUrl - If true, treat input as URL, otherwise as title
     * @returns {Promise<Object>} Manga information object
     */
    async getMangaInfo(urlOrTitle, byUrl = false) {
        try {
            const param = byUrl ? `url=${encodeURIComponent(urlOrTitle)}` : `title=${encodeURIComponent(urlOrTitle)}`;
            const response = await fetch(`/api/nautiljon/info?${param}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            const data = await response.json();
            return data.info || null;
        } catch (error) {
            console.error('Nautiljon info error:', error);
            return null;
        }
    },

    /**
     * Enrich a series with Nautiljon data
     * @param {number} seriesId - Series ID to enrich
     * @param {string} searchValue - Title or URL to search for
     * @param {string} searchBy - 'title' or 'url'
     * @returns {Promise<Object>} Enrichment result
     */
    async enrichSeries(seriesId, searchValue, searchBy = 'title') {
        try {
            const response = await fetch(`/api/nautiljon/enrich/${seriesId}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    search_by: searchBy,
                    value: searchValue
                })
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Series enrichment error:', error);
            return { success: false, error: error.message };
        }
    },

    /**
     * Get series details including Nautiljon data
     * @param {number} seriesId - Series ID
     * @returns {Promise<Object>} Complete series information
     */
    async getSeriesWithNautiljon(seriesId) {
        try {
            const response = await fetch(`/api/series/${seriesId}`);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Series details error:', error);
            return null;
        }
    },

    /**
     * Batch enrich multiple series
     * @param {Array<number>} seriesIds - Array of series IDs
     * @param {string} searchBy - 'title' or 'url'
     * @returns {Promise<Object>} Batch enrichment result
     */
    async batchEnrichSeries(seriesIds, searchBy = 'title') {
        try {
            const response = await fetch('/api/nautiljon/batch-enrich', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    series_ids: seriesIds,
                    search_by: searchBy
                })
            });
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Batch enrichment error:', error);
            return { success: false, error: error.message };
        }
    },

    /**
     * Display Nautiljon info card
     * @param {Object} nautiljonData - Nautiljon data object
     * @param {HTMLElement} container - Container to insert into
     */
    displayInfoCard(nautiljonData, container) {
        if (!nautiljonData || !nautiljonData.url) {
            container.innerHTML = '<p class="no-data">Nautiljon data not available</p>';
            return;
        }

        const html = `
            <div class="nautiljon-card">
                <h3>📚 Nautiljon Information</h3>
                <div class="info-grid">
                    ${nautiljonData.total_volumes ? `
                        <div class="info-item">
                            <span class="label">Total Volumes:</span>
                            <span class="value">${nautiljonData.total_volumes}</span>
                        </div>
                    ` : ''}
                    ${nautiljonData.french_volumes ? `
                        <div class="info-item">
                            <span class="label">French Volumes:</span>
                            <span class="value">${nautiljonData.french_volumes}</span>
                        </div>
                    ` : ''}
                    ${nautiljonData.editor ? `
                        <div class="info-item">
                            <span class="label">French Editor:</span>
                            <span class="value">${nautiljonData.editor}</span>
                        </div>
                    ` : ''}
                    ${nautiljonData.status ? `
                        <div class="info-item">
                            <span class="label">Status:</span>
                            <span class="value status-${nautiljonData.status.toLowerCase()}">${nautiljonData.status}</span>
                        </div>
                    ` : ''}
                    ${nautiljonData.mangaka ? `
                        <div class="info-item">
                            <span class="label">Mangaka:</span>
                            <span class="value">${nautiljonData.mangaka}</span>
                        </div>
                    ` : ''}
                    ${nautiljonData.year_start ? `
                        <div class="info-item">
                            <span class="label">Years:</span>
                            <span class="value">${nautiljonData.year_start}${nautiljonData.year_end ? ` - ${nautiljonData.year_end}` : ''}</span>
                        </div>
                    ` : ''}
                </div>
                <div class="action-buttons">
                    <a href="${nautiljonData.url}" target="_blank" class="btn btn-primary">
                        View on Nautiljon ↗️
                    </a>
                </div>
                ${nautiljonData.updated_at ? `
                    <small class="updated-at">Last updated: ${new Date(nautiljonData.updated_at).toLocaleDateString()}</small>
                ` : ''}
            </div>
        `;

        container.innerHTML = html;
    },

    /**
     * Show enrichment progress modal
     * @param {Array<number>} seriesIds - Series being enriched
     * @returns {Promise<Object>} Enrichment results
     */
    async showEnrichmentProgress(seriesIds) {
        // Create progress modal
        const modal = document.createElement('div');
        modal.className = 'modal nautiljon-progress';
        modal.innerHTML = `
            <div class="modal-content">
                <h2>🔍 Enriching Series with Nautiljon Data</h2>
                <div class="progress-bar">
                    <div class="progress-fill" style="width: 0%"></div>
                </div>
                <p class="progress-text">Starting enrichment... <span class="count">0/${seriesIds.length}</span></p>
            </div>
        `;
        document.body.appendChild(modal);

        // Perform enrichment
        const results = await this.batchEnrichSeries(seriesIds);

        // Update modal with results
        const progressText = modal.querySelector('.progress-text');
        const progressFill = modal.querySelector('.progress-fill');
        const percentage = (results.succeeded / results.total) * 100;

        progressFill.style.width = percentage + '%';
        progressText.innerHTML = `
            ✅ Complete! <strong>${results.succeeded}/${results.total}</strong> series enriched
            ${results.failed > 0 ? `<br>❌ ${results.failed} failed` : ''}
        `;

        // Add close button
        const closeBtn = document.createElement('button');
        closeBtn.textContent = 'Close';
        closeBtn.className = 'btn btn-secondary';
        closeBtn.onclick = () => modal.remove();
        modal.querySelector('.modal-content').appendChild(closeBtn);

        return results;
    },

    /**
     * Get search results for a series with preview info
     * @param {number} seriesId - Series ID
     * @param {string} overrideTitle - Optional title to search instead of series title
     * @returns {Promise<Object>} Search results with preview data
     */
    async getSearchResultsForSeries(seriesId, overrideTitle = null) {
        try {
            let url = `/api/nautiljon/search-results/${seriesId}`;
            if (overrideTitle) {
                url += `?title=${encodeURIComponent(overrideTitle)}`;
            }
            const response = await fetch(url);
            if (!response.ok) throw new Error(`HTTP ${response.status}`);
            return await response.json();
        } catch (error) {
            console.error('Search results error:', error);
            return { success: false, error: error.message, results: [] };
        }
    }
};

// Make available globally
window.NautiljonAPI = NautiljonAPI;
