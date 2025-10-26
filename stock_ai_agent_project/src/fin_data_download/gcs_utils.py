from google.cloud import storage

def upload_to_gcs(bucket_name, source_file, dest_blob):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(dest_blob)
    blob.upload_from_filename(source_file)
    print(f"✅ Uploaded {source_file} → gs://{bucket_name}/{dest_blob}")

def download_from_gcs(bucket_name, source_blob, dest_file):
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(source_blob)
    blob.download_to_filename(dest_file)
    print(f"✅ Downloaded gs://{bucket_name}/{source_blob} → {dest_file}")