"""
Model loader and initialization for Alfa rating prediction system.

Handles:
- Loading trained ML models (logistic regression, anomaly detection)
- Cold start engine initialization
- Model caching and lifecycle management
- Error handling for missing/corrupt models
- Health checks for model readiness
"""

import logging
import pickle
import os
import json
from pathlib import Path
from typing import Optional, Dict, Any
from datetime import datetime
import traceback

logger = logging.getLogger(__name__)


class ModelLoadError(Exception):
    """Raised when model loading fails."""

    pass


class ModelLoader:
    """Singleton model loader for Alfa system."""

    _instance: Optional["ModelLoader"] = None
    _initialized: bool = False

    def __new__(cls):
        """Ensure singleton pattern."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self):
        """Initialize model loader (only once)."""
        if self._initialized:
            return

        self.models: Dict[str, Any] = {}
        self.model_metadata: Dict[str, Dict[str, Any]] = {}
        self.load_errors: list[str] = []
        self.last_health_check: Optional[datetime] = None
        self.health_status: bool = False

        # Project root
        self.project_root = Path(__file__).resolve().parent.parent.parent
        self.models_dir = self.project_root / "models"
        self.config_dir = self.project_root / "config"

        # Ensure directories exist
        self.models_dir.mkdir(parents=True, exist_ok=True)
        self.config_dir.mkdir(parents=True, exist_ok=True)

        # Load all models on initialization
        self._load_all_models()
        ModelLoader._initialized = True
        logger.info("ModelLoader initialized (singleton)")

    def _load_all_models(self) -> None:
        """Load all models and initialize engines."""
        logger.info("Loading Alfa prediction models...")

        # Load logistic regression model
        self._load_logistic_regression()

        # Load anomaly detection model
        self._load_anomaly_detection()

        # Load cold start engine
        self._load_cold_start_engine()

        # Check overall health
        self._perform_health_check()

    def _load_logistic_regression(self) -> None:
        """Load trained logistic regression model."""
        model_file = self.models_dir / "alfa_logistic_regression_optimized.pkl"

        if not model_file.exists():
            error_msg = f"Logistic regression model not found: {model_file}"
            logger.warning(error_msg)
            self.load_errors.append(error_msg)
            return

        try:
            with open(model_file, "rb") as f:
                model = pickle.load(f)

            self.models["logistic_regression"] = model
            self.model_metadata["logistic_regression"] = {
                "file": str(model_file),
                "loaded_at": datetime.utcnow().isoformat(),
                "status": "ready",
            }
            logger.info("✓ Logistic regression model loaded successfully")

        except Exception as e:
            error_msg = f"Failed to load logistic regression: {str(e)}"
            logger.error(error_msg)
            self.load_errors.append(error_msg)

    def _load_anomaly_detection(self) -> None:
        """Load anomaly detection module and parameters."""
        anomaly_module_file = self.models_dir / "alfa_anomaly_detection_v2.py"
        thresholds_file = self.models_dir / "alfa_anomaly_thresholds_optimized.json"

        anomaly_detected = anomaly_module_file.exists()
        thresholds_detected = thresholds_file.exists()

        if not anomaly_detected or not thresholds_detected:
            msg = f"Anomaly detection files missing: module={anomaly_detected}, thresholds={thresholds_detected}"
            logger.warning(msg)
            if not anomaly_detected or not thresholds_detected:
                self.load_errors.append(msg)

        try:
            # Load thresholds JSON
            thresholds = {}
            if thresholds_file.exists():
                with open(thresholds_file, "r") as f:
                    thresholds = json.load(f)

            self.models["anomaly_detection"] = {
                "type": "anomaly_detection_v2",
                "thresholds": thresholds,
            }
            self.model_metadata["anomaly_detection"] = {
                "file": str(anomaly_module_file),
                "config_file": str(thresholds_file),
                "loaded_at": datetime.utcnow().isoformat(),
                "status": "ready",
            }
            logger.info("✓ Anomaly detection model loaded successfully")

        except Exception as e:
            error_msg = f"Failed to load anomaly detection: {str(e)}"
            logger.error(error_msg)
            self.load_errors.append(error_msg)

    def _load_cold_start_engine(self) -> None:
        """Load cold start engine."""
        from models.alfa_cold_start import ColdStartEngine

        try:
            engine = ColdStartEngine()
            self.models["cold_start_engine"] = engine
            self.model_metadata["cold_start_engine"] = {
                "class": "ColdStartEngine",
                "loaded_at": datetime.utcnow().isoformat(),
                "status": "ready",
            }
            logger.info("✓ Cold start engine initialized successfully")

        except Exception as e:
            error_msg = f"Failed to initialize cold start engine: {str(e)}"
            logger.error(error_msg)
            self.load_errors.append(error_msg)

    def get_model(self, model_name: str) -> Any:
        """
        Get a loaded model by name.

        Args:
            model_name: Name of model (e.g., 'logistic_regression', 'anomaly_detection')

        Returns:
            Model instance or dict

        Raises:
            ModelLoadError: If model not available
        """
        if model_name not in self.models:
            available = list(self.models.keys())
            raise ModelLoadError(
                f"Model '{model_name}' not available. Available: {available}"
            )
        return self.models[model_name]

    def get_all_models(self) -> Dict[str, Any]:
        """Get all loaded models."""
        return dict(self.models)

    def get_model_info(self, model_name: str) -> Dict[str, Any]:
        """Get metadata about a specific model."""
        return self.model_metadata.get(model_name, {})

    def _perform_health_check(self) -> None:
        """Check if critical models are ready."""
        required_models = {"logistic_regression", "anomaly_detection", "cold_start_engine"}
        loaded_models = set(self.models.keys())

        missing = required_models - loaded_models
        self.health_status = len(missing) == 0

        self.last_health_check = datetime.utcnow()

        if self.health_status:
            logger.info("✓ All critical models loaded successfully")
        else:
            logger.warning(f"⚠ Missing critical models: {missing}")

    def is_healthy(self) -> bool:
        """Check if all models are ready."""
        return self.health_status

    def get_health_report(self) -> Dict[str, Any]:
        """Get comprehensive health status."""
        return {
            "is_healthy": self.health_status,
            "models_loaded": list(self.models.keys()),
            "load_errors": self.load_errors,
            "last_check": self.last_health_check.isoformat()
            if self.last_health_check
            else None,
            "model_metadata": self.model_metadata,
        }

    def reload_models(self) -> None:
        """Reload all models (useful for updates without restart)."""
        logger.info("Reloading models...")
        self.models.clear()
        self.model_metadata.clear()
        self.load_errors.clear()
        self._load_all_models()
        logger.info("Models reloaded")


# Global singleton instance
_loader: Optional[ModelLoader] = None


def get_model_loader() -> ModelLoader:
    """Get or create the global model loader instance."""
    global _loader
    if _loader is None:
        _loader = ModelLoader()
    return _loader


def ensure_models_loaded() -> bool:
    """
    Ensure all models are loaded and healthy.

    Returns:
        True if all models loaded, False otherwise
    """
    loader = get_model_loader()
    if not loader.is_healthy():
        logger.error(
            f"Models not healthy. Errors: {loader.load_errors}"
        )
        return False
    return True


def get_logistic_regression_model():
    """Get logistic regression model for predictions."""
    loader = get_model_loader()
    return loader.get_model("logistic_regression")


def get_anomaly_detection_config():
    """Get anomaly detection configuration."""
    loader = get_model_loader()
    return loader.get_model("anomaly_detection")


def get_cold_start_engine():
    """Get cold start engine."""
    loader = get_model_loader()
    return loader.get_model("cold_start_engine")


# ============================================================================
# CACHING UTILITIES
# ============================================================================


class SimpleCache:
    """In-memory cache with TTL support."""

    def __init__(self, default_ttl: int = 3600):
        """
        Initialize cache.

        Args:
            default_ttl: Default time-to-live in seconds (default 1 hour)
        """
        self.cache: Dict[str, tuple[Any, datetime]] = {}
        self.default_ttl = default_ttl

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """
        Set cache value.

        Args:
            key: Cache key
            value: Cache value
            ttl: Time-to-live in seconds (None = use default)
        """
        self.cache[key] = (value, datetime.utcnow())

    def get(self, key: str, ttl: Optional[int] = None) -> Optional[Any]:
        """
        Get cache value if not expired.

        Args:
            key: Cache key
            ttl: Time-to-live in seconds (None = use default)

        Returns:
            Cached value or None if expired/missing
        """
        if key not in self.cache:
            return None

        value, timestamp = self.cache[key]
        ttl_seconds = ttl or self.default_ttl

        # Check if expired
        age = (datetime.utcnow() - timestamp).total_seconds()
        if age > ttl_seconds:
            del self.cache[key]
            return None

        return value

    def delete(self, key: str) -> None:
        """Delete a cache entry."""
        self.cache.pop(key, None)

    def clear(self) -> None:
        """Clear all cache entries."""
        self.cache.clear()

    def cleanup_expired(self) -> int:
        """Remove expired entries. Returns count removed."""
        expired_keys = []
        for key, (value, timestamp) in self.cache.items():
            age = (datetime.utcnow() - timestamp).total_seconds()
            if age > self.default_ttl:
                expired_keys.append(key)

        for key in expired_keys:
            del self.cache[key]

        return len(expired_keys)


# Global caches
player_ratings_cache = SimpleCache(default_ttl=3600)  # 1 hour
prediction_cache = SimpleCache(default_ttl=300)  # 5 minutes
