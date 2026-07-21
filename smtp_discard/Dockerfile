FROM python:3.12-alpine

ENV PYTHONDONTWRITEBYTECODE=1

WORKDIR /app
COPY smtp_sink.py .

USER 65534:65534
EXPOSE 2525

HEALTHCHECK --interval=10s --timeout=3s --retries=3 \
  CMD python -c "import socket; s=socket.create_connection(('127.0.0.1', 2525), 2); assert s.recv(3) == b'220'; s.close()"

CMD ["python", "smtp_sink.py"]
