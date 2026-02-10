# Implementation Plan: User Management, Skill Self-Management, and Audit Notification System

**Project**: Claude Code Skill Registry Feature Enhancement
**Date**: 2026-02-10
**Status**: Ready for Implementation
**Estimated Duration**: 3 days
**Complexity**: HIGH

---

## Executive Summary

This plan implements three core modules for the Skill Registry system:

1. **User Management System** - Complete admin CRUD operations for user accounts
2. **User Skill Self-Management** - Allow users to manage their own uploaded skills
3. **Audit Notification System** - Fix approval bug and implement in-app notifications

The implementation is organized into **4 stages** that can be executed in parallel by multiple agents.

---

## Stage 0: Directory Setup

**Complexity**: LOW
**Dependencies**: None
**Files to Create**: 0
**Directories to Create**: 1

### Tasks

#### 0.1 Create Static JavaScript Directory
**Action**: Create `static/js/` directory for JavaScript modules

**Command**:
```bash
mkdir -p static/js/
```

**Verification**:
```bash
ls -la static/js/
```

**Acceptance Criteria**:
- Directory exists and is writable
- FastAPI static file mounting works (will be verified during testing)

---

## Stage 1: Database Schema & Migration Foundation

**Complexity**: MEDIUM
**Dependencies**: None
**Files to Create**: 0
**Files to Modify**: 1 (`database.py`)

### Tasks

#### 1.1 Create Migration Function
**File**: `database.py`
**Action**: Add `migrate_add_user_management_features()` function

**Requirements**:
- Add `status` column to `users` table (default: 'active')
- Add `skills_count` column to `users` table (default: 0)
- Add `is_active` column to `skills` table (default: 1, TINYINT)
- Add `is_default_version` column to `skills` table (default: 0, TINYINT)
- Create `notifications` table with schema:
  - id (INT PRIMARY KEY AUTO_INCREMENT)
  - user_id (INT NOT NULL, FK to users)
  - type (VARCHAR(50))
  - title (VARCHAR(255))
  - content (TEXT)
  - related_skill_id (INT, FK to skills)
  - is_read (TINYINT(1), default 0)
  - created_at (TIMESTAMP, default CURRENT_TIMESTAMP)
- Create indexes for performance:
  - `idx_users_status` on users(status)
  - `idx_users_status_role` on users(status, role)
  - `idx_skills_is_active` on skills(is_active)
  - `idx_skills_uploader_active` on skills(uploader_id, is_active)
  - `idx_notifications_user_unread` on notifications(user_id, is_read)
  - `idx_notifications_user_created` on notifications(user_id, created_at DESC)
- Initialize `skills_count` for existing users

**Acceptance Criteria**:
- Migration runs successfully without errors
- All columns and indexes are created in MySQL
- Existing users get correct `skills_count` values
- Migration is idempotent (can be run multiple times safely)

#### 1.2 Add Database Helper Functions
**File**: `database.py`
**Action**: Add new functions for user management and notifications

**Functions to Add**:
```python
def get_users_list(page: int, per_page: int, role_filter: Optional[str] = None,
                   status_filter: Optional[str] = None, search: Optional[str] = None)
def create_user(employee_id: str, role: str, status: str = 'active') -> Tuple[int, str]
def update_user_role(user_id: int, role: str) -> bool
def update_user_status(user_id: int, status: str) -> bool
def reset_user_api_key(user_id: int) -> str
def get_user_skills_count(user_id: int) -> int
def increment_user_skills_count(user_id: int) -> None
def decrement_user_skills_count(user_id: int) -> None
def get_my_skills(user_id: int, status_filter: Optional[str] = None,
                  page: int = 1, per_page: int = 20)
def update_skill_active_status(skill_id: int, is_active: bool) -> bool
def set_default_skill_version(skill_id: int) -> bool
def get_skill_versions(skill_name: str, uploader_id: int) -> List[Dict]
def create_notification(user_id: int, type: str, title: str,
                        content: Optional[str] = None, related_skill_id: Optional[int] = None) -> int
def get_user_notifications(user_id: int, unread_only: bool = False,
                           limit: int = 50, offset: int = 0) -> Dict
def mark_notification_read(notification_id: int, user_id: int) -> bool
def mark_all_notifications_read(user_id: int) -> int
def get_unread_notifications_count(user_id: int) -> int
def cleanup_old_notifications(user_id: int, keep_count: int = 100) -> None
```

