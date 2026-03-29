// 👥 User Management JavaScript
// Handles CRUD operations for user management interface

let currentDeleteUserId = null;
let currentEditUserId = null;
let currentResetPwdUserId = null;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    loadUsers();
});

/**
 * Load all users from API
 */
async function loadUsers() {
    try {
        const response = await apiCall('/auth/users', 'GET');
        
        if (!response.success) {
            showError('Erreur lors du chargement des utilisateurs');
            return;
        }

        const users = response.users || [];
        renderUsersTable(users);
        updateStats(users);

        // Preserve main admin button state
        setTimeout(() => updateButtonStates(users), 100);
    } catch (error) {
        console.error('Error loading users:', error);
        showError('Impossible de charger les utilisateurs');
    }
}

/**
 * Render users table with data
 */
function renderUsersTable(users) {
    const tbody = document.getElementById('users-tbody');
    
    if (users.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="5" class="no-users">
                    Aucun utilisateur - Créez-en un nouveau
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = users.map(user => `
        <tr>
            <td><span class="user-id">#${user.id}</span></td>
            <td>${escapeHtml(user.username)}</td>
            <td>
                <span class="admin-badge ${user.is_admin}">
                    ${user.is_admin ? '🔒 Admin' : '👤 Utilisateur'}
                </span>
            </td>
            <td>
                ${user.is_admin ? 'Accès complèt' : 'Accès limité'}
            </td>
            <td>
                <div class="user-actions">
                    <button class="btn-action btn-edit" 
                            onclick="openEditModal('${user.id}', '${escapeHtml(user.username)}', ${user.is_admin})"
                            ${user.id === '1' ? 'disabled' : ''}>
                        ✏️ Éditer
                    </button>
                    <button class="btn-action btn-reset-pwd" 
                            onclick="openResetPwdModal('${user.id}', '${escapeHtml(user.username)}')">
                        🔑 Pwd
                    </button>
                    <button class="btn-action btn-delete" 
                            onclick="openDeleteModal('${user.id}', '${escapeHtml(user.username)}')"
                            ${user.id === '1' ? 'disabled' : ''}>
                        🗑️ Supp.
                    </button>
                </div>
            </td>
        </tr>
    `).join('');
}

/**
 * Update statistics cards
 */
function updateStats(users) {
    const totalUsers = users.length;
    const adminUsers = users.filter(u => u.is_admin).length;
    const normalUsers = totalUsers - adminUsers;

    document.getElementById('total-users').textContent = totalUsers;
    document.getElementById('admin-users').textContent = adminUsers;
    document.getElementById('normal-users').textContent = normalUsers;
}

/**
 * Update button states for main admin
 */
function updateButtonStates(users) {
    const mainAdminButtons = document.querySelectorAll('button[onclick*="\'1\'"]');
    mainAdminButtons.forEach(btn => {
        if (btn.classList.contains('btn-edit') || btn.classList.contains('btn-delete')) {
            btn.disabled = true;
            btn.classList.add('btn-disabled');
            btn.title = 'Cannot modify main admin user';
        }
    });
}

/**
 * Modal Management
 */
function openCreateModal() {
    document.getElementById('createForm').reset();
    document.getElementById('create-error').style.display = 'none';
    document.getElementById('createModal').classList.add('active');
}

function closeCreateModal() {
    document.getElementById('createModal').classList.remove('active');
    document.getElementById('create-error').innerHTML = '';
}

function openEditModal(userId, username, isAdmin) {
    document.getElementById('edit-user-id').value = userId;
    document.getElementById('edit-username').textContent = username;
    document.getElementById('edit-is-admin').checked = isAdmin;
    document.getElementById('edit-error').style.display = 'none';
    document.getElementById('editModal').classList.add('active');
}

function closeEditModal() {
    document.getElementById('editModal').classList.remove('active');
    document.getElementById('edit-error').innerHTML = '';
}

function openResetPwdModal(userId, username) {
    document.getElementById('reset-user-id').value = userId;
    document.getElementById('reset-username').textContent = username;
    document.getElementById('new-password').value = '';
    document.getElementById('reset-error').style.display = 'none';
    document.getElementById('resetPwdModal').classList.add('active');
}

function closeResetPwdModal() {
    document.getElementById('resetPwdModal').classList.remove('active');
    document.getElementById('reset-error').innerHTML = '';
}

function openDeleteModal(userId, username) {
    currentDeleteUserId = userId;
    document.getElementById('delete-message').innerHTML = `
        Êtes-vous sûr de vouloir supprimer l'utilisateur <strong>${username}</strong> ?<br>
        <span style="color: #f44336; font-size: 12px; margin-top: 10px; display: block;">
            Cette action est irréversible.
        </span>
    `;
    document.getElementById('deleteModal').classList.add('active');
}

function closeDeleteModal() {
    document.getElementById('deleteModal').classList.remove('active');
    currentDeleteUserId = null;
}

/**
 * Handle Create User Form
 */
async function handleCreateUser(event) {
    event.preventDefault();

    const username = document.getElementById('username').value.trim().toLowerCase();
    const password = document.getElementById('password').value;
    const isAdmin = document.getElementById('is_admin').checked;

    // Client-side validation
    if (username.length < 3) {
        showCreateError('Username doit avoir au moins 3 caractères');
        return;
    }
    if (username.length > 32) {
        showCreateError('Username doit avoir au maximum 32 caractères');
        return;
    }
    if (password.length < 8) {
        showCreateError('Mot de passe doit avoir au moins 8 caractères');
        return;
    }

    try {
        const response = await apiCall('/auth/users', 'POST', {
            username,
            password,
            is_admin: isAdmin
        });

        if (response.success) {
            showSuccess(`Utilisateur ${username} créé avec succès`);
            closeCreateModal();
            setTimeout(loadUsers, 500);
        } else {
            showCreateError(response.error || 'Erreur lors de la création');
        }
    } catch (error) {
        console.error('Error creating user:', error);
        showCreateError('Erreur lors de la création de l\'utilisateur');
    }
}

/**
 * Handle Edit User Form
 */
async function handleEditUser(event) {
    event.preventDefault();

    const userId = document.getElementById('edit-user-id').value;
    const isAdmin = document.getElementById('edit-is-admin').checked;

    // Prevent removing admin status from main admin
    if (userId === '1' && !isAdmin) {
        showEditError('Cannot remove admin status from main admin');
        return;
    }

    try {
        const response = await apiCall(`/auth/users/${userId}`, 'PUT', {
            is_admin: isAdmin
        });

        if (response.success) {
            showSuccess('Utilisateur modifié avec succès');
            closeEditModal();
            setTimeout(loadUsers, 500);
        } else {
            showEditError(response.error || 'Erreur lors de la modification');
        }
    } catch (error) {
        console.error('Error editing user:', error);
        showEditError('Erreur lors de la modification');
    }
}

/**
 * Handle Reset Password
 */
async function handleResetPassword(event) {
    event.preventDefault();

    const userId = document.getElementById('reset-user-id').value;
    const password = document.getElementById('new-password').value;

    if (password.length < 8) {
        showResetError('Mot de passe doit avoir au moins 8 caractères');
        return;
    }

    try {
        const response = await apiCall(`/auth/users/${userId}/reset-password`, 'POST', {
            password
        });

        if (response.success) {
            showSuccess('Mot de passe réinitialisé avec succès');
            closeResetPwdModal();
            setTimeout(loadUsers, 500);
        } else {
            showResetError(response.error || 'Erreur lors de la réinitialisation');
        }
    } catch (error) {
        console.error('Error resetting password:', error);
        showResetError('Erreur lors de la réinitialisation du mot de passe');
    }
}

/**
 * Confirm and Execute Delete
 */
async function confirmDelete() {
    if (!currentDeleteUserId) return;

    // Prevent deleting main admin
    if (currentDeleteUserId === '1') {
        showError('Impossible de supprimer l\'administrateur principal');
        closeDeleteModal();
        return;
    }

    try {
        const response = await apiCall(`/auth/users/${currentDeleteUserId}`, 'DELETE');

        if (response.success) {
            showSuccess('Utilisateur supprimé avec succès');
            closeDeleteModal();
            setTimeout(loadUsers, 500);
        } else {
            showError(response.error || 'Erreur lors de la suppression');
            closeDeleteModal();
        }
    } catch (error) {
        console.error('Error deleting user:', error);
        showError('Erreur lors de la suppression de l\'utilisateur');
        closeDeleteModal();
    }
}

/**
 * Error/Success Message Handlers
 */
function showError(message) {
    const container = document.getElementById('error-container');
    container.innerHTML = `<div class="error-message">${escapeHtml(message)}</div>`;
    setTimeout(() => container.innerHTML = '', 5000);
}

function showSuccess(message) {
    const container = document.getElementById('success-container');
    container.innerHTML = `<div class="success-message">${escapeHtml(message)}</div>`;
    setTimeout(() => container.innerHTML = '', 5000);
}

function showCreateError(message) {
    const errorDiv = document.getElementById('create-error');
    errorDiv.innerHTML = escapeHtml(message);
    errorDiv.style.display = 'block';
}

function showEditError(message) {
    const errorDiv = document.getElementById('edit-error');
    errorDiv.innerHTML = escapeHtml(message);
    errorDiv.style.display = 'block';
}

function showResetError(message) {
    const errorDiv = document.getElementById('reset-error');
    errorDiv.innerHTML = escapeHtml(message);
    errorDiv.style.display = 'block';
}

/**
 * Utility: API Call Wrapper with CSRF Token
 */
async function apiCall(endpoint, method = 'GET', data = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRFToken': getCookie('csrf_token') || ''
        }
    };

    if (data) {
        options.body = JSON.stringify(data);
    }

    const response = await fetch(endpoint, options);
    return await response.json();
}

/**
 * Utility: Get CSRF Token from Cookie
 */
function getCookie(name) {
    const value = `; ${document.cookie}`;
    const parts = value.split(`; ${name}=`);
    if (parts.length === 2) return parts.pop().split(';').shift();
    return '';
}

/**
 * Utility: Escape HTML to prevent XSS
 */
function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Allow closing modals by clicking outside
window.onclick = function(event) {
    const createModal = document.getElementById('createModal');
    const editModal = document.getElementById('editModal');
    const resetPwdModal = document.getElementById('resetPwdModal');
    const deleteModal = document.getElementById('deleteModal');

    if (event.target === createModal) {
        closeCreateModal();
    } else if (event.target === editModal) {
        closeEditModal();
    } else if (event.target === resetPwdModal) {
        closeResetPwdModal();
    } else if (event.target === deleteModal) {
        closeDeleteModal();
    }
}
