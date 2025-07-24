# src/core/async_data_manager.py
import threading
import logging
import time
from queue import Queue, Empty
from typing import Optional
import numpy as np
import serial

from ..sensors.hwt905_data_decoder import HWT905DataDecoder
from ..storage.storage_manager import StorageManager
from ..processing.data_processor import SensorDataProcessor
from ..sensors.hwt905_constants import PACKET_TYPE_ACC
from ..mqtt.publisher_factory import get_publisher
from ..mqtt.batch_publisher import BatchPublisher
from ..mqtt.scheduled_publisher import ScheduledPublisher
from ..core.connection_manager import SensorConnectionManager

logger = logging.getLogger(__name__)

def convert_numpy_to_native(data):
    """
    Hàm đệ quy để chuyển đổi tất cả các giátrị numpy.ndarray hoặc numpy number
    trong một cấu trúc dữ liệu (dict, list) thành kiểu dữ liệu gốc của Python.
    """
    if isinstance(data, dict):
        return {k: convert_numpy_to_native(v) for k, v in data.items()}
    elif isinstance(data, list):
        return [convert_numpy_to_native(i) for i in data]
    elif isinstance(data, np.ndarray):
        return data.tolist()
    elif isinstance(data, (np.generic, np.number)):
        return data.item()
    return data

class SerialReaderThread(threading.Thread):
    """
    Luồng chuyên quản lý kết nối cảm biến, tự động kết nối lại,
    đọc dữ liệu thô từ cổng serial và đưa vào hàng đợi.
    """
    def __init__(self, 
                 connection_manager: SensorConnectionManager,
                 data_decoder: HWT905DataDecoder, 
                 raw_data_queue: Queue, 
                 running_flag: threading.Event):
        super().__init__(daemon=True, name="SerialReaderThread")
        self.connection_manager = connection_manager
        self.data_decoder = data_decoder
        self.raw_data_queue = raw_data_queue
        self.running_flag = running_flag
        self.raw_packet_count = 0
        self.last_log_time = time.time()

    def run(self):
        logger.info("Luồng đọc Serial (tự phục hồi) đã bắt đầu.")
        
        while self.running_flag.is_set():
            # --- Vòng lặp quản lý kết nối ---
            ser_instance = self.connection_manager.establish_connection()
            if not ser_instance:
                # establish_connection là một vòng lặp vô tận,
                # nó chỉ trả về None nếu có lỗi không mong muốn hoặc ứng dụng dừng.
                logger.warning("[Reader] Không thể thiết lập kết nối. Sẽ thử lại.")
                time.sleep(self.connection_manager.reconnect_delay_s)
                continue

            # Đảm bảo baudrate đúng, nếu sai nó sẽ tự cấu hình và ngắt kết nối
            if not self.connection_manager.ensure_correct_config():
                logger.info("[Reader] Cảm biến đã được cấu hình lại. Bắt đầu quá trình kết nối lại.")
                # connection_manager.close_connection() đã được gọi bên trong
                continue 
            
            # Cập nhật ser_instance cho data_decoder và xóa bộ đệm
            self.data_decoder.set_ser_instance(ser_instance)
            try:
                if ser_instance.in_waiting > 0:
                    ser_instance.reset_input_buffer()
                    logger.debug(f"[Reader] Đã xóa {ser_instance.in_waiting} bytes rác khỏi bộ đệm khi kết nối.")
            except Exception as e:
                logger.warning(f"[Reader] Không thể xóa bộ đệm đầu vào: {e}")

            logger.info("[Reader] Cảm biến đã sẵn sàng. Bắt đầu đọc dữ liệu...")

            # --- Vòng lặp đọc dữ liệu ---
            while self.running_flag.is_set():
                try:
                    raw_packet = self.data_decoder.read_raw_packet()
                    if raw_packet:
                        self.raw_data_queue.put(raw_packet)
                        self.raw_packet_count += 1
                    else:
                        # Kiểm tra xem có phải do mất kết nối không
                        if self.data_decoder.ser is None or not self.data_decoder.ser.is_open:
                            logger.warning("[Reader] Phát hiện mất kết nối serial. Bắt đầu quá trình kết nối lại...")
                            break # Thoát vòng lặp đọc, quay lại vòng lặp kết nối

                        # Ngủ một chút nếu không có dữ liệu để tránh chiếm dụng CPU
                        time.sleep(0.0001)

                    current_time = time.time()
                    if current_time - self.last_log_time >= 5.0:
                        rate = self.raw_packet_count / (current_time - self.last_log_time)
                        logger.info(f"[Reader] Tốc độ đọc: {rate:.2f} packets/s. Queue size: {self.raw_data_queue.qsize()}")
                        self.raw_packet_count = 0
                        self.last_log_time = current_time

                except serial.SerialException as e:
                    logger.error(f"[Reader] Lỗi Serial trong khi đọc: {e}. Bắt đầu quá trình kết nối lại...")
                    break # Thoát vòng lặp đọc, quay lại vòng lặp kết nối
                except Exception as e:
                    logger.error(f"[Reader] Lỗi không mong muốn trong luồng đọc: {e}", exc_info=True)
                    break # Thoát vòng lặp đọc, quay lại vòng lặp kết nối
            
            # Dọn dẹp trước khi kết nối lại
            logger.info("[Reader] Đang đóng kết nối hiện tại...")
            self.connection_manager.close_connection()
            # Vòng lặp chính (while self.running_flag.is_set()) sẽ lặp lại và bắt đầu kết nối lại

        logger.info("Luồng đọc Serial đã dừng.")

