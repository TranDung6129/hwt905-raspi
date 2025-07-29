# HWT905 IoT AI Pipeline

## Tổng quan

HWT905 IoT AI Pipeline là một hệ thống IoT hoàn chỉnh được thiết kế để thu thập, xử lý, lưu trữ và phân tích dữ liệu cảm biến từ thiết bị HWT905 IMU. Hệ thống tích hợp AI/ML để huấn luyện mô hình, triển khai edge inference và giám sát toàn diện với Prometheus và Grafana.

## Kiến trúc hệ thống

### Sơ đồ kiến trúc

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Raspberry Pi  │    │   Gateway       │    │   InfluxDB      │
│   (HWT905 IMU)  │───▶│   Service       │───▶│   Database      │
└─────────────────┘    └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   MQTT Broker   │    │    Grafana      │
                       │   (Mosquitto)   │    │   Dashboard     │
                       └─────────────────┘    └─────────────────┘
                                │                        │
                                ▼                        ▼
                       ┌─────────────────┐    ┌─────────────────┐
                       │   AI Training   │    │   Prometheus    │
                       │   & Inference   │    │   Monitoring    │
                       └─────────────────┘    └─────────────────┘
```

### Các thành phần chính

#### 1. **Raspberry Pi với HWT905 IMU**
- **Chức năng**: Thu thập dữ liệu gia tốc và góc quay từ cảm biến IMU
- **Giao tiếp**: Serial communication qua USB/UART
- **Dữ liệu**: acceleration_x/y/z, angular_velocity_x/y/z, displacement_x/y/z
- **Tần suất**: Configurable (mặc định 100Hz)

#### 2. **MQTT Broker (Mosquitto)**
- **Chức năng**: Message broker cho communication giữa các component
- **Topics chính**:
  - `sensor/hwt905/processed_data`: Dữ liệu cảm biến đã xử lý
  - `sensor/hwt905/model_update`: Cập nhật mô hình AI
- **Port**: 1883 (MQTT), 9001 (WebSocket)

#### 3. **Gateway Service**
- **Chức năng**: Xử lý trung tâm, nhận dữ liệu từ MQTT và ghi vào InfluxDB
- **Tính năng**:
  - Xử lý và validate dữ liệu MQTT
  - Ghi dữ liệu vào InfluxDB
  - Chia sẻ mô hình AI qua MQTT
  - Expose Prometheus metrics
- **Metrics**: `gateway_mqtt_messages_processed_total`, `gateway_influxdb_points_written_total`

#### 4. **InfluxDB**
- **Chức năng**: Time-series database để lưu trữ dữ liệu cảm biến
- **Schema**: 
  - Measurement: `sensor_data`
  - Tags: `device_id`, `strategy`
  - Fields: `disp_x`, `disp_y`, `disp_z`, etc.
- **Port**: 8086

#### 5. **Grafana**
- **Chức năng**: Visualization và dashboard cho dữ liệu
- **Datasources**: InfluxDB, Prometheus
- **Port**: 3000
- **Default login**: admin/admin

#### 6. **Prometheus + Node Exporter**
- **Chức năng**: Monitoring và metrics collection
- **Targets**: Gateway Service (port 8000), Node Exporter (port 9100)
- **Port**: 9090 (Prometheus), 9100 (Node Exporter)

#### 7. **AI Training & Inference**
- **Chức năng**: Huấn luyện mô hình ML và thực hiện edge inference
- **Algorithm**: RandomForestClassifier (có thể mở rộng)
- **Features**: displacement_x, displacement_y, displacement_z
- **Model sharing**: Qua MQTT và shared volume

```
hwt905-raspi/
├── docker-compose.yml           # Orchestration chính
├── services/                    # Microservices
│   └── gateway/                 # Gateway Service
│       ├── Dockerfile
│       ├── gateway_service.py
│       └── requirements.txt
├── scripts/                     # Standalone scripts
│   ├── main.py                  # Script chính cho Raspberry Pi
│   ├── train_model.py           # Script huấn luyện AI
│   └── edge_inference.py        # Script edge inference
├── config/                      # Configuration files
│   └── prometheus/
│       └── prometheus.yml
├── shared_models/               # Shared AI models
│   └── latest_model.joblib
├── gateway_data/                # Persistent data
│   ├── influxdb/
│   ├── grafana/
│   ├── mosquitto/
│   └── prometheus/
└── README.md
```

## Cài đặt và Triển khai

### Yêu cầu hệ thống

- **Docker**: >= 20.10
- **Docker Compose**: >= 2.0
- **RAM**: >= 4GB (khuyến nghị 8GB)
- **Storage**: >= 10GB free space
- **OS**: Linux (Ubuntu 20.04+), macOS, Windows với WSL2

### Bước 1: Clone repository

```bash
git clone <repository-url>
cd hwt905-raspi
```

### Bước 2: Tạo thư mục dữ liệu

```bash
mkdir -p gateway_data/{influxdb/{data,config},grafana/data,mosquitto/{config,data,log},prometheus/data}
```

### Bước 3: Cấu hình quyền (Linux/macOS)

```bash
# Cấu hình quyền cho InfluxDB
sudo chown -R 1000:1000 gateway_data/influxdb

