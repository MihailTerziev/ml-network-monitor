FROM zeek/zeek:9.0.0

USER root
RUN apt-get update \
    && apt-get install -y --no-install-recommends python3 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /opt/ml-network-monitor
COPY zeek/monitor.zeek zeek/forwarder.py ./

ENV PYTHONUNBUFFERED=1
ENTRYPOINT ["python3", "/opt/ml-network-monitor/forwarder.py"]
