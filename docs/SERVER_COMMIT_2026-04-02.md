# Server worktree commit — 2026-04-02

Snapshot generated on the server immediately before `git add` / commit / push.
Purpose: document everything that was pending in the working tree for this repository.

## Branch tracking
## main...origin/main
 M .docker-build-hash
 M .env.example
 M .github/workflows/tests.yml
 M .gitignore
 M Dockerfile
 M EXTERNALPOOL_ANALYSIS.md
 M EXTERNALPOOL_SCRAPER_STATUS.md
 M EXTERNAL_POOL_INTEGRATION_COMPLETE.md
 M FRONTEND_REBUILD_GUIDE.md
 M LICENSE_RESEARCH_BY_ORG.md
 M LICENSE_RESEARCH_STRATEGY.md
 M PRODUCTION_DEPLOYMENT.md
 M QUICK_START_REFERENCE.md
 M REVIEW_AND_DEPLOY.md
 M SESSION_COMPLETION_SUMMARY.md
 M WEB_RESEARCH_FINDINGS.md
 M WPA_ARCHIVE_COMPLETE.md
 M api/cache.py
 M api/config/admin_config.py
 M api/main.py
 M api/middleware/feature_flags.py
 M api/models/ai_coach.py
 M api/models/pydantic_schemas.py
 M api/models/tournament_models.py
 M api/models/user.py
 M api/parsers/rankings_import.py
 M api/routes/admin.py
 M api/routes/admin_security.py
 M api/routes/ai_coach.py
 M api/routes/alfa_ratings.py
 M api/routes/auth.py
 M api/routes/backups.py
 M api/routes/csv_import.py
 M api/routes/health.py
 M api/routes/logs.py
 M api/routes/messages.py
 M api/routes/network.py
 M api/routes/player_performance.py
 M api/routes/rankings.py
 M api/routes/splash_v1.py
 M api/routes/tournament_history.py
 M api/routes/tournaments.py
 M api/routes/users.py
 M api/services/alfa_constants.py
 M api/services/alfa_engine.py
 M api/services/bulk_user_service.py
 M api/services/cache_store.py
 M api/services/celery_worker.py
 M api/services/email.py
 M api/services/fairmatch_scraper.py
 M api/services/fargo_handicap.py
 M api/services/fargo_name_variations.py
 M api/services/frame_storage.py
 M api/services/health_check.py
 M api/services/hometown_scraper.py
 M api/services/live_rating_engine.py
 M api/tournament_manager.py
 M api/utils/error_handling.py
 D data/externalpool_archive/digitalpool_archive_20260219_113955.json
 M database/__init__.py
 M database/enrichment_engine.py
 M database/postgres_manager.py
 M docker-compose-staging.yml
 M docker-compose.performance.yml
 M docker-compose.yml
 M docs/ALFA_SETUP_SCREENS_REFERENCE.md
 M docs/BAD_GATEWAY_TROUBLESHOOTING.md
 M docs/DOCKER_POSTGRES_ONLY.md
 M docs/ENV_VARS.md
 M docs/FARGO_RATING_GAPS.md
 M docs/FULL_DEPLOY_AND_ERRORS.md
 M docs/HOT_STREAK_CHANGES.md
 M docs/INDEX.md
 M docs/IOS_SWIFT_NEXT_STEPS.md
 M docs/LEAGUE_MANAGER.md
 M docs/MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md
 M docs/MONITORING_HEALTH.md
 M docs/MONITORING_SETUP_GUIDE.md
 M docs/PERFORMANCE_TUNING.md
 M docs/PRODUCTION_DEPLOYMENT.md
 M docs/PRODUCTION_READINESS.md
 M docs/RANKINGS_TABLE_DESIGN.md
 M docs/ROADMAP.md
 M docs/ROADMAP_LOWER_PRIORITY.md
 M docs/SCRAPING.md
 M docs/START_STOP_RESTART.md
 M docs/TEST_TOURNAMENT_MANUAL_PLAN.md
 M docs/TOURNAMENT_CLARIFICATIONS.md
 M docs/TOURNAMENT_HISTORY_SCRAPER.md
 M docs/TOURNAMENT_SCRAPER_IMPROVEMENTS.md
 M docs/screenshots/README.md
 D docs/screenshots/digitalpool/README.md
 D docs/screenshots/digitalpool/dp_01.png
 D docs/screenshots/digitalpool/dp_02.png
 D docs/screenshots/digitalpool/dp_03.png
 D docs/screenshots/digitalpool/dp_04.png
 D docs/screenshots/digitalpool/dp_05.png
 D docs/screenshots/digitalpool/dp_06.png
 D docs/screenshots/digitalpool/dp_07.png
 D docs/screenshots/digitalpool/dp_08.png
 D docs/screenshots/digitalpool/dp_09.png
 D docs/screenshots/digitalpool/dp_10.png
 D docs/screenshots/digitalpool/dp_11.png
 D docs/screenshots/digitalpool/dp_12.png
 D docs/screenshots/digitalpool/dp_13.png
 D docs/screenshots/digitalpool/dp_14.png
 D docs/screenshots/digitalpool/dp_15.png
 D docs/screenshots/digitalpool/dp_16.png
 D docs/screenshots/digitalpool/dp_17.png
 D docs/screenshots/digitalpool/dp_18.png
 D docs/screenshots/digitalpool/dp_19.png
 D docs/screenshots/digitalpool/dp_20.png
 D docs/screenshots/digitalpool/dp_21.png
 D docs/screenshots/digitalpool/dp_22.png
 D docs/screenshots/digitalpool/dp_23.png
 D docs/screenshots/digitalpool/dp_24.png
 D docs/screenshots/digitalpool/dp_25.png
 D docs/screenshots/digitalpool/dp_26.png
 D docs/screenshots/digitalpool/dp_27.png
 D docs/screenshots/digitalpool/dp_28.png
 D docs/screenshots/digitalpool/dp_29.png
 D docs/screenshots/digitalpool/dp_extra_01.png
 D docs/screenshots/digitalpool/dp_extra_02.png
 D docs/screenshots/digitalpool/dp_extra_03.png
 D docs/screenshots/digitalpool/dp_extra_04.png
 D docs/screenshots/digitalpool/dp_extra_05.png
 D docs/screenshots/digitalpool/dp_extra_06.png
 D docs/screenshots/digitalpool/dp_extra_07.png
 D docs/screenshots/digitalpool/dp_extra_08.png
 D docs/screenshots/digitalpool/dp_extra_09.png
 D docs/screenshots/digitalpool/dp_extra_10.png
 D docs/screenshots/digitalpool/dp_extra_11.png
 D docs/screenshots/digitalpool/dp_extra_12.png
 D docs/screenshots/digitalpool/dp_extra_13.png
 D docs/screenshots/digitalpool/dp_extra_14.png
 D docs/screenshots/digitalpool/dp_extra_15.png
 D docs/screenshots/digitalpool/dp_extra_16.png
 D docs/screenshots/digitalpool/dp_extra_17.png
 D docs/screenshots/digitalpool/dp_extra_18.png
 D docs/screenshots/digitalpool/dp_extra_19.png
 D docs/screenshots/digitalpool/dp_extra_20.png
 M frontend/Dockerfile
 M frontend/nginx.conf
 M frontend/src/App.tsx
 M frontend/src/__tests__/pages/TournamentHistory.test.tsx
 M frontend/src/api/admin.ts
 M frontend/src/api/auth.ts
 M frontend/src/api/client.ts
 M frontend/src/api/loginFeatures.ts
 M frontend/src/api/logs.ts
 M frontend/src/api/rankings.ts
 M frontend/src/api/tournamentHistory.ts
 M frontend/src/api/tournaments.ts
 M frontend/src/api/users.ts
 M frontend/src/components/ErrorBoundary.tsx
 M frontend/src/components/RankingsTable.tsx
 M frontend/src/components/Sidebar.tsx
 M frontend/src/contexts/AuthContext.tsx
 M frontend/src/features/admin/components/LoginAttemptsMonitor.tsx
 M frontend/src/features/admin/pages/HealthDashboard.tsx
 M frontend/src/hooks/useLiveUpdates.ts
 M frontend/src/pages/FutureTournaments.tsx
 M frontend/src/pages/HotStreak.tsx
 M frontend/src/pages/Leaderboard.tsx
 M frontend/src/pages/PlayerPerformance.tsx
 M frontend/src/pages/Rankings.tsx
 M frontend/src/pages/SettingsAdmin.tsx
 M frontend/src/pages/SettingsLayout.tsx
 M frontend/src/pages/System.tsx
 M frontend/src/pages/TournamentHistory.tsx
 M index.js
 M internet_access_control.py
 M master-control.md
 M nginx-config/docker-compose.nginx.yml
 M nginx-config/rankings-bot-maintenance.conf
 M production/docker-compose.prod.yml
 M requirements.txt
 M scrapers/base_scraper.py
 D scrapers/digital_pool_scraper.py
 M scrapers/externalpool_scraper.py
 M scrapers/fetch_utils.py
 M scrapers/multi_type_rankings_scraper.py
 M scrapers/org_metadata_scraper.py
 M scrapers/tournament_bracket_parser.py
 M scrapers/tournament_history_discovery.py
 M scrapers/wpa_scraper.py
 M scrapers/wpba_scraper.py
 M scripts/alfa_rating_data_prep.py
 M scripts/archive/README.md
