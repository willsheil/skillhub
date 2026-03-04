/**
 * Skill Management - My Skills Page
 * Handles skill listing, filtering, and actions
 */

// State
let allSkills = [];
let filteredSkills = [];
let currentStatus = 'all';
let currentPage = 1;
let pageSize = 12;
let searchQuery = '';
let statusCounts = { all: 0, active: 0, unlisted: 0, pending: 0, rejected: 0 };
let confirmCallback = null;
let searchDebounceTimer = null;
let selectedSkillIds = new Set();  // Track selected skill IDs for batch operations

// Skill icons mapping
function getSkillIcon(skillName) {
    const name = skillName.toLowerCase();

    if (name.includes('代码') || name.includes('code') || name.includes('programming')) return '💻';
    if (name.includes('安全') || name.includes('security') || name.includes('audit')) return '🔒';
    if (name.includes('分析') || name.includes('analysis') || name.includes('analytics')) return '📊';
    if (name.includes('搜索') || name.includes('search') || name.includes('find')) return '🔍';
    if (name.includes('效率') || name.includes('productivity') || name.includes('tool')) return '⚡';
    if (name.includes('ai') || name.includes('智能') || name.includes('gpt')) return '🤖';
    if (name.includes('文件') || name.includes('file') || name.includes('document')) return '📁';
    if (name.includes('网络') || name.includes('network') || name.includes('web')) return '🌐';
    if (name.includes('测试') || name.includes('test') || name.includes('check')) return '🧪';
    if (name.includes('数据库') || name.includes('database') || name.includes('db')) return '🗄️';
    if (name.includes('api') || name.includes('接口')) return '🔌';
    if (name.includes('部署') || name.includes('deploy') || name.includes('devops')) return '🚀';
    if (name.includes('监控') || name.includes('monitor') || name.includes('alert')) return '📈';
    if (name.includes('日志') || name.includes('log') || name.includes('debug')) return '📋';
    if (name.includes('代码审查') || name.includes('review') || name.includes('lint')) return '👁️';
    if (name.includes('重构') || name.includes('refactor') || name.includes('format')) return '🔧';

    return '📦';
}

// Format date
function formatDate(dateString) {
    if (!dateString) return '未知';

    const date = new Date(dateString);
    const now = new Date();
    const diffMs = now - date;
    const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));

    if (diffDays === 0) return '今天';
    if (diffDays === 1) return '昨天';
    if (diffDays < 7) return `${diffDays} 天前`;
    if (diffDays < 30) return `${Math.floor(diffDays / 7)} 周前`;
    if (diffDays < 365) return `${Math.floor(diffDays / 30)} 月前`;

    return date.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

// Escape HTML to prevent XSS
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Show toast notification
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    toast.textContent = message;
    toast.className = `toast ${type} show`;

    setTimeout(() => {
        toast.classList.remove('show');
    }, 3000);
}

// Show confirm dialog
function showConfirmDialog(title, content, onConfirm) {
    const dialog = document.getElementById('confirmDialog');
    document.getElementById('dialogTitle').textContent = title;
    document.getElementById('dialogContent').textContent = content;
    confirmCallback = onConfirm;
    dialog.classList.add('show');
}

// Hide confirm dialog
function hideConfirmDialog() {
    document.getElementById('confirmDialog').classList.remove('show');
    confirmCallback = null;
}

// Initialize dialog buttons
document.getElementById('dialogCancel').addEventListener('click', hideConfirmDialog);
document.getElementById('dialogConfirm').addEventListener('click', () => {
    if (confirmCallback) confirmCallback();
    hideConfirmDialog();
});

// Close dialog on overlay click
document.getElementById('confirmDialog').addEventListener('click', (e) => {
    if (e.target.id === 'confirmDialog') hideConfirmDialog();
});

