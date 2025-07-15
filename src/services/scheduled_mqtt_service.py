import logging
import threading
import time
import json
import os
from datetime import datetime
from typing import Optional, Dict, Any, List
from queue import Queue, Empty
import pandas as pd

from ..mqtt.base_publisher import BasePublisher
from ..utils.common import load_config


class ScheduledMqttService:
    """Service để gửi dữ liệu định kỳ từ storage lên MQTT"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(__name__)
        self.running = False
        self.thread: Optional[threading.Thread] = None
        self.mqtt_client: Optional[BasePublisher] = None
        
        # Cấu hình từ config
        self.enabled = config.get("enabled", False)
        self.interval_seconds = config.get("interval_seconds", 60)  # Mặc định 60 giây
        self.data_source_dir = config.get("data_source_dir", "data/processed_data")
        self.batch_size = config.get("batch_size", 100)  # Số record gửi mỗi lần
        self.delete_after_send = config.get("delete_after_send", False)
        self.mqtt_topic = config.get("mqtt_topic", "sensor/batch_data")
        
        # Theo dõi file đã xử lý
        self.processed_files = set()
        self.last_processed_timestamp = None
        
        self.logger.info(f"ScheduledMqttService initialized: enabled={self.enabled}, interval={self.interval_seconds}s")
    
    def start(self):
        """Khởi động service"""
        if not self.enabled:
            self.logger.info("ScheduledMqttService is disabled")
            return
        
        if self.running:
            self.logger.warning("ScheduledMqttService is already running")
            return
        
        self.logger.info("Starting ScheduledMqttService...")
        self.running = True
        
        # Khởi tạo MQTT client
        try:
            mqtt_config = load_config().get("mqtt", {})
            self.mqtt_client = BasePublisher(mqtt_config)
            self.mqtt_client.connect()
            self.logger.info("MQTT client connected for scheduled service")
        except Exception as e:
            self.logger.error(f"Failed to connect MQTT client: {e}")
            self.running = False
            return
        
        # Khởi động thread
        self.thread = threading.Thread(target=self._run, name="ScheduledMqttService")
        self.thread.daemon = True
        self.thread.start()
        
        self.logger.info("ScheduledMqttService started successfully")
    
    def stop(self):
        """Dừng service"""
        if not self.running:
            return
        
        self.logger.info("Stopping ScheduledMqttService...")
        self.running = False
        
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=5)
            if self.thread.is_alive():
                self.logger.warning("ScheduledMqttService thread did not stop within timeout")
        
        if self.mqtt_client:
            try:
                self.mqtt_client.disconnect()
                self.logger.info("MQTT client disconnected")
            except Exception as e:
                self.logger.error(f"Error disconnecting MQTT client: {e}")
        
        self.logger.info("ScheduledMqttService stopped")
    
    def _run(self):
        """Vòng lặp chính của service"""
        self.logger.info("ScheduledMqttService main loop started")
        
        while self.running:
            try:
                # Gửi dữ liệu
                self._send_batch_data()
                
                # Đợi interval
                for _ in range(self.interval_seconds):
                    if not self.running:
                        break
                    time.sleep(1)
                        
            except Exception as e:
                self.logger.error(f"Error in ScheduledMqttService main loop: {e}", exc_info=True)
                time.sleep(5)  # Đợi 5 giây trước khi thử lại
        
        self.logger.info("ScheduledMqttService main loop ended")
    
    def _send_batch_data(self):
        """Gửi dữ liệu batch lên MQTT"""
        try:
            # Tìm và xử lý các file dữ liệu
            data_files = self._find_new_data_files()
            
            if not data_files:
                self.logger.debug("No new data files to process")
                return
            
            self.logger.info(f"Found {len(data_files)} new data files to process")
            
            for file_path in data_files:
                if not self.running:
                    break
                
                try:
                    self._process_data_file(file_path)
                except Exception as e:
                    self.logger.error(f"Error processing file {file_path}: {e}", exc_info=True)
                    
        except Exception as e:
            self.logger.error(f"Error in _send_batch_data: {e}", exc_info=True)
    
    def _find_new_data_files(self) -> List[str]:
        """Tìm các file dữ liệu mới cần xử lý"""
        if not os.path.exists(self.data_source_dir):
            self.logger.warning(f"Data source directory does not exist: {self.data_source_dir}")
            return []
        
        new_files = []
        
        try:
            for filename in os.listdir(self.data_source_dir):
                if filename.endswith('.csv') and filename not in self.processed_files:
                    file_path = os.path.join(self.data_source_dir, filename)
                    
                    # Kiểm tra xem file có được tạo sau lần xử lý cuối không
                    if self.last_processed_timestamp:
                        file_mtime = os.path.getmtime(file_path)
                        if file_mtime <= self.last_processed_timestamp:
                            continue
                    
                    new_files.append(file_path)
            
            # Sắp xếp theo thời gian tạo file (cũ nhất trước)
            new_files.sort(key=lambda x: os.path.getmtime(x))
            
        except Exception as e:
            self.logger.error(f"Error finding new data files: {e}", exc_info=True)
        
        return new_files
    
    def _process_data_file(self, file_path: str):
        """Xử lý một file dữ liệu"""
        try:
            self.logger.info(f"Processing data file: {file_path}")
            
            # Đọc dữ liệu từ file CSV
            df = pd.read_csv(file_path)
            
            if df.empty:
                self.logger.warning(f"Data file is empty: {file_path}")
                self._mark_file_as_processed(file_path)
                return
            
            # Chia dữ liệu thành các batch
            total_records = len(df)
            self.logger.info(f"File {file_path} contains {total_records} records")
            
            batch_count = 0
            for i in range(0, total_records, self.batch_size):
                if not self.running:
                    break
                
                batch_df = df.iloc[i:i + self.batch_size]
                batch_data = self._prepare_batch_data(batch_df, file_path, batch_count)
                
                # Gửi batch lên MQTT
                success = self._send_mqtt_batch(batch_data)
                
                if success:
                    batch_count += 1
                    self.logger.debug(f"Sent batch {batch_count} from {file_path} ({len(batch_df)} records)")
                else:
                    self.logger.error(f"Failed to send batch {batch_count} from {file_path}")
                    return  # Dừng xử lý file này nếu gửi thất bại
            
            # Đánh dấu file đã xử lý
            self._mark_file_as_processed(file_path)
            
            # Xóa file nếu được cấu hình
            if self.delete_after_send:
                try:
                    os.remove(file_path)
                    self.logger.info(f"Deleted processed file: {file_path}")
                except Exception as e:
                    self.logger.error(f"Error deleting file {file_path}: {e}")
            
            self.logger.info(f"Successfully processed file {file_path} ({batch_count} batches sent)")
            
        except Exception as e:
            self.logger.error(f"Error processing data file {file_path}: {e}", exc_info=True)
    
    def _prepare_batch_data(self, df: pd.DataFrame, file_path: str, batch_index: int) -> Dict[str, Any]:
        """Chuẩn bị dữ liệu batch để gửi"""
        # Chuyển DataFrame thành list of dictionaries
        records = df.to_dict('records')
        
        # Tạo metadata
        metadata = {
            "source_file": os.path.basename(file_path),
            "batch_index": batch_index,
            "record_count": len(records),
            "timestamp": datetime.now().isoformat(),
            "data_type": "processed_batch"
        }
        
        # Tạo payload
        batch_data = {
            "metadata": metadata,
            "data": records
        }
        
        return batch_data
    
    def _send_mqtt_batch(self, batch_data: Dict[str, Any]) -> bool:
        """Gửi batch data lên MQTT"""
        try:
            if not self.mqtt_client or not self.mqtt_client.client.is_connected():
                self.logger.error("MQTT client is not connected")
                return False
            
            # Chuyển thành JSON
            json_payload = json.dumps(batch_data, ensure_ascii=False)
            
            # Gửi lên MQTT
            result = self.mqtt_client.client.publish(
                self.mqtt_topic,
                json_payload,
                qos=1  # Đảm bảo tin nhắn được gửi
            )
            
            if result.rc == 0:
                self.logger.debug(f"Successfully sent batch to MQTT topic: {self.mqtt_topic}")
                return True
            else:
                self.logger.error(f"Failed to send batch to MQTT: {result.rc}")
                return False
                
        except Exception as e:
            self.logger.error(f"Error sending MQTT batch: {e}", exc_info=True)
            return False
    
    def _mark_file_as_processed(self, file_path: str):
        """Đánh dấu file đã được xử lý"""
        filename = os.path.basename(file_path)
        self.processed_files.add(filename)
        self.last_processed_timestamp = time.time()
        self.logger.debug(f"Marked file as processed: {filename}")


class ScheduledMqttServiceManager:
    """Manager để quản lý ScheduledMqttService"""
    
    def __init__(self):
        self.service: Optional[ScheduledMqttService] = None
        self.logger = logging.getLogger(__name__)
    
    def initialize(self, config: Dict[str, Any]):
        """Khởi tạo service với cấu hình"""
        try:
            self.service = ScheduledMqttService(config)
            self.logger.info("ScheduledMqttServiceManager initialized")
        except Exception as e:
            self.logger.error(f"Failed to initialize ScheduledMqttServiceManager: {e}")
            raise
    
    def start(self):
        """Khởi động service"""
        if self.service:
            self.service.start()
        else:
            self.logger.warning("ScheduledMqttService not initialized")
    
    def stop(self):
        """Dừng service"""
        if self.service:
            self.service.stop()
        else:
            self.logger.warning("ScheduledMqttService not initialized")


# Global instance
scheduled_mqtt_manager = ScheduledMqttServiceManager()
