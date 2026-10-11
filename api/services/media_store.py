"""
Media store: Postgres table for scraped WPBA/WPA media with source, category, contributor.
Used for weighted slideshow (women 2x men, Debbie Teichert at least 1 in 8).
"""

import logging
from typing import List, Optional

from sqlalchemy import text

logger = logging.getLogger(__name__)


def _ensure_media_table(engine):
    """Create media table in Postgres if it does not exist."""
    with engine.connect() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS media (
                id SERIAL PRIMARY KEY,
                path VARCHAR(2048) NOT NULL UNIQUE,
                source VARCHAR(255) NOT NULL,
                category VARCHAR(255) NOT NULL,
                contributor VARCHAR(255),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_media_source ON media(source)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_media_category ON media(category)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_media_contributor ON media(contributor)"))
        conn.commit()


def add_media(path: str, source: str, category: str, contributor: Optional[str] = None) -> bool:
    """Add or replace a media entry. path is serve path e.g. /api/assets/serve/image/xyz.jpg."""
    try:
        from database import get_engine, get_database_manager
        engine = get_engine()
        _ensure_media_table(engine)
        db = get_database_manager()
        conn = db.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO media (path, source, category, contributor)
            VALUES (%s, %s, %s, %s)
            ON CONFLICT (path) DO UPDATE SET
                source = EXCLUDED.source,
                category = EXCLUDED.category,
                contributor = EXCLUDED.contributor
        """, (path, source, category, contributor or ""))
        conn.commit()
        conn.close()
        return True
    except Exception as e:
        logger.warning("add_media failed: %s", e)
        return False


def get_slideshow_urls(
    limit: int = 24,
    women_weight: float = 2.0,
    men_weight: float = 1.0,
    debbie_every_n: int = 8,
) -> List[str]:
    """
    Return a weighted random slideshow sequence.
    - Women (WPBA/WPA women) appear 2x as often as men.
    - Debbie Teichert (contributor) appears at least once every debbie_every_n slides.
    """
    import random
    from database import get_engine, get_database_manager
    engine = get_engine()
    _ensure_media_table(engine)
    db = get_database_manager()
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT path, category, contributor FROM media WHERE path IS NOT NULL AND path != ''"
    )
    rows = cursor.fetchall()
    conn.close()
    if not rows:
        return []

    def row_dict(r):
        return {"path": r[0], "category": r[1] or "", "contributor": r[2] or ""}

    rows = [row_dict(r) for r in rows]
    women = [r["path"] for r in rows if (r["category"] or "").lower() in ("women", "wpba", "wpa_women")]
    men = [r["path"] for r in rows if (r["category"] or "").lower() in ("men", "wpa_men")]
    debbie = [
        r["path"]
        for r in rows
        if "debbie" in (r["contributor"] or "").lower() or "teichert" in (r["contributor"] or "").lower()
    ]

    if not women and not men:
        women = [r["path"] for r in rows]
    if not women:
        women = list(men) if men else []
    if not men:
        men = list(women) if women else []
    pool = women + men
    if not pool:
        return []

    out: List[str] = []
    for start in range(0, limit, debbie_every_n):
        window_size = min(debbie_every_n, limit - len(out))
        window: List[str] = []
        if debbie and window_size > 0:
            window.append(random.choice(debbie))
            window_size -= 1
        for _ in range(window_size):
            if random.random() < (women_weight / (women_weight + men_weight)) and women:
                window.append(random.choice(women))
            elif men:
                window.append(random.choice(men))
            elif women:
                window.append(random.choice(women))
        random.shuffle(window)
        out.extend(window)
    return out[:limit]


def count_media() -> int:
    from database import get_engine, get_database_manager
    engine = get_engine()
    _ensure_media_table(engine)
    db = get_database_manager()
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM media")
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else 0