class DecoderThread(threading.Thread):
    """
    Luồng chuyên lấy dữ liệu thô từ hàng đợi, giải mã, lưu trữ dữ liệu đã giải mã
    và đẩy dữ liệu đã giải mã vào hàng đợi khác để xử lý.
    """
    def __init__(self, data_decoder: HWT905DataDecoder, 
                 raw_data_queue: Queue, 
                 decoded_data_queue: Queue,
                 running_flag: threading.Event,
                 decoded_storage_manager: Optional[StorageManager] = None):
        super().__init__(daemon=True, name="DecoderThread")
        self.data_decoder = data_decoder
        self.raw_data_queue = raw_data_queue
        self.decoded_data_queue = decoded_data_queue
        self.running_flag = running_flag
        self.decoded_storage_manager = decoded_storage_manager
        
        self.decoded_packet_count = 0
        self.last_log_time = time.time()

    def run(self):
        logger.info("Luồng Giải mã (DecoderThread) đã bắt đầu.")
        while self.running_flag.is_set() or not self.raw_data_queue.empty():
            try:
                raw_packet = self.raw_data_queue.get(timeout=1)
                
                # 1. Decode
                packet_info = self.data_decoder.decode_raw_packet(raw_packet)

                if not packet_info or "error" in packet_info:
                    if packet_info:
                        logger.warning(f"[Decoder] Lỗi giải mã gói tin: {packet_info.get('message', 'Unknown')}")
                    self.raw_data_queue.task_done()
                    continue
                
                # Chỉ xử lý các gói gia tốc
                if packet_info.get("type") != PACKET_TYPE_ACC:
                    self.raw_data_queue.task_done()
                    continue
                
                self.decoded_packet_count += 1

                acc_data = {
                    'acc_x': packet_info.get("acc_x"),
                    'acc_y': packet_info.get("acc_y"),
                    'acc_z': packet_info.get("acc_z")
                }
                current_timestamp = time.time()
                
                # Tạo một tuple chứa timestamp và dữ liệu để đưa vào hàng đợi
                decoded_item = (current_timestamp, acc_data)

                # 2. Lưu dữ liệu đã giải mã (nếu được cấu hình)
                if self.decoded_storage_manager:
                    self.decoded_storage_manager.store_and_prepare_for_transmission(acc_data, current_timestamp)

                # 3. Đẩy dữ liệu đã giải mã vào hàng đợi để xử lý
                if self.decoded_data_queue:
                    self.decoded_data_queue.put(decoded_item)

                self.raw_data_queue.task_done()

                # Ghi log định kỳ
                current_time = time.time()
                if current_time - self.last_log_time >= 5.0:
                    decode_rate = self.decoded_packet_count / (current_time - self.last_log_time)
                    q_info = f"Queue raw: {self.raw_data_queue.qsize()}"
                    if self.decoded_data_queue:
                        q_info += f", decoded: {self.decoded_data_queue.qsize()}"
                    logger.info(f"[Decoder] Tốc độ: {decode_rate:.2f} packets/s. {q_info}")
                    self.decoded_packet_count = 0
                    self.last_log_time = current_time

            except Empty:
                if not self.running_flag.is_set():
                    logger.info("Hàng đợi thô trống và cờ đã tắt, thoát luồng Decoder.")
                    break
                continue
            except Exception as e:
                logger.error(f"[Decoder] Lỗi trong luồng Decoder: {e}", exc_info=True)
                # Không clear running_flag để main thread có thể xử lý reconnection
                break
                
        logger.info("Luồng Giải mã (DecoderThread) đã dừng.")
        # Báo hiệu cho luồng Processor rằng không còn dữ liệu mới
        if self.decoded_data_queue:
            self.decoded_data_queue.put(None)