**Acceptance Criteria**:
- All functions use MySQL-compatible syntax
- Functions handle edge cases (user not found, skill not found, etc.)
- Proper error logging for debugging
- Type hints included for all parameters

#### 1.3 Integrate Migration into init_db
**File**: `database.py`
**Location**: `init_db()` function, after line 256 (after `migrate_add_source_type_to_skills()`)

**Action**: Add migration call
```python
# In init_db(), after line 256:
migrate_add_user_management_features()
```

**Acceptance Criteria**:
- Migration runs automatically on server startup
- Idempotent (safe to run multiple times)
- No errors during initialization

---

## Stage 2: User Management API & UI

**Complexity**: HIGH
**Dependencies**: Stage 1 (must complete first)
**Files to Create**: 1 (`templates/admin_users.html`)
**Files to Modify**: 1 (`main.py`)

### Tasks

#### 2.1 Implement User Management API Endpoints
**File**: `main.py`
**Location**: After line 2532 (before `if __name__` block)

**Endpoints to Add**:

```python
# GET /api/admin/users - List users with pagination and filters
@app.get("/api/admin/users")
async def api_get_users(
    request: Request,
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    role: Optional[str] = Query(None),
    status: Optional[str] = Query(None),
    search: Optional[str] = Query(None),
    _: bool = Depends(require_admin)
)

# POST /api/admin/users - Create new user
@app.post("/api/admin/users")
async def api_create_user(
    request: Request,
    employee_id: str = Form(...),
    role: str = Form(...),
    _: bool = Depends(require_admin)
)

# PUT /api/admin/users/{user_id} - Update user role
@app.put("/api/admin/users/{user_id:int}")
async def api_update_user(
    user_id: int,
    request: Request,
    _: bool = Depends(require_admin)
)

# DELETE /api/admin/users/{user_id} - Disable user
@app.delete("/api/admin/users/{user_id:int}")
async def api_disable_user(
    user_id: int,
    request: Request,
    _: bool = Depends(require_admin)
)

# PATCH /api/admin/users/{user_id}/enable - Re-enable user
@app.patch("/api/admin/users/{user_id:int}/enable")
async def api_enable_user(
    user_id: int,
    request: Request,
    _: bool = Depends(require_admin)
)

# POST /api/admin/users/{user_id}/reset-key - Reset API key
@app.post("/api/admin/users/{user_id:int}/reset-key")
async def api_reset_user_key(
    user_id: int,
    request: Request,
    _: bool = Depends(require_admin)
)
```

**Security Requirements**:
- All endpoints require `@require_admin` decorator
- Prevent admin from disabling themselves (user_id == session.user_id)
- Prevent deletion if user has associated skills (check `skills_count > 0`)
- Implement rate limiting for API key reset (max 1 per 5 minutes per user)
- Validate employee_id format (alphanumeric, max 50 chars)
- Validate role values ('admin' or 'user')

**Acceptance Criteria**:
- All endpoints return JSON responses with standard format
- Error codes: UNAUTHORIZED, FORBIDDEN, NOT_FOUND, VALIDATION_ERROR, DUPLICATE_ERROR, OPERATION_NOT_ALLOWED, USER_HAS_SKILLS
- API key generation returns 32-character random string
- API key displayed only once on creation (subsequent requests show placeholder)

#### 2.2 Create User Management UI
**File**: `templates/admin_users.html` (NEW)

**Page Sections**:
1. **Header**: Title "用户管理" with breadcrumb navigation
2. **Action Bar**:
   - Search input (employee_id)
   - Role filter dropdown (All/Admin/User)
   - Status filter dropdown (All/Active/Disabled)
   - "Add User" button
3. **Users Table**:
   - Columns: Employee ID, Role, Status, Skills Count, Created At, Last Login, Actions
   - Pagination (20 per page, max 100)
   - Row actions: Edit, Disable/Enable, Reset Key, Delete (if no skills)
4. **Create/Edit Modal**:
   - Create: Employee ID (required), Role (required)
   - Edit: Role only (employee_id read-only)
   - Show API Key on create (with copy button)
5. **Reset Key Confirmation Modal**: Secondary confirmation required

