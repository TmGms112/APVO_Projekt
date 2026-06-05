import pika
import json
import os

RABBIT_HOST = os.getenv("RABBITMQ_HOST", "localhost")

def send_to_queue(song_id: str, file_key: str, bucket: str = "songs"):
    connection = pika.BlockingConnection(
        pika.ConnectionParameters(host=RABBIT_HOST)
    )
    channel = connection.channel()

    channel.queue_declare(queue="songs", durable=True)

    message = {
        "song_id": song_id,
        "file_key": file_key,
        "bucket": bucket 
    }

    channel.basic_publish(
        exchange="",
        routing_key="songs",
        body=json.dumps(message),
        properties=pika.BasicProperties(
            delivery_mode=2  
        )
    )

    connection.close()
    print(f" RabbitMQ: Sent message for song {song_id}")