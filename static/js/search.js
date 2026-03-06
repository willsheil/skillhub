/**
 * 搜索增强功能
 * - 搜索建议
 * - 搜索历史
 * - 高级搜索
 */

// 搜索建议组件
class SearchSuggestions {
    constructor(inputElement, options = {}) {
        this.input = inputElement;
        this.options = {
            apiUrl: '/api/search/suggestions',
            historyUrl: '/api/search/history',
            minChars: 2,
            maxSuggestions: 5,
            maxHistory: 5,
            debounceMs: 300,
            ...options
        };
        this.suggestionsContainer = null;
        this.debounceTimer = null;
        this.selectedIndex = -1;
        this.init();
    }

    init() {
        // 创建建议容器
        this.suggestionsContainer = document.createElement('div');
        this.suggestionsContainer.className = 'search-suggestions';
        this.suggestionsContainer.style.cssText = `
            position: absolute;
            top: 100%;
            left: 0;
            right: 0;
            background: white;
            border: 1px solid #eaeaea;
            border-top: none;
            border-radius: 0 0 16px 16px;
            box-shadow: 0 4px 12px rgba(0,0,0,0.1);
            z-index: 1000;
            display: none;
            max-height: 400px;
            overflow-y: auto;
        `;

        // 插入到搜索框后面
        this.input.parentElement.style.position = 'relative';
        this.input.parentElement.appendChild(this.suggestionsContainer);

        // 绑定事件
        this.input.addEventListener('input', this.handleInput.bind(this));
        this.input.addEventListener('focus', this.handleFocus.bind(this));
        this.input.addEventListener('keydown', this.handleKeydown.bind(this));

        // 点击外部关闭
        document.addEventListener('click', (e) => {
            if (!this.input.parentElement.contains(e.target)) {
                this.hide();
            }
        });
    }

    async handleInput(e) {
        const query = e.target.value.trim();
        clearTimeout(this.debounceTimer);

        if (query.length < this.options.minChars) {
            this.hide();
            return;
        }

        this.debounceTimer = setTimeout(() => {
            this.fetchSuggestions(query);
        }, this.options.debounceMs);
    }

    async handleFocus(e) {
        const query = e.target.value.trim();
        if (query.length < this.options.minChars) {
            // 显示搜索历史
            this.showHistory();
        } else {
            this.fetchSuggestions(query);
        }
    }

    handleKeydown(e) {
        const items = this.suggestionsContainer.querySelectorAll('.suggestion-item');
        if (items.length === 0) return;

        if (e.key === 'ArrowDown') {
            e.preventDefault();
            this.selectedIndex = Math.min(this.selectedIndex + 1, items.length - 1);
            this.updateSelection(items);
        } else if (e.key === 'ArrowUp') {
            e.preventDefault();
            this.selectedIndex = Math.max(this.selectedIndex - 1, -1);
            this.updateSelection(items);
        } else if (e.key === 'Enter') {
            if (this.selectedIndex >= 0) {
                e.preventDefault();
                this.selectItem(items[this.selectedIndex]);
            }
        } else if (e.key === 'Escape') {
            this.hide();
        }
    }

    updateSelection(items) {
        items.forEach((item, index) => {
            item.style.backgroundColor = index === this.selectedIndex ? '#f0f9ff' : '';
        });
    }

    selectItem(item) {
        const text = item.dataset.value || item.textContent;
        this.input.value = text;
        this.hide();
        // 触发搜索
        if (typeof handleSearch === 'function') {
            handleSearch();
        } else if (this.options.onSelect) {
            this.options.onSelect(text);
        }
    }

    async fetchSuggestions(query) {
        try {
            const response = await fetch(`${this.options.apiUrl}?q=${encodeURIComponent(query)}&limit=${this.options.maxSuggestions}`);
            const data = await response.json();

            this.render({
                suggestions: data.suggestions || [],
                query: query
            });
        } catch (error) {
            console.error('Failed to fetch suggestions:', error);
        }
    }

    async showHistory() {
        try {
            const response = await fetch(this.options.historyUrl);
            if (!response.ok) {
                this.hide();
                return;
            }
            const data = await response.json();

            if (data.history && data.history.length > 0) {
                this.render({
                    history: data.history.slice(0, this.options.maxHistory)
                });
            } else {
                this.hide();
            }
        } catch (error) {
            this.hide();
        }
    }

