/**
 * 评分评论组件
 * - 1-5 星评分
 * - 评论功能
 * - 安装命令复制
 */

// 评分组件
class RatingComponent {
    constructor(containerId, skillId, options = {}) {
        this.container = document.getElementById(containerId);
        this.skillId = skillId;
        this.options = {
            apiUrl: `/api/skills/${skillId}/rating`,
            onRate: null,
            readonly: false,
            ...options
        };
        this.userRating = 0;
        this.stats = {
            average: 0,
            total: 0,
            distribution: {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
        };
        this.init();
    }

    async init() {
        await this.loadRating();
        this.render();
    }

    async loadRating() {
        try {
            const response = await fetch(this.options.apiUrl);
            const data = await response.json();
            this.stats = {
                average: data.average || 0,
                total: data.total || 0,
                distribution: data.distribution || {1: 0, 2: 0, 3: 0, 4: 0, 5: 0}
            };
            this.userRating = data.user_rating || 0;
        } catch (error) {
            console.error('Failed to load rating:', error);
        }
    }

    render() {
        if (!this.container) return;

        const readonly = this.options.readonly ? 'readonly' : '';

        let html = `
            <div class="rating-component">
                <div class="rating-summary">
                    <div class="rating-average">${this.stats.average.toFixed(1)}</div>
                    <div class="rating-stars-large">
                        ${this.renderStars(this.stats.average, true)}
                    </div>
                    <div class="rating-count">${this.stats.total} 个评分</div>
                </div>

                <div class="rating-distribution">
                    ${[5,4,3,2,1].map(star => `
                        <div class="distribution-row">
                            <span class="star-label">${star} 星</span>
                            <div class="distribution-bar">
                                <div class="distribution-fill" style="width: ${this.getPercentage(star)}%"></div>
                            </div>
                            <span class="distribution-count">${this.stats.distribution[star] || 0}</span>
                        </div>
                    `).join('')}
                </div>

                ${!this.options.readonly ? `
                    <div class="user-rating">
                        <span class="rating-label">您的评分：</span>
                        <div class="rating-stars-interactive" id="userRatingStars">
                            ${[1,2,3,4,5].map(star => `
                                <span class="star ${star <= this.userRating ? 'active' : ''}"
                                      data-star="${star}"
                                      onclick="ratingComponent.setRating(${star})">★</span>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}
            </div>

            <style>
                .rating-component {
                    display: flex;
                    gap: 32px;
                    padding: 24px;
                    background: #f8fafc;
                    border-radius: 12px;
                    margin-bottom: 24px;
                }

                .rating-summary {
                    text-align: center;
                    min-width: 150px;
                }

                .rating-average {
                    font-size: 48px;
                    font-weight: 700;
                    color: #171717;
                    line-height: 1;
                }

                .rating-stars-large {
                    font-size: 24px;
                    margin: 8px 0;
                    color: #fbbf24;
                }

                .rating-stars-large .star.empty {
                    color: #e5e7eb;
                }

                .rating-count {
                    font-size: 14px;
                    color: #64748b;
                }

                .rating-distribution {
                    flex: 1;
                }

                .distribution-row {
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    margin-bottom: 6px;
                }

                .star-label {
                    font-size: 12px;
                    color: #64748b;
                    width: 36px;
                }

                .distribution-bar {
                    flex: 1;
                    height: 8px;
                    background: #e5e7eb;
                    border-radius: 4px;
                    overflow: hidden;
                }

                .distribution-fill {
                    height: 100%;
                    background: #fbbf24;
                    border-radius: 4px;
                    transition: width 0.3s ease;
                }

                .distribution-count {
                    font-size: 12px;
                    color: #64748b;
                    width: 30px;
                    text-align: right;
                }

                .user-rating {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    margin-top: 16px;
                    padding-top: 16px;
                    border-top: 1px solid #e5e7eb;
                }

                .rating-label {
                    font-size: 14px;
                    color: #64748b;
                }

                .rating-stars-interactive .star {
                    font-size: 28px;
                    color: #e5e7eb;
                    cursor: pointer;
                    transition: color 0.2s, transform 0.1s;
                }

                .rating-stars-interactive .star:hover {
                    transform: scale(1.2);
                }

                .rating-stars-interactive .star.active {
                    color: #fbbf24;
                }

                @media (max-width: 768px) {
                    .rating-component {
                        flex-direction: column;
                        gap: 24px;
                    }

                    .rating-summary {
                        display: flex;
                        align-items: center;
                        gap: 16px;
                        justify-content: center;
                    }
                }
            </style>
        `;

        this.container.innerHTML = html;

        // 绑定悬停效果
        if (!this.options.readonly) {
            const starsContainer = document.getElementById('userRatingStars');
            if (starsContainer) {
                starsContainer.addEventListener('mouseover', (e) => {
                    const star = e.target.closest('.star');
                    if (star) {
                        const starValue = parseInt(star.dataset.star);
                        this.highlightStars(starValue);
                    }
                });

                starsContainer.addEventListener('mouseout', () => {
                    this.highlightStars(this.userRating);
                });
            }
        }
    }

    renderStars(rating, large = false) {
        const fullStars = Math.floor(rating);
        const hasHalf = rating % 1 >= 0.5;
        let html = '';

        for (let i = 1; i <= 5; i++) {
            if (i <= fullStars) {
                html += '<span class="star">★</span>';
            } else if (i === fullStars + 1 && hasHalf) {
                html += '<span class="star half">★</span>';
            } else {
                html += '<span class="star empty">★</span>';
            }
        }

        return html;
    }

    highlightStars(count) {
        const stars = document.querySelectorAll('#userRatingStars .star');
        stars.forEach((star, index) => {
            if (index < count) {
                star.classList.add('active');
            } else {
                star.classList.remove('active');
            }
        });
    }

    getPercentage(star) {
        if (this.stats.total === 0) return 0;
        return ((this.stats.distribution[star] || 0) / this.stats.total) * 100;
    }

    async setRating(rating) {
        try {
            const response = await fetch(this.options.apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ rating })
            });

            const data = await response.json();

            if (data.success) {
                this.userRating = rating;
                await this.loadRating();
                this.render();

                if (this.options.onRate) {
                    this.options.onRate(rating);
                }

                this.showMessage('评分成功！', 'success');
            } else {
                this.showMessage(data.error || '评分失败', 'error');
            }
        } catch (error) {
            console.error('Failed to submit rating:', error);
            this.showMessage('评分失败，请稍后重试', 'error');
        }
    }

