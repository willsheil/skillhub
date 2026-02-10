# Implementation Specification: User Management, Skill Self-Management, and Audit Notification System

**Project**: Claude Code Skill Registry Feature Enhancement
**Date**: 2025-02-10
**Status**: Ready for Implementation
**Priority**: High

---

## Executive Summary

This specification implements three core modules for the Skill Registry system:

1. **User Management System** - Complete admin CRUD operations for user accounts
2. **User Skill Self-Management** - Allow users to manage (unlist/publish/version) their own uploaded skills
3. **Audit Notification System** - Fix approval bug and implement in-app notifications for review outcomes

---

## Part 1: Functional Requirements

### 1.1 User Management Module

#### 1.1.1 User List Page
- Display all users with pagination (default: 20 per page, max: 100)
- Display fields: employee_id, role, status, skills_count, created_at, last_login
- Support search by employee_id
- Support filtering by role (admin/user) and status (active/disabled)
- Operations: Edit, Delete/Disable, Reset API Key, Re-enable

#### 1.1.2 Create User
- Required fields: employee_id, role
- Auto-generate 32-character random API Key
- Display API Key once on creation (with copy button)
- **Decision**: Old API Key expires immediately on reset (no grace period for security)

#### 1.1.3 Edit User
- Modifiable: role
- Non-modifiable: employee_id (primary key)
- Additional: Reset API Key (generates new one)

#### 1.1.4 Delete/Disable User
- Soft delete: Set status to 'disabled'
- **Prevent deletion** if user has associated skills
- Admin can re-enable disabled users
- **Decision**: Cannot delete self (prevent lockout)

#### 1.1.5 Reset API Key
- Generate new 32-character key
- Old key becomes invalid immediately
- Requires secondary confirmation
- **Decision**: Implement rate limiting (max 1 reset per user per 5 minutes)

### 1.2 Skill Self-Management Module

#### 1.2.1 My Skills Page
- Route: `/my-skills`
- Display all skills uploaded by current user (all versions)
- Display fields: skill_name, version, is_active, status, uploaded_at, download_count
- Support filtering by: all/active/unlisted/pending/rejected
- **Decision**: Only accessible to authenticated users

#### 1.2.2 Unlist Skill
- Set `is_active` to false
- Skill no longer appears in homepage and market index
- **Decision**: Data remains intact, file not deleted

#### 1.2.3 Publish Skill
- Set `is_active` to true
- Previously approved skills can be published without re-review

#### 1.2.4 Version Management
- Display all versions of a skill, ordered newest first
- Support setting "default version" (used for downloads)
- **Decision**: Max 20 versions per skill (prevent abuse)
- **Decision**: If default version is deleted/unlisted, auto-select latest active version

#### 1.2.5 Re-upload
- **Decision**: "重新上传" button navigates to upload page with skill_name pre-filled
- User must upload a new version number (existing version validation enforced)

### 1.3 Audit Notification Module

#### 1.3.1 Bug Fix: approve_skill_file
- **Root Cause**: `shutil.move` fails when target file exists
- **Fix**: Check and remove existing file before move

#### 1.3.2 Notification System
- Create notifications on: approval, rejection
- Display unread count in navigation bar
- **Decision**: Notifications capped at 100 per user (oldest deleted first)
- **Decision**: Simple polling every 30 seconds (no WebSocket for simplicity)

#### 1.3.3 Notification Types
- `review_success`: "您的技能已通过审核"
- `review_rejected`: "您的技能未通过审核" (includes reason)

---

## Part 2: Technical Architecture

### 2.1 Tech Stack
- **Backend**: FastAPI (existing)
- **Database**: MySQL with PyMySQL (existing)
- **Frontend**: Jinja2 templates + vanilla JavaScript (existing)
- **No new dependencies** required

### 2.2 Database Schema Changes

#### 2.2.1 Users Table Additions
```sql
-- MySQL compatible syntax
ALTER TABLE users
ADD COLUMN status VARCHAR(20) DEFAULT 'active',
ADD COLUMN skills_count INT DEFAULT 0;

CREATE INDEX idx_users_status ON users(status);
CREATE INDEX idx_users_employee_id ON users(employee_id);

-- Composite index for admin user list filtering
CREATE INDEX idx_users_status_role ON users(status, role);
```

**Decision**: `skills_count` counts ALL skills regardless of is_active status (easier to maintain)

