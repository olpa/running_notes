DOVECOT_IMAGE := dovecot/dovecot:2.4.4
FRONTEND_IMAGE := running-notes-frontend:0.1.0
BACKEND_IMAGE := running-notes-be:0.1.0

.PHONY: production-images
production-images:
	docker pull $(DOVECOT_IMAGE)
	docker build --pull --tag $(FRONTEND_IMAGE) --file frontend/Dockerfile .
	docker build --pull --tag $(BACKEND_IMAGE) ./backend
