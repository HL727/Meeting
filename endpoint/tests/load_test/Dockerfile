FROM python:3.8-slim-buster

RUN apt-get update && apt-get install -y wamerican && apt-get clean && rm -rf /var/lib/apt/lists/*

RUN pip install requests gunicorn[gevent]
COPY load_test/__main__.py  /
COPY load_test/simulator  /simulator
COPY data/*xml /data/

RUN chmod 755 /__main__.py

RUN groupadd mividas && useradd -g mividas -ms /bin/bash mividas
USER mividas

EXPOSE 8087
CMD ["python3", "/__main__.py"]
