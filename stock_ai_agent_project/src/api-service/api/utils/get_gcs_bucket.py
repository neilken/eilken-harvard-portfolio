# from google.oauth2 import service_account
import pandas as pd
from google.cloud import storage
from io import BytesIO
from google.auth import default

credentials_path = "../secrets/stock-busters-service-account.json"
import os

storage_client = None

# try:
#     if os.path.exists(credentials_path):
#         storage_client = storage.Client.from_service_account_json(credentials_path)
#         print(f"GCS Client initialized using service account: {credentials_path}")
#     else:
#         # Credentials file not found - will be mocked in tests
#         print(f"Info: Credentials file not found at {credentials_path}. GCS client will be mocked in tests.")
# except Exception as e:
#     # Any error initializing - will be mocked in tests
#     print(f"Info: Could not initialize GCS Client: {e}. Will be mocked in tests.")
#     storage_client = None
try:
    credentials, project_id = default()
    storage_client = storage.Client(credentials=credentials, project=project_id)
    print(f"GCS Client initialized with project: {project_id}")
except Exception as e:
    # Any error initializing - will be mocked in tests
    print(f"Info: Could not initialize GCS Client: {e}. Will be mocked in tests.")
    storage_client = None

bucket_name = "fin-data-bucket-115"


def get_gcs_data(file_name, file_type="csv", storage_client=storage_client, bucket_name=bucket_name):

    # Check if client initialization was successful
    if storage_client is None:
        print("GCS client is not initialized. Cannot proceed.")
        return None

    try:
        # Get the bucket
        bucket = storage_client.bucket(bucket_name)

        # Get the blob (file)
        blob = bucket.blob(file_name)

        # Download the content as bytes
        csv_bytes = blob.download_as_bytes()

        # Read into pandas DataFrame
        if file_type == "csv":
            df = pd.read_csv(BytesIO(csv_bytes))
        elif file_type == "parquet":
            df = pd.read_parquet(BytesIO(csv_bytes))

        # Display basic info
        print(f"Successfully loaded {file_name}")
        print(f"Shape: {df.shape}")

        return df

    except Exception as e:
        print(f"Error accessing file: {e}")
        return None
