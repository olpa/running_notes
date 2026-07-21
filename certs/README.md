# TLS certificates for Running Notes

This directory contains a single Let's Encrypt certificate valid for:

- `notes.handsfree.vc`
- `notes-dev.handsfree.vc`
- `mail.handsfree.vc`

Certbot uses the HTTP-01 standalone-server method. Both domain names must resolve
to this server, inbound TCP port 80 must be reachable from the Internet, and no
other process may listen on port 80 while Certbot runs.

## Initial issuance command

Run from this directory:

```sh
sudo certbot certonly \
  --standalone \
  --non-interactive \
  --agree-tos \
  --register-unsafely-without-email \
  --preferred-challenges http \
  --config-dir "$PWD/letsencrypt" \
  --work-dir "$PWD/letsencrypt-work" \
  --logs-dir "$PWD/letsencrypt-logs" \
  --cert-name notes.handsfree.vc \
  -d notes.handsfree.vc \
  -d notes-dev.handsfree.vc \
  -d mail.handsfree.vc
```

The account was registered without an email address, so Let's Encrypt will not
send expiration notices.

The Dovecot container runs as the workspace user's UID and needs to read the
bind-mounted private key. When Certbot is run with `sudo`, restore ownership to
the user that runs Docker while keeping the key private:

```sh
sudo chown "$(id -u):$(id -g)" letsencrypt/archive/notes.handsfree.vc/privkey*.pem
sudo chmod 600 letsencrypt/archive/notes.handsfree.vc/privkey*.pem
```

## Certificate files

Use the stable symlinks under:

```text
letsencrypt/live/notes.handsfree.vc/
```

The important files are:

- `fullchain.pem`: the server certificate followed by the intermediate CA
  certificate chain. Send this to TLS clients. This is the certificate file
  normally configured in nginx and Dovecot.
- `privkey.pem`: the private key corresponding to the server certificate. It
  proves the server's identity and must remain secret. It is intentionally
  readable only by root; never publish, email, or commit it.
- `cert.pem`: only the server/leaf certificate, without the intermediate chain.
- `chain.pem`: only the intermediate CA certificate chain, without the server
  certificate.

`live` contains symlinks maintained by Certbot. Do not configure services to use
the numbered files in `letsencrypt/archive`, because their names change during
renewal.

## nginx configuration

```nginx
ssl_certificate     /mnt/HC_Volume_103849597/home/olpa/running_notes/certs/letsencrypt/live/notes.handsfree.vc/fullchain.pem;
ssl_certificate_key /mnt/HC_Volume_103849597/home/olpa/running_notes/certs/letsencrypt/live/notes.handsfree.vc/privkey.pem;
```

After changing nginx configuration, check and reload it:

```sh
sudo nginx -t
sudo systemctl reload nginx
```

## Dovecot configuration

```conf
ssl = required
ssl_cert = </mnt/HC_Volume_103849597/home/olpa/running_notes/certs/letsencrypt/live/notes.handsfree.vc/fullchain.pem
ssl_key = </mnt/HC_Volume_103849597/home/olpa/running_notes/certs/letsencrypt/live/notes.handsfree.vc/privkey.pem
```

The leading `<` tells Dovecot to read the contents of the file. After changing
the configuration, check and reload it:

```sh
sudo doveconf -n
sudo systemctl reload dovecot
```

## Renewal

Because Certbot state is stored in this custom local directory, the default
system Certbot timer does not discover it. Renew explicitly with the same paths.
First stop any service listening on port 80, then run from this directory:

```sh
sudo certbot renew \
  --config-dir "$PWD/letsencrypt" \
  --work-dir "$PWD/letsencrypt-work" \
  --logs-dir "$PWD/letsencrypt-logs"
```

Certbot renews certificates only when they are close enough to expiration. It
updates the `live` symlinks automatically. Reload nginx and Dovecot afterward so
they read the new certificate and key. Restore the private-key ownership as
described above before recreating containerized services.

```sh
sudo systemctl reload nginx
sudo systemctl reload dovecot
```

To test the renewal process without obtaining a production certificate, keep
port 80 free and run:

```sh
sudo certbot renew --dry-run \
  --config-dir "$PWD/letsencrypt" \
  --work-dir "$PWD/letsencrypt-work" \
  --logs-dir "$PWD/letsencrypt-logs"
```

## Checking the certificate

Inspect the local certificate's subject, issuer, validity dates, and domain
names:

```sh
sudo openssl x509 \
  -in letsencrypt/live/notes.handsfree.vc/fullchain.pem \
  -noout -subject -issuer -dates -ext subjectAltName
```

Check that the certificate matches the private key. These two commands must
print the same SHA-256 value:

```sh
sudo openssl x509 \
  -in letsencrypt/live/notes.handsfree.vc/cert.pem \
  -pubkey -noout | openssl pkey -pubin -outform DER | sha256sum

sudo openssl pkey \
  -in letsencrypt/live/notes.handsfree.vc/privkey.pem \
  -pubout -outform DER | sha256sum
```

After nginx is running, inspect the certificate actually served over HTTPS:

```sh
openssl s_client \
  -connect notes.handsfree.vc:443 \
  -servername notes.handsfree.vc </dev/null 2>/dev/null \
  | openssl x509 -noout -subject -issuer -dates -ext subjectAltName
```

Repeat with `notes-dev.handsfree.vc` and `mail.handsfree.vc` to check the other
names as well.
