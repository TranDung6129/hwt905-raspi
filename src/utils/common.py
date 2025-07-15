import json
import os
from pathlib import Path
import random
from typing import Dict, Any
import numpy as np
from .config_loader import load_config as load_config_new, load_config_legacy

PACKET_TYPE_ACC = 0x01  # Giả sử đây là mã loại gói dữ liệu gia tốc

def load_config(file_path: str = None) -> dict:
    """
    Tải cấu hình từ các nguồn khác nhau.
    
    Args:
        file_path (str, optional): Đường dẫn đến file cấu hình JSON (legacy).
                                  Nếu None, sẽ tải cấu hình mới từ .env và YAML.

    Returns:
        dict: Một dictionary chứa dữ liệu cấu hình.

    Raises:
        FileNotFoundError: Nếu file cấu hình không tìm thấy.
        json.JSONDecodeError: Nếu file JSON không hợp lệ.
        Exception: Các lỗi khác trong quá trình đọc file.
    """
    if file_path is None:
        # Use new configuration system
        return load_config_new("all")
    else:
        # Use legacy JSON configuration system
        return load_config_legacy(file_path)

def ensure_directory_exists(path: str):
    """
    Đảm bảo thư mục tồn tại. Nếu không, nó sẽ được tạo ra.

    Args:
        path (str): Đường dẫn thư mục cần kiểm tra/tạo.
    """
    Path(path).mkdir(parents=True, exist_ok=True)

def bytes_to_hex_string(data_bytes: bytes) -> str:
    """
    Chuyển đổi một chuỗi bytes thành chuỗi hex.

    Args:
        data_bytes (bytes): Chuỗi bytes đầu vào.

    Returns:
        str: Chuỗi hex tương ứng.
    """
    return data_bytes.hex().upper()

def hex_string_to_bytes(hex_str: str) -> bytes:
    """
    Chuyển đổi một chuỗi hex thành chuỗi bytes.

    Args:
        hex_str (str): Chuỗi hex đầu vào.

    Returns:
        bytes: Chuỗi bytes tương ứng.
    """
    return bytes.fromhex(hex_str)

def generate_mock_acc_data(time_elapsed: float) -> Dict[str, Any]:
    """
    Tạo một gói dữ liệu gia tốc giả lập (tương tự như từ HWT905DataDecoder).
    """
    # Gia tốc (dao động xung quanh 0, trục Z xung quanh 1g)
    acc_x = 0.1 * np.sin(2 * np.pi * 1 * time_elapsed) + random.uniform(-0.01, 0.01)
    acc_y = 0.05 * np.cos(2 * np.pi * 0.5 * time_elapsed) + random.uniform(-0.01, 0.01)
    acc_z = 1.0 + 0.02 * np.sin(2 * np.pi * 2 * time_elapsed) + random.uniform(-0.01, 0.01)
    
    # Mô phỏng cấu trúc trả về của data_decoder
    return {
        "raw_packet": b'', # Giả lập gói raw
        "header": 0x55,
        "type": PACKET_TYPE_ACC,
        "type_name": "ACCELERATION",
        "payload": b'',
        "checksum": 0x00,
        "acc_x": acc_x,
        "acc_y": acc_y,
        "acc_z": acc_z,
        "temperature": 25.0 + random.uniform(-1,1),
    }
