FROM python:3.12-slim

WORKDIR /app

RUN apt-get update \
    && apt-get install --no-install-recommends -y ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY database.py users.py oauth.py oauth_identities.py mailbox.py messages.py audio.py autoconfig.py application_routes.py guest.py admin.py auth_deps.py auth_routes.py autodiscover_routes.py config.py guest_retention.py lmtp_delivery.py messages_routes.py notes_routes.py profile_routes.py services.py main.py ./

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
