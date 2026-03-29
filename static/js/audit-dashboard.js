/**
 * Audit Dashboard JavaScript
 * Manages dashboard initialization, data fetching, and chart updates
 */

// Chart instances
let charts = {};

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', function() {
    console.log('🎯 Initializing audit dashboard...');
    
    // Check authentication
    checkAuth();
    
    // Initialize event listeners
    setupEventListeners();
    
    // Load initial data
    refreshDashboard();
    
    // Auto-refresh every 30 seconds
    setInterval(refreshDashboard, 30000);
});

/**
 * Check if user is authenticated and is admin
 */
function checkAuth() {
    fetch('/auth/current-user')
        .then(response => response.json())
        .then(data => {
            if (data.success && data.user) {
                document.getElementById('current-user').textContent = `👤 ${data.user.username}`;
            } else {
                window.location.href = '/auth/login';
            }
        })
        .catch(() => window.location.href = '/auth/login');
}

/**
 * Setup event listeners
 */
function setupEventListeners() {
    document.getElementById('logout-btn').addEventListener('click', logout);
}

/**
 * Refresh all dashboard data
 */
function refreshDashboard() {
    console.log('🔄 Refreshing dashboard...');
    showLoadingSpinner(true);
    
    const days = document.getElementById('days-selector').value;
    
    fetch(`/audit/dashboard-data?days=${days}`)
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('✓ Dashboard data received');
                updateDashboardContent(data.data);
                updateCharts(data.data);
                updateTables(data.data);
            } else {
                console.error('❌ Dashboard error:', data.error);
                showError(data.error);
            }
        })
        .catch(error => {
            console.error('❌ Fetch error:', error);
            showError('Erreur lors du chargement des données');
        })
        .finally(() => showLoadingSpinner(false));
}

/**
 * Update quick stats cards
 */
function updateDashboardContent(data) {
    const stats = data.quick_stats || {};
    
    document.getElementById('stat-total-events').textContent = stats.total_events || 0;
    document.getElementById('stat-failed-logins').textContent = stats.failed_logins || 0;
    document.getElementById('stat-users').textContent = stats.unique_users || 0;
    document.getElementById('stat-ips').textContent = stats.unique_ips || 0;
    document.getElementById('stat-user-creates').textContent = stats.user_creations || 0;
    document.getElementById('stat-user-deletes').textContent = stats.user_deletions || 0;
}

/**
 * Update all charts
 */
function updateCharts(data) {
    console.log('📊 Updating charts...');
    
    // Activity Trend Chart
    updateActivityTrendChart(data.activity_trend || {});
    
    // Failed Login Chart
    updateFailedLoginChart(data.failed_login_trend || {});
    
    // Action Distribution Chart
    updateActionDistributionChart(data.action_distribution || {});
    
    // User Activity Chart
    updateUserActivityChart(data.user_activity || {});
}

/**
 * Update activity trend line chart
 */