    showMessage(message, type) {
        const toast = document.createElement('div');
        toast.className = `rating-toast rating-toast-${type}`;
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            z-index: 9999;
            animation: slideIn 0.3s ease;
            ${type === 'success' ? 'background: #10B981; color: white;' : 'background: #ef4444; color: white;'}
        `;

        document.body.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'slideOut 0.3s ease';
            setTimeout(() => toast.remove(), 300);
        }, 2000);
    }
}

// 评论组件
class CommentComponent {
    constructor(containerId, skillId, options = {}) {
        this.container = document.getElementById(containerId);
        this.skillId = skillId;
        this.options = {
            apiUrl: `/api/skills/${skillId}/comments`,
            pageSize: 10,
            ...options
        };
        this.comments = [];
        this.currentPage = 1;
        this.totalPages = 0;
        this.init();
    }

    async init() {
        await this.loadComments();
        this.render();
    }

    async loadComments(page = 1) {
        try {
            const response = await fetch(`${this.options.apiUrl}?page=${page}&per_page=${this.options.pageSize}`);
            const data = await response.json();
            this.comments = data.comments || [];
            this.currentPage = data.page || 1;
            this.totalPages = data.total_pages || 0;
            this.total = data.total || 0;
        } catch (error) {
            console.error('Failed to load comments:', error);
        }
    }

    render() {
        if (!this.container) return;

        let html = `
            <div class="comments-section">
                <h3 class="comments-title">💬 评论 (${this.total})</h3>

                <!-- 评论输入框 -->
                <div class="comment-form">
                    <textarea id="commentInput" placeholder="写下你的评论..." maxlength="500"></textarea>
                    <div class="comment-form-footer">
                        <span class="char-count"><span id="charCount">0</span>/500</span>
                        <button class="submit-btn" onclick="commentComponent.submitComment()">发表评论</button>
                    </div>
                </div>

                <!-- 评论列表 -->
                <div class="comments-list" id="commentsList">
                    ${this.comments.length > 0 ? this.comments.map(comment => this.renderComment(comment)).join('') : '<p class="no-comments">暂无评论，来发表第一条吧！</p>'}
                </div>

                <!-- 分页 -->
                ${this.totalPages > 1 ? this.renderPagination() : ''}
            </div>

            <style>
                .comments-section {
                    margin-top: 32px;
                }

                .comments-title {
                    font-size: 20px;
                    font-weight: 600;
                    margin-bottom: 20px;
                    color: #171717;
                }

                .comment-form {
                    background: #f8fafc;
                    border-radius: 12px;
                    padding: 16px;
                    margin-bottom: 24px;
                }

                .comment-form textarea {
                    width: 100%;
                    min-height: 100px;
                    padding: 12px;
                    border: 1px solid #e5e7eb;
                    border-radius: 8px;
                    font-size: 14px;
                    resize: vertical;
                    font-family: inherit;
                }

                .comment-form textarea:focus {
                    outline: none;
                    border-color: #10B981;
                    box-shadow: 0 0 0 3px rgba(16, 185, 129, 0.1);
                }

                .comment-form-footer {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-top: 12px;
                }

                .char-count {
                    font-size: 12px;
                    color: #64748b;
                }

                .submit-btn {
                    background: #10B981;
                    color: white;
                    border: none;
                    padding: 8px 20px;
                    border-radius: 8px;
                    font-size: 14px;
                    font-weight: 500;
                    cursor: pointer;
                    transition: background 0.2s;
                }

                .submit-btn:hover {
                    background: #059669;
                }

                .comment-item {
                    padding: 16px 0;
                    border-bottom: 1px solid #e5e7eb;
                }

                .comment-header {
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                    margin-bottom: 8px;
                }

                .comment-author {
                    font-weight: 600;
                    color: #171717;
                }

                .comment-rating {
                    color: #fbbf24;
                    font-size: 12px;
                }

                .comment-date {
                    font-size: 12px;
                    color: #64748b;
                }

                .comment-content {
                    font-size: 14px;
                    line-height: 1.6;
                    color: #374151;
                }

                .comment-actions {
                    margin-top: 8px;
                }

                .delete-btn {
                    background: none;
                    border: none;
                    color: #ef4444;
                    font-size: 12px;
                    cursor: pointer;
                    padding: 0;
                }

                .delete-btn:hover {
                    text-decoration: underline;
                }

                .no-comments {
                    text-align: center;
                    color: #64748b;
                    padding: 40px 0;
                }

                .pagination {
                    display: flex;
                    justify-content: center;
                    gap: 8px;
                    margin-top: 24px;
                }

                .page-btn {
                    padding: 8px 16px;
                    border: 1px solid #e5e7eb;
                    background: white;
                    border-radius: 8px;
                    cursor: pointer;
                    font-size: 14px;
                }

                .page-btn:hover:not(:disabled) {
                    background: #f3f4f6;
                }

                .page-btn:disabled {
                    opacity: 0.5;
                    cursor: not-allowed;
                }

                .page-btn.active {
                    background: #10B981;
                    color: white;
                    border-color: #10B981;
                }
            </style>
        `;

        this.container.innerHTML = html;

        // 绑定字符计数
        const textarea = document.getElementById('commentInput');
        if (textarea) {
            textarea.addEventListener('input', () => {
                document.getElementById('charCount').textContent = textarea.value.length;
            });
        }
    }

    renderComment(comment) {
        return `
            <div class="comment-item" data-id="${comment.id}">
                <div class="comment-header">
                    <div>
                        <span class="comment-author">${this.escapeHtml(comment.author)}</span>
                        ${comment.rating ? `<span class="comment-rating"> ★ ${comment.rating}</span>` : ''}
                    </div>
                    <span class="comment-date">${this.formatDate(comment.created_at)}</span>
                </div>
                <div class="comment-content">${this.escapeHtml(comment.content)}</div>
                ${comment.is_owner ? `
                    <div class="comment-actions">
                        <button class="delete-btn" onclick="commentComponent.deleteComment(${comment.id})">删除</button>
                    </div>
                ` : ''}
            </div>
        `;
    }

    renderPagination() {
        let html = '<div class="pagination">';

        // 上一页
        html += `<button class="page-btn" onclick="commentComponent.goToPage(${this.currentPage - 1})" ${this.currentPage === 1 ? 'disabled' : ''}>上一页</button>`;

        // 页码
        for (let i = 1; i <= this.totalPages; i++) {
            if (i === 1 || i === this.totalPages || (i >= this.currentPage - 2 && i <= this.currentPage + 2)) {
                html += `<button class="page-btn ${i === this.currentPage ? 'active' : ''}" onclick="commentComponent.goToPage(${i})">${i}</button>`;
            } else if (i === this.currentPage - 3 || i === this.currentPage + 3) {
                html += '<span>...</span>';
            }
        }

        // 下一页
        html += `<button class="page-btn" onclick="commentComponent.goToPage(${this.currentPage + 1})" ${this.currentPage === this.totalPages ? 'disabled' : ''}>下一页</button>`;

        html += '</div>';
        return html;
    }

    async submitComment() {
        const textarea = document.getElementById('commentInput');
        const content = textarea.value.trim();

        if (!content) {
            alert('请输入评论内容');
            return;
        }

        try {
            const response = await fetch(this.options.apiUrl, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ content })
            });

            const data = await response.json();

            if (data.success) {
                textarea.value = '';
                document.getElementById('charCount').textContent = '0';
                await this.loadComments(1);
                this.render();
            } else {
                alert(data.error || '评论失败');
            }
        } catch (error) {
            console.error('Failed to submit comment:', error);
            alert('评论失败，请稍后重试');
        }
    }

    async deleteComment(commentId) {
        if (!confirm('确定要删除这条评论吗？')) {
            return;
        }

        try {
            const response = await fetch(`${this.options.apiUrl}/${commentId}`, {
                method: 'DELETE'
            });

            const data = await response.json();

            if (data.success) {
                await this.loadComments(this.currentPage);
                this.render();
            } else {
                alert(data.error || '删除失败');
            }
        } catch (error) {
            console.error('Failed to delete comment:', error);
            alert('删除失败，请稍后重试');
        }
    }

    async goToPage(page) {
        if (page < 1 || page > this.totalPages) return;
        await this.loadComments(page);
        this.render();
        // 滚动到评论区
        this.container.scrollIntoView({ behavior: 'smooth' });
    }

    formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        const now = new Date();
        const diff = now - date;

        if (diff < 60000) return '刚刚';
        if (diff < 3600000) return `${Math.floor(diff / 60000)} 分钟前`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)} 小时前`;
        if (diff < 604800000) return `${Math.floor(diff / 86400000)} 天前`;

        return date.toLocaleDateString('zh-CN');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

// 安装命令组件
class InstallCommand {
    constructor(containerId, skillName, options = {}) {
        this.container = document.getElementById(containerId);
        this.skillName = skillName;
        this.options = {
            marketplace: 'marketplace',
            ...options
        };
        this.render();
    }

    render() {
        if (!this.container) return;

        const commands = [
            {
                label: 'Claude Code',
                cmd: `/plugin install ${this.skillName}@${this.options.marketplace}`,
                icon: '🤖'
            },
            {
                label: 'npx',
                cmd: `npx skills add ${this.skillName}`,
                icon: '📦'
            }
        ];

        let html = `
            <div class="install-commands">
                <h4>📥 安装命令</h4>
                <div class="commands-list">
                    ${commands.map(c => `
                        <div class="command-item">
                            <span class="command-icon">${c.icon}</span>
                            <code class="command-text">${this.escapeHtml(c.cmd)}</code>
                            <button class="copy-btn" onclick="navigator.clipboard.writeText('${this.escapeJs(c.cmd)}').then(() => this.showCopied(this))">
                                <span class="copy-icon">📋</span>
                                <span class="copy-text">复制</span>
                            </button>
                        </div>
                    `).join('')}
                </div>
            </div>

            <style>
                .install-commands {
                    background: #1e293b;
                    border-radius: 12px;
                    padding: 20px;
                    margin-bottom: 24px;
                }

                .install-commands h4 {
                    color: #94a3b8;
                    font-size: 14px;
                    margin-bottom: 16px;
                }

                .command-item {
                    display: flex;
                    align-items: center;
                    gap: 12px;
                    padding: 12px 16px;
                    background: #0f172a;
                    border-radius: 8px;
                    margin-bottom: 8px;
                }

                .command-item:last-child {
                    margin-bottom: 0;
                }

                .command-icon {
                    font-size: 18px;
                }

                .command-text {
                    flex: 1;
                    color: #22d3ee;
                    font-family: 'Monaco', 'Menlo', monospace;
                    font-size: 14px;
                }

                .copy-btn {
                    background: #334155;
                    border: none;
                    color: #94a3b8;
                    padding: 6px 12px;
                    border-radius: 6px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    gap: 6px;
                    font-size: 12px;
                    transition: all 0.2s;
                }

                .copy-btn:hover {
                    background: #475569;
                    color: white;
                }

                .copy-btn.copied {
                    background: #10B981;
                    color: white;
                }
            </style>
        `;

        this.container.innerHTML = html;
    }

    showCopied(btn) {
        btn.classList.add('copied');
        btn.querySelector('.copy-text').textContent = '已复制';
        setTimeout(() => {
            btn.classList.remove('copied');
            btn.querySelector('.copy-text').textContent = '复制';
        }, 2000);
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    escapeJs(text) {
        return text.replace(/\\/g, '\\\\').replace(/'/g, "\\'").replace(/"/g, '\\"');
    }
}

// 导出
window.RatingComponent = RatingComponent;
window.CommentComponent = CommentComponent;
window.InstallCommand = InstallCommand;
