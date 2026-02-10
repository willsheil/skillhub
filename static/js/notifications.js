/**
 * Notification Bell UI Component
 * Handles polling, display, and interaction for user notifications
 */

(function() {
    'use strict';

    // Configuration
    const CONFIG = {
        pollInterval: 30000, // 30 seconds
        apiEndpoints: {
            unreadCount: '/api/notifications/unread-count',
            list: '/api/notifications',
            markRead: '/api/notifications/{id}/read',
            markAllRead: '/api/notifications/read-all'
        },
        maxDisplay: 5
    };

    // State
    let pollTimer = null;
    let isDropdownOpen = false;
    let isPaused = false;
    let unreadCount = 0;

    // DOM Elements
    let bell, badge, dropdown, notificationList;

    /**
     * Initialize the notification system
     */
    function init() {
        // Only initialize for logged-in users
        const employeeIdSpan = document.querySelector('.user-actions span[style*="employee_id"]');
        if (!employeeIdSpan) return;

        // Inject notification bell HTML
        injectNotificationBell();

        // Cache DOM elements
        bell = document.getElementById('notificationBell');
        badge = document.getElementById('notificationBadge');
        dropdown = document.getElementById('notificationDropdown');
        notificationList = document.getElementById('notificationList');

        // Setup event listeners
        setupEventListeners();

        // Start polling
        startPolling();

        // Initial fetch
        updateUnreadCount();
    }

    /**
     * Inject notification bell HTML into the DOM
     */
    function injectNotificationBell() {
        const userActions = document.querySelector('.user-actions');
        if (!userActions) return;

        const notificationHTML = `
            <div class="notification-wrapper">
                <button class="notification-bell" id="notificationBell" aria-label="通知">
                    <svg width="20" height="20" viewBox="0 0 20 20" fill="none" xmlns="http://www.w3.org/2000/svg">
                        <path d="M10 2.5C7.23858 2.5 5 4.73858 5 7.5V10.2676C5 10.9066 4.73939 11.5215 4.27279 11.9791L3.85901 12.3847C3.33105 12.9027 3.69146 13.75 4.42963 13.75H15.5704C16.3085 13.75 16.6689 12.9027 16.141 12.3847L15.7272 11.9791C15.2606 11.5215 15 10.9066 15 10.2676V7.5C15 4.73858 12.7614 2.5 10 2.5Z" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                        <path d="M8 15C8.23209 15.8664 8.87273 16.5634 9.72508 16.8593C9.90507 16.9213 10.0949 16.9213 10.2749 16.8593C11.1273 16.5634 11.7679 15.8664 12 15" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"/>
                    </svg>
                    <span class="badge" id="notificationBadge"></span>
                </button>
                <div class="dropdown" id="notificationDropdown">
                    <div class="header">
                        <span>通知</span>
                        <a href="#" class="mark-all-read" id="markAllReadBtn">全部已读</a>
                    </div>
                    <div class="list" id="notificationList">
                        <div class="loading">加载中...</div>
                    </div>
                    <div class="footer">
                        <a href="/notifications">查看全部</a>
                    </div>
                </div>
            </div>
        `;

        // Insert before the employee_id span
        const employeeIdSpan = userActions.querySelector('span');
        if (employeeIdSpan) {
            employeeIdSpan.insertAdjacentHTML('beforebegin', notificationHTML);
        } else {
            userActions.insertAdjacentHTML('afterbegin', notificationHTML);
        }

        // Inject CSS styles
        injectStyles();
    }

    /**
     * Inject CSS styles for the notification bell
     */
    function injectStyles() {
        if (document.getElementById('notification-styles')) return;

        const style = document.createElement('style');
        style.id = 'notification-styles';
        style.textContent = `
            /* Notification Wrapper */
            .notification-wrapper {
                position: relative;
            }

            /* Bell Button */
            .notification-bell {
                position: relative;
                width: 40px;
                height: 40px;
                display: flex;
                align-items: center;
                justify-content: center;
                background: transparent;
                border: none;
                border-radius: 8px;
                cursor: pointer;
                color: #64748b;
                transition: all 0.2s ease;
            }

            .notification-bell:hover {
                background: #f3f4f6;
                color: #10B981;
            }

            .notification-bell:focus {
                outline: none;
                box-shadow: 0 0 0 2px rgba(16, 185, 129, 0.2);
            }

            /* Badge */
            .notification-bell .badge {
                position: absolute;
                top: 4px;
                right: 4px;
                min-width: 18px;
                height: 18px;
                padding: 0 5px;
                background: linear-gradient(135deg, #ef4444, #dc2626);
                color: white;
                font-size: 11px;
                font-weight: 600;
                border-radius: 9px;
                display: flex;
                align-items: center;
                justify-content: center;
                transform: scale(0);
                transition: transform 0.2s cubic-bezier(0.34, 1.56, 0.64, 1);
            }

            .notification-bell .badge.visible {
                transform: scale(1);
            }

            .notification-bell .badge.pulse {
                animation: badgePulse 0.3s cubic-bezier(0.34, 1.56, 0.64, 1);
            }

            @keyframes badgePulse {
                0% { transform: scale(1); }
                50% { transform: scale(1.3); }
                100% { transform: scale(1); }
            }

            /* Dropdown */
            .dropdown {
                position: absolute;
                top: calc(100% + 8px);
                right: 0;
                width: 320px;
                background: white;
                border-radius: 12px;
                box-shadow: 0 10px 40px rgba(0, 0, 0, 0.1), 0 0 0 1px rgba(0, 0, 0, 0.05);
                opacity: 0;
                visibility: hidden;
                transform: translateY(-10px);
                transition: all 0.2s cubic-bezier(0.16, 1, 0.3, 1);
                z-index: 1000;
            }

            .dropdown.open {
                opacity: 1;
                visibility: visible;
                transform: translateY(0);
            }

            /* Dropdown Header */
            .dropdown .header {
                display: flex;
                align-items: center;
                justify-content: space-between;
                padding: 16px 20px;
                border-bottom: 1px solid #eaeaea;
                font-weight: 600;
                color: #171717;
                font-size: 14px;
            }

            .dropdown .header .mark-all-read {
                font-size: 12px;
                font-weight: 500;
                color: #10B981;
                text-decoration: none;
                transition: opacity 0.2s ease;
            }

            .dropdown .header .mark-all-read:hover {
                opacity: 0.8;
                text-decoration: none;
            }

            /* Notification List */
            .dropdown .list {
                max-height: 320px;
                overflow-y: auto;
            }

            .dropdown .list::-webkit-scrollbar {
                width: 4px;
            }

            .dropdown .list::-webkit-scrollbar-track {
                background: transparent;
            }

            .dropdown .list::-webkit-scrollbar-thumb {
                background: #eaeaea;
                border-radius: 2px;
            }

            .dropdown .list::-webkit-scrollbar-thumb:hover {
                background: #d1d5db;
            }

            /* Notification Item */
            .notification-item {
                display: flex;
                gap: 12px;
                padding: 14px 20px;
                border-bottom: 1px solid #f3f4f6;
                cursor: pointer;
                transition: background 0.15s ease;
                animation: slideIn 0.2s ease-out;
            }

            @keyframes slideIn {
                from {
                    opacity: 0;
                    transform: translateX(-10px);
                }
                to {
                    opacity: 1;
                    transform: translateX(0);
                }
            }

            .notification-item:hover {
                background: #fafafa;
            }

            .notification-item:last-child {
                border-bottom: none;
            }

            .notification-item.unread {
                background: #f0fdf4;
            }

            .notification-item.unread:hover {
                background: #ecfdf5;
            }

            .notification-icon {
                width: 36px;
                height: 36px;
                border-radius: 8px;
                display: flex;
                align-items: center;
                justify-content: center;
                flex-shrink: 0;
                font-size: 16px;
            }

            .notification-icon.info {
                background: #dbeafe;
                color: #3b82f6;
            }

            .notification-icon.success {
                background: #d1fae5;
                color: #10b981;
            }

            .notification-icon.warning {
                background: #fef3c7;
                color: #f59e0b;
            }

            .notification-icon.error {
                background: #fee2e2;
                color: #ef4444;
            }

            .notification-content {
                flex: 1;
                min-width: 0;
            }

            .notification-title {
                font-size: 13px;
                font-weight: 500;
                color: #171717;
                margin-bottom: 2px;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .notification-item.unread .notification-title {
                font-weight: 600;
            }

            .notification-message {
                font-size: 12px;
                color: #64748b;
                overflow: hidden;
                text-overflow: ellipsis;
                white-space: nowrap;
            }

            .notification-time {
                font-size: 11px;
                color: #a1a1aa;
                margin-top: 2px;
            }

            /* Empty State */
            .dropdown .list .empty {
                padding: 40px 20px;
                text-align: center;
                color: #64748b;
                font-size: 13px;
            }

            .dropdown .list .empty-icon {
                font-size: 40px;
                margin-bottom: 12px;
                opacity: 0.5;
            }

            /* Loading State */
            .dropdown .list .loading {
                padding: 40px 20px;
                text-align: center;
                color: #64748b;
                font-size: 13px;
            }

            .dropdown .list .loading::after {
                content: '';
                display: inline-block;
                width: 14px;
                height: 14px;
                border: 2px solid #eaeaea;
                border-top-color: #10B981;
                border-radius: 50%;
                animation: spin 0.6s linear infinite;
                margin-left: 8px;
                vertical-align: middle;
            }

            @keyframes spin {
                to { transform: rotate(360deg); }
            }

            /* Dropdown Footer */
            .dropdown .footer {
                padding: 12px 20px;
                border-top: 1px solid #eaeaea;
                text-align: center;
            }

            .dropdown .footer a {
                font-size: 13px;
                font-weight: 500;
                color: #10B981;
                text-decoration: none;
                transition: opacity 0.2s ease;
            }

            .dropdown .footer a:hover {
                opacity: 0.8;
                text-decoration: none;
            }

            /* Responsive */
            @media (max-width: 640px) {
                .dropdown {
                    right: -60px;
                    width: 280px;
                }
            }
        `;

        document.head.appendChild(style);
    }

    /**
     * Setup event listeners
     */
    function setupEventListeners() {
        // Bell click
        bell.addEventListener('click', (e) => {
            e.stopPropagation();
            toggleDropdown();
        });

        // Mark all read button
        const markAllReadBtn = document.getElementById('markAllReadBtn');
        if (markAllReadBtn) {
            markAllReadBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                markAllRead();
            });
        }

        // Close dropdown on outside click
        document.addEventListener('click', (e) => {
            if (isDropdownOpen && !dropdown.contains(e.target) && !bell.contains(e.target)) {
                closeDropdown();
            }
        });

        // Close dropdown on escape key
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && isDropdownOpen) {
                closeDropdown();
            }
        });

        // Page Visibility API - pause polling when tab is hidden
        document.addEventListener('visibilitychange', () => {
            if (document.hidden) {
                isPaused = true;
                stopPolling();
            } else {
                isPaused = false;
                startPolling();
                updateUnreadCount();
            }
        });
    }

    /**
     * Toggle dropdown visibility
     */
    function toggleDropdown() {
        if (isDropdownOpen) {
            closeDropdown();
        } else {
            openDropdown();
        }
    }

    /**
     * Open dropdown and fetch notifications
     */
    function openDropdown() {
        isDropdownOpen = true;
        dropdown.classList.add('open');
        bell.setAttribute('aria-expanded', 'true');
        fetchNotifications();
    }

    /**
     * Close dropdown
     */
    function closeDropdown() {
        isDropdownOpen = false;
        dropdown.classList.remove('open');
        bell.setAttribute('aria-expanded', 'false');
    }

    /**
     * Start polling for unread count
     */
    function startPolling() {
        if (pollTimer) return;
        pollTimer = setInterval(() => {
            if (!isPaused && !isDropdownOpen) {
                updateUnreadCount();
            }
        }, CONFIG.pollInterval);
    }

    /**
     * Stop polling
     */
    function stopPolling() {
        if (pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    /**
     * Update unread count badge
     */
    async function updateUnreadCount() {
        try {
            const response = await fetch(CONFIG.apiEndpoints.unreadCount);
            if (!response.ok) throw new Error('Failed to fetch unread count');

            const data = await response.json();
            const count = data.count || 0;

            updateBadge(count);
        } catch (error) {
            console.error('Error updating unread count:', error);
        }
    }

    /**
     * Update badge display
     */
    function updateBadge(count) {
        const oldCount = unreadCount;
        unreadCount = count;

        if (count > 0) {
            badge.textContent = count > 99 ? '99+' : count;
            badge.classList.add('visible');

            // Add pulse animation if count increased
            if (count > oldCount) {
                badge.classList.remove('pulse');
                void badge.offsetWidth; // Trigger reflow
                badge.classList.add('pulse');
            }
        } else {
            badge.classList.remove('visible');
        }
    }

    /**
     * Fetch and display notifications
     */
    async function fetchNotifications() {
        try {
            notificationList.innerHTML = '<div class="loading">加载中...</div>';

            const response = await fetch(`${CONFIG.apiEndpoints.list}?limit=${CONFIG.maxDisplay}`);
            if (!response.ok) throw new Error('Failed to fetch notifications');

            const data = await response.json();
            const notifications = data.notifications || [];

            if (notifications.length === 0) {
                notificationList.innerHTML = `
                    <div class="empty">
                        <div class="empty-icon">🔔</div>
                        <div>暂无通知</div>
                    </div>
                `;
                return;
            }

            notificationList.innerHTML = notifications.map(notification =>
                createNotificationItem(notification)
            ).join('');

            // Add click handlers to items
            notificationList.querySelectorAll('.notification-item').forEach(item => {
                item.addEventListener('click', () => {
                    const notificationId = item.dataset.notificationId;
                    if (notificationId) {
                        markAsRead(notificationId);
                    }
                });
            });

        } catch (error) {
            console.error('Error fetching notifications:', error);
            notificationList.innerHTML = `
                <div class="empty">
                    <div class="empty-icon">⚠️</div>
                    <div>加载失败，请重试</div>
                </div>
            `;
        }
    }

    /**
     * Create notification item HTML
     */
    function createNotificationItem(notification) {
        const type = notification.type || 'info';
        const isUnread = !notification.read_at;
        const timeAgo = formatTimeAgo(notification.created_at);

        return `
            <div class="notification-item ${isUnread ? 'unread' : ''}" data-notification-id="${notification.id}">
                <div class="notification-icon ${type}">${getTypeIcon(type)}</div>
                <div class="notification-content">
                    <div class="notification-title">${escapeHtml(notification.title)}</div>
                    <div class="notification-message">${escapeHtml(notification.message)}</div>
                    <div class="notification-time">${timeAgo}</div>
                </div>
            </div>
        `;
    }

    /**
     * Get icon for notification type
     */
    function getTypeIcon(type) {
        const icons = {
            info: 'ℹ️',
            success: '✓',
            warning: '⚠️',
            error: '✕',
            skill_upload: '📦',
            skill_update: '🔄',
            download: '⬇️',
            system: '⚙️'
        };
        return icons[type] || '📌';
    }

    /**
     * Format time ago
     */
    function formatTimeAgo(dateString) {
        const now = new Date();
        const date = new Date(dateString);
        const seconds = Math.floor((now - date) / 1000);

        if (seconds < 60) return '刚刚';
        if (seconds < 3600) return `${Math.floor(seconds / 60)}分钟前`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)}小时前`;
        if (seconds < 604800) return `${Math.floor(seconds / 86400)}天前`;

        return date.toLocaleDateString('zh-CN');
    }

    /**
     * Mark notification as read
     */
    async function markAsRead(notificationId) {
        try {
            const response = await fetch(CONFIG.apiEndpoints.markRead.replace('{id}', notificationId), {
                method: 'POST'
            });

            if (response.ok) {
                // Remove unread styling
                const item = document.querySelector(`[data-notification-id="${notificationId}"]`);
                if (item) {
                    item.classList.remove('unread');
                }

                // Update badge
                updateUnreadCount();
            }
        } catch (error) {
            console.error('Error marking notification as read:', error);
        }
    }

    /**
     * Mark all notifications as read
     */
    async function markAllRead() {
        try {
            const response = await fetch(CONFIG.apiEndpoints.markAllRead, {
                method: 'POST'
            });

            if (response.ok) {
                // Update all items to read
                notificationList.querySelectorAll('.notification-item.unread').forEach(item => {
                    item.classList.remove('unread');
                });

                // Update badge
                updateBadge(0);
            }
        } catch (error) {
            console.error('Error marking all as read:', error);
        }
    }

    /**
     * Escape HTML to prevent XSS
     */
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // Initialize when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', init);
    } else {
        init();
    }

    // Expose markAllRead globally for the onclick handler
    window.markAllRead = markAllRead;

})();