A  scripts/cleanup_docker_disk.sh
 M scripts/full_deploy.sh
 M scripts/import_fargo_csv.py
 M scripts/phase1_license_lookup.py
 M scripts/rebuild_api.sh
 M scripts/refresh_rankings.py
 M scripts/restart_api.sh
 M scripts/run_all_scrapers.py
 M scripts/scrape_bracket_data.py
 M scripts/scrape_browser_based.py
 M scripts/scrape_enhanced.py
 M scripts/scrape_externalpool_selenium.py
 M scripts/start.sh
 M scripts/start_web.sh
 M scripts/stop.sh
 M scripts/switch-site.sh
 M scripts/test_live_rating_engine.py
 D test_ai_coach_endpoints.py
 D test_digital_pool_integration.py
 D test_grok_client.py
 M test_license_matching.py
 M tests/backend/test_api_http.py
 M tests/backend/test_database.py
 M tests/backend/test_fetch_utils_stale_fallback.py
 M tests/backend/test_scrapers.py
 M tests/backend/test_tournaments_more.py
 D tests/test_ai_coach_endpoints.py
?? .cursor/rules/no-container-workarounds-drift-guard.mdc
?? .cursor/rules/no-workarounds.mdc
?? .github/workflows/ci-grok-suggest-fix.yml
?? Gemfile
?? alembic/versions/043_add_audit_log_created_at.py
?? alembic/versions/044_allow_dynamic_wpba_tournament_systems.py
?? alembic/versions/045_add_user_associations.py
?? alembic/versions/046_users_columns_idempotent_repair.py
?? alembic/versions/047_audit_log_auth_columns.py
?? alembic/versions/048_tournament_results_stops_played.py
?? alembic/versions/049_association_rankings_tables.py
?? alembic/versions/050_ollama_activity_log.py
?? android/
?? api/middleware/prometheus.py
?? api/routes/admin_dev_tools.py
?? api/routes/metrics.py
?? api/services/admin_dev_tools_service.py
?? api/services/ci_failure_suggestion.py
?? api/services/ollama_activity_log.py
?? api/services/ollama_client.py
?? api/services/ollama_extractor.py
?? api/services/ollama_name_resolver.py
?? api/services/ollama_narratives.py
?? config/.internet_access
?? data/externalpool_archive/externalpool_archive_20260219_113955.json
?? docs/10_TOURNAMENT_RULE.md
?? docs/BACKUP_AND_RECOVERY.md
?? docs/CI_GROK_SUGGEST.md
?? docs/CODE_QUALITY_AUDIT.md
?? docs/CONTAINER_DRIFT_PREVENTION.md
?? docs/DOCKER_DISK_CLEANUP.md
?? docs/IOS_PURE_REACT_NATIVE_SETUP.md
?? docs/MONITORING_RANKINGS_BOT.md
?? docs/OLLAMA_AND_AI_MONITOR.md
?? docs/SERVER_COMMIT_2026-04-02.md
?? docs/WPBA_DATA_FLOW.md
?? docs/screenshots/externalpool/
?? frontend/src/api/adminDevTools.ts
?? frontend/src/components/EmailSetup.tsx
?? frontend/src/components/TournamentSourceTabs.tsx
?? frontend/src/pages/SettingsAIDevTools.tsx
?? frontend/src/pages/SettingsAIMonitor.tsx
?? ios/
?? monitoring/grafana/dashboards/rankings_bot_api.json
?? monitoring/grafana/dashboards/rankings_bot_overview.json
?? monitoring/grafana/provisioning/
?? monitoring/prometheus/rankings_alerts.yml
?? monitoring/prometheus/rankings_prometheus.yml
?? scraped_data/
?? scrapers/externalpool_tournament_harvester.py
?? scrapers/fargo_rankings_scraper.py
?? scrapers/wpa_artistic_scraper.py
?? scrapers/wpa_heyball_men_scraper.py
?? scrapers/wpa_heyball_women_scraper.py
?? scrapers/wpa_men_scraper.py
?? scrapers/wpa_women_scraper.py
?? scrapers/wpba_pdf_columns.py
?? scrapers/wpba_rankings_scraper.py
?? scripts/archive/start_legacy.sh
?? scripts/build_frontend_with_docker.sh
?? scripts/bulk_create_fargo_accounts.py
?? scripts/ci_grok_suggest_fix.py
?? scripts/clean_frontend_dist.sh
?? scripts/export_compose_uid_gid.sh
?? scripts/extract_fargo_player_names.py
?? scripts/load_wpba_pdf_local.py
?? scripts/restore_from_nas.sh
?? scripts/scrape_externalpool_tournaments.py
?? scripts/sync_to_nas.sh
?? scripts/verify_user_email.py
?? test_external_pool_integration.py
?? tests/backend/test_compliance_guardrails.py
?? tests/backend/test_externalpool_harvester.py
?? tests/backend/test_wpba_pdf_columns.py

