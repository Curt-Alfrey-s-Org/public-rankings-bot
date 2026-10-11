"""
Intelligent Cross-System Data Enrichment Engine

This module provides smart data enrichment across ranking systems with:
- System relationship mapping
- Data source prioritization
- Conflict resolution logic
- Validation and quality checks
- Name normalization for cross-format matching (Last, First ↔ First Last)
"""

import logging
from typing import Dict, List, Optional, Set, Tuple, Any
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

# Import name normalization functions from Fargo client
try:
    from api.services.fargo_client import canonical_form, parse_name, names_match_fuzzy
    FARGO_CLIENT_AVAILABLE = True
except ImportError:
    FARGO_CLIENT_AVAILABLE = False
    logger.warning("Fargo client not available - name normalization disabled")

try:
    from api.services.ollama_name_resolver import resolve_name_match as _ollama_resolve_name
    _OLLAMA_RESOLVER_AVAILABLE = True
except ImportError:
    _OLLAMA_RESOLVER_AVAILABLE = False


class DataSource(Enum):
    """Enumeration of data sources by reliability priority"""
    OFFICIAL_API = 1      # Official FargoRate API (highest priority)
    COMPETITORS_POOL = 2  # CP data (high priority for fresh data)
    PRIMARY_SYSTEM = 3    # Player's primary ranking system
    RELATED_SYSTEM = 4    # Related ranking systems (same gender/type)
    EXTERNAL_SYSTEM = 5   # Unrelated systems (lowest priority)


class SystemRelationship(Enum):
    """Defines relationships between ranking systems"""
    IDENTICAL = 1         # Same organization and division
    RELATED = 2          # Same gender/sport type, different organizations
    CROSS_GENDER = 3     # Different gender, same sport
    UNRELATED = 4        # Completely different sports/organizations


@dataclass
class SystemMetadata:
    """Metadata for each ranking system"""
    code: str
    name: str
    gender: str  # 'men', 'women', 'mixed'
    sport_type: str  # 'pool', 'snooker', 'heyball', etc.
    organization: str  # 'WPBA', 'WPA', etc.
    region: str = 'global'  # 'global', 'regional', etc.


@dataclass
class DataField:
    """Metadata for data fields that can be enriched"""
    name: str
    description: str
    shareable: bool  # Can this data be shared across systems?
    priority_sources: List[DataSource]  # Preferred sources in priority order
    validation_rules: Dict[str, Any] = None


