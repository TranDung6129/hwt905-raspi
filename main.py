import logging
import time
import json
import threading
import signal
import sys
from queue import Queue
from typing import Optional

# Import các module và lớp cần thiết
from src.utils.common import load_config
from src.utils.logger_setup import setup_logging
from src.core.connection_manager import SensorConnectionManager
from src.sensors.hwt905_data_decoder import HWT905DataDecoder
from src.processing.data_processor import SensorDataProcessor
from src.storage.storage_manager import StorageManager
from src.core.async_data_manager import SerialReaderThread, DecoderThread, ProcessorThread, MqttPublisherThread
from src.services import cleanup_manager, scheduled_mqtt_manager

# Cờ để điều khiển vòng lặp chính
_running_flag = threading.Event()

def signal_handler(signum, frame):
    """Xử lý tín hiệu dừng một cách graceful"""
    logger = logging.getLogger(__name__)
    logger.info(f"Nhận tín hiệu {signum}. Đang dừng ứng dụng...")
    _running_flag.clear()
    
    # Dừng cleanup service
    try:
        cleanup_manager.stop()
        logger.info("Cleanup service đã dừng")
    except Exception as e:
        logger.error(f"Lỗi khi dừng cleanup service: {e}")
    
    # Dừng scheduled MQTT service
    try:
        scheduled_mqtt_manager.stop()
        logger.info("Scheduled MQTT service đã dừng")
    except Exception as e:
        logger.error(f"Lỗi khi dừng scheduled MQTT service: {e}")