# Cấu hình quyền cho Grafana
sudo chown -R 472:472 gateway_data/grafana

# Cấu hình quyền cho Prometheus
sudo chown -R 65534:65534 gateway_data/prometheus

# Cấu hình quyền cho shared models
sudo chown -R 1000:1000 shared_models
```

### Bước 4: Khởi động hệ thống

```bash
# Build và khởi động tất cả services
docker compose up -d --build

# Kiểm tra trạng thái
docker compose ps

# Xem logs
docker compose logs -f
```

### Bước 5: Xác minh hoạt động

1. **InfluxDB**: http://localhost:8086
2. **Grafana**: http://localhost:3000 (admin/admin)
3. **Prometheus**: http://localhost:9090
4. **MQTT**: localhost:1883

## Cấu hình các thành phần

### InfluxDB Configuration

```yaml
# Trong docker-compose.yml
environment:
  - DOCKER_INFLUXDB_INIT_MODE=setup
  - DOCKER_INFLUXDB_INIT_USERNAME=my-user
  - DOCKER_INFLUXDB_INIT_PASSWORD=my-password
  - DOCKER_INFLUXDB_INIT_ORG=my-org
  - DOCKER_INFLUXDB_INIT_BUCKET=my-bucket
  - DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=my-super-secret-token
```

### Gateway Service Configuration

```python
# Environment variables
MQTT_BROKER_HOST=mosquitto
INFLUXDB_HOST=influxdb
MQTT_DATA_TOPIC=sensor/hwt905/processed_data
MQTT_MODEL_TOPIC=sensor/hwt905/model_update
MODEL_PUBLISH_INTERVAL=60
```

### Prometheus Configuration

```yaml
# config/prometheus/prometheus.yml
global:
  scrape_interval: 15s

scrape_configs:
  - job_name: 'prometheus'
    static_configs:
      - targets: ['localhost:9090']
  
  - job_name: 'node-exporter'
    static_configs:
      - targets: ['node-exporter:9100']
  
  - job_name: 'gateway_service'
    static_configs:
      - targets: ['gateway_service:8000']
```

## AI Model Development

### Cải thiện thuật toán

#### 1. **Thay đổi thuật toán**

```python
# Trong scripts/train_model.py
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.svm import SVC
from sklearn.neural_network import MLPClassifier

# Thay thế RandomForestClassifier
model = GradientBoostingClassifier(n_estimators=200, learning_rate=0.1)
# hoặc
model = SVC(kernel='rbf', C=1.0)
# hoặc
model = MLPClassifier(hidden_layer_sizes=(100, 50), max_iter=500)
```

#### 2. **Feature Engineering**

```python
def extract_features(df):
    """Trích xuất features nâng cao"""
    # Rolling statistics
    df['disp_x_rolling_mean'] = df['disp_x'].rolling(window=10).mean()
    df['disp_x_rolling_std'] = df['disp_x'].rolling(window=10).std()
    
    # Magnitude
    df['displacement_magnitude'] = np.sqrt(df['disp_x']**2 + df['disp_y']**2 + df['disp_z']**2)
    
    # Frequency domain features (FFT)
    df['disp_x_fft'] = np.abs(np.fft.fft(df['disp_x']))
    
    return df
```

#### 3. **Hyperparameter Tuning**

```python
from sklearn.model_selection import GridSearchCV

param_grid = {
    'n_estimators': [100, 200, 300],
    'max_depth': [10, 20, None],
    'min_samples_split': [2, 5, 10]
}

grid_search = GridSearchCV(RandomForestClassifier(), param_grid, cv=5)
grid_search.fit(X_train, y_train)
best_model = grid_search.best_estimator_
```

#### 4. **Deep Learning Integration**

```python
import tensorflow as tf
from tensorflow.keras.models import Sequential
from tensorflow.keras.layers import LSTM, Dense, Dropout

def create_lstm_model(input_shape):
    model = Sequential([
        LSTM(50, return_sequences=True, input_shape=input_shape),
        Dropout(0.2),
        LSTM(50, return_sequences=False),
        Dropout(0.2),
        Dense(25),
        Dense(1, activation='sigmoid')
    ])
    model.compile(optimizer='adam', loss='binary_crossentropy', metrics=['accuracy'])
    return model
