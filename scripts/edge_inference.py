import os
import time
import logging
import joblib
import paho.mqtt.client as mqtt
import numpy as np

MODEL_DIR = os.getenv("MODEL_DIR", "./shared_models")
MODEL_PATH = os.path.join(MODEL_DIR, "latest_model.joblib")
MQTT_BROKER_HOST = os.getenv("MQTT_BROKER_HOST", "localhost")
MQTT_BROKER_PORT = int(os.getenv("MQTT_BROKER_PORT", 1883))
MQTT_MODEL_TOPIC = os.getenv("MQTT_MODEL_TOPIC", "sensor/hwt905/model_update")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("edge_inference")

def on_connect(client, userdata, flags, rc):
    if rc == 0:
        logger.info("Connected to MQTT Broker!")
        client.subscribe(MQTT_MODEL_TOPIC)
        logger.info(f"Subscribed to topic: {MQTT_MODEL_TOPIC}")
    else:
        logger.error(f"Failed to connect to MQTT, return code {rc}")

def on_message(client, userdata, msg):
    try:
        logger.info(f"Received model update from topic {msg.topic}")
        with open(MODEL_PATH, "wb") as f:
            f.write(msg.payload)
        logger.info(f"Model saved to {MODEL_PATH}")
        # Reload model for inference
        userdata['model'] = joblib.load(MODEL_PATH)
        logger.info("Model loaded for inference.")
    except Exception as e:
        logger.error(f"Error saving/loading model: {e}")

def run_inference(data, model, model_lock):
    """Hàm ví dụ: nhận dict dữ liệu cảm biến, trả về dự đoán từ model mới nhất."""
    features = ['disp_x', 'disp_y', 'disp_z']
    x = np.array([[data.get(f, 0) for f in features]])
    with model_lock:
        if model is not None:
            pred = model.predict(x)
            return pred[0]
        else:
            return None

def main():
    model = None
    if os.path.exists(MODEL_PATH):
        try:
            model = joblib.load(MODEL_PATH)
            logger.info("Loaded existing model for inference.")
        except Exception as e:
            logger.error(f"Could not load model: {e}")
    mqtt_client = mqtt.Client(userdata={'model': model})
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(MQTT_BROKER_HOST, MQTT_BROKER_PORT, 60)
    try:
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down edge inference service.")
    finally:
        mqtt_client.disconnect()

if __name__ == "__main__":
    main()