// Load skills from API
async function loadSkills() {
    try {
        const response = await fetch(`/api/my-skills?status=${currentStatus}&page=${currentPage}&per_page=100`);
        if (!response.ok) {
            throw new Error('Failed to load skills');
        }

        const result = await response.json();
        allSkills = result.data || [];

        // Calculate status counts
        calculateStatusCounts();

        // Filter and render
        filterAndRenderSkills();

    } catch (error) {
        console.error('Error loading skills:', error);
        document.getElementById('skillsList').innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">⚠️</div>
                <h3>加载失败</h3>
                <p>无法加载技能列表，请刷新页面重试</p>
                <button class="btn-action primary" onclick="location.reload()" style="margin-top: 12px;">刷新页面</button>
            </div>
        `;
    }
}

// Calculate status counts
async function calculateStatusCounts() {
    // For now, calculate from loaded data
    // In production, you might want a dedicated API endpoint
    statusCounts = { all: allSkills.length, active: 0, unlisted: 0, pending: 0, rejected: 0 };

    allSkills.forEach(skill => {
        if (skill.status === 'approved') {
            if (skill.is_active) {
                statusCounts.active++;
            } else {
                statusCounts.unlisted++;
            }
        } else if (skill.status === 'pending') {
            statusCounts.pending++;
        } else if (skill.status === 'rejected') {
            statusCounts.rejected++;
        }
        // all count is set above
    });

    updateStatusCounts();
}

// Update status count badges
function updateStatusCounts() {
    document.getElementById('count-all').textContent = statusCounts.all;
    document.getElementById('count-active').textContent = statusCounts.active;
    document.getElementById('count-unlisted').textContent = statusCounts.unlisted;
    document.getElementById('count-pending').textContent = statusCounts.pending;
    document.getElementById('count-rejected').textContent = statusCounts.rejected;
}

// Filter and render skills
function filterAndRenderSkills() {
    // Filter by search query
    filteredSkills = allSkills.filter(skill => {
        if (!searchQuery) return true;
        const query = searchQuery.toLowerCase();
        return skill.skill_name.toLowerCase().includes(query);
    });

    // Sort by upload date (newest first)
    filteredSkills.sort((a, b) => new Date(b.uploaded_at) - new Date(a.uploaded_at));

    // Render
    renderSkills(filteredSkills);
    updatePagination();
}

// Render skills
function renderSkills(skills) {
    const container = document.getElementById('skillsList');

    if (skills.length === 0) {
        const emptyMessage = searchQuery
            ? '没有找到匹配的技能'
            : getStatusEmptyMessage();

        container.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">📦</div>
                <h3>${emptyMessage.title}</h3>
                <p>${emptyMessage.subtitle}</p>
                ${!searchQuery ? '<a href="/upload" class="btn-upload" style="display: inline-flex; margin-top: 12px;">上传第一个技能</a>' : ''}
            </div>
        `;
        return;
    }

    container.innerHTML = skills.map(skill => renderSkillCard(skill)).join('');

    // Add event listeners
    attachSkillEventListeners();
}

// Get empty state message based on current status filter
function getStatusEmptyMessage() {
    const messages = {
        all: { title: '还没有上传任何技能', subtitle: '点击上方"上传新技能"按钮开始上传' },
        active: { title: '没有已发布的技能', subtitle: '审核通过并发布的技能会显示在这里' },
        unlisted: { title: '没有未上架的技能', subtitle: '您可以随时发布或隐藏已审核通过的技能' },
        pending: { title: '没有待审核的技能', subtitle: '上传的技能需要管理员审核后才能发布' },
        rejected: { title: '没有被拒绝的技能', subtitle: '被拒绝的技能可以修改后重新上传' }
    };
    return messages[currentStatus] || messages.all;
}