def main():
    # 1. Tải cấu hình ứng dụng từ .env và YAML files
    try:
        app_config = load_config()  # Sử dụng hệ thống cấu hình mới
    except Exception as e:
        print(f"FATAL ERROR: Không thể tải cấu hình ứng dụng: {e}")
        exit(1)

    # 2. Thiết lập hệ thống ghi log
    log_config = app_config.get("logging", {})
    setup_logging(
        log_file_path=log_config.get("log_file_path", "logs/application.log"),
        log_level=log_config.get("log_level", "INFO"),
        max_bytes=log_config.get("max_bytes", 10485760),
        backup_count=log_config.get("backup_count", 5)
    )
    logger = logging.getLogger(__name__)
    logger.info("Ứng dụng Backend IMU đã khởi động.")
    logger.debug(f"Đã tải cấu hình: {app_config}")

    # Thiết lập signal handlers để dừng ứng dụng một cách an toàn
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    _running_flag.set()
    
    # 2.5. Khởi tạo và khởi động cleanup service
    cleanup_config = app_config.get("cleanup", {})
    if cleanup_config.get("enabled", True):
        logger.info("Khởi tạo cleanup service...")
        cleanup_manager.initialize(cleanup_config)
        cleanup_manager.start()

    # 3. Đọc cấu hình điều khiển quy trình
    process_control_config = app_config.get("process_control", {})
    decoding_enabled = process_control_config.get("decoding", True)
    processing_enabled = process_control_config.get("processing", True)
    mqtt_sending_enabled = process_control_config.get("mqtt_sending", True)
    mqtt_mode = process_control_config.get("mqtt_mode", "continuous")  # continuous hoặc scheduled
    logger.info(f"Cấu hình quy trình: Decoding={decoding_enabled}, Processing={processing_enabled}, MQTT Sending={mqtt_sending_enabled}, MQTT Mode={mqtt_mode}")

    # 4. Khởi tạo các thành phần cốt lõi
    sensor_config = app_config["sensor"]
    
    # ConnectionManager sẽ được quản lý bởi SerialReaderThread
    connection_manager = SensorConnectionManager(
        sensor_config=sensor_config,
        debug=(logger.level <= logging.DEBUG)
    )
    
    # DataDecoder không cần ser_instance lúc khởi tạo nữa, ReaderThread sẽ cung cấp sau
    data_decoder = HWT905DataDecoder(debug=(logger.level <= logging.DEBUG))
    
    target_output_rate = sensor_config["default_output_rate_hz"]
    app_config["processing"]["dt_sensor_actual"] = 1.0 / target_output_rate

    # 5. Khởi tạo các trình quản lý lưu trữ (nếu được bật)
    storage_config = app_config.get("data_storage", {"enabled": False})
    decoded_storage_manager: Optional[StorageManager] = None
    if decoding_enabled and storage_config.get("enabled", False):
        logger.info("Khởi tạo StorageManager cho dữ liệu DECODED.")
        decoded_storage_manager = StorageManager(
            storage_config,
            data_type="decoded",
            fields_to_write=['acc_x', 'acc_y', 'acc_z']
        )

    sensor_data_processor: Optional[SensorDataProcessor] = None
    processed_storage_manager: Optional[StorageManager] = None
    if processing_enabled:
        logger.info("Khởi tạo SensorDataProcessor.")
        processing_config = app_config["processing"]
        sensor_data_processor = SensorDataProcessor(
            dt_sensor=processing_config["dt_sensor_actual"],
            gravity_g=processing_config["gravity_g"],
            acc_filter_type=processing_config.get("acc_filter_type"),
            acc_filter_param=processing_config.get("acc_filter_param"),
            rls_sample_frame_size=processing_config["rls_sample_frame_size"],
            rls_calc_frame_multiplier=processing_config["rls_calc_frame_multiplier"],
            rls_filter_q=processing_config["rls_filter_q"],
            fft_n_points=processing_config["fft_n_points"],
            fft_min_freq_hz=processing_config["fft_min_freq_hz"],
            fft_max_freq_hz=processing_config["fft_max_freq_hz"]
        )
        if storage_config.get("enabled", False):
            logger.info("Khởi tạo StorageManager cho dữ liệu PROCESSED.")
            processed_fields_to_write = [
                'vel_x', 'vel_y', 'vel_z', 'disp_x', 'disp_y', 'disp_z',
                'dominant_freq_x', 'dominant_freq_y', 'dominant_freq_z'
            ]
            processed_storage_manager = StorageManager(
                storage_config, data_type="processed", fields_to_write=processed_fields_to_write
            )

    # 6. Thiết lập pipeline với các hàng đợi
    raw_data_queue = Queue(maxsize=8192)
    decoded_data_queue = Queue(maxsize=8192) if processing_enabled else None
    # Chỉ tạo mqtt_queue nếu MQTT mode là continuous
    mqtt_queue = Queue(maxsize=8192) if mqtt_sending_enabled and mqtt_mode == "continuous" else None

    # 7. Khởi tạo các luồng xử lý
    
    # Luồng 1: Tự quản lý kết nối và đọc dữ liệu
    reader_thread = SerialReaderThread(
        connection_manager=connection_manager,
        data_decoder=data_decoder,
        raw_data_queue=raw_data_queue,
        running_flag=_running_flag
    )
    
    # Luồng 2: Giải mã
    decoder_thread = DecoderThread(
        data_decoder=data_decoder,
        raw_data_queue=raw_data_queue,
        decoded_data_queue=decoded_data_queue,
        running_flag=_running_flag,
        decoded_storage_manager=decoded_storage_manager
    )

    # Luồng 3: Xử lý (nếu được bật)
    processor_thread: Optional[ProcessorThread] = None
    if processing_enabled and sensor_data_processor and decoded_data_queue:
        processor_thread = ProcessorThread(
            decoded_data_queue=decoded_data_queue,
            running_flag=_running_flag,
            sensor_data_processor=sensor_data_processor,
            processed_storage_manager=processed_storage_manager,
            mqtt_queue=mqtt_queue
        )

    # Luồng 4: Gửi MQTT (nếu được bật và mode là continuous)
    mqtt_publisher_thread: Optional[MqttPublisherThread] = None
    if mqtt_sending_enabled and mqtt_mode == "continuous" and mqtt_queue:
        mqtt_publisher_thread = MqttPublisherThread(
            mqtt_queue=mqtt_queue,
            running_flag=_running_flag
        )

    # Khởi động scheduled MQTT service (nếu được bật và mode là scheduled)
    if mqtt_sending_enabled and mqtt_mode == "scheduled":
        scheduled_mqtt_config = app_config.get("scheduled_mqtt", {})
        if scheduled_mqtt_config.get("enabled", False):
            logger.info("Khởi tạo scheduled MQTT service...")
            scheduled_mqtt_manager.initialize(scheduled_mqtt_config)
            scheduled_mqtt_manager.start()
        else:
            logger.warning("MQTT mode is 'scheduled' but scheduled_mqtt.enabled is False")

    # 8. Chạy các luồng
    threads = [t for t in [reader_thread, decoder_thread, processor_thread, mqtt_publisher_thread] if t]
    logger.info("Bắt đầu các luồng xử lý...")
    for thread in threads:
        thread.start()

    # 9. Vòng lặp chính chỉ cần đợi cho đến khi ứng dụng được yêu cầu dừng
    try:
        while _running_flag.is_set():
            # Kiểm tra trạng thái của các luồng, nếu có luồng nào chết bất thường thì dừng ứng dụng
            for thread in threads:
                if not thread.is_alive():
                    logger.critical(f"Luồng {thread.name} đã dừng đột ngột! Dừng ứng dụng.")
                    _running_flag.clear()
                    break
            time.sleep(1)
    except KeyboardInterrupt:
        logger.info("Nhận tín hiệu dừng (Ctrl+C).")
    except Exception as e:
        logger.error(f"Lỗi không mong muốn trong vòng lặp chính: {e}", exc_info=True)
    finally:
        logger.info("Bắt đầu quá trình dừng ứng dụng...")
        _running_flag.clear()

    # 10. Đợi các luồng kết thúc
    logger.info("Đang đợi các luồng kết thúc...")
    for thread in threads:
        thread.join(timeout=5)
        if thread.is_alive():
            logger.warning(f"Luồng {thread.name} không kết thúc sau 5 giây.")

    # 11. Dọn dẹp tài nguyên
    logger.info("Đang dọn dẹp tài nguyên...")
    if connection_manager:
        connection_manager.close_connection() # Đảm bảo kết nối cuối cùng được đóng
    if decoded_storage_manager:
        decoded_storage_manager.close()
    if processed_storage_manager:
        processed_storage_manager.close()
    
    logger.info("Ứng dụng Backend IMU đã dừng.")

if __name__ == '__main__':
    main()