#### 2.2.2 Skills Table Additions
```sql
-- MySQL compatible syntax (TINYINT(1) for boolean)
ALTER TABLE skills
ADD COLUMN is_active TINYINT(1) DEFAULT 1,
ADD COLUMN is_default_version TINYINT(1) DEFAULT 0;

CREATE INDEX idx_skills_is_active ON skills(is_active);
CREATE INDEX idx_skills_uploader_active ON skills(uploader_id, is_active);

-- Unique constraint: only one default version per skill per uploader
CREATE UNIQUE INDEX idx_skills_unique_default
ON skills(skill_name, uploader_id, is_default_version)
WHERE is_default_version = 1;
-- Note: MySQL 8.0+ supports functional indexes, otherwise use app-level validation
```

#### 2.2.3 Notifications Table (New)
```sql
CREATE TABLE notifications (
    id INT PRIMARY KEY AUTO_INCREMENT,
    user_id INT NOT NULL,
    type VARCHAR(50) NOT NULL,
    title VARCHAR(255) NOT NULL,
    content TEXT,
    related_skill_id INT,
    is_read TINYINT(1) DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    FOREIGN KEY (related_skill_id) REFERENCES skills(id)
);

CREATE INDEX idx_notifications_user_unread ON notifications(user_id, is_read);
CREATE INDEX idx_notifications_user_created ON notifications(user_id, created_at DESC);
```

### 2.3 API Endpoints

#### User Management APIs
```
GET    /api/admin/users          - List users (paginated, filtered)
POST   /api/admin/users          - Create user
PUT    /api/admin/users/{id}     - Update user role
DELETE /api/admin/users/{id}     - Disable user
PATCH  /api/admin/users/{id}/enable - Re-enable user
POST   /api/admin/users/{id}/reset-key - Reset API Key
```

#### Skill Self-Management APIs
```
GET    /api/my-skills             - List my skills (paginated, filtered)
POST   /api/my-skills/{id}/unlist - Unlist skill
POST   /api/my-skills/{id}/publish - Publish skill
POST   /api/my-skills/{id}/set-default - Set default version
GET    /api/my-skills/{skill_name}/versions - Get all versions
```

#### Notification APIs
```
GET    /api/notifications          - List notifications (paginated)
GET    /api/notifications/unread-count - Get unread count
POST   /api/notifications/{id}/read - Mark as read
POST   /api/notifications/read-all - Mark all as read
```

### 2.4 File Structure
```
D:\work\skillhub\
├── main.py                    # Add new API endpoints
├── database.py                # Add DB functions and migration
├── static/
│   └── js/
│       └── notifications.js   # New: notification polling
├── templates/
│   ├── admin_users.html       # New: user management page
│   ├── my_skills.html         # New: my skills page
│   └── layout.html            # Modify: add notification bell
└── database.py                # Modify: add migration function
```

---

## Part 3: Clarifications and Decisions

Based on the Analyst and Architect review, the following decisions were made:

### 3.1 Security Decisions
| Question | Decision | Rationale |
|----------|----------|-----------|
| API Key reset grace period | None (immediate) | Security priority |
| Admin self-deletion | Blocked | Prevent lockout |
| Admin self-role-change | Blocked | Prevent privilege escalation |
| API key reset rate limit | 1 per 5 minutes per user | Prevent abuse |
| Audit logging | Implement `audit_logs` table | Compliance and debugging |

### 3.2 Data Decisions
| Question | Decision | Rationale |
|----------|----------|-----------|
| skills_count calculation | Count all skills | Simpler, avoids complex triggers |
| Notification cleanup | Delete oldest > 100 on insert | Simple implementation |
| Max versions per skill | 20 | Prevent storage abuse |
| Orphan handling | Block delete if skills exist | Force explicit transfer |

### 3.3 UX Decisions
| Question | Decision | Rationale |
|----------|----------|-----------|
| Notification real-time | 30s polling | Simple, no WebSocket complexity |
| 重新上传 button | Navigate to upload with pre-filled name | Consistent UX |
| Default version on delete | Auto-select latest active version | Maintain usability |

---

## Part 4: Integration Points

### 4.1 Existing Functions to Modify
- `database.py:169-256` `init_db()` - Add new tables
- `database.py:94-110` - Add new migration function
- `main.py:971-1004` `approve_skill_file()` - Fix bug, add notification
- `main.py:382-437` `scan_plugins()` - Filter by is_active
- `templates/layout.html` - Add notification bell

### 4.2 Bug Fix Details
Location: `main.py:971-1004` `approve_skill_file()`

**Problem**: Uses `shutil.move()` which fails when target exists

**Solution**:
```python
# Before moving, check and remove existing file
if plugins_path.exists():
    logger.info(f"Removing existing file: {plugins_path}")
    plugins_path.unlink()
shutil.move(str(pending_path), str(plugins_path))
```