// Render a skill card
function renderSkillCard(skill) {
    const icon = getSkillIcon(skill.skill_name);
    const isSelected = selectedSkillIds.has(skill.id);

    // Determine status badge
    let statusBadge = '';
    let activeBadge = '';
    let rejectionReason = '';

    if (skill.status === 'pending') {
        statusBadge = '<span class="badge badge-status pending">待审核</span>';
    } else if (skill.status === 'rejected') {
        statusBadge = '<span class="badge badge-status rejected">已拒绝</span>';
        // Add rejection reason if available
        if (skill.review_comment) {
            rejectionReason = `<div class="rejection-reason">拒绝原因: ${escapeHtml(skill.review_comment)}</div>`;
        }
    } else if (skill.status === 'approved') {
        if (skill.is_active) {
            statusBadge = '<span class="badge badge-status">已发布</span>';
            activeBadge = '<span class="badge badge-active">Active</span>';
        } else {
            statusBadge = '<span class="badge badge-status unlisted">未上架</span>';
        }
    }

    // Count downloads (mock data for now)
    const downloads = skill.download_count || 0;

    // Generate action buttons
    const actionButtons = generateActionButtons(skill);

    return `
        <div class="skill-group" data-skill-id="${skill.id}">
            <div class="skill-card-header">
                <div class="skill-checkbox">
                    <input type="checkbox" class="skill-select-checkbox" data-skill-id="${skill.id}" ${isSelected ? 'checked' : ''} onclick="event.stopPropagation(); toggleSkillSelection(${skill.id})">
                </div>
                <div class="skill-icon">${icon}</div>
                <div class="skill-info">
                    <div class="skill-name-row">
                        <span class="skill-name">${skill.skill_name}</span>
                        <div class="skill-badges">
                            ${statusBadge}
                            ${activeBadge}
                        </div>
                    </div>
                    ${rejectionReason}
                    <div class="skill-meta">
                        <span class="meta-item">
                            <span class="meta-icon">📦</span>
                            v${skill.version}
                        </span>
                        <span class="meta-item">
                            <span class="meta-icon">📅</span>
                            ${formatDate(skill.uploaded_at)}
                        </span>
                        <span class="meta-item">
                            <span class="meta-icon">⬇️</span>
                            ${downloads} 次下载
                        </span>
                    </div>
                </div>
                ${actionButtons}
            </div>
        </div>
    `;
}

// Generate action buttons for a skill
function generateActionButtons(skill) {
    let buttons = '';
    const skillName = encodeURIComponent(skill.skill_name);

    // Re-upload button (update)
    buttons += `
        <a href="/upload?skill_name=${skillName}" class="btn-action" onclick="event.stopPropagation();">
            更新技能
        </a>
    `;

    if (skill.status === 'approved') {
        if (skill.is_active) {
            buttons += `
                <button class="btn-action danger" onclick="event.stopPropagation(); unlistSkill(${skill.id}, '${skillName}', '${skill.version}')">
                    下架
                </button>
            `;
        } else {
            buttons += `
                <button class="btn-action primary" onclick="event.stopPropagation(); publishSkill(${skill.id}, '${skillName}', '${skill.version}')">
                    发布
                </button>
            `;
        }
    } else if (skill.status === 'pending') {
        buttons += `<span style="font-size: 13px; color: #a1a1aa;">等待审核...</span>`;
    } else if (skill.status === 'rejected') {
        buttons += `
            <a href="/upload?skill_name=${skillName}" class="btn-action" onclick="event.stopPropagation();">
                重新上传
            </a>
        `;
    }

    // Delete button (admin only)
    if (window.currentUserRole === 'admin') {
        buttons += `
            <button class="btn-action danger" onclick="event.stopPropagation(); deleteSkill(${skill.id}, '${skillName}', '${skill.version}')" style="margin-left: 4px;">
                删除
            </button>
        `;
    }

    return `<div class="skill-actions">${buttons}</div>`;
}

// Attach event listeners
function attachSkillEventListeners() {
    // No expand/collapse functionality needed in single-version mode
}

