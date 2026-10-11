#!/bin/bash
# Archive old/unused code to consolidate and cleanup the repository
# This script identifies files not used in production and moves them to an archive

set -e

ARCHIVE_DIR="archive"
ARCHIVE_TIMESTAMP=$(date +%Y%m%d_%H%M%S)

echo "🗂️  Repository Cleanup & Archiving"
echo "=================================="

# Create archive directory
mkdir -p "$ARCHIVE_DIR"

# Function to safely archive files
archive_files() {
    local category="$1"
    shift
    local files=("$@")

    if [ ${#files[@]} -eq 0 ]; then
        echo "   ℹ️  No $category files to archive"
        return
    fi

    local archive_subdir="$ARCHIVE_DIR/${category}_$ARCHIVE_TIMESTAMP"
    mkdir -p "$archive_subdir"

    echo "   📦 Archiving ${#files[@]} $category files to $archive_subdir/"
    for file in "${files[@]}"; do
        if [ -f "$file" ] || [ -d "$file" ]; then
            echo "     → $file"
            mv "$file" "$archive_subdir/"
        fi
    done

    # Create manifest
    cat > "$archive_subdir/MANIFEST.txt" << EOF
Archived $category files on $(date)
These files were identified as unused in production.

To restore any file:
  cp $archive_subdir/FILENAME ./PATH/

Files archived:
$(ls -la "$archive_subdir" | grep -v "MANIFEST.txt" | awk '{print "  " $9}')
EOF
}

# 1. Archive old migration files (keep only recent ones)
echo "🔄 Checking alembic migrations..."
MIGRATION_FILES=$(find alembic/versions -name "*.py" -type f | sort)
TOTAL_MIGRATIONS=$(echo "$MIGRATION_FILES" | wc -l)

if [ "$TOTAL_MIGRATIONS" -gt 5 ]; then
    # Keep only the 5 most recent migrations
    OLD_MIGRATIONS=$(echo "$MIGRATION_FILES" | head -n -$((5)) )
    if [ -n "$OLD_MIGRATIONS" ]; then
        echo "   📜 Found $TOTAL_MIGRATIONS migration files, archiving old ones..."
        archive_files "old_migrations" $OLD_MIGRATIONS
    fi
fi

# 2. Archive old backup files (keep recent ones)
echo "💾 Checking backup files..."
BACKUP_FILES=$(find backups -name "*" -type f -o -name "*" -type d | grep -v "^backups$" | sort)
TOTAL_BACKUPS=$(echo "$BACKUP_FILES" | wc -l)

if [ "$TOTAL_BACKUPS" -gt 3 ]; then
    # Keep only the 3 most recent backups
    OLD_BACKUPS=$(echo "$BACKUP_FILES" | head -n -$((3)) )
    if [ -n "$OLD_BACKUPS" ]; then
        echo "   📦 Found $TOTAL_BACKUPS backup files, archiving old ones..."
        archive_files "old_backups" $OLD_BACKUPS
    fi
fi

# 3. Archive development-only files
echo "🔧 Checking development-only files..."
DEV_FILES=()

# Check for test files not used in production
if [ -f "pytest.ini" ]; then
    DEV_FILES+=("pytest.ini")
fi

# Check for development scripts
if [ -f "scripts/migrate_sqlite_to_postgres.py" ]; then
    DEV_FILES+=("scripts/migrate_sqlite_to_postgres.py")
fi

if [ -f "scripts/populate_player_metadata.py" ]; then
    DEV_FILES+=("scripts/populate_player_metadata.py")
fi

if [ -f "scripts/update_rankings_with_accurate_data.py" ]; then
    DEV_FILES+=("scripts/update_rankings_with_accurate_data.py")
fi

if [ -f "scripts/test_player_performance.py" ]; then
    DEV_FILES+=("scripts/test_player_performance.py")
fi

# Check for old Dockerfiles
if [ -f "Dockerfile.optimized" ]; then
    DEV_FILES+=("Dockerfile.optimized")
fi

# Check for Vite config files (keep only one)
if [ -f "frontend/vite.config.optimized.js" ]; then
    DEV_FILES+=("frontend/vite.config.optimized.js")
fi

if [ ${#DEV_FILES[@]} -gt 0 ]; then
    archive_files "development_files" "${DEV_FILES[@]}"
fi

# 4. Archive documentation that's outdated
echo "📚 Checking documentation..."
DOC_FILES=()

# Check for old deployment analysis (keep the latest one)
if [ -f "DEPLOYMENT_PERFORMANCE_ANALYSIS.md" ]; then
    DOC_FILES+=("DEPLOYMENT_PERFORMANCE_ANALYSIS.md")
fi

if [ ${#DOC_FILES[@]} -gt 0 ]; then
    archive_files "old_documentation" "${DOC_FILES[@]}"
fi

# 5. Clean up empty directories
echo "🧹 Cleaning up empty directories..."
find . -type d -empty -not -path "./.git/*" -delete 2>/dev/null || true

# 6. Create archive summary
echo ""
echo "📋 Archive Summary"
echo "=================="

if [ -d "$ARCHIVE_DIR" ]; then
    echo "Archives created in: $ARCHIVE_DIR/"
    echo ""
    echo "Archive contents:"
    find "$ARCHIVE_DIR" -name "MANIFEST.txt" -exec echo "📄 {}" \; -exec cat {} \; -exec echo "" \;
else
    echo "No archives were created - repository was already clean!"
fi

echo ""
echo "✅ Repository cleanup complete!"
echo ""
echo "Repository is now focused on production code with old files safely archived."
echo "To restore any archived file, check the MANIFEST.txt files in the archive directories."