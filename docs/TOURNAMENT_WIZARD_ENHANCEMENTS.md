# Tournament Wizard Enhancement Plan

## Feature Requests

### 1. Auto-save Tournament Draft on Each Step
**Priority**: High  
**User Benefit**: Prevents data loss, allows users to resume later

**Implementation:**

#### Backend
- **New Table**: `tournament_drafts`
  ```sql
  CREATE TABLE tournament_drafts (
    draft_id SERIAL PRIMARY KEY,
    user_id TEXT NOT NULL,
    draft_data JSONB NOT NULL,
    current_step INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
  );
  ```

- **New Endpoints**:
  - `POST /api/tournaments/drafts` - Save/update draft (auto-save on step navigation)
  - `GET /api/tournaments/drafts` - Get user's latest draft
  - `DELETE /api/tournaments/drafts/{draft_id}` - Delete draft after completion

#### Frontend
- Auto-save on "Next" button click
- Load draft on wizard mount (show "Resume draft?" dialog)
- "Save & Exit" button in each step
- Clear draft after successful tournament creation

---

### 2. Save Tournament as Template
**Priority**: Medium  
**User Benefit**: Quick tournament creation with pre-configured settings

**Implementation:**

#### Backend
- **Enhance existing `tournament_templates` table**: Already exists, just needs UI
- **New Endpoint**: 
  - `POST /api/tournaments/{tournament_id}/save-as-template`
  - Request body: `{ template_name: string, include_players: boolean }`

#### Frontend
- "Save as Template" button in step 4 (review screen)
- Dialog to name the template
- Options to include/exclude:
  - ☐ Players
  - ☐ Dates (use them or make them blank)
  - ☐ Location
  - ☑ Points structure (always included)
  - ☑ Tournament type (always included)

---

### 3. Template Management (CRUD)
**Priority**: Medium  
**User Benefit**: Edit and organize templates, fix mistakes

**Implementation:**

#### Backend
- **Existing endpoints** (already implemented):
  - `GET /api/tournaments/templates` - List templates
  - `POST /api/tournaments/templates` - Create template (manual)
  - `GET /api/tournaments/templates/{id}` - Get template details
  
- **New endpoints**:
  - `PUT /api/tournaments/templates/{id}` - Update template
    - Permissions: Creator OR admin+
  - `POST /api/tournaments/templates/{id}/clone` - Clone as new template
    - Creates copy with new name
  - `DELETE /api/tournaments/templates/{id}` - Delete template
    - Permissions: Admin+ only

#### Frontend
- **New Page**: Settings → Tournament Templates
  - List all templates (table view)
  - Edit button → Opens edit dialog
  - Clone button → Prompts for new name
  - Delete button → Confirmation dialog (admin only)

- **Edit Dialog**:
  - Editable fields: name, elimination_type, max_players, points_structure
  - "Save" or "Save as New" buttons
  - Validation (same as wizard)

---

## Permissions Summary

| Feature | User | Director | Admin | Super Admin |
|---------|------|----------|-------|-------------|
| Save draft | ✅ | ✅ | ✅ | ✅ |
| Load draft | ✅ (own) | ✅ (own) | ✅ (own) | ✅ (all) |
| Save as template | ✅ (private) | ✅ (private) | ✅ (global) | ✅ (global) |
| Edit template | ✅ (own) | ✅ (own) | ✅ (all) | ✅ (all) |
| Clone template | ✅ | ✅ | ✅ | ✅ |
| Delete template | ❌ | ❌ | ✅ | ✅ |

---

## Implementation Phases

### Phase 1: Auto-save Drafts (2-3 hours)
1. Create `tournament_drafts` table (Alembic migration)
2. Add backend endpoints (drafts CRUD)
3. Add frontend auto-save on "Next" button
4. Add "Resume draft?" dialog on wizard mount
5. Clear draft on successful create

### Phase 2: Save as Template (1-2 hours)
1. Add `save-as-template` endpoint
2. Add "Save as Template" button in step 4
3. Add name/options dialog
4. Test template creation flow

### Phase 3: Template Management (3-4 hours)
1. Add edit/clone/delete endpoints
2. Create Templates management page
3. Add edit dialog with validation
4. Add permissions checks (admin delete)
5. Test CRUD operations

### Phase 4: Polish (1 hour)
- Toast notifications for all operations
- Loading states
- Error handling
- Documentation updates

**Total Estimated Time**: 7-10 hours

---

## Current Blocker Issues to Fix First

### Issue 1: Live Updates 404
**Status**: API router added, needs API restart  
**Fix**: Run `bash ./scripts/full_deploy.sh` to restart API

### Issue 2: Competitors Import Failing
**Status**: Import feature has bugs, causing 400 errors  
**Workaround**: Uncheck "Import from Competitors" in step 3  
**Proper Fix**: Debug the competitors import endpoint or disable the checkbox by default

### Issue 3: Empty Tournament Creation
**Current Behavior**: Can create tournament without players (gets "Need 2 players" error)  
**Already Fixed**: Bracket only generates when players are selected  
**User Action**: Select players in step 3, or create tournament without bracket for "setup mode"

---

## Usage Patterns

### Pattern 1: Quick Tournament (with template)
1. Select template in step 2
2. Adjust dates/location in step 1
3. Select players in step 3
4. Create → Done in 30 seconds

### Pattern 2: Custom Tournament (save for later)
1. Fill step 1 → Auto-saved
2. Configure points in step 2 → Auto-saved
3. Exit wizard → Draft saved
4. Return later → "Resume draft?" → Continue from step 3

### Pattern 3: Recurring Event (template)
1. Create first tournament with full details
2. In step 4, click "Save as Template"
3. Name it "Weekly Thursday League"
4. Next week: Select that template → Just update date → Create

---

## Database Schema Changes

```sql
-- New table for drafts
CREATE TABLE tournament_drafts (
  draft_id SERIAL PRIMARY KEY,
  user_id TEXT NOT NULL,
  draft_data JSONB NOT NULL,
  current_step INTEGER DEFAULT 1 CHECK (current_step BETWEEN 1 AND 4),
  created_at TIMESTAMP DEFAULT NOW(),
  updated_at TIMESTAMP DEFAULT NOW(),
  FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE,
  INDEX idx_drafts_user (user_id, updated_at DESC)
);

-- Existing table (already exists, no changes needed)
-- tournament_templates
```

---

## API Endpoints to Add

```
POST   /api/tournaments/drafts                    # Save/update draft
GET    /api/tournaments/drafts                    # Get user's drafts
GET    /api/tournaments/drafts/latest             # Get most recent draft
DELETE /api/tournaments/drafts/{draft_id}         # Delete draft

POST   /api/tournaments/{id}/save-as-template     # Save tournament as template
PUT    /api/tournaments/templates/{id}            # Edit template
POST   /api/tournaments/templates/{id}/clone      # Clone template
DELETE /api/tournaments/templates/{id}            # Delete template (admin+)
```

---

## Notes

- Drafts are **per-user** (users can only see their own)
- Templates can be **private** (user-only) or **global** (admin-created, all users see)
- Competitor import feature needs debugging before it's reliable
- Entry fee now accepts values up to $999,999.99 (fixed Feb 21)