// Unlist a skill
async function unlistSkill(skillId, skillName, version) {
    showConfirmDialog(
        '确认下架',
        `确定要下架 ${decodeURIComponent(skillName)}@${version} 吗？下架后用户将无法下载此技能。`,
        async () => {
            try {
                const response = await fetch(`/api/my-skills/${skillId}/unlist`, {
                    method: 'POST'
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || '下架失败');
                }

                showToast('技能已下架');
                await loadSkills(); // Reload to refresh data

            } catch (error) {
                console.error('Error unlisting skill:', error);
                showToast(error.message || '下架失败', 'error');
            }
        }
    );
}

// Publish a skill
async function publishSkill(skillId, skillName, version) {
    showConfirmDialog(
        '确认发布',
        `确定要发布 ${decodeURIComponent(skillName)}@${version} 吗？发布后用户即可下载此技能。`,
        async () => {
            try {
                const response = await fetch(`/api/my-skills/${skillId}/publish`, {
                    method: 'POST'
                });

                if (!response.ok) {
                    const error = await response.json();
                    throw new Error(error.detail || '发布失败');
                }

                showToast('技能已发布');
                await loadSkills(); // Reload to refresh data

            } catch (error) {
                console.error('Error publishing skill:', error);
                showToast(error.message || '发布失败', 'error');
            }
        }
    );
}

// Update pagination
function updatePagination() {
    const totalPages = Math.ceil(filteredSkills.length / pageSize);
    const pagination = document.getElementById('pagination');

    if (totalPages <= 1) {
        pagination.style.display = 'none';
        return;
    }

    pagination.style.display = 'flex';

    let buttons = '';

    buttons += `<button class="page-btn" ${currentPage === 1 ? 'disabled' : ''} onclick="goToPage(${currentPage - 1})">‹ 上一页</button>`;

    for (let i = 1; i <= totalPages; i++) {
        buttons += `<button class="page-btn ${i === currentPage ? 'active' : ''}" onclick="goToPage(${i})">${i}</button>`;
    }

    buttons += `<button class="page-btn" ${currentPage >= totalPages ? 'disabled' : ''} onclick="goToPage(${currentPage + 1})">下一页 ›</button>`;

    pagination.innerHTML = buttons;
}

// Go to page
function goToPage(page) {
    currentPage = page;
    filterAndRenderSkills();
    window.scrollTo({ top: 0, behavior: 'smooth' });
}

// Handle filter tab click
function handleFilterClick(status) {
    currentStatus = status;
    currentPage = 1;

    // Update active tab
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.status === status);
    });

    // Reload data with new filter
    loadSkills();
}

// Handle search input
function handleSearch(value) {
    searchQuery = value.trim();
    currentPage = 1;
    filterAndRenderSkills();
}

// Initialize event listeners
function initEventListeners() {
    // Filter tabs
    document.querySelectorAll('.filter-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            handleFilterClick(tab.dataset.status);
        });
    });

    // Search input with debounce
    const searchInput = document.getElementById('searchInput');
    searchInput.addEventListener('input', (e) => {
        clearTimeout(searchDebounceTimer);
        searchDebounceTimer = setTimeout(() => {
            handleSearch(e.target.value);
        }, 300);
    });
}

// Toggle skill selection
function toggleSkillSelection(skillId) {
    if (selectedSkillIds.has(skillId)) {
        selectedSkillIds.delete(skillId);
    } else {
        selectedSkillIds.add(skillId);
    }
    updateBatchActionsBar();
}

// Toggle all skills selection
function toggleAllSkills(checked) {
    const checkboxes = document.querySelectorAll('.skill-select-checkbox');
    if (checked) {
        checkboxes.forEach(cb => {
            const skillId = parseInt(cb.dataset.skillId);
            selectedSkillIds.add(skillId);
            cb.checked = true;
        });
    } else {
        selectedSkillIds.clear();
        checkboxes.forEach(cb => {
            cb.checked = false;
        });
    }
    updateBatchActionsBar();
}