## Unstaged/staged diff stat (before `git add`)
 .docker-build-hash                                 |    2 +-
 .env.example                                       |    5 +
 .github/workflows/tests.yml                        |   63 +-
 .gitignore                                         |   12 +
 Dockerfile                                         |    9 +
 EXTERNALPOOL_ANALYSIS.md                           |   50 +-
 EXTERNALPOOL_SCRAPER_STATUS.md                     |   34 +-
 EXTERNAL_POOL_INTEGRATION_COMPLETE.md              |    2 +-
 FRONTEND_REBUILD_GUIDE.md                          |    2 +-
 LICENSE_RESEARCH_BY_ORG.md                         |    2 +-
 LICENSE_RESEARCH_STRATEGY.md                       |   16 +-
 PRODUCTION_DEPLOYMENT.md                           |    2 +-
 QUICK_START_REFERENCE.md                           |   28 +-
 REVIEW_AND_DEPLOY.md                               |    1 -
 SESSION_COMPLETION_SUMMARY.md                      |   50 +-
 WEB_RESEARCH_FINDINGS.md                           |   10 +-
 WPA_ARCHIVE_COMPLETE.md                            |    4 +-
 api/cache.py                                       |    2 +-
 api/config/admin_config.py                         |    4 +-
 api/main.py                                        |   21 +-
 api/middleware/feature_flags.py                    |    5 +-
 api/models/ai_coach.py                             |    2 +-
 api/models/pydantic_schemas.py                     |    1 +
 api/models/tournament_models.py                    |   75 +-
 api/models/user.py                                 |    2 +
 api/parsers/rankings_import.py                     |    4 +-
 api/routes/admin.py                                |   77 +-
 api/routes/admin_security.py                       |  194 +-
 api/routes/ai_coach.py                             |  105 ++
 api/routes/alfa_ratings.py                         |   32 +-
 api/routes/auth.py                                 |  184 +-
 api/routes/backups.py                              |    3 +-
 api/routes/csv_import.py                           |    2 +-
 api/routes/health.py                               |   45 +-
 api/routes/logs.py                                 |  137 +-
 api/routes/messages.py                             |   28 +-
 api/routes/network.py                              |    6 +-
 api/routes/player_performance.py                   |  223 ++-
 api/routes/rankings.py                             |  342 +++-
 api/routes/splash_v1.py                            |    2 +-
 api/routes/tournament_history.py                   |   12 +-
 api/routes/tournaments.py                          |  144 +-
 api/routes/users.py                                |  124 +-
 api/services/alfa_constants.py                     |    2 +-
 api/services/alfa_engine.py                        |    2 +-
 api/services/bulk_user_service.py                  |   78 +-
 api/services/cache_store.py                        |    2 +-
 api/services/celery_worker.py                      |  110 ++
 api/services/email.py                              |    3 +-
 api/services/fairmatch_scraper.py                  |    4 +-
 api/services/fargo_handicap.py                     |    4 +-
 api/services/fargo_name_variations.py              |    6 +-
 api/services/frame_storage.py                      |   22 +-
 api/services/health_check.py                       |   43 +
 api/services/hometown_scraper.py                   |    2 +-
 api/services/live_rating_engine.py                 |    8 +-
 api/tournament_manager.py                          |    5 +-
 api/utils/error_handling.py                        |   10 +-
 .../digitalpool_archive_20260219_113955.json       |   12 -
 database/__init__.py                               |   10 +-
 database/enrichment_engine.py                      |   34 +-
 database/postgres_manager.py                       | 1850 ++++++++++++++++++--
 docker-compose-staging.yml                         |    4 +
 docker-compose.performance.yml                     |    2 +
 docker-compose.yml                                 |  150 +-
 docs/ALFA_SETUP_SCREENS_REFERENCE.md               |   12 +-
 docs/BAD_GATEWAY_TROUBLESHOOTING.md                |    2 +-
 docs/DOCKER_POSTGRES_ONLY.md                       |   13 +-
 docs/ENV_VARS.md                                   |   55 +-
 docs/FARGO_RATING_GAPS.md                          |    2 +-
 docs/FULL_DEPLOY_AND_ERRORS.md                     |    2 +-
 docs/HOT_STREAK_CHANGES.md                         |   41 +
 docs/INDEX.md                                      |   18 +-
 docs/IOS_SWIFT_NEXT_STEPS.md                       |    2 +-
 docs/LEAGUE_MANAGER.md                             |    6 +-
 docs/MAINTENANCE_PAGE_AND_DEMO_WORKFLOW.md         |   13 +-
 docs/MONITORING_HEALTH.md                          |   33 +
 docs/MONITORING_SETUP_GUIDE.md                     |   25 +
 docs/PERFORMANCE_TUNING.md                         |    6 +-
 docs/PRODUCTION_DEPLOYMENT.md                      |   84 +-
 docs/PRODUCTION_READINESS.md                       |    6 +-
 docs/RANKINGS_TABLE_DESIGN.md                      |    2 +-
 docs/ROADMAP.md                                    |  106 +-
 docs/ROADMAP_LOWER_PRIORITY.md                     |    4 +-
 docs/SCRAPING.md                                   |  145 +-
 docs/START_STOP_RESTART.md                         |   83 +-
 docs/TEST_TOURNAMENT_MANUAL_PLAN.md                |    6 +-
 docs/TOURNAMENT_CLARIFICATIONS.md                  |    4 +-
 docs/TOURNAMENT_HISTORY_SCRAPER.md                 |   10 +-
 docs/TOURNAMENT_SCRAPER_IMPROVEMENTS.md            |    2 +-
 docs/screenshots/README.md                         |    4 +-
 docs/screenshots/digitalpool/README.md             |   32 -
 docs/screenshots/digitalpool/dp_01.png             |  Bin 311261 -> 0 bytes
 docs/screenshots/digitalpool/dp_02.png             |  Bin 376733 -> 0 bytes
 docs/screenshots/digitalpool/dp_03.png             |  Bin 288086 -> 0 bytes
 docs/screenshots/digitalpool/dp_04.png             |  Bin 280137 -> 0 bytes
 docs/screenshots/digitalpool/dp_05.png             |  Bin 262672 -> 0 bytes
 docs/screenshots/digitalpool/dp_06.png             |  Bin 288586 -> 0 bytes
 docs/screenshots/digitalpool/dp_07.png             |  Bin 274357 -> 0 bytes
 docs/screenshots/digitalpool/dp_08.png             |  Bin 272752 -> 0 bytes
 docs/screenshots/digitalpool/dp_09.png             |  Bin 101224 -> 0 bytes
 docs/screenshots/digitalpool/dp_10.png             |  Bin 297423 -> 0 bytes
 docs/screenshots/digitalpool/dp_11.png             |  Bin 291224 -> 0 bytes
 docs/screenshots/digitalpool/dp_12.png             |  Bin 292240 -> 0 bytes
 docs/screenshots/digitalpool/dp_13.png             |  Bin 260181 -> 0 bytes
 docs/screenshots/digitalpool/dp_14.png             |  Bin 345646 -> 0 bytes
 docs/screenshots/digitalpool/dp_15.png             |  Bin 291019 -> 0 bytes
 docs/screenshots/digitalpool/dp_16.png             |  Bin 278957 -> 0 bytes
 docs/screenshots/digitalpool/dp_17.png             |  Bin 308442 -> 0 bytes
 docs/screenshots/digitalpool/dp_18.png             |  Bin 296722 -> 0 bytes
 docs/screenshots/digitalpool/dp_19.png             |  Bin 277037 -> 0 bytes
 docs/screenshots/digitalpool/dp_20.png             |  Bin 306001 -> 0 bytes
 docs/screenshots/digitalpool/dp_21.png             |  Bin 273803 -> 0 bytes
 docs/screenshots/digitalpool/dp_22.png             |  Bin 265992 -> 0 bytes
 docs/screenshots/digitalpool/dp_23.png             |  Bin 280991 -> 0 bytes
 docs/screenshots/digitalpool/dp_24.png             |  Bin 348849 -> 0 bytes
 docs/screenshots/digitalpool/dp_25.png             |  Bin 332922 -> 0 bytes
 docs/screenshots/digitalpool/dp_26.png             |  Bin 298522 -> 0 bytes
 docs/screenshots/digitalpool/dp_27.png             |  Bin 282885 -> 0 bytes
 docs/screenshots/digitalpool/dp_28.png             |  Bin 270681 -> 0 bytes
 docs/screenshots/digitalpool/dp_29.png             |  Bin 271477 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_01.png       |  Bin 428754 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_02.png       |  Bin 428754 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_03.png       |  Bin 670947 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_04.png       |  Bin 670947 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_05.png       |  Bin 708657 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_06.png       |  Bin 532814 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_07.png       |  Bin 532814 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_08.png       |  Bin 440872 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_09.png       |  Bin 440872 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_10.png       |  Bin 663308 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_11.png       |  Bin 809867 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_12.png       |  Bin 836662 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_13.png       |  Bin 512749 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_14.png       |  Bin 512749 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_15.png       |  Bin 579638 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_16.png       |  Bin 579638 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_17.png       |  Bin 613322 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_18.png       |  Bin 613322 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_19.png       |  Bin 652735 -> 0 bytes
 docs/screenshots/digitalpool/dp_extra_20.png       |  Bin 652735 -> 0 bytes
 frontend/Dockerfile                                |   19 +-
 frontend/nginx.conf                                |   17 +-
 frontend/src/App.tsx                               |   33 +-
 .../src/__tests__/pages/TournamentHistory.test.tsx |   15 +-
 frontend/src/api/admin.ts                          |   30 +-
 frontend/src/api/auth.ts                           |   13 +-
 frontend/src/api/client.ts                         |   34 +-
 frontend/src/api/loginFeatures.ts                  |   47 -
 frontend/src/api/logs.ts                           |   16 +-
 frontend/src/api/rankings.ts                       |   59 +-
 frontend/src/api/tournamentHistory.ts              |    2 +-
 frontend/src/api/tournaments.ts                    |  113 +-
 frontend/src/api/users.ts                          |    8 +
 frontend/src/components/ErrorBoundary.tsx          |   12 +-
 frontend/src/components/RankingsTable.tsx          |    1 +
 frontend/src/components/Sidebar.tsx                |    6 +-
 frontend/src/contexts/AuthContext.tsx              |   35 +-
 .../admin/components/LoginAttemptsMonitor.tsx      |   20 +-
 .../src/features/admin/pages/HealthDashboard.tsx   |   64 +
 frontend/src/hooks/useLiveUpdates.ts               |    2 +-
 frontend/src/pages/FutureTournaments.tsx           |    2 +-
 frontend/src/pages/HotStreak.tsx                   |  270 ++-
 frontend/src/pages/Leaderboard.tsx                 |   96 +-
 frontend/src/pages/PlayerPerformance.tsx           |  187 ++
 frontend/src/pages/Rankings.tsx                    |   78 +-
 frontend/src/pages/SettingsAdmin.tsx               |  242 ++-
 frontend/src/pages/SettingsLayout.tsx              |   14 +-
 frontend/src/pages/System.tsx                      |  163 +-
 frontend/src/pages/TournamentHistory.tsx           |  390 ++++-
 index.js                                           |    2 +-
 internet_access_control.py                         |   18 +
 master-control.md                                  |    2 +-
 nginx-config/docker-compose.nginx.yml              |    2 +
 nginx-config/rankings-bot-maintenance.conf         |   53 +
 production/docker-compose.prod.yml                 |  200 ++-
 requirements.txt                                   |    1 +
 scrapers/base_scraper.py                           |    2 +-
 scrapers/digital_pool_scraper.py                   |  268 ---
 scrapers/externalpool_scraper.py                   |  915 +++-------
 scrapers/fetch_utils.py                            |   14 +-
 scrapers/multi_type_rankings_scraper.py            |   90 +-
 scrapers/org_metadata_scraper.py                   |   41 +-
 scrapers/tournament_bracket_parser.py              |   51 +-
 scrapers/tournament_history_discovery.py           |   12 +-
 scrapers/wpa_scraper.py                            |   32 +-
 scrapers/wpba_scraper.py                           |  415 ++++-
 scripts/alfa_rating_data_prep.py                   |    3 +-
 scripts/archive/README.md                          |   19 +-
 scripts/cleanup_docker_disk.sh                     |  113 ++
 scripts/full_deploy.sh                             |  127 +-
 scripts/import_fargo_csv.py                        |    4 +-
 scripts/phase1_license_lookup.py                   |    4 +-
 scripts/rebuild_api.sh                             |   10 +-
 scripts/refresh_rankings.py                        |  178 +-
 scripts/restart_api.sh                             |    8 +
 scripts/run_all_scrapers.py                        |    2 +-
 scripts/scrape_bracket_data.py                     |    8 +-
 scripts/scrape_browser_based.py                    |    6 +-
 scripts/scrape_enhanced.py                         |    4 +-
 scripts/scrape_externalpool_selenium.py            |    4 +-
 scripts/start.sh                                   |   12 +-
 scripts/start_web.sh                               |    3 +-
 scripts/stop.sh                                    |   21 +-
 scripts/switch-site.sh                             |    2 +-
 scripts/test_live_rating_engine.py                 |    5 +-
 test_ai_coach_endpoints.py                         |  729 --------
 test_digital_pool_integration.py                   |  445 -----
 test_grok_client.py                                |  119 --
 test_license_matching.py                           |    6 +-
 tests/backend/test_api_http.py                     |   78 +-
 tests/backend/test_database.py                     |  680 +++++++
 tests/backend/test_fetch_utils_stale_fallback.py   |   12 +-
 tests/backend/test_scrapers.py                     |   24 +
 tests/backend/test_tournaments_more.py             |   20 +-
 tests/test_ai_coach_endpoints.py                   |  142 --
 216 files changed, 8363 insertions(+), 3680 deletions(-)
 scripts/cleanup_docker_disk.sh | 113 +++++++++++++++++++++++++++++++++++++++++
 1 file changed, 113 insertions(+)