---

## Part 5: Security Considerations

### 5.1 Authorization
- All user management endpoints require `@require_admin`
- All `/api/my-skills` endpoints verify ownership
- Notification access limited to own notifications

### 5.2 Input Validation
- Employee ID: max 50 chars, alphanumeric
- Role: enum ['admin', 'user']
- Version: semver pattern validation
- Notification content: max 1000 chars

### 5.3 Audit Logging
Track all sensitive operations:
- User creation, deletion, role changes, key resets
- Skill approval, rejection
- Admin access to user management

---

## Part 6: Error Handling

### 6.1 Standard Error Response
```json
{
  "success": false,
  "error": "ERROR_CODE",
  "message": "User-friendly description",
  "details": {}
}
```

### 6.2 Error Codes
- `UNAUTHORIZED` - Not logged in
- `FORBIDDEN` - Insufficient permissions
- `NOT_FOUND` - Resource doesn't exist
- `VALIDATION_ERROR` - Invalid input
- `DUPLICATE_ERROR` - Resource already exists
- `OPERATION_NOT_ALLOWED` - Action not permitted
- `USER_HAS_SKILLS` - Cannot delete user with skills
- `EMPLOYEE_ID_EXISTS` - Employee ID already taken

---

## Part 7: Migration Script

```python
def migrate_add_user_management_features():
    """Add user management, skill self-management, and notification features."""
    with get_connection() as conn:
        # Users table additions
        conn.execute("""
            ALTER TABLE users
            ADD COLUMN status VARCHAR(20) DEFAULT 'active' IF NOT EXISTS
        """)
        conn.execute("""
            ALTER TABLE users
            ADD COLUMN skills_count INT DEFAULT 0 IF NOT EXISTS
        """)

        # Skills table additions
        conn.execute("""
            ALTER TABLE skills
            ADD COLUMN is_active TINYINT(1) DEFAULT 1 IF NOT EXISTS
        """)
        conn.execute("""
            ALTER TABLE skills
            ADD COLUMN is_default_version TINYINT(1) DEFAULT 0 IF NOT EXISTS
        """)

        # Create notifications table
        conn.execute("""
            CREATE TABLE IF NOT EXISTS notifications (
                id INT PRIMARY KEY AUTO_INCREMENT,
                user_id INT NOT NULL,
                type VARCHAR(50) NOT NULL,
                title VARCHAR(255) NOT NULL,
                content TEXT,
                related_skill_id INT,
                is_read TINYINT(1) DEFAULT 0,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(id),
                FOREIGN KEY (related_skill_id) REFERENCES skills(id)
            )
        """)

        # Create indexes
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_status ON users(status)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_users_status_role ON users(status, role)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_skills_is_active ON skills(is_active)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_skills_uploader_active ON skills(uploader_id, is_active)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_unread ON notifications(user_id, is_read)")
        conn.execute("CREATE INDEX IF NOT EXISTS idx_notifications_user_created ON notifications(user_id, created_at DESC)")

        # Initialize skills_count for existing users
        conn.execute("""
            UPDATE users u
            SET skills_count = (
                SELECT COUNT(*) FROM skills s WHERE s.uploader_id = u.id
            )
        """)

        conn.commit()
        logger.info("Migration completed: user management features added")
```

---

## Part 8: Test Plan

### 8.1 Unit Tests
- User CRUD operations
- Skill unlist/publish
- Notification creation and retrieval
- Authorization checks

### 8.2 Integration Tests
- Full user lifecycle (create → upload → approve → disable)
- Skill version management
- End-to-end audit notification flow

### 8.3 Edge Cases
- Duplicate employee_id
- Delete user with skills (should fail)
- Version limit (20) enforcement
- Notification cleanup at 100

---

## Appendix: Agent Analysis Summary

### Analyst Findings
- Spec is ~85% complete
- Identified 8 missing questions (resolved above)
- Identified 8 undefined guardrails (addressed)
- Key risks: race conditions, orphan handling, concurrent modifications

### Architect Findings
- **Critical Issue**: SQLite syntax in MySQL database (TEXT vs VARCHAR, AUTOINCREMENT vs AUTO_INCREMENT, BOOLEAN vs TINYINT)
- **17 technical issues** identified:
  - Schema syntax mismatches (fixed in this spec)
  - Missing database constraints (added)
  - Authorization gaps (addressed)
  - Missing audit logging (added to requirements)

---

**Specification Status**: READY FOR IMPLEMENTATION
**Estimated Duration**: 3 days (1 day user management, 1 day skill management, 0.5 day notifications, 0.5 day testing)
