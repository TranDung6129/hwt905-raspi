import os
import json
import logging
import time
from datetime import datetime
import threading
import joblib
from prometheus_client import start_http_server, Counter

import paho.mqtt.client as mqtt
from influxdb_client.client.influxdb_client import InfluxDBClient
from influxdb_client.client.write.point import Point
from influxdb_client.client.write_api import WriteOptions
from influxdb_client.client.write_api import SYNCHRONOUS

# --- Configuration ---
# Setup basic logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# InfluxDB Configuration from environment variables
INFLUXDB_HOST = os.getenv("INFLUXDB_HOST", "localhost")
INFLUXDB_PORT = int(os.getenv("INFLUXDB_PORT", 8086))
INFLUXDB_URL = f"http://{INFLUXDB_HOST}:{INFLUXDB_PORT}"
INFLUXDB_TOKEN = os.getenv("DOCKER_INFLUXDB_INIT_ADMIN_TOKEN", "my-super-secret-token")
INFLUXDB_ORG = os.getenv("DOCKER_INFLUXDB_INIT_ORG", "my-org")
INFLUXDB_BUCKET = os.getenv("DOCKER_INFLUXDB_INIT_BUCKET", "my-bucket")

# MQTT Configuration from environment variables
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
MQTT_DATA_TOPIC = os.getenv("MQTT_DATA_TOPIC", "sensor/hwt905/processed_data")
CLIENT_ID = f"gateway_service_{os.getpid()}"

# --- Prometheus Metrics ---
MQTT_MESSAGES_PROCESSED = Counter('gateway_mqtt_messages_processed_total', 'Total number of MQTT messages processed', ['topic'])
INFLUXDB_POINTS_WRITTEN = Counter('gateway_influxdb_points_written_total', 'Total number of data points written to InfluxDB', ['device_id'])

# Thêm cấu hình cho model sharing
MODEL_DIR = os.getenv("MODEL_DIR", "./shared_models")
MODEL_PATH = os.path.join(MODEL_DIR, "latest_model.joblib")
MQTT_MODEL_TOPIC = os.getenv("MQTT_MODEL_TOPIC", "sensor/hwt905/model_update")
MODEL_PUBLISH_INTERVAL = int(os.getenv("MODEL_PUBLISH_INTERVAL", 60))  # giây

# --- InfluxDB Client ---
def get_influx_client():
    """Initializes and returns the InfluxDB client, retrying on failure."""
    max_retries = 5
    retry_delay = 10  # seconds
    for attempt in range(max_retries):
        try:
            logger.info(f"Connecting to InfluxDB at {INFLUXDB_URL} (Attempt {attempt + 1}/{max_retries})")
            client = InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG)
            health = client.health()
            if health.status == "pass":
                logger.info("InfluxDB connection successful.")
                return client
            else:
                logger.warning(f"InfluxDB health check failed. Status: {health.status}")
        except Exception as e:
            logger.error(f"Error connecting to InfluxDB: {e}")
        
        logger.info(f"Retrying in {retry_delay} seconds...")
        time.sleep(retry_delay)
    
    logger.critical("Could not establish connection to InfluxDB after multiple retries.")
    return None

# --- MQTT Callbacks ---
def on_connect(client, userdata, flags, rc):
    """Callback for when the client connects to MQTT."""
    if rc == 0:
        logger.info("Connected to MQTT Broker!")
        client.subscribe(MQTT_DATA_TOPIC)
        logger.info(f"Subscribed to topic: {MQTT_DATA_TOPIC}")
    else:
        logger.error(f"Failed to connect to MQTT, return code {rc}")

def on_message(client, userdata, msg):
    """Callback for when a message is received from MQTT."""
    try:
        payload = msg.payload.decode()
        data = json.loads(payload)
        logger.info(f"Received message from topic {msg.topic}")
        MQTT_MESSAGES_PROCESSED.labels(topic=msg.topic).inc()

        write_api = userdata.get('write_api')
        if not write_api:
            logger.error("InfluxDB write_api not found in userdata.")
            return

        # Extract metadata
        metadata = data.get("metadata", {})
        device_id = metadata.get("source", "unknown_device")
        
        # Extract data points
        data_points = data.get("data_points", [])
        
        if not data_points:
            logger.warning("No data points found in message")
            return
            
        # Process each data point
        for data_point in data_points:
            timestamp = datetime.fromtimestamp(data_point.get("ts", time.time()))
            
            point = Point("sensor_data") \
                .tag("device_id", device_id) \
                .tag("strategy", metadata.get("strategy", "unknown")) \
                .time(timestamp)

            # Add sensor data fields
            for key, value in data_point.items():
                if key != "ts" and isinstance(value, (int, float)):
                    # Map displacement fields to acceleration fields for Grafana compatibility
                    if key == "disp_x":
                        point = point.field("disp_x", value)
                    elif key == "disp_y":
                        point = point.field("disp_y", value)
                    elif key == "disp_z":
                        point = point.field("disp_z", value)
                    else:
                        point = point.field(key, value)

            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
            INFLUXDB_POINTS_WRITTEN.labels(device_id=device_id).inc()
            logger.info(f"Wrote data point for device {device_id} to InfluxDB at {timestamp}")

    except json.JSONDecodeError:
        logger.error(f"Failed to decode JSON from message payload: {msg.payload}")
    except Exception as e:
        logger.error(f"An error occurred in on_message: {e}", exc_info=True)

def publish_model_periodically(mqtt_client):
    last_mtime = None
    while True:
        try:
            if os.path.exists(MODEL_PATH):
                mtime = os.path.getmtime(MODEL_PATH)
                if last_mtime is None or mtime > last_mtime:
                    with open(MODEL_PATH, "rb") as f:
                        model_bytes = f.read()
                    mqtt_client.publish(MQTT_MODEL_TOPIC, payload=model_bytes, qos=1)
                    logger.info(f"Published new model to topic {MQTT_MODEL_TOPIC}")
                    last_mtime = mtime
        except Exception as e:
            logger.error(f"Error publishing model: {e}")
        time.sleep(MODEL_PUBLISH_INTERVAL)

def main():
    """Main function to set up clients and start the loop."""
    # Start Prometheus metrics server in a background thread
    start_http_server(8000)
    logger.info("Started Prometheus metrics server on port 8000.")
    influx_client = get_influx_client()
    if not influx_client:
        logger.critical("Exiting due to InfluxDB connection failure.")
        return

    write_api = influx_client.write_api(write_options=SYNCHRONOUS)

    mqtt_client = mqtt.Client(client_id=CLIENT_ID)
    mqtt_client.user_data_set({'write_api': write_api})
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message

    try:
        logger.info(f"Connecting to MQTT Broker at {MQTT_BROKER_HOST}:{MQTT_BROKER_PORT}")
        mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
    except Exception as e:
        logger.critical(f"Could not connect to MQTT Broker: {e}")
        influx_client.close()
        return

    try:
        # Khởi động thread theo dõi và publish model
        model_thread = threading.Thread(target=publish_model_periodically, args=(mqtt_client,), daemon=True)
        model_thread.start()
        logger.info("Started model publisher thread.")
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down gateway service.")
    finally:
        mqtt_client.disconnect()
        influx_client.close()
        logger.info("Clients disconnected. Shutdown complete.")

if __name__ == "__main__":
    main()