**Styling**: Match existing `index.html` style (green theme #10B981)

**Acceptance Criteria**:
- Responsive design (mobile-friendly)
- Client-side validation for employee_id format
- Real-time search with debounce (300ms)
- AJAX for all actions (no page reload)
- Loading states for async operations
- Error messages displayed inline

#### 2.3 Add Navigation Link
**File**: `templates/index.html` (modify top-nav section)
**Action**: Add "用户管理" link in admin-only nav section
**Location**: Find the `<nav>` section with `.user-actions` div, locate `{% if user.role == 'admin' %}` block, insert after existing admin links (search for "管理后台")

---

## Stage 3: Skill Self-Management Features

**Complexity**: MEDIUM
**Dependencies**: Stage 1
**Files to Create**: 2 (`templates/my_skills.html`, `static/js/skill-management.js`)
**Files to Modify**: 2 (`main.py`, `templates/index.html`)

### Tasks

#### 3.1 Implement Skill Management API Endpoints
**File**: `main.py`
**Location**: After user management endpoints

**Endpoints to Add**:

```python
# GET /api/my-skills - List current user's skills
@app.get("/api/my-skills")
async def api_get_my_skills(
    request: Request,
    status: Optional[str] = Query(None),  # all/active/unlisted/pending/rejected
    page: int = Query(1, ge=1),
    per_page: int = Query(20, ge=1, le=100),
    _: bool = Depends(require_auth)
)

# GET /my-skills - My Skills page
@app.get("/my-skills", response_class=HTMLResponse)
async def my_skills_page(request: Request)

# POST /api/my-skills/{skill_id}/unlist - Unlist skill
@app.post("/api/my-skills/{skill_id:int}/unlist")
async def api_unlist_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_auth)
)

# POST /api/my-skills/{skill_id}/publish - Publish skill
@app.post("/api/my-skills/{skill_id:int}/publish")
async def api_publish_skill(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_auth)
)

# POST /api/my-skills/{skill_id}/set-default - Set default version
@app.post("/api/my-skills/{skill_id:int}/set-default")
async def api_set_default_version(
    skill_id: int,
    request: Request,
    _: bool = Depends(require_auth)
)

# GET /api/my-skills/versions/{skill_name} - Get all versions
@app.get("/api/my-skills/versions/{skill_name:path}")
async def api_get_skill_versions(
    skill_name: str,
    request: Request,
    _: bool = Depends(require_auth)
)
```

**Business Logic**:
- Verify ownership: `skill.uploader_id == session.user_id`
- Version limit: Max 20 versions per skill name per uploader
- Default version handling: Auto-select latest active if default is deleted/unlisted
- Unlist: Set `is_active = 0`, data remains intact
- Publish: Set `is_active = 1`, no re-review needed if previously approved

**Acceptance Criteria**:
- Returns 403 if user doesn't own the skill
- Returns 400 if trying to create more than 20 versions
- Updates `skills_count` on upload/delete
- Pagination works correctly

#### 3.2 Create My Skills Page
**File**: `templates/my_skills.html` (NEW)

**Page Sections**:
1. **Header**: Title "我的技能" with upload button
2. **Filter Bar**:
   - Tabs: All/Active/Unlisted/Pending/Rejected
   - Search input (skill name)
3. **Skills List**:
   - Card layout showing: skill_name, version, status, is_active badge, uploaded_at, download_count
   - Group by skill name (show all versions collapsed by default)
   - Actions per skill: Publish/Unlist, Set Default, Delete, Upload New Version
4. **Version Management**:
   - Expandable section showing all versions
   - Radio button to select default version
   - Version badges: Default (star icon), Active (green), Unlisted (gray)
5. **Upload Button**: Redirects to `/upload?skill_name=<name>` for re-upload

**Acceptance Criteria**:
- Only accessible to authenticated users
- Empty state message when no skills
- Confirmation dialogs for destructive actions
- Version group sorted newest first

#### 3.3 Modify Existing Functions
**File**: `main.py`
**Function**: `approve_skill_file()` (line 971-1004)

**Pre-verification**:
- `grep -r "def approve_skill_file" --include="*.py" .` to ensure only one instance exists
- Result should show ONLY `main.py:971` (other matches in docs/ are acceptable)

**Bug Fix**:

**Bug Fix**:
```python
# BEFORE (line 996):
shutil.move(str(pending_path), str(plugins_path))

# AFTER:
if plugins_path.exists():
    logger.info(f"Removing existing file: {plugins_path}")
    plugins_path.unlink()
shutil.move(str(pending_path), str(plugins_path))
```

**Additional Changes**:
- Create notification on approval: `create_notification(uploader_id, 'review_success', ...)`
- Create notification on rejection: `create_notification(uploader_id, 'review_rejected', ...)`
- Set `is_active = 1` on approval

**File**: `main.py`
**Function**: `scan_plugins()` (line 382-437)

**Modification**:
- Filter by `is_active` status when building plugins list
- Only return skills where `is_active = 1`

**Acceptance Criteria**:
- Bug fix prevents `FileExistsError` on re-approval
- Notifications created for both approval and rejection
- Unlisted skills don't appear in homepage/marketplace

#### 3.4 Add Navigation Link
**File**: `templates/index.html`
**Action**: Add "我的技能" link in user nav section
**Location**: In `<nav>` with `.user-actions` div, find the user links section, insert after "上传" link (search for href="/upload")

#### 3.5 Create Skill Management JavaScript Module
**File**: `static/js/skill-management.js` (NEW)
**Location**: Created in Stage 0 directory setup

**Features to Implement**:
- Skill card rendering with version grouping
- Version management modal (expandable sections)
- AJAX handlers for: unlist, publish, set-default
- Filter tab switching (All/Active/Unlisted/Pending/Rejected)
- Search with 300ms debounce
- Confirmation dialogs for destructive actions
- Re-upload button (redirects to `/upload?skill_name=<name>`)

**Acceptance Criteria**:
- Module loads without errors
- All AJAX calls use proper error handling
- User feedback (toasts/loading states) for all actions
- Responsive design for mobile

---

## Stage 4: Notification System

**Complexity**: MEDIUM
**Dependencies**: Stage 1, Stage 3 (for approval notifications)
**Files to Create**: 1 (`static/js/notifications.js`)
**Files to Modify**: 2 (`main.py`, `templates/index.html`)

### Tasks

#### 4.1 Implement Notification API Endpoints
**File**: `main.py`
**Location**: After skill management endpoints

**Endpoints to Add**:

```python
# GET /api/notifications - List user notifications
@app.get("/api/notifications")
async def api_get_notifications(
    request: Request,
    unread_only: bool = Query(False),
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    _: bool = Depends(require_auth)
)

# GET /api/notifications/unread-count - Get unread count
@app.get("/api/notifications/unread-count")
async def api_get_unread_count(
    request: Request,
    _: bool = Depends(require_auth)
)

# POST /api/notifications/{notification_id}/read - Mark as read
@app.post("/api/notifications/{notification_id:int}/read")
async def api_mark_notification_read(
    notification_id: int,
    request: Request,
    _: bool = Depends(require_auth)
)

# POST /api/notifications/read-all - Mark all as read
@app.post("/api/notifications/read-all")
async def api_mark_all_read(
    request: Request,
    _: bool = Depends(require_auth)
)
```

**Acceptance Criteria**:
- Users can only access their own notifications
- Automatic cleanup: Delete oldest notifications when count exceeds 100
- Newest notifications first (ORDER BY created_at DESC)

#### 4.2 Add Notification Bell to Navigation
**File**: `templates/index.html`
**Location**: In `<nav>` with `.user-actions` div, before the employee_id span (search for class="employee-id" or similar user identifier)

**HTML to Add**:
```html
<div class="notification-wrapper" style="position: relative; margin-right: 12px;">
    <button class="notification-bell" id="notificationBell" onclick="toggleNotifications()">
        <span style="font-size: 20px;">🔔</span>
        <span class="notification-badge" id="notificationBadge" style="display: none;"></span>
    </button>
    <div class="notification-dropdown" id="notificationDropdown" style="display: none;">
        <div class="notification-header">
            <span>通知</span>
            <a href="#" onclick="markAllRead(); return false;">全部已读</a>
        </div>
        <div class="notification-list" id="notificationList"></div>
        <div class="notification-footer">
            <a href="/notifications">查看全部</a>
        </div>
    </div>
</div>
```

**CSS to Add** (in `<style>` section):
```css
.notification-bell {
    background: none;
    border: none;
    cursor: pointer;
    position: relative;
    padding: 4px;
}

.notification-badge {
    position: absolute;
    top: 0;
    right: 0;
    background: #ef4444;
    color: white;
    border-radius: 50%;
    width: 18px;
    height: 18px;
    font-size: 11px;
    display: flex;
    align-items: center;
    justify-content: center;
}

.notification-dropdown {
    position: absolute;
    top: 100%;
    right: 0;
    margin-top: 8px;
    background: white;
    border: 1px solid #eaeaea;
    border-radius: 12px;
    box-shadow: 0 4px 20px rgba(0,0,0,0.1);
    width: 320px;
    max-height: 400px;
    z-index: 1000;
}

.notification-header {
    padding: 12px 16px;
    border-bottom: 1px solid #eaeaea;
    display: flex;
    justify-content: space-between;
    align-items: center;
    font-weight: 600;
}

.notification-list {
    max-height: 300px;
    overflow-y: auto;
}

.notification-item {
    padding: 12px 16px;
    border-bottom: 1px solid #f3f4f6;
    cursor: pointer;
}

.notification-item.unread {
    background: #f0fdf4;
}

.notification-item:hover {
    background: #f9fafb;
}

.notification-footer {
    padding: 12px 16px;
    border-top: 1px solid #eaeaea;
    text-align: center;
}
```

#### 4.3 Create Notification Polling Script
**File**: `static/js/notifications.js` (NEW)

**Features**:
- Poll `/api/notifications/unread-count` every 30 seconds
- Update badge count
- Fetch and display notifications when bell clicked
- Mark as read on click
- Mark all as read button

**Acceptance Criteria**:
- Polling stops when tab is inactive (Page Visibility API)
- Debounce bell click (prevent double-toggle)
- Close dropdown when clicking outside

---

## Integration Points

### Files Modified Summary

| File | Lines Added | Lines Modified | Purpose |
|------|-------------|----------------|---------|
| `database.py` | ~400 | ~50 | Schema migration, helper functions |
| `main.py` | ~600 | ~10 | API endpoints, bug fixes |
| `templates/index.html` | ~100 | ~20 | Notification bell, navigation links |
| `templates/admin_users.html` | ~500 | 0 | User management UI (NEW) |
| `templates/my_skills.html` | ~400 | 0 | My skills page (NEW) |
| `static/js/notifications.js` | ~150 | 0 | Notification polling (NEW) |

### Database Changes

**New Table**: `notifications`
**Modified Tables**: `users` (+2 columns), `skills` (+2 columns)
**New Indexes**: 6 performance indexes

### External Dependencies

**None required** - uses existing stack (FastAPI, PyMySQL, Jinja2, vanilla JS)

---

## Testing Requirements

### Unit Tests (if adding test suite)
- User CRUD operations
- Skill unlist/publish
- Notification creation and cleanup
- Authorization checks

### Integration Tests
- Full user lifecycle (create → upload → approve → disable)
- Skill version management (default version selection)
- End-to-end notification flow (approve → notification → read)

### Manual Testing Checklist
- [ ] Admin can create user and see API key
- [ ] Admin cannot delete themselves
- [ ] Admin cannot delete user with skills
- [ ] User can see only their own skills
- [ ] Unlisted skills don't appear on homepage
- [ ] Default version downloads correctly
- [ ] Notification appears after approval
- [ ] Notification badge updates count
- [ ] Polling stops on tab inactive

---

## Error Codes Reference

| Code | HTTP Status | Description |
|------|-------------|-------------|
| UNAUTHORIZED | 401 | Not logged in |
| FORBIDDEN | 403 | Insufficient permissions |
| NOT_FOUND | 404 | Resource doesn't exist |
| VALIDATION_ERROR | 400 | Invalid input |
| DUPLICATE_ERROR | 409 | Resource already exists |
| OPERATION_NOT_ALLOWED | 403 | Action not permitted |
| USER_HAS_SKILLS | 403 | Cannot delete user with skills |
| EMPLOYEE_ID_EXISTS | 409 | Employee ID already taken |

---

## Deployment Notes

1. **Backup First**: Run database backup before migration
2. **Migration Order**: Run Stage 1 migration first
3. **Graceful Period**: No grace period for API key reset (immediate)
4. **Notification Cleanup**: Runs automatically on new notification insert
5. **Rollback Plan**: SQL rollback script not provided (manual revert required)

---

## Success Criteria

### Functional Requirements
- All 17 API endpoints respond correctly
- Database migration completes without errors
- UI pages render without JavaScript errors
- Notifications appear within 30 seconds of approval
- Unlisted skills are hidden from public view

### Non-Functional Requirements
- Response time < 500ms for all endpoints
- Polling doesn't cause performance degradation
- Database queries use indexes (no full table scans)
- Mobile UI is fully functional

---

**Plan Status**: READY FOR IMPLEMENTATION
**Next Action**: Execute Stage 1 (Database Migration)