function updateActivityTrendChart(trend) {
    const ctx = document.getElementById('activity-trend-chart');
    if (!ctx) return;
    
    const dates = Object.keys(trend).sort();
    const values = dates.map(date => trend[date]);
    
    if (charts.activityTrend) {
        charts.activityTrend.data.labels = dates;
        charts.activityTrend.data.datasets[0].data = values;
        charts.activityTrend.update();
    } else {
        charts.activityTrend = new Chart(ctx, {
            type: 'line',
            data: {
                labels: dates,
                datasets: [{
                    label: 'Événements d\'activité',
                    data: values,
                    borderColor: '#1f77b4',
                    backgroundColor: 'rgba(31, 119, 180, 0.1)',
                    tension: 0.3,
                    fill: true
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { display: true }
                },
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }
}

/**
 * Update failed login chart
 */
function updateFailedLoginChart(trend) {
    const ctx = document.getElementById('failed-login-chart');
    if (!ctx) return;
    
    const dates = Object.keys(trend).sort();
    const values = dates.map(date => trend[date]);
    
    if (charts.failedLogin) {
        charts.failedLogin.data.labels = dates;
        charts.failedLogin.data.datasets[0].data = values;
        charts.failedLogin.update();
    } else {
        charts.failedLogin = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: dates,
                datasets: [{
                    label: 'Tentatives échouées',
                    data: values,
                    backgroundColor: 'rgba(214, 39, 40, 0.7)',
                    borderColor: 'rgb(214, 39, 40)',
                    borderWidth: 1
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { display: true }
                },
                scales: {
                    y: { beginAtZero: true }
                }
            }
        });
    }
}

/**
 * Update action distribution pie chart
 */
function updateActionDistributionChart(distribution) {
    const ctx = document.getElementById('action-distribution-chart');
    if (!ctx) return;
    
    const labels = Object.keys(distribution);
    const values = Object.values(distribution);
    
    const colors = ['#1f77b4', '#ff7f0e', '#2ca02c', '#d62728', '#9467bd'];
    
    if (charts.actionDistribution) {
        charts.actionDistribution.data.labels = labels;
        charts.actionDistribution.data.datasets[0].data = values;
        charts.actionDistribution.update();
    } else {
        charts.actionDistribution = new Chart(ctx, {
            type: 'doughnut',
            data: {
                labels: labels,
                datasets: [{
                    data: values,
                    backgroundColor: colors.slice(0, labels.length)
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { position: 'right' }
                }
            }
        });
    }
}

/**
 * Update user activity bar chart
 */
function updateUserActivityChart(userActivity) {
    const ctx = document.getElementById('user-activity-chart');
    if (!ctx) return;
    
    const users = Object.keys(userActivity);
    const counts = Object.values(userActivity);
    
    if (charts.userActivity) {
        charts.userActivity.data.labels = users;
        charts.userActivity.data.datasets[0].data = counts;
        charts.userActivity.update();
    } else {
        charts.userActivity = new Chart(ctx, {
            type: 'bar',
            data: {
                labels: users,
                datasets: [{
                    label: 'Nombre d\'événements',
                    data: counts,
                    backgroundColor: 'rgba(44, 160, 44, 0.7)',
                    borderColor: 'rgb(44, 160, 44)',
                    borderWidth: 1
                }]
            },
            options: {
                indexAxis: 'y',
                responsive: true,
                maintainAspectRatio: true,
                plugins: {
                    legend: { display: false }
                },
                scales: {
                    x: { beginAtZero: true }
                }
            }
        });
    }
}

/**
 * Update data tables
 */
function updateTables(data) {
    updateIPStatsTable(data.ip_statistics || {});
    updateActivityTable(data.recent_activity || []);
}

/**
 * Update IP statistics table
 */
function updateIPStatsTable(ipStats) {
    const tbody = document.getElementById('ip-stats-body');
    const table = document.getElementById('ip-stats-table');
    
    if (!tbody) return;
    
    const ips = Object.keys(ipStats);
    const total = Object.values(ipStats).reduce((a, b) => a + b, 0);
    
    if (ips.length === 0) {
        tbody.innerHTML = '<tr><td colspan="3" class="no-data">Aucune données</td></tr>';
        return;
    }
    
    tbody.innerHTML = ips.map(ip => {
        const count = ipStats[ip];
        const percentage = ((count / total) * 100).toFixed(1);
        return `
            <tr>
                <td><code>${escapeHtml(ip)}</code></td>
                <td>${count}</td>
                <td><div class="progress-bar" style="width: ${percentage}%">${percentage}%</div></td>
            </tr>
        `;
    }).join('');
}

/**
 * Update recent activity table
 */
function updateActivityTable(activities) {
    const tbody = document.getElementById('activity-body');
    
    if (!tbody) return;
    
    if (activities.length === 0) {
        tbody.innerHTML = '<tr><td colspan="5" class="no-data">Aucune activité</td></tr>';
        return;
    }
    
    tbody.innerHTML = activities.slice(0, 50).map(activity => {
        const timestamp = new Date(activity.timestamp).toLocaleString('fr-FR');
        const level = activity.level || 'INFO';
        const levelClass = level === 'ERROR' ? 'error' : level === 'WARNING' ? 'warning' : 'info';
        
        return `
            <tr class="activity-row ${levelClass}">
                <td>${escapeHtml(timestamp)}</td>
                <td>${escapeHtml(activity.username || '-')}</td>
                <td>${escapeHtml(activity.action || '-')}</td>
                <td><code>${escapeHtml(activity.ip_address || '-')}</code></td>
                <td><span class="level-badge ${levelClass}">${level}</span></td>
            </tr>
        `;
    }).join('');
}

/**
 * Update dashboard when period changes
 */
function updateDashboard() {
    console.log('📅 Period changed, updating...');
    refreshDashboard();
}

/**
 * Show/hide loading spinner
 */
function showLoadingSpinner(show) {
    const spinner = document.getElementById('loading-spinner');
    if (spinner) {
        spinner.classList.toggle('hidden', !show);
    }
}

/**
 * Show error message
 */
function showError(message) {
    alert(`❌ Erreur: ${message}`);
}

/**
 * Go to page
 */
function goToPage(path) {
    window.location.href = path;
}

/**
 * Show section
 */
function showSection(section) {
    alert(`Section ${section} - À implémenter`);
}

/**
 * Open export dialog
 */
function openExport() {
    window.location.href = '/audit/export';
}

/**
 * Logout user
 */
function logout() {
    if (confirm('Êtes-vous sûr de vouloir vous déconnecter?')) {
        fetch('/auth/logout', { method: 'POST' })
            .then(() => window.location.href = '/auth/login')
            .catch(error => console.error('Logout error:', error));
    }
}

/**
 * Escape HTML special characters
 */
function escapeHtml(text) {
    const map = {
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        '"': '&quot;',
        "'": '&#039;'
    };
    return String(text).replace(/[&<>"']/g, m => map[m]);
}
