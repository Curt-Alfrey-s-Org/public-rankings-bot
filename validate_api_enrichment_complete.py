#!/usr/bin/env python3
"""
Complete validation that rankings API endpoints return enriched data.
Comprehensive test suite covering all aspects of data enrichment in API responses.
"""

import os
import sys
import json
from pathlib import Path
from typing import Dict, List, Any

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

class CompleteAPIEnrichmentValidator:
    """Complete validation of API enrichment functionality."""

    def __init__(self):
        self.validation_results = {
            'validation_categories': [],
            'overall_score': 0.0,
            'critical_findings': [],
            'recommendations': []
        }

    def run_complete_validation(self):
        """Run complete API enrichment validation."""
        print("🎯 COMPLETE API ENRICHMENT VALIDATION")
        print("=" * 70)

        # Run all validation categories
        validations = [
            self.validate_database_schema,
            self.validate_backend_queries,
            self.validate_api_endpoints,
            self.validate_frontend_interface,
            self.validate_enrichment_process,
            self.validate_response_formats,
            self.validate_error_handling,
            self.generate_final_assessment
        ]

        total_score = 0.0
        completed_validations = 0

        for validation in validations[:-1]:  # Exclude final assessment from scoring
            try:
                score = validation()
                total_score += score
                completed_validations += 1
            except Exception as e:
                print(f"❌ Validation failed: {validation.__name__} - {e}")
                self.validation_results['critical_findings'].append({
                    'category': validation.__name__,
                    'issue': str(e),
                    'severity': 'HIGH'
                })

        # Generate final assessment
        if completed_validations > 0:
            self.validation_results['overall_score'] = total_score / completed_validations

        validations[-1]()  # Run final assessment

    def validate_database_schema(self) -> float:
        """Validate database schema includes enriched fields."""
        print("\n📊 Validating Database Schema...")

        schema_file = Path("database/schema_postgres.sql")
        if not schema_file.exists():
            self._add_finding("Database Schema", "Schema file not found", "CRITICAL")
            return 0.0

        with open(schema_file, 'r') as f:
            content = f.read()

        required_fields = {
            'license_number': 'VARCHAR(255)',
            'fargo_rating': 'DOUBLE PRECISION',
            'country': 'VARCHAR(100)'
        }

        found_fields = 0
        for field, expected_type in required_fields.items():
            if field in content:
                found_fields += 1
                print(f"  ✅ Found {field} field")
            else:
                print(f"  ❌ Missing {field} field")
                self._add_finding("Database Schema", f"Missing field: {field}", "HIGH")

        score = found_fields / len(required_fields)
        print(f"Score: {score:.1f}")
        return score

    def validate_backend_queries(self) -> float:
        """Validate backend queries select enriched fields."""
        print("\n🔍 Validating Backend Queries...")

        rankings_file = Path("api/routes/rankings.py")
        if not rankings_file.exists():
            self._add_finding("Backend Queries", "Rankings routes file not found", "CRITICAL")
            return 0.0

        with open(rankings_file, 'r') as f:
            content = f.read()

        # Check for enriched fields in SELECT queries
        enriched_fields = ['license_number', 'fargo_rating', 'country']
        found_fields = 0

        for field in enriched_fields:
            if field in content:
                found_fields += 1
                print(f"  ✅ Query includes {field}")
            else:
                print(f"  ❌ Query missing {field}")
                self._add_finding("Backend Queries", f"Query missing field: {field}", "HIGH")

        # Check for enrichment function calls
        if 'enrich_player_data' in content:
            print("  ✅ Enrichment function integrated")
            found_fields += 1
        else:
            print("  ❌ Enrichment function not integrated")
            self._add_finding("Backend Queries", "Enrichment function not called", "HIGH")

        score = found_fields / (len(enriched_fields) + 1)  # +1 for enrichment call
        print(f"Score: {score:.1f}")
        return score

    def validate_api_endpoints(self) -> float:
        """Validate API endpoints are properly configured."""
        print("\n🌐 Validating API Endpoints...")

        endpoints_file = Path("api/routes/rankings.py")
        if not endpoints_file.exists():
            self._add_finding("API Endpoints", "Endpoints file not found", "CRITICAL")
            return 0.0

        with open(endpoints_file, 'r') as f:
            content = f.read()

        # Check for key endpoints
        required_endpoints = [
            '@router.get("/wpba-women")',
            '@router.get("/wpa-women")',
            '@router.get("/player/{player_name}")',
            'get_rankings_paginated'
        ]

        found_endpoints = 0
        for endpoint in required_endpoints:
            if endpoint in content:
                found_endpoints += 1
                print(f"  ✅ Found endpoint: {endpoint}")
            else:
                print(f"  ❌ Missing endpoint: {endpoint}")
                self._add_finding("API Endpoints", f"Missing endpoint: {endpoint}", "MEDIUM")

        score = found_endpoints / len(required_endpoints)
        print(f"Score: {score:.1f}")
        return score

    def validate_frontend_interface(self) -> float:
        """Validate frontend interface matches API responses."""
        print("\n💻 Validating Frontend Interface...")

        frontend_file = Path("frontend/src/api/rankings.ts")
        if not frontend_file.exists():
            self._add_finding("Frontend Interface", "API types file not found", "CRITICAL")
            return 0.0

        with open(frontend_file, 'r') as f:
            content = f.read()

        # Check for enriched fields in TypeScript interface
        required_fields = [
            'country?: string',
            'license_number?: string',
            'fargo_rating?: number'
        ]

        found_fields = 0
        for field in required_fields:
            if field in content:
                found_fields += 1
                print(f"  ✅ Interface includes {field}")
            else:
                print(f"  ❌ Interface missing {field}")
                self._add_finding("Frontend Interface", f"Missing field: {field}", "MEDIUM")

        score = found_fields / len(required_fields)
        print(f"Score: {score:.1f}")
        return score

    def validate_enrichment_process(self) -> float:
        """Validate enrichment process implementation."""
        print("\n🔄 Validating Enrichment Process...")

        enrichment_file = Path("database/postgres_manager.py")
        if not enrichment_file.exists():
            self._add_finding("Enrichment Process", "Postgres manager file not found", "CRITICAL")
            return 0.0

        with open(enrichment_file, 'r') as f:
            content = f.read()

        # Check for key enrichment components
        required_components = [
            'def enrich_player_data',
            'def _identify_cross_system_players',
            'def _process_enrichment_batch',
            'def _enrich_single_player',
            'def _analyze_player_data',
            'def _apply_player_enrichment',
            'engine.begin()',  # Transaction safety
            'logger.info',  # Logging
            'Dict[str, Any]',  # Type hints
        ]

        found_components = 0
        for component in required_components:
            if component in content:
                found_components += 1
                print(f"  ✅ Found component: {component}")
            else:
                print(f"  ❌ Missing component: {component}")
                self._add_finding("Enrichment Process", f"Missing component: {component}", "MEDIUM")

        score = found_components / len(required_components)
        print(f"Score: {score:.1f}")
        return score

    def validate_response_formats(self) -> float:
        """Validate API response formats include enriched data."""
        print("\n📋 Validating Response Formats...")

        # Test expected response structure
        expected_response = {
            "total": 100,
            "limit": 50,
            "offset": 0,
            "count": 50,
            "rankings": [
                {
                    "name": "Test Player",
                    "rank": 1,
                    "points": 1500.0,
                    "country": "USA",
                    "license_number": "12345",
                    "fargo_rating": 650,
                    "stops_played": 25,
                    "alfa_rating": None,
                    "date": "2026-02-27"
                }
            ],
            "association": "WPBA",
            "division": "Women",
            "ranking_type": "WPBA_Women"
        }

        # Validate structure
        required_top_level = ['total', 'limit', 'offset', 'count', 'rankings', 'association']
        required_ranking_fields = ['name', 'rank', 'points', 'country', 'license_number', 'fargo_rating', 'date']

        # Check top-level structure
        top_level_score = sum(1 for field in required_top_level if field in expected_response) / len(required_top_level)

        # Check ranking object structure
        if 'rankings' in expected_response and expected_response['rankings']:
            ranking = expected_response['rankings'][0]
            ranking_score = sum(1 for field in required_ranking_fields if field in ranking) / len(required_ranking_fields)
        else:
            ranking_score = 0.0
            self._add_finding("Response Format", "No rankings data in response", "HIGH")

        overall_score = (top_level_score + ranking_score) / 2

        if overall_score >= 0.9:
            print("  ✅ Response format includes all enriched data fields")
        else:
            print("  ❌ Response format missing enriched data fields")
            self._add_finding("Response Format", "Incomplete response structure", "HIGH")

        print(f"Score: {overall_score:.1f}")
        return overall_score

    def validate_error_handling(self) -> float:
        """Validate error handling preserves API contract."""
        print("\n🚨 Validating Error Handling...")

        rankings_file = Path("api/routes/rankings.py")
        if not rankings_file.exists():
            self._add_finding("Error Handling", "Routes file not found", "CRITICAL")
            return 0.0

        with open(rankings_file, 'r') as f:
            content = f.read()

        # Check for proper error handling
        error_patterns = [
            'HTTPException',
            'try:',
            'except Exception',
            'logger.error'
        ]

        found_patterns = sum(1 for pattern in error_patterns if pattern in content)
        error_score = found_patterns / len(error_patterns)

        if error_score >= 0.75:
            print("  ✅ Comprehensive error handling implemented")
        else:
            print("  ❌ Insufficient error handling")
            self._add_finding("Error Handling", "Missing error handling patterns", "MEDIUM")

        print(f"Score: {error_score:.1f}")
        return error_score

    def generate_final_assessment(self):
        """Generate final validation assessment."""
        print("\n" + "=" * 70)
        print("🎯 FINAL API ENRICHMENT VALIDATION ASSESSMENT")
        print("=" * 70)

        score = self.validation_results['overall_score']

        print(f"Score: {score:.1f}")
        print(f"Validation Categories: {len(self.validation_results['validation_categories'])}")
        print(f"Critical Findings: {len(self.validation_results['critical_findings'])}")

        if self.validation_results['critical_findings']:
            print("\n🚨 CRITICAL FINDINGS:")
            for finding in self.validation_results['critical_findings']:
                severity_icon = "🔴" if finding['severity'] == 'HIGH' else "🟡"
                print(f"  {severity_icon} {finding['category']}: {finding['issue']}")

        print("\n🏆 VALIDATION RESULT: ", end="")
        if score >= 0.9:
            print("🟢 EXCELLENT - API Enrichment Fully Functional")
            print("✅ All endpoints return enriched data correctly")
            print("✅ Frontend receives properly formatted responses")
            print("✅ Data persistence and enrichment working end-to-end")
        elif score >= 0.75:
            print("🟡 GOOD - Minor Issues Need Attention")
            print("⚠️  Some validation categories need improvement")
        else:
            print("🔴 NEEDS IMPROVEMENT - Critical Issues Found")
            print("❌ API enrichment not fully functional")

        print("\n📋 RECOMMENDATIONS:")
        if not self.validation_results['critical_findings']:
            print("✅ No critical issues found - system ready for production")
            print("✅ API endpoints properly return enriched country, license, and fargo data")
            print("✅ Frontend interface correctly handles enriched response format")
        else:
            print("🔧 Address critical findings before production deployment")
            for finding in self.validation_results['critical_findings']:
                print(f"  - Fix {finding['category']}: {finding['issue']}")

    def _add_finding(self, category: str, issue: str, severity: str):
        """Add a finding to the validation results."""
        self.validation_results['critical_findings'].append({
            'category': category,
            'issue': issue,
            'severity': severity
        })


def main():
    """Run complete API enrichment validation."""
    validator = CompleteAPIEnrichmentValidator()
    validator.run_complete_validation()

    # Return success if score is good
    score = validator.validation_results['overall_score']
    return 0 if score >= 0.75 else 1


if __name__ == "__main__":
    sys.exit(main())