    render(data) {
        let html = '';

        // 搜索历史
        if (data.history && data.history.length > 0) {
            html += '<div class="suggestion-group"><div class="suggestion-header"><span>搜索历史</span><button class="clear-history" onclick="clearSearchHistory()">清空</button></div>';
            data.history.forEach(item => {
                html += `<div class="suggestion-item history-item" data-value="${this.escapeHtml(item)}">
                    <span class="history-icon">🕐</span>
                    <span>${this.escapeHtml(item)}</span>
                </div>`;
            });
            html += '</div>';
        }

        // 搜索建议
        if (data.suggestions && data.suggestions.length > 0) {
            html += '<div class="suggestion-group"><div class="suggestion-header">搜索建议</div>';
            data.suggestions.forEach(item => {
                const highlighted = data.query ? this.highlightMatch(item, data.query) : item;
                html += `<div class="suggestion-item" data-value="${this.escapeHtml(item)}">
                    <span class="suggestion-icon">🔍</span>
                    <span>${highlighted}</span>
                </div>`;
            });
            html += '</div>';
        }

        if (html) {
            this.suggestionsContainer.innerHTML = html;
            this.suggestionsContainer.style.display = 'block';
            this.selectedIndex = -1;

            // 绑定点击事件
            this.suggestionsContainer.querySelectorAll('.suggestion-item').forEach(item => {
                item.addEventListener('click', () => this.selectItem(item));
                item.style.cssText = `
                    padding: 12px 16px;
                    cursor: pointer;
                    display: flex;
                    align-items: center;
                    gap: 8px;
                    border-bottom: 1px solid #f0f0f0;
                `;
                item.addEventListener('mouseenter', () => {
                    item.style.backgroundColor = '#f0f9ff';
                });
                item.addEventListener('mouseleave', () => {
                    item.style.backgroundColor = '';
                });
            });

            // 添加样式
            const headers = this.suggestionsContainer.querySelectorAll('.suggestion-header');
            headers.forEach(header => {
                header.style.cssText = `
                    padding: 8px 16px;
                    font-size: 12px;
                    color: #64748b;
                    background: #f8fafc;
                    display: flex;
                    justify-content: space-between;
                    align-items: center;
                `;
            });

            const clearBtn = this.suggestionsContainer.querySelector('.clear-history');
            if (clearBtn) {
                clearBtn.style.cssText = `
                    background: none;
                    border: none;
                    color: #64748b;
                    cursor: pointer;
                    font-size: 12px;
                `;
            }
        } else {
            this.hide();
        }
    }

    highlightMatch(text, query) {
        const regex = new RegExp(`(${this.escapeRegex(query)})`, 'gi');
        return text.replace(regex, '<strong style="color: #10B981;">$1</strong>');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    escapeRegex(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    hide() {
        this.suggestionsContainer.style.display = 'none';
        this.selectedIndex = -1;
    }
}

// 清空搜索历史
async function clearSearchHistory() {
    try {
        const response = await fetch('/api/search/history', { method: 'DELETE' });
        const data = await response.json();
        if (data.success) {
            // 关闭建议框
            const container = document.querySelector('.search-suggestions');
            if (container) {
                container.style.display = 'none';
            }
        }
    } catch (error) {
        console.error('Failed to clear history:', error);
    }
}

// 高级搜索组件
class AdvancedSearch {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            apiUrl: '/api/search',
            onResults: null,
            ...options
        };
        this.filters = {
            query: '',
            category: '',
            source_type: '',
            sort: 'relevance',
            page: 1,
            per_page: 20
        };
    }

    setFilter(key, value) {
        this.filters[key] = value;
        this.filters.page = 1; // 重置页码
    }

    async search() {
        const params = new URLSearchParams();
        if (this.filters.query) params.append('q', this.filters.query);
        if (this.filters.category) params.append('category', this.filters.category);
        if (this.filters.source_type) params.append('source_type', this.filters.source_type);
        params.append('sort', this.filters.sort);
        params.append('page', this.filters.page);
        params.append('per_page', this.filters.per_page);

        try {
            const response = await fetch(`${this.options.apiUrl}?${params.toString()}`);
            const data = await response.json();

            if (this.options.onResults) {
                this.options.onResults(data);
            }

            return data;
        } catch (error) {
            console.error('Search failed:', error);
            return null;
        }
    }

    nextPage() {
        this.filters.page++;
        return this.search();
    }

    prevPage() {
        if (this.filters.page > 1) {
            this.filters.page--;
            return this.search();
        }
        return null;
    }

    goToPage(page) {
        this.filters.page = page;
        return this.search();
    }
}

// 分类筛选组件
class CategoryFilter {
    constructor(containerId, options = {}) {
        this.container = document.getElementById(containerId);
        this.options = {
            apiUrl: '/api/categories',
            onSelect: null,
            ...options
        };
        this.categories = [];
        this.selectedCategory = null;
        this.init();
    }

    async init() {
        await this.loadCategories();
        this.render();
    }

    async loadCategories() {
        try {
            const response = await fetch(this.options.apiUrl);
            const data = await response.json();
            this.categories = data.categories || [];
        } catch (error) {
            console.error('Failed to load categories:', error);
            this.categories = [];
        }
    }

    render() {
        if (!this.container) return;

        // 添加"全部"选项
        let html = `<div class="category-pill ${this.selectedCategory === null ? 'active' : ''}" data-slug="">全部</div>`;

        this.categories.forEach(cat => {
            html += `<div class="category-pill ${this.selectedCategory === cat.slug ? 'active' : ''}" data-slug="${cat.slug}">
                ${cat.icon ? `<span>${this.getIcon(cat.icon)}</span>` : ''}
                <span>${cat.name}</span>
            </div>`;
        });

        this.container.innerHTML = html;

        // 绑定点击事件
        this.container.querySelectorAll('.category-pill').forEach(pill => {
            pill.addEventListener('click', () => {
                const slug = pill.dataset.slug;
                this.selectCategory(slug || null);
            });
        });
    }

    getIcon(iconName) {
        const icons = {
            'code': '💻',
            'server': '🖥️',
            'git-branch': '🌿',
            'shield': '🛡️',
            'database': '🗄️',
            'tool': '🔧'
        };
        return icons[iconName] || '📦';
    }

    selectCategory(slug) {
        this.selectedCategory = slug;
        this.render();

        if (this.options.onSelect) {
            this.options.onSelect(slug);
        }
    }
}

// 导出
window.SearchSuggestions = SearchSuggestions;
window.AdvancedSearch = AdvancedSearch;
window.CategoryFilter = CategoryFilter;
window.clearSearchHistory = clearSearchHistory;
