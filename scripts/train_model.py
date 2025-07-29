import os
import logging
from influxdb_client.client.influxdb_client import InfluxDBClient
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import joblib

# --- Configuration ---
INFLUXDB_URL = os.getenv("INFLUXDB_URL", "http://localhost:8086")
INFLUXDB_TOKEN = os.getenv("DOCKER_INFLUXDB_INIT_ADMIN_TOKEN", "my-super-secret-token")
INFLUXDB_ORG = os.getenv("DOCKER_INFLUXDB_INIT_ORG", "my-org")
INFLUXDB_BUCKET = os.getenv("DOCKER_INFLUXDB_INIT_BUCKET", "my-bucket")
MODEL_DIR = os.getenv("MODEL_DIR", "./shared_models")
MODEL_PATH = os.path.join(MODEL_DIR, "latest_model.joblib")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("train_model")

def query_data():
    query = f'''from(bucket: "{INFLUXDB_BUCKET}")\n  |> range(start: -30d)\n  |> filter(fn: (r) => r["_measurement"] == "sensor_data")\n  |> pivot(rowKey:["_time"], columnKey: ["_field"], valueColumn: "_value")'''
    with InfluxDBClient(url=INFLUXDB_URL, token=INFLUXDB_TOKEN, org=INFLUXDB_ORG) as client:
        result = client.query_api().query_data_frame(query)
        if isinstance(result, list):
            df = pd.concat(result)
        else:
            df = result
        return df

def train_model(df):
    # Giả sử dữ liệu có các trường: 'disp_x', 'disp_y', 'disp_z', 'label'
    features = ['disp_x', 'disp_y', 'disp_z']
    target = 'label'

    # --- Tạm thời: Tạo dummy labels nếu cột 'label' không tồn tại ---
    if target not in df.columns:
        logger.warning(f"'{target}' column not found. Creating dummy labels for testing.")
        # Tạo nhãn dựa trên một điều kiện đơn giản. Ví dụ: nếu disp_x > 0.1, gán nhãn 1, còn lại 0.
        # Bạn nên thay thế logic này bằng cách gán nhãn thực tế.
        df[target] = (df['disp_x'] > 0.1).astype(int)
        logger.info(f"Created dummy labels: {df[target].value_counts().to_dict()}")
    # ----------------------------------------------------------------

    df = df.dropna(subset=features + [target])

    if df.empty:
        logger.error("No data left for training after dropping NA values.")
        return None

    X = df[features]
    y = df[target]
    model = RandomForestClassifier(n_estimators=100, random_state=42)
    model.fit(X, y)
    return model

def save_model(model):
    os.makedirs(MODEL_DIR, exist_ok=True)
    joblib.dump(model, MODEL_PATH)
    logger.info(f"Model saved to {MODEL_PATH}")

if __name__ == "__main__":
    logger.info("Querying data from InfluxDB...")
    df = query_data()
    if df is None or df.empty:
        logger.error("No data found for training.")
        exit(1)
    logger.info(f"Fetched {len(df)} rows from InfluxDB.")
    logger.info("Training model...")
    model = train_model(df)
    save_model(model)
    logger.info("Training complete.")
