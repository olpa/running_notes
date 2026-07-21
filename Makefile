DOVECOT_IMAGE := dovecot/dovecot:2.4.4
IMAGE_TAG ?= 0.1.0
FRONTEND_IMAGE := running-notes-frontend:$(IMAGE_TAG)
BACKEND_IMAGE := running-notes-be:$(IMAGE_TAG)

.PHONY: production-images
production-images:
	docker pull $(DOVECOT_IMAGE)
	docker build --pull --tag $(FRONTEND_IMAGE) --file frontend/Dockerfile .
	docker build --pull --tag $(BACKEND_IMAGE) ./backend
