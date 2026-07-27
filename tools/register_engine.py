"""
Engine Registration CLI Tool for camera_analytics framework v1.0.0.

Publishes an EngineRegistrationRequest message over RabbitMQ to the .NET Enterprise Backend.
"""

import os
import socket
import sys
import uuid
from datetime import datetime, timezone

from camera_analytics.communication.publishers.rabbitmq_publisher import RabbitMQPublisher

def main():
    application_id = os.getenv("APPLICATION_ID", "e078ee93-90c4-4b95-9651-7bf82c8a6d33")
    engine_id = os.getenv("ENGINE_ID", str(uuid.uuid4()))
    hostname = os.getenv("HOSTNAME", socket.gethostname())
    node_id = os.getenv("NODE_ID", str(uuid.uuid5(uuid.NAMESPACE_DNS, hostname)))
    ip_address = os.getenv("IP_ADDRESS", "127.0.0.1")
    rabbitmq_host = os.getenv("RABBITMQ_HOST", "localhost")
    rabbitmq_port = int(os.getenv("RABBITMQ_PORT", "5672"))
    rabbitmq_vhost = os.getenv("RABBITMQ_VHOST", "cctv_vhost")
    rabbitmq_user = os.getenv("RABBITMQ_USER", "cctv_admin")
    rabbitmq_pass = os.getenv("RABBITMQ_PASS", "SecureCctvPass123")

    registration_payload = {
        "messageVersion": "1.0.0",
        "correlationId": str(uuid.uuid4()),
        "applicationId": application_id,
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "engineId": engine_id,
        "nodeId": node_id,
        "engineVersion": "1.0.0",
        "hostname": hostname,
        "ipAddress": ip_address,
        "gpuName": os.getenv("GPU_NAME", "NVIDIA GeForce RTX 4090"),
        "cudaVersion": os.getenv("CUDA_VERSION", "12.2"),
        "totalGpuMemoryMb": int(os.getenv("TOTAL_GPU_MEMORY_MB", "24576")),
        "maxPipelineCapacity": int(os.getenv("MAX_PIPELINE_CAPACITY", "8")),
        "supportedModules": ["INTRUSION_DETECTION", "LINE_CROSSING", "LPR", "FACE_RECOGNITION"],
        "startupTime": datetime.now(timezone.utc).isoformat()
    }

    publisher = RabbitMQPublisher(
        name="registration_publisher",
        host=rabbitmq_host,
        port=rabbitmq_port,
        vhost=rabbitmq_vhost,
        username=rabbitmq_user,
        password=rabbitmq_pass
    )

    publisher.initialize({})
    publisher.start()

    success = publisher.publish_raw(
        exchange="cctv.engine",
        routing_key="engine.register",
        payload_dict=registration_payload
    )

    if success:
        print(f"[+] EngineRegistrationRequest sent successfully for Engine ID '{engine_id}' Node ID '{node_id}' (Host: {hostname})")
    else:
        print(f"[-] Failed to send EngineRegistrationRequest for Engine ID '{engine_id}'")

    publisher.stop()

if __name__ == "__main__":
    main()