class ProcessorThread(threading.Thread):
    """
    Luồng chuyên lấy dữ liệu đã giải mã từ hàng đợi, xử lý,
    lưu trữ kết quả và đẩy vào hàng đợi MQTT (nếu được kích hoạt).
    """
    def __init__(self, 
                 decoded_data_queue: Queue,
                 running_flag: threading.Event,
                 sensor_data_processor: SensorDataProcessor,
                 processed_storage_manager: Optional[StorageManager] = None,
                 mqtt_queue: Optional[Queue] = None):
        super().__init__(daemon=True, name="ProcessorThread")
        self.decoded_data_queue = decoded_data_queue
        self.running_flag = running_flag
        self.sensor_data_processor = sensor_data_processor
        self.processed_storage_manager = processed_storage_manager
        self.mqtt_queue = mqtt_queue
        
        self.processed_packet_count = 0
        self.last_log_time = time.time()

    def run(self):
        logger.info("Luồng Xử lý (ProcessorThread) đã bắt đầu.")
        while self.running_flag.is_set() or not self.decoded_data_queue.empty():
            try:
                # Lấy dữ liệu từ hàng đợi đã giải mã
                decoded_item = self.decoded_data_queue.get(timeout=1)

                # Kiểm tra tín hiệu kết thúc
                if decoded_item is None:
                    logger.info("[Processor] Nhận được tín hiệu kết thúc từ Decoder.")
                    break
                
                timestamp, acc_data = decoded_item
                
                # 1. Xử lý dữ liệu
                processed_results = self.sensor_data_processor.process_new_sample(
                    acc_data['acc_x'], acc_data['acc_y'], acc_data['acc_z']
                )

                # Nếu có kết quả, tiếp tục xử lý
                if processed_results:
                    self.processed_packet_count += 1
                    
                    # 2. Thêm timestamp vào kết quả
                    processed_results['ts'] = timestamp

                    # 3. Lưu dữ liệu đã xử lý (nếu được cấu hình)
                    if self.processed_storage_manager:
                        self.processed_storage_manager.store_and_prepare_for_transmission(processed_results, timestamp)

                    # 4. Đẩy vào hàng đợi MQTT (nếu được cấu hình)
                    if self.mqtt_queue:
                        # Chuyển đổi tất cả các giá trị numpy sang kiểu Python gốc
                        native_data = convert_numpy_to_native(processed_results)
                        
                        # Tạo payload MQTT chỉ chứa các trường cần thiết
                        mqtt_payload = {
                            'ts': native_data.get('ts'),
                            'disp_x': native_data.get('disp_x'),
                            'disp_y': native_data.get('disp_y'),
                            'disp_z': native_data.get('disp_z'),
                            'dominant_freq_x': native_data.get('dominant_freq_x'),
                            'dominant_freq_y': native_data.get('dominant_freq_y'),
                            'dominant_freq_z': native_data.get('dominant_freq_z'),
                        }
                        self.mqtt_queue.put(mqtt_payload)
                
                self.decoded_data_queue.task_done()

                # Ghi log định kỳ
                current_time = time.time()
                if current_time - self.last_log_time >= 5.0:
                    process_rate = self.processed_packet_count / (current_time - self.last_log_time)
                    q_info = f"Queue decoded: {self.decoded_data_queue.qsize()}"
                    if self.mqtt_queue:
                        q_info += f", mqtt: {self.mqtt_queue.qsize()}"
                    logger.info(f"[Processor] Tốc độ: {process_rate:.2f} packets/s. {q_info}")
                    self.processed_packet_count = 0
                    self.last_log_time = current_time

            except Empty:
                if not self.running_flag.is_set():
                    logger.info("Hàng đợi giải mã trống và cờ đã tắt, thoát luồng Processor.")
                    break
                continue
            except Exception as e:
                logger.error(f"[Processor] Lỗi trong luồng Processor: {e}", exc_info=True)
                # Không clear running_flag để main thread có thể xử lý reconnection
                break
        
        # Báo hiệu cho luồng MQTT rằng không còn dữ liệu mới
        if self.mqtt_queue:
            self.mqtt_queue.put(None)
                
        logger.info("Luồng Xử lý (ProcessorThread) đã dừng.")