```

### Model Validation và Testing

```python
from sklearn.model_selection import cross_val_score, train_test_split
from sklearn.metrics import classification_report, confusion_matrix

# Cross validation
scores = cross_val_score(model, X, y, cv=5)
print(f"Cross-validation scores: {scores}")
print(f"Average CV score: {scores.mean():.3f} (+/- {scores.std() * 2:.3f})")

# Train/test split
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
model.fit(X_train, y_train)
y_pred = model.predict(X_test)

# Evaluation
print(classification_report(y_test, y_pred))
print(confusion_matrix(y_test, y_pred))
```

## Troubleshooting

### Lỗi thường gặp

#### 1. **Container không khởi động được**

```bash
# Kiểm tra logs
docker compose logs <service_name>

# Kiểm tra tài nguyên
docker system df
docker system prune  # Dọn dẹp nếu cần
```

#### 2. **InfluxDB connection failed**

```bash
# Kiểm tra InfluxDB health
curl http://localhost:8086/health

# Restart InfluxDB
docker compose restart influxdb

# Kiểm tra quyền thư mục
ls -la gateway_data/influxdb/
sudo chown -R 1000:1000 gateway_data/influxdb
```

#### 3. **MQTT connection refused**

```bash
# Test MQTT connection
mosquitto_pub -h localhost -p 1883 -t test -m "hello"
mosquitto_sub -h localhost -p 1883 -t test

# Kiểm tra Mosquitto logs
docker compose logs mosquitto
```

#### 4. **Prometheus targets DOWN**

```bash
# Kiểm tra network connectivity
docker compose exec prometheus wget -qO- http://gateway_service:8000/metrics

# Rebuild gateway service
docker compose up -d --build gateway_service
```

#### 5. **Permission denied errors**

```bash
# Linux/macOS
sudo chown -R $USER:$USER .
sudo chmod -R 755 gateway_data/

# Specific services
sudo chown -R 472:472 gateway_data/grafana
sudo chown -R 65534:65534 gateway_data/prometheus
```

#### 6. **Out of memory errors**

```bash
# Kiểm tra memory usage
docker stats

# Tăng memory limit trong docker-compose.yml
services:
  gateway_service:
    mem_limit: 1g
    memswap_limit: 1g
```

### Debug Commands

```bash
# Kiểm tra network
docker network ls
docker network inspect hwt905-raspi_default

# Exec vào container
docker compose exec gateway_service bash
docker compose exec influxdb bash

# Kiểm tra logs realtime
docker compose logs -f --tail=100

# Restart specific service
docker compose restart <service_name>

# Rebuild và restart
docker compose up -d --build <service_name>
```

## Triển khai lên máy nhúng

### Raspberry Pi Deployment

#### Chuẩn bị Raspberry Pi

```bash
# Cập nhật hệ thống
sudo apt update && sudo apt upgrade -y

# Cài đặt Docker
curl -fsSL https://get.docker.com -o get-docker.sh
sh get-docker.sh
sudo usermod -aG docker $USER

# Cài đặt Docker Compose
sudo apt install docker-compose-plugin
```

#### Lightweight Deployment

Tạo `docker-compose.embedded.yml` cho máy nhúng:

```yaml
services:
  mosquitto:
    image: eclipse-mosquitto:2.0
    ports:
      - "1883:1883"
    volumes:
      - mosquitto_data:/mosquitto/data
    restart: unless-stopped

  gateway_service:
    build:
      context: services/gateway
    depends_on:
      - mosquitto
    environment:
      - MQTT_BROKER_HOST=mosquitto
      - INFLUXDB_HOST=remote_influxdb_ip  # IP của server trung tâm
    restart: unless-stopped

volumes:
  mosquitto_data:
```

#### Edge-only Deployment

Tạo `edge-deployment/` folder:

```
edge-deployment/
├── docker-compose.yml
├── main.py                    # Script thu thập dữ liệu
├── edge_inference.py          # Edge inference
├── requirements.txt
└── models/                    # Local models
    └── latest_model.joblib
```

```python
# edge-deployment/main.py - Simplified version
import serial
import json
import paho.mqtt.client as mqtt
import time

def collect_and_send_data():
    # Simplified data collection
    ser = serial.Serial('/dev/ttyUSB0', 9600)
    client = mqtt.Client()
    client.connect("localhost", 1883, 60)
    
    while True:
        data = ser.readline().decode().strip()
        # Process and send data
        client.publish("sensor/data", data)
        time.sleep(0.1)

