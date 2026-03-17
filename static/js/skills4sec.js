/**
 * Skills4sec Common JavaScript Components
 * Skills Registry Project
 */

(function() {
  'use strict';

  /* ===================== Mobile Menu ===================== */
  function initMobileMenu() {
    const btn = document.getElementById('mobile-menu-btn');
    const menu = document.getElementById('mobile-menu');

    if (!btn || !menu) return;

    btn.addEventListener('click', function() {
      const isOpen = menu.style.display === 'block';
      menu.style.display = isOpen ? 'none' : 'block';
      btn.setAttribute('aria-expanded', !isOpen);
    });

    // Close menu when clicking outside
    document.addEventListener('click', function(e) {
      if (!btn.contains(e.target) && !menu.contains(e.target)) {
        menu.style.display = 'none';
        btn.setAttribute('aria-expanded', 'false');
      }
    });
  }

  /* ===================== Search ===================== */
  function initSearch() {
    const searchInput = document.getElementById('skill-search');
    if (!searchInput) return;

    let debounceTimer;
    searchInput.addEventListener('input', function() {
      clearTimeout(debounceTimer);
      debounceTimer = setTimeout(function() {
        const query = searchInput.value.trim();
        if (typeof window.performSearch === 'function') {
          window.performSearch(query);
        } else {
          // Fallback: filter cards client-side
          filterSkillsByQuery(query);
        }
      }, 300);
    });
  }

  function filterSkillsByQuery(query) {
    const cards = document.querySelectorAll('.skill-card');
    const normalizedQuery = query.toLowerCase();

    cards.forEach(function(card) {
      const name = card.querySelector('.skill-name')?.textContent?.toLowerCase() || '';
      const desc = card.querySelector('.skill-desc')?.textContent?.toLowerCase() || '';

      if (!query || name.includes(normalizedQuery) || desc.includes(normalizedQuery)) {
        card.style.display = '';
      } else {
        card.style.display = 'none';
      }
    });
  }

  /* ===================== Category Filter ===================== */
  function initCategoryFilter() {
    const pills = document.querySelectorAll('.pill[data-category]');
    if (!pills.length) return;

    pills.forEach(function(pill) {
      pill.addEventListener('click', function() {
        // Update active state
        pills.forEach(function(p) { p.classList.remove('active'); });
        pill.classList.add('active');

        const category = pill.dataset.category;
        filterSkillsByCategory(category);
      });
    });
  }

  function filterSkillsByCategory(category) {
    const cards = document.querySelectorAll('.skill-card');

    cards.forEach(function(card) {
      const cardCategory = card.dataset.category || 'all';

      if (category === 'all' || cardCategory === category) {
        card.style.display = '';
      } else {
        card.style.display = 'none';
      }
    });
  }

  /* ===================== Toast Notification ===================== */
  function showToast(message, duration) {
    duration = duration || 3000;

    let toast = document.getElementById('toast');
    if (!toast) {
      toast = document.createElement('div');
      toast.id = 'toast';
      toast.className = 'toast';
      document.body.appendChild(toast);
    }

    toast.textContent = message;
    toast.classList.add('show');

    setTimeout(function() {
      toast.classList.remove('show');
    }, duration);
  }

  /* ===================== Copy to Clipboard ===================== */
  function initCopyButtons() {
    document.addEventListener('click', function(e) {
      const btn = e.target.closest('.copy-btn, [data-copy]');
      if (!btn) return;

      const targetId = btn.dataset.copy || btn.dataset.target;
      const text = btn.dataset.text || document.getElementById(targetId)?.textContent?.trim();

      if (!text) return;

      navigator.clipboard.writeText(text).then(function() {
        showToast('已复制到剪贴板');
      }).catch(function() {
        showToast('复制失败', 2000);
      });
    });
  }

  /* ===================== Confirm Dialog ===================== */
  function confirmAction(message, onConfirm) {
    const overlay = document.createElement('div');
    overlay.className = 'modal-overlay';
    overlay.innerHTML = `
      <div class="modal">
        <h3 class="modal-title">确认操作</h3>
        <p class="modal-body">${message}</p>
        <div class="modal-actions">
          <button class="btn-secondary modal-cancel">取消</button>
          <button class="btn-primary modal-confirm">确认</button>
        </div>
      </div>
    `;

    document.body.appendChild(overlay);

    overlay.querySelector('.modal-cancel').addEventListener('click', function() {
      overlay.remove();
    });

    overlay.querySelector('.modal-confirm').addEventListener('click', function() {
      overlay.remove();
      if (typeof onConfirm === 'function') {
        onConfirm();
      }
    });

    overlay.addEventListener('click', function(e) {
      if (e.target === overlay) {
        overlay.remove();
      }
    });
  }

  /* ===================== Tab Navigation ===================== */
  function initTabs() {
    const tabContainers = document.querySelectorAll('[data-tabs]');
    if (!tabContainers.length) return;

    tabContainers.forEach(function(container) {
      const tabs = container.querySelectorAll('[data-tab]');
      const panels = container.querySelectorAll('[data-panel]');

      tabs.forEach(function(tab) {
        tab.addEventListener('click', function() {
          const target = tab.dataset.tab;

          // Update tabs
          tabs.forEach(function(t) { t.classList.remove('active'); });
          tab.classList.add('active');

          // Update panels
          panels.forEach(function(panel) {
            if (panel.dataset.panel === target) {
              panel.classList.remove('hidden');
            } else {
              panel.classList.add('hidden');
            }
          });
        });
      });
    });
  }

  /* ===================== Dropdown ===================== */
  function initDropdowns() {
    document.addEventListener('click', function(e) {
      const toggle = e.target.closest('[data-dropdown-toggle]');
      if (!toggle) {
        // Close all dropdowns
        document.querySelectorAll('[data-dropdown].open').forEach(function(dropdown) {
          dropdown.classList.remove('open');
        });
        return;
      }

      const dropdown = toggle.closest('[data-dropdown]');
      if (!dropdown) return;

      const isOpen = dropdown.classList.contains('open');
      document.querySelectorAll('[data-dropdown].open').forEach(function(d) {
        if (d !== dropdown) d.classList.remove('open');
      });
      dropdown.classList.toggle('open', !isOpen);
    });
  }

  /* ===================== Form Validation ===================== */
  function validateForm(form) {
    if (!form) return true;

    const required = form.querySelectorAll('[required]');
    let valid = true;

    required.forEach(function(field) {
      if (!field.value.trim()) {
        field.style.borderColor = 'var(--danger)';
        valid = false;
      } else {
        field.style.borderColor = '';
      }
    });

    return valid;
  }

  /* ===================== File Upload ===================== */
  function initUploadZone() {
    const zone = document.querySelector('.upload-zone');
    if (!zone) return;

    const input = zone.querySelector('input[type="file"]');

    zone.addEventListener('click', function() {
      input?.click();
    });

    zone.addEventListener('dragover', function(e) {
      e.preventDefault();
      zone.classList.add('dragover');
    });

    zone.addEventListener('dragleave', function() {
      zone.classList.remove('dragover');
    });

    zone.addEventListener('drop', function(e) {
      e.preventDefault();
      zone.classList.remove('dragover');

      const files = e.dataTransfer.files;
      if (files.length && input) {
        input.files = files;
        handleFileSelect(files);
      }
    });

    input?.addEventListener('change', function() {
      handleFileSelect(input.files);
    });
  }

  function handleFileSelect(files) {
    if (!files.length) return;

    const file = files[0];
    const maxSize = 50 * 1024 * 1024; // 50MB

    if (file.size > maxSize) {
      showToast('文件大小不能超过 50MB', 3000);
      return;
    }

    // Show file info
    const zone = document.querySelector('.upload-zone');
    const info = zone?.querySelector('.upload-info');
    if (info) {
      info.innerHTML = `
        <p><strong>${file.name}</strong></p>
        <p class="text-sm text-muted">${formatFileSize(file.size)}</p>
      `;
    }

    if (typeof window.onFileSelect === 'function') {
      window.onFileSelect(file);
    }
  }

  function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
  }

  /* ===================== Debounce Utility ===================== */
  function debounce(func, wait) {
    let timeout;
    return function executedFunction() {
      const context = this;
      const args = arguments;
      clearTimeout(timeout);
      timeout = setTimeout(function() {
        func.apply(context, args);
      }, wait);
    };
  }

  /* ===================== Initialize All ===================== */
  function init() {
    initMobileMenu();
    initSearch();
    initCategoryFilter();
    initCopyButtons();
    initTabs();
    initDropdowns();
    initUploadZone();
  }

  // Run on DOM ready
  if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', init);
  } else {
    init();
  }

  // Expose utilities globally
  window.skills4sec = {
    showToast: showToast,
    confirmAction: confirmAction,
    validateForm: validateForm,
    debounce: debounce,
    filterSkillsByQuery: filterSkillsByQuery,
    filterSkillsByCategory: filterSkillsByCategory
  };

})();
