"""
Utility functions for Quantamental Model
- Configuration loading
- GCS file operations
- Helper functions
"""

import os
import yaml
from pathlib import Path
from datetime import date, timedelta
from typing import Dict, Any, Optional
import pandas as pd
from google.cloud import storage
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def load_config(config_path: str = "config.yaml") -> Dict[str, Any]:
    """
    Load configuration from YAML file.
    Override with environment variables where applicable.

    Args:
        config_path: Path to config.yaml file

    Returns:
        Configuration dictionary
    """
    # Try to find config in multiple locations
    possible_paths = [
        config_path,
        Path(__file__).parent / config_path,
        Path(__file__).parent.parent / config_path,
    ]

    config_file = None
    for path in possible_paths:
        if Path(path).exists():
            config_file = path
            break

    if config_file is None:
        raise FileNotFoundError(f"Config file not found. Tried: {possible_paths}")

    with open(config_file, "r") as f:
        config = yaml.safe_load(f)

    # Override with environment variables
    if os.getenv("FMP_API_KEY"):
        config["api"]["fmp_api_key"] = os.getenv("FMP_API_KEY")

    if os.getenv("WANDB_PROJECT"):
        config["wandb"]["project"] = os.getenv("WANDB_PROJECT")

    if os.getenv("WANDB_API_KEY"):
        config["wandb"]["api_key"] = os.getenv("WANDB_API_KEY")
    elif "api_key" in config.get("wandb", {}):
        os.environ["WANDB_API_KEY"] = config["wandb"]["api_key"]

    if os.getenv("GCS_BUCKET"):
        config["gcs"]["bucket_name"] = os.getenv("GCS_BUCKET")

    if os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
        config["gcs"]["credentials_path"] = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")

    # Compute date ranges if not set
    if config["data"]["start_date"] is None:
        config["data"]["start_date"] = (
            date.today() - timedelta(days=3 * 365)
        ).isoformat()

    if config["data"]["end_date"] is None:
        config["data"]["end_date"] = date.today().isoformat()

    logger.info(f"✅ Config loaded from {config_file}")
    logger.info(
        f"📅 Date range: {config['data']['start_date']} → {config['data']['end_date']}"
    )

    return config


class GCSHandler:
    """Handle all GCS upload/download operations"""

    def __init__(self, bucket_name: str, credentials_path: Optional[str] = None):
        """
        Initialize GCS client

        Args:
            bucket_name: GCS bucket name
            credentials_path: Optional path to service account JSON
        """
        self.bucket_name = bucket_name

        if credentials_path and os.path.exists(credentials_path):
            self.client = storage.Client.from_service_account_json(credentials_path)
        else:
            # Use default credentials (from environment)
            self.client = storage.Client()

        self.bucket = self.client.bucket(bucket_name)
        logger.info(f"✅ GCS Handler initialized for bucket: {bucket_name}")

    def upload_file(self, local_path: str, gcs_path: str) -> str:
        """
        Upload a file to GCS

        Args:
            local_path: Local file path
            gcs_path: Destination path in GCS (e.g., "model_output/predictions.csv")

        Returns:
            Public URL of uploaded file
        """
        try:
            blob = self.bucket.blob(gcs_path)
            blob.upload_from_filename(local_path)

            url = f"gs://{self.bucket_name}/{gcs_path}"
            logger.info(f"✅ Uploaded {local_path} → {url}")
            return url

        except Exception as e:
            logger.error(f"❌ Failed to upload {local_path}: {e}")
            raise

    def upload_dataframe(
        self, df: pd.DataFrame, gcs_path: str, format: str = "csv"
    ) -> str:
        """
        Upload a pandas DataFrame directly to GCS

        Args:
            df: DataFrame to upload
            gcs_path: Destination path in GCS
            format: File format ('csv' or 'parquet')

        Returns:
            Public URL of uploaded file
        """
        try:
            # Create temp file
            temp_file = f"/tmp/{Path(gcs_path).name}"

            if format == "csv":
                df.to_csv(temp_file, index=False)
            elif format == "parquet":
                df.to_parquet(temp_file, index=False)
            else:
                raise ValueError(f"Unsupported format: {format}")

            # Upload
            url = self.upload_file(temp_file, gcs_path)

            # Cleanup
            os.remove(temp_file)

            return url

        except Exception as e:
            logger.error(f"❌ Failed to upload DataFrame: {e}")
            raise

    def download_file(self, gcs_path: str, local_path: str) -> str:
        """
        Download a file from GCS

        Args:
            gcs_path: Source path in GCS
            local_path: Destination local path

        Returns:
            Local file path
        """
        try:
            blob = self.bucket.blob(gcs_path)
            blob.download_to_filename(local_path)

            logger.info(f"✅ Downloaded {gcs_path} → {local_path}")
            return local_path

        except Exception as e:
            logger.error(f"❌ Failed to download {gcs_path}: {e}")
            raise

    def list_files(self, prefix: str = "") -> list:
        """
        List files in GCS bucket with given prefix

        Args:
            prefix: Folder prefix (e.g., "model_output/")

        Returns:
            List of blob names
        """
        blobs = self.client.list_blobs(self.bucket_name, prefix=prefix)
        return [blob.name for blob in blobs]


def get_feature_list(config: Dict[str, Any]) -> list:
    """
    Get complete list of features with proper lag naming for technicals

    Args:
        config: Configuration dictionary

    Returns:
        List of feature names
    """
    tech_features = [f"{col}_lag1" for col in config["features"]["technical"]]
    fund_features = config["features"]["fundamental"]

    return tech_features + fund_features


def ensure_dir(path: str) -> str:
    """
    Ensure directory exists, create if not

    Args:
        path: Directory path

    Returns:
        Absolute path to directory
    """
    path = Path(path)
    path.mkdir(parents=True, exist_ok=True)
    return str(path.absolute())


def get_timestamp_suffix() -> str:
    """
    Get timestamp string for file naming

    Returns:
        Timestamp in format YYYYMMDD_HHMMSS
    """
    from datetime import datetime

    return datetime.now().strftime("%Y%m%d_%H%M%S")


if __name__ == "__main__":
    # Test config loading
    config = load_config()
    print("\n📋 Configuration loaded successfully!")
    print(f"   W&B Project: {config['wandb']['project']}")
    print(f"   GCS Bucket: {config['gcs']['bucket_name']}")
    print(f"   Features: {len(get_feature_list(config))} total")
    print(f"   Technical: {len(config['features']['technical'])}")
    print(f"   Fundamental: {len(config['features']['fundamental'])}")
