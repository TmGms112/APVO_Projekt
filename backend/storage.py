import os

from minio import Minio

MINIO_ENDPOINT = os.getenv("MINIO_ENDPOINT", "minio1:9000")
MINIO_ACCESS_KEY = os.getenv("MINIO_ACCESS_KEY", "minio")
MINIO_SECRET_KEY = os.getenv("MINIO_SECRET_KEY", "minio123")
MINIO_SECURE = os.getenv("MINIO_SECURE", "False").lower() == "true"

minio_client = Minio(
    MINIO_ENDPOINT,
    access_key=MINIO_ACCESS_KEY,
    secret_key=MINIO_SECRET_KEY,
    secure=MINIO_SECURE,
)

DEFAULT_BUCKET = os.getenv("MINIO_BUCKET", "songs")


def get_file(file_name: str, bucket: str = DEFAULT_BUCKET):
    return minio_client.get_object(bucket_name=bucket, object_name=file_name)


def upload_file(file_name: str, file_data, content_type: str, bucket: str = DEFAULT_BUCKET):
    if not minio_client.bucket_exists(bucket):
        minio_client.make_bucket(bucket)

    if hasattr(file_data, "seek"):
        file_data.seek(0)

    minio_client.put_object(
        bucket_name=bucket,
        object_name=file_name,
        data=file_data,
        length=-1,
        part_size=10 * 1024 * 1024,
        content_type=content_type,
    )
