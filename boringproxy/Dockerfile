FROM alpine:3.22 AS downloader

ARG BORINGPROXY_VERSION=v0.10.0
ARG TARGETARCH
ARG TARGETVARIANT

RUN set -eux; \
    case "${TARGETARCH}/${TARGETVARIANT}" in \
      amd64/) asset_arch=x86_64 ;; \
      arm64/) asset_arch=arm64 ;; \
      arm/v7) asset_arch=arm ;; \
      386/) asset_arch=386 ;; \
      *) echo "Unsupported target architecture: ${TARGETARCH}/${TARGETVARIANT}" >&2; exit 1 ;; \
    esac; \
    wget -O /boringproxy \
      "https://github.com/boringproxy/boringproxy/releases/download/${BORINGPROXY_VERSION}/boringproxy-linux-${asset_arch}"; \
    chmod 0755 /boringproxy

FROM alpine:3.22

RUN apk add --no-cache ca-certificates openssh-client

COPY --from=downloader /boringproxy /usr/local/bin/boringproxy

ENTRYPOINT ["/usr/local/bin/boringproxy"]