## Untracked files (first 400 lines)
.cursor/rules/no-container-workarounds-drift-guard.mdc
.cursor/rules/no-workarounds.mdc
.github/workflows/ci-grok-suggest-fix.yml
Gemfile
alembic/versions/043_add_audit_log_created_at.py
alembic/versions/044_allow_dynamic_wpba_tournament_systems.py
alembic/versions/045_add_user_associations.py
alembic/versions/046_users_columns_idempotent_repair.py
alembic/versions/047_audit_log_auth_columns.py
alembic/versions/048_tournament_results_stops_played.py
alembic/versions/049_association_rankings_tables.py
alembic/versions/050_ollama_activity_log.py
android/app/build.gradle
android/app/debug.keystore
android/app/proguard-rules.pro
android/app/src/main/AndroidManifest.xml
android/app/src/main/java/com/rankingsbot/MainActivity.kt
android/app/src/main/java/com/rankingsbot/MainApplication.kt
android/app/src/main/res/drawable/rn_edit_text_material.xml
android/app/src/main/res/mipmap-hdpi/ic_launcher.png
android/app/src/main/res/mipmap-hdpi/ic_launcher_round.png
android/app/src/main/res/mipmap-mdpi/ic_launcher.png
android/app/src/main/res/mipmap-mdpi/ic_launcher_round.png
android/app/src/main/res/mipmap-xhdpi/ic_launcher.png
android/app/src/main/res/mipmap-xhdpi/ic_launcher_round.png
android/app/src/main/res/mipmap-xxhdpi/ic_launcher.png
android/app/src/main/res/mipmap-xxhdpi/ic_launcher_round.png
android/app/src/main/res/mipmap-xxxhdpi/ic_launcher.png
android/app/src/main/res/mipmap-xxxhdpi/ic_launcher_round.png
android/app/src/main/res/values/strings.xml
android/app/src/main/res/values/styles.xml
android/build.gradle
android/gradle.properties
android/gradle/wrapper/gradle-wrapper.jar
android/gradle/wrapper/gradle-wrapper.properties
android/gradlew
android/gradlew.bat
android/settings.gradle
api/middleware/prometheus.py
api/routes/admin_dev_tools.py
api/routes/metrics.py
api/services/admin_dev_tools_service.py
api/services/ci_failure_suggestion.py
api/services/ollama_activity_log.py
api/services/ollama_client.py
api/services/ollama_extractor.py
api/services/ollama_name_resolver.py
api/services/ollama_narratives.py
config/.internet_access
data/externalpool_archive/externalpool_archive_20260219_113955.json
docs/10_TOURNAMENT_RULE.md
docs/BACKUP_AND_RECOVERY.md
docs/CI_GROK_SUGGEST.md
docs/CODE_QUALITY_AUDIT.md
docs/CONTAINER_DRIFT_PREVENTION.md
docs/DOCKER_DISK_CLEANUP.md
docs/IOS_PURE_REACT_NATIVE_SETUP.md
docs/MONITORING_RANKINGS_BOT.md
docs/OLLAMA_AND_AI_MONITOR.md
docs/SERVER_COMMIT_2026-04-02.md
docs/WPBA_DATA_FLOW.md
docs/screenshots/externalpool/README.md
docs/screenshots/externalpool/dp_01.png
docs/screenshots/externalpool/dp_02.png
docs/screenshots/externalpool/dp_03.png
docs/screenshots/externalpool/dp_04.png
docs/screenshots/externalpool/dp_05.png
docs/screenshots/externalpool/dp_06.png
docs/screenshots/externalpool/dp_07.png
docs/screenshots/externalpool/dp_08.png
docs/screenshots/externalpool/dp_09.png
docs/screenshots/externalpool/dp_10.png
docs/screenshots/externalpool/dp_11.png
docs/screenshots/externalpool/dp_12.png
docs/screenshots/externalpool/dp_13.png
docs/screenshots/externalpool/dp_14.png
docs/screenshots/externalpool/dp_15.png
docs/screenshots/externalpool/dp_16.png
docs/screenshots/externalpool/dp_17.png
docs/screenshots/externalpool/dp_18.png
docs/screenshots/externalpool/dp_19.png
docs/screenshots/externalpool/dp_20.png
docs/screenshots/externalpool/dp_21.png
docs/screenshots/externalpool/dp_22.png
docs/screenshots/externalpool/dp_23.png
docs/screenshots/externalpool/dp_24.png
docs/screenshots/externalpool/dp_25.png
docs/screenshots/externalpool/dp_26.png
docs/screenshots/externalpool/dp_27.png
docs/screenshots/externalpool/dp_28.png
docs/screenshots/externalpool/dp_29.png
docs/screenshots/externalpool/dp_extra_01.png
docs/screenshots/externalpool/dp_extra_02.png
docs/screenshots/externalpool/dp_extra_03.png
docs/screenshots/externalpool/dp_extra_04.png
docs/screenshots/externalpool/dp_extra_05.png
docs/screenshots/externalpool/dp_extra_06.png
docs/screenshots/externalpool/dp_extra_07.png
docs/screenshots/externalpool/dp_extra_08.png
docs/screenshots/externalpool/dp_extra_09.png
docs/screenshots/externalpool/dp_extra_10.png
docs/screenshots/externalpool/dp_extra_11.png
docs/screenshots/externalpool/dp_extra_12.png
docs/screenshots/externalpool/dp_extra_13.png
docs/screenshots/externalpool/dp_extra_14.png
docs/screenshots/externalpool/dp_extra_15.png
docs/screenshots/externalpool/dp_extra_16.png
docs/screenshots/externalpool/dp_extra_17.png
docs/screenshots/externalpool/dp_extra_18.png
docs/screenshots/externalpool/dp_extra_19.png
docs/screenshots/externalpool/dp_extra_20.png
frontend/src/api/adminDevTools.ts
frontend/src/components/EmailSetup.tsx
frontend/src/components/TournamentSourceTabs.tsx
frontend/src/pages/SettingsAIDevTools.tsx
frontend/src/pages/SettingsAIMonitor.tsx
ios/.xcode.env
ios/Podfile
ios/RankingsBot.xcodeproj/project.pbxproj
ios/RankingsBot.xcodeproj/xcshareddata/xcschemes/RankingsBot.xcscheme
ios/RankingsBot/AppDelegate.swift
ios/RankingsBot/Images.xcassets/AppIcon.appiconset/Contents.json
ios/RankingsBot/Images.xcassets/Contents.json
ios/RankingsBot/Info.plist
ios/RankingsBot/LaunchScreen.storyboard
ios/RankingsBot/PrivacyInfo.xcprivacy
monitoring/grafana/dashboards/rankings_bot_api.json
monitoring/grafana/dashboards/rankings_bot_overview.json
monitoring/grafana/provisioning/dashboards/default.yml
monitoring/grafana/provisioning/datasources/prometheus.yml
monitoring/prometheus/rankings_alerts.yml
monitoring/prometheus/rankings_prometheus.yml
scraped_data/wpba/wpba_rankings_20260317_152308.json
scraped_data/wpba/wpba_rankings_20260317_203527.json
scraped_data/wpba/wpba_rankings_20260317_203717.json
scraped_data/wpba/wpba_rankings_20260317_203817.json
scraped_data/wpba/wpba_rankings_20260318_093712.json
scraped_data/wpba/wpba_rankings_20260318_103959.json
scraped_data/wpba/wpba_rankings_20260320_114511.json
scraped_data/wpba/wpba_rankings_20260323_104308.json
scraped_data/wpba/wpba_rankings_20260327_075722.json
scraped_data/wpba/wpba_rankings_20260327_200821.json
scraped_data/wpba/wpba_rankings_20260327_201441.json
scraped_data/wpba/wpba_rankings_20260327_201505.json
scrapers/externalpool_tournament_harvester.py
scrapers/fargo_rankings_scraper.py
scrapers/wpa_artistic_scraper.py
scrapers/wpa_heyball_men_scraper.py
scrapers/wpa_heyball_women_scraper.py
scrapers/wpa_men_scraper.py
scrapers/wpa_women_scraper.py
scrapers/wpba_pdf_columns.py
scrapers/wpba_rankings_scraper.py
scripts/archive/start_legacy.sh
scripts/build_frontend_with_docker.sh
scripts/bulk_create_fargo_accounts.py
scripts/ci_grok_suggest_fix.py
scripts/clean_frontend_dist.sh
scripts/export_compose_uid_gid.sh
scripts/extract_fargo_player_names.py
scripts/load_wpba_pdf_local.py
scripts/restore_from_nas.sh
scripts/scrape_externalpool_tournaments.py
scripts/sync_to_nas.sh
scripts/verify_user_email.py
test_external_pool_integration.py
tests/backend/test_compliance_guardrails.py
tests/backend/test_externalpool_harvester.py
tests/backend/test_wpba_pdf_columns.py

## Recent commits (last 5)
124875a WPBA 500 fix, duplicate column fix, Expo removal, pure React Native migration
4dab8d4 Merge branch 'main' of https://github.com/example-owner-s-Org/Rankings-Bot
fafb6d9 iOS Rankings integration, docs, and build fix
6f8feed chore: production hardening, script consolidation, Hot Streak, docs (Mar 15 2026)
50266be Fargo history, Player Performance Fargo chart, super-admin all players, View History for own player