if __name__ == "__main__":
    collect_and_send_data()
```

#### Deployment Script

```bash
#!/bin/bash
# deploy-to-edge.sh

echo "Deploying to Raspberry Pi..."

# Copy only necessary files
rsync -av --exclude='gateway_data' \
          --exclude='.git' \
          --exclude='*.log' \
          edge-deployment/ pi@raspberry-pi-ip:/home/pi/hwt905/

# SSH and deploy
ssh pi@raspberry-pi-ip << 'EOF'
cd /home/pi/hwt905
docker compose -f docker-compose.yml up -d --build
EOF

echo "Deployment completed!"
```

### Performance Optimization cho Embedded

#### 1. **Giảm memory footprint**

```python
# Trong gateway_service.py
import gc

def optimize_memory():
    gc.collect()  # Force garbage collection
    
# Batch processing thay vì real-time
data_buffer = []
BATCH_SIZE = 100

def process_batch(data_batch):
    # Process multiple data points at once
    pass
```

#### 2. **Cấu hình Docker cho ARM**

```dockerfile
# services/gateway/Dockerfile.arm
FROM python:3.9-slim-buster

# Optimize for ARM
RUN apt-get update && apt-get install -y \
    --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

# Install only essential packages
COPY requirements.embedded.txt .
RUN pip install --no-cache-dir -r requirements.embedded.txt

COPY . .
CMD ["python", "gateway_service.py"]
```

#### 3. **Data compression**

```python
import gzip
import json

def compress_data(data):
    json_str = json.dumps(data)
    compressed = gzip.compress(json_str.encode())
    return compressed

def decompress_data(compressed_data):
    decompressed = gzip.decompress(compressed_data)
    return json.loads(decompressed.decode())
```

## Monitoring và Maintenance

### Health Checks

```bash
#!/bin/bash
# health-check.sh

echo "Checking system health..."

# Check containers
docker compose ps

# Check disk space
df -h

# Check memory
free -h

# Check specific endpoints
curl -f http://localhost:8086/health || echo "InfluxDB unhealthy"
curl -f http://localhost:9090/-/healthy || echo "Prometheus unhealthy"
curl -f http://localhost:3000/api/health || echo "Grafana unhealthy"
```

### Backup Strategy

```bash
#!/bin/bash
# backup.sh

BACKUP_DIR="/backup/$(date +%Y%m%d)"
mkdir -p $BACKUP_DIR

# Backup InfluxDB
docker compose exec influxdb influx backup /tmp/backup
docker cp influxdb:/tmp/backup $BACKUP_DIR/influxdb

# Backup Grafana
cp -r gateway_data/grafana $BACKUP_DIR/

# Backup configurations
cp -r config $BACKUP_DIR/

echo "Backup completed: $BACKUP_DIR"
```

### Log Rotation

```bash
# /etc/logrotate.d/docker-hwt905
/var/lib/docker/containers/*/*.log {
    daily
    rotate 7
    compress
    delaycompress
    missingok
    notifempty
    create 0644 root root
    postrotate
        docker kill --signal=USR1 $(docker ps -q) 2>/dev/null || true
    endscript
}
```

## Mở rộng hệ thống

### Thêm service mới

1. Tạo thư mục `services/new_service/`
2. Thêm Dockerfile và source code
3. Cập nhật `docker-compose.yml`
4. Cập nhật Prometheus config nếu cần

### Horizontal Scaling

```yaml
# docker-compose.yml
services:
  gateway_service:
    deploy:
      replicas: 3
    # Load balancer configuration
```

### Multi-node Deployment

```yaml
# docker-swarm.yml
version: '3.8'
services:
  gateway_service:
    deploy:
      replicas: 3
      placement:
        constraints:
          - node.role == worker
```

## Bảo mật

### MQTT Security

```bash
# Tạo user/password cho MQTT
docker compose exec mosquitto mosquitto_passwd -c /mosquitto/config/passwd username
```

### InfluxDB Security

```bash
# Thay đổi default tokens
export DOCKER_INFLUXDB_INIT_ADMIN_TOKEN=$(openssl rand -hex 32)
```

### Network Security

```yaml
# docker-compose.yml
networks:
  internal:
    driver: bridge
    internal: true
  external:
    driver: bridge

services:
  gateway_service:
    networks:
      - internal
      - external
```

## Liên hệ và Hỗ trợ

- **Issues**: Tạo issue trên GitHub repository
- **Documentation**: Xem thêm tại `/docs` folder
- **Community**: Join Discord/Slack channel

---

**Lưu ý**: Tài liệu này được cập nhật thường xuyên. Vui lòng kiểm tra version mới nhất trước khi triển khai.