class EnrichmentEngine:
    """Intelligent cross-system data enrichment engine"""

    def __init__(self):
        self.systems = self._load_system_metadata()
        self.fields = self._load_field_definitions()
        self.relationships = self._build_relationship_matrix()

    def _load_system_metadata(self) -> Dict[str, SystemMetadata]:
        """Load metadata for all ranking systems"""
        return {
            'WPBA_Women': SystemMetadata(
                code='WPBA_Women',
                name='WPBA Women',
                gender='women',
                sport_type='pool',
                organization='WPBA'
            ),
            'WPA_Women': SystemMetadata(
                code='WPA_Women',
                name='WPA Women',
                gender='women',
                sport_type='pool',
                organization='WPA'
            ),
            'WPA_Men': SystemMetadata(
                code='WPA_Men',
                name='WPA Men',
                gender='men',
                sport_type='pool',
                organization='WPA'
            ),
            'WPA_Heyball_Men': SystemMetadata(
                code='WPA_Heyball_Men',
                name='WPA Heyball Men',
                gender='men',
                sport_type='heyball',
                organization='WPA'
            ),
            'WPA_Heyball_Women': SystemMetadata(
                code='WPA_Heyball_Women',
                name='WPA Heyball Women',
                gender='women',
                sport_type='heyball',
                organization='WPA'
            ),
            # CP (External Pool) systems
            'Competitors_Pool_9Ball': SystemMetadata(
                code='Competitors_Pool_9Ball',
                name='CP 9-Ball Overall',
                gender='mixed',
                sport_type='external_pool',
                organization='CP'
            ),
            'Competitors_Pool_10Ball': SystemMetadata(
                code='Competitors_Pool_10Ball',
                name='CP 10-Ball Overall',
                gender='mixed',
                sport_type='external_pool',
                organization='CP'
            ),
            'Competitors_Pool_8Ball': SystemMetadata(
                code='Competitors_Pool_8Ball',
                name='CP 8-Ball Overall',
                gender='mixed',
                sport_type='external_pool',
                organization='CP'
            ),
            'Competitors_Pool_StraitPool': SystemMetadata(
                code='Competitors_Pool_StraitPool',
                name='CP Straight Pool',
                gender='mixed',
                sport_type='external_pool',
                organization='CP'
            ),
            'Competitors_Pool_OnePocket': SystemMetadata(
                code='Competitors_Pool_OnePocket',
                name='CP One Pocket',
                gender='mixed',
                sport_type='external_pool',
                organization='CP'
            ),
            'Competitors_Pool_BankPool': SystemMetadata(
                code='Competitors_Pool_BankPool',
                name='CP Bank Pool',
                gender='mixed',
                sport_type='external_pool',
                organization='CP'
            ),
            'Competitors_Pool_Women_9Ball': SystemMetadata(
                code='Competitors_Pool_Women_9Ball',
                name='CP 9-Ball Women',
                gender='women',
                sport_type='external_pool',
                organization='CP'
            ),
            'Competitors_Pool_Men_9Ball': SystemMetadata(
                code='Competitors_Pool_Men_9Ball',
                name='CP 9-Ball Men',
                gender='men',
                sport_type='external_pool',
                organization='CP'
            ),
            'Competitors_Pool_Mixed_9Ball': SystemMetadata(
                code='Competitors_Pool_Mixed_9Ball',
                name='CP 9-Ball Mixed',
                gender='mixed',
                sport_type='external_pool',
                organization='CP'
            )
        }

    def _load_field_definitions(self) -> Dict[str, DataField]:
        """Load definitions for enrichable data fields"""
        return {
            'license_number': DataField(
                name='license_number',
                description='Official player license number',
                shareable=True,
                priority_sources=[
                    DataSource.PRIMARY_SYSTEM,
                    DataSource.RELATED_SYSTEM,
                    DataSource.COMPETITORS_POOL,  # Include for comprehensive CP data
                    DataSource.OFFICIAL_API,
                    DataSource.EXTERNAL_SYSTEM
                ],
                validation_rules={
                    'format': r'^[A-Z0-9\-]+$',
                    'max_length': 50
                }
            ),
            'fargo_rating': DataField(
                name='fargo_rating',
                description='Fargo rating score',
                shareable=True,
                priority_sources=[
                    DataSource.OFFICIAL_API,
                    DataSource.COMPETITORS_POOL,  # High priority for fresh CP data
                    DataSource.PRIMARY_SYSTEM,
                    DataSource.RELATED_SYSTEM,
                    DataSource.EXTERNAL_SYSTEM
                ],
                validation_rules={
                    'range': (0, 1000),
                    'type': 'numeric'
                }
            ),
            'country': DataField(
                name='country',
                description='Player country of origin',
                shareable=True,
                priority_sources=[
                    DataSource.COMPETITORS_POOL,  # High priority for detailed location data
                    DataSource.PRIMARY_SYSTEM,
                    DataSource.RELATED_SYSTEM,
                    DataSource.OFFICIAL_API,
                    DataSource.EXTERNAL_SYSTEM
                ],
                validation_rules={
                    'format': r'^[A-Z]{2,3}$',
                    'max_length': 3,
                    'min_length': 2
                }
            )
        }

    def _build_relationship_matrix(self) -> Dict[Tuple[str, str], SystemRelationship]:
        """Build matrix of relationships between all system pairs"""
        relationships = {}

        for sys1_code, sys1_meta in self.systems.items():
            for sys2_code, sys2_meta in self.systems.items():
                if sys1_code == sys2_code:
                    relationships[(sys1_code, sys2_code)] = SystemRelationship.IDENTICAL
                elif (sys1_meta.organization == sys2_meta.organization and
                      sys1_meta.gender == sys2_meta.gender and
                      sys1_meta.sport_type == sys2_meta.sport_type):
                    relationships[(sys1_code, sys2_code)] = SystemRelationship.IDENTICAL
                elif (sys1_meta.gender == sys2_meta.gender and
                      sys1_meta.sport_type == sys2_meta.sport_type):
                    relationships[(sys1_code, sys2_code)] = SystemRelationship.RELATED
                elif (sys1_meta.gender == sys2_meta.gender and
                      ((sys1_meta.sport_type == 'pool' and sys2_meta.sport_type == 'external_pool') or
                       (sys1_meta.sport_type == 'external_pool' and sys2_meta.sport_type == 'pool'))):
                    # External Pool is related to traditional pool for same gender
                    relationships[(sys1_code, sys2_code)] = SystemRelationship.RELATED
                elif sys1_meta.gender == sys2_meta.gender:
                    relationships[(sys1_code, sys2_code)] = SystemRelationship.RELATED
                elif sys1_meta.organization == sys2_meta.organization:
                    relationships[(sys1_code, sys2_code)] = SystemRelationship.CROSS_GENDER
                else:
                    relationships[(sys1_code, sys2_code)] = SystemRelationship.UNRELATED

        return relationships

    def get_system_relationship(self, sys1: str, sys2: str) -> SystemRelationship:
        """Get relationship between two systems"""
        return self.relationships.get((sys1, sys2), SystemRelationship.UNRELATED)

    def get_related_systems(self, system_code: str) -> List[str]:
        """Get systems related to the given system (for data sharing)"""
        related = []
        for other_sys in self.systems.keys():
            if other_sys != system_code:
                relationship = self.get_system_relationship(system_code, other_sys)
                if relationship in [SystemRelationship.IDENTICAL, SystemRelationship.RELATED]:
                    related.append(other_sys)
        return related

    def validate_field_data(self, field_name: str, value: Any) -> bool:
        """Validate data for a specific field"""
        if field_name not in self.fields:
            return False

        field_def = self.fields[field_name]
        if not field_def.validation_rules:
            return True

        rules = field_def.validation_rules

        # Type validation
        if 'type' in rules:
            if rules['type'] == 'numeric' and not isinstance(value, (int, float)):
                return False

        # Range validation
        if 'range' in rules and isinstance(value, (int, float)):
            min_val, max_val = rules['range']
            if not (min_val <= value <= max_val):
                return False

        # Format validation
        if 'format' in rules and isinstance(value, str):
            import re
            if not re.match(rules['format'], value):
                return False

        # Length validation
        if 'max_length' in rules and isinstance(value, str):
            if len(value) > rules['max_length']:
                return False

        return True

    def select_best_data_source(self, field_name: str, system_code: str,
                               available_data: Dict[str, Any]) -> Tuple[str, Any]:
        """
        Select the best data source for a field based on priority rules

        Args:
            field_name: The field to find data for
            system_code: The primary system code
            available_data: Dict of system_code -> field_value

        Returns:
            Tuple of (selected_system, selected_value)
        """
        if field_name not in self.fields:
            return None, None

        field_def = self.fields[field_name]
        if not available_data:
            return None, None

        # Score each available data source
        scored_sources = []

        for source_sys, value in available_data.items():
            if value is None:
                continue

            # Skip invalid data
            if not self.validate_field_data(field_name, value):
                continue

            # Calculate priority score
            relationship = self.get_system_relationship(system_code, source_sys)

            # Check if source is CP - give it high priority for fresh data
            if source_sys.startswith('Competitors_Pool'):
                priority = DataSource.COMPETITORS_POOL
            elif source_sys == system_code:
                priority = DataSource.PRIMARY_SYSTEM
            elif relationship in [SystemRelationship.IDENTICAL, SystemRelationship.RELATED]:
                priority = DataSource.RELATED_SYSTEM
            elif relationship == SystemRelationship.CROSS_GENDER:
                priority = DataSource.EXTERNAL_SYSTEM
            else:
                priority = DataSource.EXTERNAL_SYSTEM

            # Check if this source is in the field's priority list
            try:
                priority_index = field_def.priority_sources.index(priority)
                base_score = len(field_def.priority_sources) - priority_index  # Higher index = higher score
            except ValueError:
                base_score = 0

            # For Fargo ratings, also consider the actual rating value (higher is better)
            value_bonus = 0
            if field_name == 'fargo_rating' and isinstance(value, (int, float)):
                # Normalize rating to a bonus score (0-1000 range becomes 0-50 bonus points)
                # This makes higher ratings significantly more attractive
                value_bonus = min(value / 20, 50) if value > 0 else 0

            # CP recency bonus - give extra points for potentially fresher data
            recency_bonus = 0
            if source_sys.startswith('Competitors_Pool'):
                if field_name == 'fargo_rating':
                    recency_bonus = 25  # Significant bonus for Fargo ratings from CP
                elif field_name == 'country':
                    recency_bonus = 15  # Good bonus for location data
                else:
                    recency_bonus = 10  # General recency bonus

            total_score = base_score + value_bonus + recency_bonus
            scored_sources.append((source_sys, value, total_score))

        if not scored_sources:
            return None, None

        # Return the highest scoring source
        scored_sources.sort(key=lambda x: x[2], reverse=True)
        best_source, best_value, _ = scored_sources[0]

        return best_source, best_value

    def enrich_player_data(self, player_name: str, all_player_records: List[Dict]) -> Dict[str, Any]:
        """
        Enrich data for a single player across all their ranking systems.
        Now also handles license-matched records from different players.

        Args:
            player_name: Name of the primary player
            all_player_records: List of all records (may include license-matched records from other players)

        Returns:
            Dict of field_name -> (source_system, value) for enrichment
        """
        enrichment_data = {}

        # Check if enrichment should be skipped for this player (e.g., complex names)
        if self._should_skip_enrichment_for_player(player_name, all_player_records):
            logger.debug(f"Enrichment skipped for player: {player_name}")
            return enrichment_data

        # Group data by system - handle license-matched records from different players
        system_data = {}
        license_groups = {}  # Group by license for cross-player matching

        for record in all_player_records:
            sys_code = record['ranking_system']
            license_num = record.get('license_number')

            # Group by system
            if sys_code not in system_data:
                system_data[sys_code] = {}
            system_data[sys_code].update(record)

            # Also group by license for cross-player matching
            if license_num:
                if license_num not in license_groups:
                    license_groups[license_num] = {}
                license_groups[license_num][sys_code] = record

        # Special handling: Use license numbers to match WPBA and WPA players
        enrichment_data.update(self._enrich_via_license_matching(system_data, player_name, license_groups))

        # Special handling: Merge Fargo ratings from WPA to WPA Heyball disciplines
        enrichment_data.update(self._enrich_heyball_from_wpa(system_data, player_name, license_groups))

        # For each enrichable field
        for field_name, field_def in self.fields.items():
            if not field_def.shareable:
                continue

            # Collect available data from all systems
            available_data = {}
            for sys_code, data in system_data.items():
                if field_name in data and data[field_name] is not None:
                    available_data[sys_code] = data[field_name]

            if not available_data:
                continue

            # Find systems that are missing this data
            missing_systems = []
            for sys_code, data in system_data.items():
                if field_name not in data or data[field_name] is None:
                    missing_systems.append(sys_code)

            # For each missing system, find the best data source
            for target_sys in missing_systems:
                best_source, best_value = self.select_best_data_source(
                    field_name, target_sys, available_data
                )

                if best_source and best_value is not None:
                    key = f"{target_sys}:{field_name}"
                    # Don't override license-matched recommendations with lower-confidence ones
                    if key not in enrichment_data or enrichment_data[key].get('match_type') != 'license_number':
                        enrichment_data[key] = {
                            'source_system': best_source,
                            'target_system': target_sys,
                            'field': field_name,
                            'value': best_value,
                            'confidence': self._calculate_confidence(field_name, best_source, target_sys)
                        }

        return enrichment_data

    def _calculate_confidence(self, field_name: str, source_sys: str, target_sys: str) -> float:
        """Calculate confidence score for a data enrichment (0.0 to 1.0)"""
        relationship = self.get_system_relationship(source_sys, target_sys)

        # Base confidence by relationship
        if relationship == SystemRelationship.IDENTICAL:
            base_confidence = 1.0
        elif relationship == SystemRelationship.RELATED:
            base_confidence = 0.9
        elif relationship == SystemRelationship.CROSS_GENDER:
            base_confidence = 0.7
        else:
            base_confidence = 0.5

        # Field-specific adjustments
        field_adjustments = {
            'license_number': 1.0,  # Licenses are highly reliable
            'fargo_rating': 0.95,   # Fargo ratings are standardized
            'country': 0.9         # Country data is usually consistent
        }

        field_multiplier = field_adjustments.get(field_name, 0.8)

        return min(1.0, base_confidence * field_multiplier)


    def _enrich_via_license_matching(self, system_data: Dict[str, Dict], player_name: str, license_groups: Optional[Dict[str, Dict[str, Dict]]] = None) -> Dict[str, Any]:
        """
        Special enrichment logic for WPBA-WPA license matching.

        Uses license numbers as primary matching key to merge data between
        WPBA and WPA systems, since WPBA often lacks country/license data
        that WPA provides.

        Args:
            system_data: Dict of system_code -> player_data
            player_name: Name of the player
            license_groups: Optional dict of license -> system -> record for cross-player matching

        Returns:
            Dict of enrichment recommendations based on license matching
        """
        enrichment_data = {}

        # Find WPBA and WPA systems in the data
        wpba_systems = [sys for sys in system_data.keys() if sys.startswith('WPBA')]
        wpa_systems = [sys for sys in system_data.keys() if sys.startswith('WPA')]

        if not wpba_systems or not wpa_systems:
            return enrichment_data

        matches_found = False

        # For each WPBA system, try to find matching WPA data via license
        for wpba_sys in wpba_systems:
            wpba_data = system_data[wpba_sys]
            wpba_license = wpba_data.get('license_number')

            if not wpba_license:
                continue  # No license to match on

            # Look for WPA systems with matching license
            for wpa_sys in wpa_systems:
                wpa_data = system_data[wpa_sys]
                wpa_license = wpa_data.get('license_number')

                if wpa_license and wpba_license.strip() == wpa_license.strip():
                    # Found matching license! Create enrichment recommendations
                    logger.info(f"🔗 License match: {wpba_sys} <- {wpa_sys} for {player_name} (license: {wpba_license})")
                    matches_found = True

                    # WPBA gets country data from WPA
                    if not wpba_data.get('country') and wpa_data.get('country'):
                        key = f"{wpba_sys}:country"
                        enrichment_data[key] = {
                            'source_system': wpa_sys,
                            'target_system': wpba_sys,
                            'field': 'country',
                            'value': wpa_data['country'],
                            'confidence': 0.95,  # High confidence for license-matched data
                            'match_type': 'license_number'
                        }

                    # WPBA gets license confirmation from WPA (if formats differ slightly)
                    if not wpba_data.get('license_number') and wpa_data.get('license_number'):
                        key = f"{wpba_sys}:license_number"
                        enrichment_data[key] = {
                            'source_system': wpa_sys,
                            'target_system': wpba_sys,
                            'field': 'license_number',
                            'value': wpa_data['license_number'],
                            'confidence': 0.95,
                            'match_type': 'license_number'
                        }

                    # WPA can get Fargo ratings from WPBA (if WPBA has them)
                    if not wpa_data.get('fargo_rating') and wpba_data.get('fargo_rating'):
                        key = f"{wpa_sys}:fargo_rating"
                        enrichment_data[key] = {
                            'source_system': wpba_sys,
                            'target_system': wpa_sys,
                            'field': 'fargo_rating',
                            'value': wpba_data['fargo_rating'],
                            'confidence': 0.90,  # Slightly lower for reverse enrichment
                            'match_type': 'license_number'
                        }

        if matches_found:
            logger.info(f"✅ License-based enrichment completed for {player_name}: {len(enrichment_data)} recommendations")

        return enrichment_data

    def _enrich_heyball_from_wpa(self, system_data: Dict[str, Dict], player_name: str, license_groups: Optional[Dict[str, Dict[str, Dict]]] = None) -> Dict[str, Any]:
        """
        Special enrichment logic for WPA Heyball -> WPA Fargo rating merging.

        Since Heyball is a WPA discipline, Heyball players should get Fargo ratings
        from the general WPA data when available via license matching.

        Handles both WPA_Heyball_Men -> WPA_Men and WPA_Heyball_Women -> WPA_Women.

        Args:
            system_data: Dict of system_code -> player_data
            player_name: Name of the player
            license_groups: Optional dict of license -> system -> record for cross-player matching

        Returns:
            Dict of enrichment recommendations for Heyball Fargo ratings
        """
        enrichment_data = {}

        # Find all Heyball and corresponding WPA systems
        heyball_systems = [sys for sys in system_data.keys() if sys.startswith('WPA_Heyball_')]
        wpa_systems = [sys for sys in system_data.keys() if sys.startswith('WPA_') and not sys.startswith('WPA_Heyball_')]

        if not heyball_systems or not wpa_systems:
            return enrichment_data

        matches_found = False

        # Create mapping of Heyball systems to their corresponding WPA systems
        heyball_to_wpa_map = {
            'WPA_Heyball_Men': 'WPA_Men',
            'WPA_Heyball_Women': 'WPA_Women'
        }

        # Use license_groups if available (from cross-player enrichment)
        if license_groups:
            for license_num, system_records in license_groups.items():
                if not license_num:
                    continue

                # Check each Heyball system
                for heyball_sys in heyball_systems:
                    wpa_target_sys = heyball_to_wpa_map.get(heyball_sys)
                    if not wpa_target_sys or wpa_target_sys not in system_records:
                        continue

                    if heyball_sys not in system_records:
                        continue

                    heyball_record = system_records[heyball_sys]
                    wpa_record = system_records[wpa_target_sys]

                    # Check if Heyball is missing Fargo rating but WPA has it
                    heyball_fargo = heyball_record.get('fargo_rating')
                    wpa_fargo = wpa_record.get('fargo_rating')

                    if (heyball_fargo is None or heyball_fargo == 0) and wpa_fargo and wpa_fargo > 0:
                        # Create enrichment recommendation
                        key = f"{heyball_sys}:fargo_rating"
                        enrichment_data[key] = {
                            'source_system': wpa_target_sys,
                            'target_system': heyball_sys,
                            'field': 'fargo_rating',
                            'value': wpa_fargo,
                            'confidence': 0.92,  # High confidence for same-organization license match
                            'match_type': 'heyball_wpa_license'
                        }
                        matches_found = True
                        logger.debug(f"Heyball Fargo enrichment: {heyball_record.get('player_name')} ({heyball_sys}) <- {wpa_fargo} from {wpa_record.get('player_name')} ({wpa_target_sys})")

        if matches_found:
            logger.info(f"✅ Heyball Fargo enrichment completed for {player_name}")

        return enrichment_data


    def _is_complex_name(self, player_name: str) -> bool:
        """
        Determine if a player name is complex and should not be enriched yet.

        Complex names include:
        - Names with 3 or more parts (e.g., "John Michael Smith")
        - Names with special characters or unusual formats
        - Names that contain numbers
        - Names that are particularly long (>50 characters)
        - Names with multiple spaces or unusual spacing

        Args:
            player_name: The player name to check

        Returns:
            True if the name is complex and should not be enriched
        """
        if not player_name or not isinstance(player_name, str):
            return True

        # Remove extra whitespace and check basic properties
        name = ' '.join(player_name.split())
        name_length = len(name)

        # Check for very long names
        if name_length > 50:
            return True

        # Check for numbers in names
        if any(char.isdigit() for char in name):
            return True

        # Check for special characters (except common ones like apostrophes)
        special_chars = set('!@#$%^&*()[]{}|\\:;"<>,.?/~`')
        if any(char in special_chars for char in name):
            return True

        # Split into name parts
        name_parts = name.split()

        # Check for 3+ name parts
        if len(name_parts) >= 3:
            return True

        # Check for unusual spacing (multiple consecutive spaces would be handled above)
        # but also check for very short parts that might indicate unusual formatting
        if any(len(part) < 2 for part in name_parts):
            # Allow single letters in some cases (like "Jr", "Sr", "II", "III")
            short_parts = [part for part in name_parts if len(part) < 2]
            if short_parts and not all(part.lower() in ['jr', 'sr', 'ii', 'iii', 'iv', 'v'] for part in short_parts):
                return True

        # Check for names that look like they might be formatted differently
        # (e.g., all caps, all lowercase except first letter, etc.)
        if name.isupper() or name.islower():
            return True

        return False

    def _normalize_player_name(self, player_name: str) -> str:
        """
        Normalize player name to canonical form for cross-format matching.
        Converts "Last, First" → "first last" and "First Last" → "first last"
        """
        if not FARGO_CLIENT_AVAILABLE:
            return player_name.lower().strip()

        try:
            return canonical_form(player_name)
        except Exception as e:
            logger.warning(f"Name normalization failed for '{player_name}': {e}")
            return player_name.lower().strip()

    def _names_match_canonical(self, name1: str, name2: str, use_fuzzy: bool = False) -> bool:
        """
        Check if two player names match using canonical normalization.
        Handles "Last, First" vs "First Last" format differences.
        """
        if not FARGO_CLIENT_AVAILABLE:
            return name1.lower().strip() == name2.lower().strip()

        try:
            canonical1 = self._normalize_player_name(name1)
            canonical2 = self._normalize_player_name(name2)

            if canonical1 == canonical2:
                return True

            if use_fuzzy and FARGO_CLIENT_AVAILABLE:
                first1, last1 = parse_name(name1)
                first2, last2 = parse_name(name2)
                deterministic = names_match_fuzzy(first1, last1, first2, last2, threshold=0.85)
                if deterministic:
                    return True

                # LLM arbitration for ambiguous cases
                if _OLLAMA_RESOLVER_AVAILABLE:
                    from difflib import SequenceMatcher
                    score = SequenceMatcher(None, canonical1, canonical2).ratio()
                    if 0.60 <= score < 0.85:
                        try:
                            import asyncio
                            loop = asyncio.new_event_loop()
                            try:
                                result = loop.run_until_complete(
                                    _ollama_resolve_name(name1, name2)
                                )
                            finally:
                                loop.close()
                            if result and result.is_confident_match:
                                logger.info("LLM enrichment match: '%s' <-> '%s'", name1, name2)
                                return True
                        except Exception as llm_err:
                            logger.debug("LLM name match unavailable: %s", llm_err)

                return False

            return False
        except Exception as e:
            logger.warning(f"Canonical name matching failed for '{name1}' vs '{name2}': {e}")
            return name1.lower().strip() == name2.lower().strip()

    def _validate_match_with_fargo_rating(self, player_records: List[Dict]) -> bool:
        """
        Validate player matches using Fargo ratings as additional confirmation.
        Players with very different Fargo ratings are unlikely to be the same person.
        """
        fargo_ratings = [record.get('fargo_rating') for record in player_records
                        if record.get('fargo_rating') is not None]

        if len(fargo_ratings) < 2:
            # Not enough data for validation, assume valid
            return True

        # Check if all Fargo ratings are within a reasonable range
        # Professional players typically don't vary by more than 200-300 points
        max_rating = max(fargo_ratings)
        min_rating = min(fargo_ratings)
        rating_spread = max_rating - min_rating

        # Allow up to 300 point spread for validation (accounts for rating changes over time)
        if rating_spread > 300:
            logger.warning(f"Large Fargo rating spread ({rating_spread} points) for matched players: {fargo_ratings}")
            return False

        return True

    def _should_skip_enrichment_for_player(self, player_name: str, all_player_records: List[Dict]) -> bool:
        """
        Determine if enrichment should be skipped for a player.

        Currently skips enrichment for players with complex names to prevent
        incorrect data matching until proper name matching is implemented.

        Args:
            player_name: The primary player name
            all_player_records: All records for this player

        Returns:
            True if enrichment should be skipped
        """
        # Skip enrichment for complex names
        if self._is_complex_name(player_name):
            logger.info(f"⏭️ Skipping enrichment for complex name: '{player_name}'")
            return True

        # Also check if any of the associated records have complex names
        for record in all_player_records:
            record_name = record.get('player_name', '')
            if record_name != player_name and self._is_complex_name(record_name):
                logger.info(f"⏭️ Skipping enrichment due to complex associated name: '{record_name}' (primary: '{player_name}')")
                return True

        return False


# Global instance for reuse
enrichment_engine = EnrichmentEngine()