"""
Cleanup service for managing log and data file retention.
Provides periodic cleanup of old files based on configuration.
"""

import os
import shutil
import threading
import time
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, Any, List
import logging
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

class CleanupService:
    """
    Service để dọn dẹp định kỳ các file log và dữ liệu cũ.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Khởi tạo cleanup service.
        
        Args:
            config: Cấu hình cleanup từ app config
        """
        self.config = config
        self.enabled = config.get("enabled", True)
        self.schedule_hours = config.get("schedule_hours", 24)
        self.logs_retention_days = config.get("logs_retention_days", 7)
        self.data_retention_days = config.get("data_retention_days", 30)
        
        # Paths to clean
        self.logs_path = Path("logs")
        self.data_path = Path("data")
        
        # Scheduler
        self.scheduler = BackgroundScheduler()
        self.is_running = False
        
        logger.info(f"CleanupService initialized - Enabled: {self.enabled}, "
                   f"Schedule: {self.schedule_hours}h, "
                   f"Logs retention: {self.logs_retention_days} days, "
                   f"Data retention: {self.data_retention_days} days")
    
    def start(self):
        """Khởi động cleanup service."""
        if not self.enabled:
            logger.info("Cleanup service disabled by configuration")
            return
        
        if self.is_running:
            logger.warning("Cleanup service is already running")
            return
        
        # Schedule periodic cleanup
        self.scheduler.add_job(
            func=self.run_cleanup,
            trigger=IntervalTrigger(hours=self.schedule_hours),
            id='cleanup_job',
            name='Periodic cleanup of logs and data',
            replace_existing=True
        )
        
        self.scheduler.start()
        self.is_running = True
        
        logger.info(f"Cleanup service started - will run every {self.schedule_hours} hours")
        
        # Run initial cleanup
        self.run_cleanup()
    
    def stop(self):
        """Dừng cleanup service."""
        if not self.is_running:
            return
        
        self.scheduler.shutdown()
        self.is_running = False
        logger.info("Cleanup service stopped")
    
    def run_cleanup(self):
        """Thực hiện cleanup process."""
        try:
            logger.info("Starting cleanup process...")
            
            # Cleanup logs
            logs_cleaned = self.cleanup_logs()
            
            # Cleanup data
            data_cleaned = self.cleanup_data()
            
            # Cleanup empty directories
            empty_dirs_cleaned = self.cleanup_empty_directories()
            
            logger.info(f"Cleanup completed - Logs: {logs_cleaned} files, "
                       f"Data: {data_cleaned} files, "
                       f"Empty dirs: {empty_dirs_cleaned}")
            
        except Exception as e:
            logger.error(f"Error during cleanup process: {e}")
    
    def cleanup_logs(self) -> int:
        """
        Dọn dẹp các file log cũ.
        
        Returns:
            Số lượng file đã xóa
        """
        if not self.logs_path.exists():
            return 0
        
        cutoff_date = datetime.now() - timedelta(days=self.logs_retention_days)
        files_cleaned = 0
        
        try:
            for file_path in self.logs_path.rglob("*"):
                if file_path.is_file():
                    # Check if file is older than retention period
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    if file_mtime < cutoff_date:
                        try:
                            file_path.unlink()
                            files_cleaned += 1
                            logger.debug(f"Removed old log file: {file_path}")
                        except Exception as e:
                            logger.error(f"Failed to remove log file {file_path}: {e}")
            
            logger.info(f"Cleaned up {files_cleaned} log files older than {self.logs_retention_days} days")
            
        except Exception as e:
            logger.error(f"Error cleaning up logs: {e}")
        
        return files_cleaned
    
    def cleanup_data(self) -> int:
        """
        Dọn dẹp các file dữ liệu cũ.
        
        Returns:
            Số lượng file đã xóa
        """
        if not self.data_path.exists():
            return 0
        
        cutoff_date = datetime.now() - timedelta(days=self.data_retention_days)
        files_cleaned = 0
        
        try:
            for file_path in self.data_path.rglob("*"):
                if file_path.is_file():
                    # Check if file is older than retention period
                    file_mtime = datetime.fromtimestamp(file_path.stat().st_mtime)
                    
                    if file_mtime < cutoff_date:
                        try:
                            file_path.unlink()
                            files_cleaned += 1
                            logger.debug(f"Removed old data file: {file_path}")
                        except Exception as e:
                            logger.error(f"Failed to remove data file {file_path}: {e}")
            
            logger.info(f"Cleaned up {files_cleaned} data files older than {self.data_retention_days} days")
            
        except Exception as e:
            logger.error(f"Error cleaning up data: {e}")
        
        return files_cleaned
    
    def cleanup_empty_directories(self) -> int:
        """
        Dọn dẹp các thư mục trống.
        
        Returns:
            Số lượng thư mục đã xóa
        """
        dirs_cleaned = 0
        
        try:
            # Check logs directory
            dirs_cleaned += self._remove_empty_dirs(self.logs_path)
            
            # Check data directory  
            dirs_cleaned += self._remove_empty_dirs(self.data_path)
            
            logger.info(f"Cleaned up {dirs_cleaned} empty directories")
            
        except Exception as e:
            logger.error(f"Error cleaning up empty directories: {e}")
        
        return dirs_cleaned
    
    def _remove_empty_dirs(self, path: Path) -> int:
        """
        Xóa các thư mục trống trong path.
        
        Args:
            path: Đường dẫn thư mục để kiểm tra
            
        Returns:
            Số lượng thư mục đã xóa
        """
        if not path.exists():
            return 0
        
        dirs_removed = 0
        
        try:
            # Walk through directories bottom-up
            for dir_path in sorted(path.rglob("*"), key=lambda x: len(x.parts), reverse=True):
                if dir_path.is_dir() and dir_path != path:
                    try:
                        # Try to remove directory if it's empty
                        dir_path.rmdir()
                        dirs_removed += 1
                        logger.debug(f"Removed empty directory: {dir_path}")
                    except OSError:
                        # Directory not empty, skip
                        pass
                    except Exception as e:
                        logger.error(f"Failed to remove directory {dir_path}: {e}")
        
        except Exception as e:
            logger.error(f"Error removing empty directories in {path}: {e}")
        
        return dirs_removed
    
    def force_cleanup(self):
        """Thực hiện cleanup ngay lập tức."""
        logger.info("Force cleanup requested")
        self.run_cleanup()
    
    def get_disk_usage(self) -> Dict[str, Dict[str, Any]]:
        """
        Lấy thông tin sử dụng disk cho logs và data.
        
        Returns:
            Dictionary chứa thông tin disk usage
        """
        usage_info = {}
        
        # Logs directory usage
        if self.logs_path.exists():
            usage_info["logs"] = self._get_directory_usage(self.logs_path)
        else:
            usage_info["logs"] = {"total_size": 0, "file_count": 0}
        
        # Data directory usage
        if self.data_path.exists():
            usage_info["data"] = self._get_directory_usage(self.data_path)
        else:
            usage_info["data"] = {"total_size": 0, "file_count": 0}
        
        return usage_info
    
    def _get_directory_usage(self, path: Path) -> Dict[str, Any]:
        """
        Tính toán disk usage cho một thư mục.
        
        Args:
            path: Đường dẫn thư mục
            
        Returns:
            Dictionary chứa thông tin usage
        """
        total_size = 0
        file_count = 0
        
        try:
            for file_path in path.rglob("*"):
                if file_path.is_file():
                    total_size += file_path.stat().st_size
                    file_count += 1
        except Exception as e:
            logger.error(f"Error calculating directory usage for {path}: {e}")
        
        return {
            "total_size": total_size,
            "total_size_mb": round(total_size / (1024 * 1024), 2),
            "file_count": file_count
        }
    
    def get_status(self) -> Dict[str, Any]:
        """
        Lấy trạng thái của cleanup service.
        
        Returns:
            Dictionary chứa trạng thái service
        """
        return {
            "enabled": self.enabled,
            "running": self.is_running,
            "schedule_hours": self.schedule_hours,
            "logs_retention_days": self.logs_retention_days,
            "data_retention_days": self.data_retention_days,
            "next_run": self.scheduler.get_job('cleanup_job').next_run_time.isoformat() if self.is_running else None,
            "disk_usage": self.get_disk_usage()
        }


class CleanupServiceManager:
    """
    Manager để quản lý cleanup service instance.
    """
    
    def __init__(self):
        self.service = None
    
    def initialize(self, config: Dict[str, Any]):
        """
        Khởi tạo cleanup service với cấu hình.
        
        Args:
            config: Cấu hình cleanup
        """
        if self.service is not None:
            self.stop()
        
        self.service = CleanupService(config)
    
    def start(self):
        """Khởi động cleanup service."""
        if self.service is not None:
            self.service.start()
    
    def stop(self):
        """Dừng cleanup service."""
        if self.service is not None:
            self.service.stop()
            self.service = None
    
    def force_cleanup(self):
        """Thực hiện cleanup ngay lập tức."""
        if self.service is not None:
            self.service.force_cleanup()
    
    def get_status(self) -> Dict[str, Any]:
        """Lấy trạng thái service."""
        if self.service is not None:
            return self.service.get_status()
        return {"enabled": False, "running": False}


# Global cleanup service manager
cleanup_manager = CleanupServiceManager() 