class MqttPublisherThread(threading.Thread):
    """
    Luồng chuyên lấy dữ liệu đã xử lý từ hàng đợi và gửi qua MQTT.
    """
    def __init__(self, mqtt_queue: Queue, running_flag: threading.Event, mode: str = "continuous"):
        super().__init__(daemon=True, name="MqttPublisherThread")
        self.mqtt_queue = mqtt_queue
        self.running_flag = running_flag
        self.mode = mode
        self.publisher = get_publisher(mode=mode)
        self.sent_packet_count = 0
        self.last_log_time = time.time()

    def run(self):
        if not self.publisher:
            logger.error("[MQTT Publisher] Không thể khởi tạo publisher. Luồng đang dừng.")
            return

        self.publisher.connect()
        logger.info("Luồng MQTT Publisher đã bắt đầu.")

        while self.running_flag.is_set() or not self.mqtt_queue.empty():
            try:
                processed_data = self.mqtt_queue.get(timeout=1)

                if processed_data is None:
                    logger.info("[MQTT Publisher] Nhận được tín hiệu kết thúc từ Processor.")
                    break
                
                self.publisher.publish(processed_data)
                self.sent_packet_count += 1
                self.mqtt_queue.task_done()

                # Ghi log định kỳ
                current_time = time.time()
                if current_time - self.last_log_time >= 5.0:
                    send_rate = self.sent_packet_count / (current_time - self.last_log_time)
                    logger.info(f"[MQTT Publisher] Tốc độ gửi: {send_rate:.2f} packets/s. Queue size: {self.mqtt_queue.qsize()}")
                    self.sent_packet_count = 0
                    self.last_log_time = current_time

            except Empty:
                if not self.running_flag.is_set():
                    logger.info("Hàng đợi MQTT trống và cờ đã tắt, thoát luồng Publisher.")
                    break
                continue
            except Exception as e:
                logger.error(f"[MQTT Publisher] Lỗi trong luồng Publisher: {e}", exc_info=True)
        
        # Gửi nốt dữ liệu còn lại trong buffer (nếu là batch mode)
        if isinstance(self.publisher, BatchPublisher):
            self.publisher.flush()
        
        # Disconnect publisher
        if self.publisher:
            self.publisher.disconnect()
            
        logger.info("Luồng MQTT Publisher đã dừng.")