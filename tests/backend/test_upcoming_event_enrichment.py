"""Unit tests for upcoming event enrichment from news/calendar text."""

from api.services.upcoming_event_enrichment import (
    enrich_upcoming_events,
    extract_elimination_type,
    extract_player_count,
    parse_format_field,
    _match_score,
)


def test_extract_player_count_from_news_phrasing():
    assert extract_player_count("Field expands to 64 players for the main draw") == 64
    assert extract_player_count("128-player bracket announced") == 128
    assert extract_player_count("No field size yet") is None


def test_extract_elimination_type():
    assert extract_elimination_type("Double elimination format") == "double"
    assert extract_elimination_type("Single elim main event") == "single"


def test_parse_format_field():
    parsed = parse_format_field("64 Player Double Elimination")
    assert parsed["max_players"] == 64
    assert parsed["elimination_type"] == "double"


def test_match_score_requires_shared_tokens():
    assert _match_score("WPBA Southern Classic", "Southern Classic field set at 64") >= 0.35
    assert _match_score("WPBA Southern Classic", "Unrelated article about cues") == 0.0


def test_enrich_upcoming_events_without_network(monkeypatch):
    monkeypatch.setattr(
        "api.services.upcoming_event_enrichment.fetch_all_feeds_sync",
        lambda: [
            {
                "title": "Southern Classic draw set at 64 players",
                "url": "https://example.com/news/1",
                "source": "WPBA",
                "summary": "Double elimination main event.",
                "published": "",
            }
        ],
    )
    events = [
        {
            "name": "Southern Classic",
            "association": "WPBA",
            "format": None,
            "url": "https://example.com/event",
        }
    ]
    out = enrich_upcoming_events(events)
    assert out[0]["max_players"] == 64
    hints = out[0]["enrichment"]["hints"]
    assert any(h["field"] == "max_players" for h in hints)
    assert any(h["field"] == "elimination_type" for h in hints)