// Update batch actions bar visibility
function updateBatchActionsBar() {
    const batchActionsBar = document.getElementById('batchActionsBar');
    if (!batchActionsBar) return;

    const count = selectedSkillIds.size;
    if (count > 0) {
        batchActionsBar.classList.add('show');
        document.getElementById('selectedCount').textContent = count;
    } else {
        batchActionsBar.classList.remove('show');
    }
}

// Delete a single skill
async function deleteSkill(skillId, skillName, version) {
    showConfirmDialog(
        '确认删除',
        `确定要删除 ${decodeURIComponent(skillName)}@${version} 吗？删除后无法恢复！`,
        async () => {
            try {
                const response = await fetch(`/api/my-skills/${skillId}`, {
                    method: 'DELETE'
                });

                if (!response.ok) {
                    let errorMsg = '删除失败';
                    try {
                        const error = await response.json();
                        errorMsg = error.detail || errorMsg;
                    } catch (e) {
                        errorMsg = `删除失败 (HTTP ${response.status})`;
                    }
                    throw new Error(errorMsg);
                }

                showToast('技能已删除');
                selectedSkillIds.delete(skillId);
                updateBatchActionsBar();
                await loadSkills(); // Reload to refresh data

            } catch (error) {
                console.error('Error deleting skill:', error);
                showToast(error.message || '删除失败', 'error');
            }
        }
    );
}

// Batch unlist skills
async function batchUnlistSkills() {
    if (selectedSkillIds.size === 0) return;

    const skillIds = Array.from(selectedSkillIds);
    showConfirmDialog(
        '确认批量下架',
        `确定要下架选中的 ${skillIds.length} 个技能吗？`,
        async () => {
            try {
                const response = await fetch('/api/my-skills/batch/unlist', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ skill_ids: skillIds })
                });

                if (!response.ok) {
                    let errorMsg = '批量下架失败';
                    try {
                        const error = await response.json();
                        errorMsg = error.detail || errorMsg;
                    } catch (e) {
                        errorMsg = `批量下架失败 (HTTP ${response.status})`;
                    }
                    throw new Error(errorMsg);
                }

                const result = await response.json();
                showToast(result.message || '批量下架成功');
                selectedSkillIds.clear();
                updateBatchActionsBar();
                await loadSkills();

            } catch (error) {
                console.error('Error batch unsting skills:', error);
                showToast(error.message || '批量下架失败', 'error');
            }
        }
    );
}

// Batch delete skills
async function batchDeleteSkills() {
    if (selectedSkillIds.size === 0) return;

    const skillIds = Array.from(selectedSkillIds);
    showConfirmDialog(
        '确认批量删除',
        `确定要删除选中的 ${skillIds.length} 个技能吗？删除后无法恢复！`,
        async () => {
            try {
                const response = await fetch('/api/my-skills/batch/delete', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ skill_ids: skillIds })
                });

                if (!response.ok) {
                    let errorMsg = '批量删除失败';
                    try {
                        const error = await response.json();
                        errorMsg = error.detail || errorMsg;
                    } catch (e) {
                        errorMsg = `批量删除失败 (HTTP ${response.status})`;
                    }
                    throw new Error(errorMsg);
                }

                const result = await response.json();
                showToast(result.message || '批量删除成功');
                selectedSkillIds.clear();
                updateBatchActionsBar();
                await loadSkills();

            } catch (error) {
                console.error('Error batch deleting skills:', error);
                showToast(error.message || '批量删除失败', 'error');
            }
        }
    );
}

// Cancel selection
function cancelSelection() {
    selectedSkillIds.clear();
    document.querySelectorAll('.skill-select-checkbox').forEach(cb => {
        cb.checked = false;
    });
    updateBatchActionsBar();
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    initEventListeners();
    loadSkills();
});
