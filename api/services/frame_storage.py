"""
Oracle Frame Storage Service
Local filesystem-based frame storage for pool coaching analyses
Handles frame persistence and lifecycle management
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict
import base64

logger = logging.getLogger(__name__)


@dataclass
class FrameStorageMetadata:
    """Metadata about stored frames"""
    analysis_id: str
    user_id: str
    bot_type: str
    frame_count: int
    total_size_mb: float
    created_at: str
    expires_at: str
    storage_path: str
    frames_info: List[Dict[str, Any]]  # Per-frame details


class OracleFrameStorage:
    """
    Manage frame storage on Oracle VM filesystem
    
    Storage Structure:
    /data/pool-coaching-frames/
    └── YYYY/MM/DD/
        └── {analysis_id}/
            ├── metadata.json
            └── frame_{index}.jpg
    """
    
    DEFAULT_STORAGE_ROOT = "/data/pool-coaching-frames"
    DEV_STORAGE_ROOT = "./pools_coaching_frames"
    
    DEFAULT_RETENTION_DAYS = 30
    
    def __init__(self, storage_root: Optional[str] = None):
        """
        Initialize storage manager.
        
        Args:
            storage_root: Root directory for frame storage.
                         Production: /data/pool-coaching-frames
                         Dev: ./pools_coaching_frames (when /data is not writable)
        """
        if storage_root:
            self.storage_root = Path(storage_root)
        else:
            default_path = Path(self.DEFAULT_STORAGE_ROOT)
            dev_path = Path(self.DEV_STORAGE_ROOT)
            try:
                default_path.parent.mkdir(parents=True, exist_ok=True)
                self.storage_root = default_path
            except (PermissionError, OSError):
                logger.info(f"Cannot write to {default_path.parent}, using dev path {dev_path}")
                self.storage_root = dev_path
        
        self._ensure_storage_directory()
        logger.info(f"OracleFrameStorage initialized at {self.storage_root}")
    
    def _ensure_storage_directory(self) -> None:
        """Create storage directory if it doesn't exist"""
        try:
            self.storage_root.mkdir(parents=True, exist_ok=True)
            # Create subdirectories for current month
            today = datetime.utcnow()
            month_dir = self.storage_root / str(today.year) / f"{today.month:02d}" / f"{today.day:02d}"
            month_dir.mkdir(parents=True, exist_ok=True)
            logger.info(f"Storage directory ready: {self.storage_root}")
        except Exception as e:
            logger.error(f"Failed to create storage directory: {e}")
            raise
    
    def _get_analysis_directory(self, analysis_id: str) -> Path:
        """
        Get the directory path for a specific analysis
        Organized by date for easy cleanup
        """
        today = datetime.utcnow()
        analysis_dir = (
            self.storage_root / 
            str(today.year) / 
            f"{today.month:02d}" / 
            f"{today.day:02d}" / 
            analysis_id
        )
        return analysis_dir
    
    async def save_frames(
        self,
        analysis_id: str,
        user_id: str,
        frames_base64: List[str],
        bot_type: str = "rankings",
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Save extracted frames to disk
        
        Args:
            analysis_id: Unique analysis identifier
            user_id: User who submitted the analysis
            frames_base64: List of base64-encoded JPEG frames
            bot_type: Type of bot (rankings, trading, contracts, credit)
            metadata: Additional metadata to store
        
        Returns:
            Storage result with paths and metadata
        """
        if not frames_base64:
            raise ValueError("No frames provided")
        
        logger.info(f"Saving {len(frames_base64)} frames for analysis {analysis_id}")
        
        try:
            # Create analysis directory
            analysis_dir = self._get_analysis_directory(analysis_id)
            analysis_dir.mkdir(parents=True, exist_ok=True)
            
            # Save individual frames
            frames_info = []
            total_size_bytes = 0
            
            for i, frame_b64 in enumerate(frames_base64):
                try:
                    # Decode base64 to bytes
                    frame_bytes = base64.b64decode(frame_b64)
                    frame_size_bytes = len(frame_bytes)
                    total_size_bytes += frame_size_bytes
                    
                    # Save frame file
                    frame_path = analysis_dir / f"frame_{i:03d}.jpg"
                    frame_path.write_bytes(frame_bytes)
                    
                    frames_info.append({
                        "index": i,
                        "filename": f"frame_{i:03d}.jpg",
                        "size_bytes": frame_size_bytes,
                        "saved_at": datetime.utcnow().isoformat()
                    })
                    
                except Exception as e:
                    logger.error(f"Failed to save frame {i}: {e}")
                    raise
            
            # Calculate total size in MB
            total_size_mb = total_size_bytes / (1024 * 1024)
            
            # Create expiration timestamp
            now = datetime.utcnow()
            expires_at = (now + timedelta(days=self.DEFAULT_RETENTION_DAYS)).isoformat()
            
            # Create metadata file
            storage_metadata = FrameStorageMetadata(
                analysis_id=analysis_id,
                user_id=user_id,
                bot_type=bot_type,
                frame_count=len(frames_base64),
                total_size_mb=round(total_size_mb, 2),
                created_at=now.isoformat(),
                expires_at=expires_at,
                storage_path=str(analysis_dir),
                frames_info=frames_info
            )
            
            # Save metadata as JSON
            metadata_path = analysis_dir / "metadata.json"
            metadata_dict = {
                **asdict(storage_metadata),
                **(metadata or {})
            }
            metadata_path.write_text(
                json.dumps(metadata_dict, indent=2),
                encoding="utf-8"
            )
            
            logger.info(
                f"Frames saved successfully: {len(frames_base64)} frames, "
                f"{total_size_mb:.2f}MB to {analysis_dir}"
            )
            
            return {
                "status": "success",
                "analysis_id": analysis_id,
                "frame_count": len(frames_base64),
                "total_size_mb": round(total_size_mb, 2),
                "storage_path": str(analysis_dir),
                "expires_at": expires_at,
                "metadata": metadata_dict
            }
        
        except Exception as e:
            logger.error(f"Failed to save frames: {e}")
            raise RuntimeError(f"Frame storage failed: {str(e)}")
    
    async def retrieve_frames(
        self,
        analysis_id: str
    ) -> Optional[Dict[str, Any]]:
        """
        Retrieve stored frames and metadata for an analysis
        
        Args:
            analysis_id: Analysis ID to retrieve
        
        Returns:
            Dictionary with frames and metadata, or None if not found
        """
        logger.info(f"Retrieving frames for analysis {analysis_id}")
        
        # Try to find the analysis directory
        # Search through recent dates (within last 30 days)
        for days_back in range(self.DEFAULT_RETENTION_DAYS):
            date = datetime.utcnow() - timedelta(days=days_back)
            possible_dir = (
                self.storage_root /
                str(date.year) /
                f"{date.month:02d}" /
                f"{date.day:02d}" /
                analysis_id
            )
            
            if possible_dir.exists():
                return await self._load_analysis_directory(possible_dir)
        
        logger.warning(f"Analysis {analysis_id} not found in storage")
        return None
    
    async def _load_analysis_directory(self, analysis_dir: Path) -> Dict[str, Any]:
        """Load all frames and metadata from analysis directory"""
        
        # Load metadata
        metadata_path = analysis_dir / "metadata.json"
        metadata = {}
        if metadata_path.exists():
            metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
        
        # Load frames
        frames = []
        for frame_file in sorted(analysis_dir.glob("frame_*.jpg")):
            frame_data = frame_file.read_bytes()
            frame_b64 = base64.b64encode(frame_data).decode('utf-8')
            frames.append({
                "filename": frame_file.name,
                "data": frame_b64,
                "size_bytes": len(frame_data)
            })
        
        return {
            "analysis_id": metadata.get("analysis_id"),
            "metadata": metadata,
            "frames": frames,
            "frame_count": len(frames)
        }
    
    async def delete_analysis(self, analysis_id: str) -> bool:
        """
        Delete frames for an analysis (manual cleanup)
        
        Args:
            analysis_id: Analysis to delete
        
        Returns:
            True if deleted, False if not found
        """
        logger.info(f"Deleting frames for analysis {analysis_id}")
        
        # Search for the directory
        for days_back in range(self.DEFAULT_RETENTION_DAYS):
            date = datetime.utcnow() - timedelta(days=days_back)
            possible_dir = (
                self.storage_root /
                str(date.year) /
                f"{date.month:02d}" /
                f"{date.day:02d}" /
                analysis_id
            )
            
            if possible_dir.exists():
                try:
                    # Delete all files in directory
                    for file in possible_dir.glob("*"):
                        file.unlink()
                    # Delete directory
                    possible_dir.rmdir()
                    logger.info(f"Deleted analysis {analysis_id}")
                    return True
                except Exception as e:
                    logger.error(f"Failed to delete analysis {analysis_id}: {e}")
                    return False
        
        return False
    
    async def cleanup_expired(self) -> Dict[str, int]:
        """
        Cleanup expired frames (older than retention period)
        
        Returns:
            Dictionary with cleanup statistics
        """
        logger.info("Starting cleanup of expired frames...")
        
        cutoff_date = datetime.utcnow() - timedelta(days=self.DEFAULT_RETENTION_DAYS)
        deleted_dirs = 0
        deleted_files = 0
        
        try:
            # Walk through all stored analyses
            for year_dir in self.storage_root.iterdir():
                if not year_dir.is_dir():
                    continue
                
                for month_dir in year_dir.iterdir():
                    if not month_dir.is_dir():
                        continue
                    
                    for day_dir in month_dir.iterdir():
                        if not day_dir.is_dir():
                            continue
                        
                        # Check if this date is before cutoff
                        try:
                            year = int(year_dir.name)
                            month = int(month_dir.name)
                            day = int(day_dir.name)
                            dir_date = datetime(year, month, day)
                            
                            if dir_date < cutoff_date:
                                # Delete all analyses in this directory
                                for analysis_dir in day_dir.iterdir():
                                    if analysis_dir.is_dir():
                                        for file in analysis_dir.glob("*"):
                                            file.unlink()
                                            deleted_files += 1
                                        analysis_dir.rmdir()
                                        deleted_dirs += 1
                        except (ValueError, Exception) as e:
                            logger.warning(f"Error processing directory: {e}")
                            continue
            
            logger.info(
                f"Cleanup complete: {deleted_dirs} directories, "
                f"{deleted_files} files deleted"
            )
            return {
                "deleted_directories": deleted_dirs,
                "deleted_files": deleted_files
            }
        
        except Exception as e:
            logger.error(f"Cleanup failed: {e}")
            return {"error": str(e)}
    
    async def get_storage_stats(self) -> Dict[str, Any]:
        """Get storage usage statistics"""
        
        total_size = 0
        total_analyses = 0
        
        try:
            for root, dirs, files in os.walk(self.storage_root):
                for file in files:
                    if file.endswith(".jpg"):
                        file_path = os.path.join(root, file)
                        total_size += os.path.getsize(file_path)
                        total_size += 1  # Count in analysis
            
            # Count analyses
            for root, dirs, files in os.walk(self.storage_root):
                if "metadata.json" in files:
                    total_analyses += 1
            
            return {
                "storage_root": str(self.storage_root),
                "total_size_mb": round(total_size / (1024 * 1024), 2),
                "total_analyses": total_analyses,
                "retention_days": self.DEFAULT_RETENTION_DAYS
            }
        except Exception as e:
            logger.error(f"Failed to get storage stats: {e}")
            return {"error": str(e)}


# Example usage
async def example_usage():
    """Example of how to use OracleFrameStorage"""
    
    storage = OracleFrameStorage()
    
    # Example: Save frames (would be real base64 JPEG data)
    example_frames = [
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg==",
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mNk+M9QDwADhgGAWjR9awAAAABJRU5ErkJggg=="
    ]
    
    # Save frames
    result = await storage.save_frames(
        analysis_id="test-analysis-001",
        user_id="user-123",
        frames_base64=example_frames,
        bot_type="rankings",
        metadata={"player_name": "Test Player"}
    )
    print(f"Saved: {result}")
    
    # Retrieve frames
    retrieve_result = await storage.retrieve_frames("test-analysis-001")
    print(f"Retrieved: {retrieve_result['frame_count']} frames")
    
    # Get storage stats
    stats = await storage.get_storage_stats()
    print(f"Storage stats: {stats}")
    
    # Cleanup
    cleanup_result = await storage.cleanup_expired()
    print(f"Cleanup: {cleanup_result}")


if __name__ == "__main__":
    asyncio.run(example_usage())
