# boringproxy reinstall runbook

This document records the non-obvious parts of the working setup as of 2026-07-19.

## Purpose and topology

The public server is `boringp.uucode.com`. The application client is identified as `notes-dev`, and both services use `notes-dev.handsfree.vc`.

```text
HTTPS:
Internet :443
  -> boringproxy SNI router :443
  -> SSH reverse tunnel on a dynamically assigned server loopback port
  -> boringproxy-client
  -> nginx:443

IMAPS:
Internet :993
  -> firewall REDIRECT to :10993
  -> externally bound SSH reverse tunnel :10993
  -> boringproxy-client
  -> dovecot:993

SMTP submission:
Internet :588
  -> firewall REDIRECT to :12588
  -> externally bound SSH reverse tunnel :12588
  -> boringproxy-client
  -> dovecot:587
```

TLS is never terminated by boringproxy. All three tunnels use
`tls_termination: "passthrough"`; nginx and Dovecot own the certificates and
terminate TLS.

When production and development share this host, boringproxy listens on public
HTTPS port 443 for both hostnames. The development hostname uses its normal SSH
reverse tunnel, while `notes.handsfree.vc` is a direct-proxy record whose
selected `tunnel_port` is the production nginx loopback listener, 18444. Do not
run a boringproxy client for that production record. IMAPS is not routed by SNI:
production uses public 993 directly and development uses public 994 translated
to its internal SSH tunnel on 10993. Production SMTP submission uses public
587 directly and development uses public 588 translated to its internal SSH
tunnel on 12588.

The installed server binary was boringproxy v0.10.0.

The HTTPS tunnel port is allocated by boringproxy. It is currently `46811` in this database, but that number is not part of the architecture and may differ after recreating or reinstalling the tunnel. Always read the current value from `boringproxy_db.json`.

## Files that must be backed up

Back up these files securely:

- `boringproxy_db.json`: contains API tokens and SSH private keys.
- `/home-or-volume-path/olpa/.ssh/authorized_keys`: contains the restricted public keys used by the tunnels.
- `/etc/ssh/sshd_config.d/boringproxy.conf`.
- `/etc/ufw/before.rules` and `/etc/ufw/before6.rules`.
- The application-side nginx/Dovecot certificates and configuration.
- The boringproxy-client token/configuration on the application host.

The database and its backups should be owned by the boringproxy user and mode `0600`.

Do not put the real database, tokens, or private keys in a public repository.

## Server installation

Install the same binary version initially. After the migration works, upgrade separately so migration and upgrade failures are not mixed together.

```bash
chmod +x boringproxy
sudo setcap cap_net_bind_service=+ep boringproxy
getcap boringproxy
./boringproxy version
```

Expected capability:

```text
boringproxy cap_net_bind_service=ep
```

The server currently starts as:

```bash
./boringproxy server -admin-domain boringp.uucode.com
```

The process working directory matters: without `-db-dir`, boringproxy reads and writes `boringproxy_db.json` in its working directory.

Before starting, confirm DNS for both `boringp.uucode.com` and `notes-dev.handsfree.vc` points to the new server.

## Tunnel database

The important non-secret fields are:

```json
{
  "tunnels": {
    "notes-dev.handsfree.vc": {
      "domain": "notes-dev.handsfree.vc",
      "server_address": "boringp.uucode.com",
      "server_port": 22,
      "username": "olpa",
      "tunnel_port": 46811,
      "client_address": "nginx",
      "client_port": 443,
      "allow_external_tcp": false,
      "tls_termination": "passthrough",
      "owner": "notes-dev",
      "client_name": "notes-dev"
    },
    "notes-dev.handsfree.vc.10993": {
      "domain": "notes-dev.handsfree.vc",
      "server_address": "boringp.uucode.com",
      "server_port": 22,
      "username": "olpa",
      "tunnel_port": 10993,
      "client_address": "dovecot",
      "client_port": 993,
      "allow_external_tcp": true,
      "tls_termination": "passthrough",
      "owner": "notes-dev",
      "client_name": "notes-dev"
    },
    "notes-dev.handsfree.vc.12588": {
      "domain": "notes-dev.handsfree.vc.12588",
      "server_address": "boringp.uucode.com",
      "server_port": 22,
      "username": "olpa",
      "tunnel_port": 12588,
      "client_address": "dovecot",
      "client_port": 587,
      "allow_external_tcp": true,
      "tls_termination": "passthrough",
      "owner": "notes-dev",
      "client_name": "notes-dev"
    }
  }
}
```

The map keys must be unique. HTTPS uses the plain hostname; `.10993` and
`.12588` distinguish the raw mail tunnel records. These suffixes are tunnel
identifiers, not hostnames entered in a mail client.

`allow_external_tcp` controls the SSH reverse-forward bind address:

- `false`: loopback-only tunnel used internally by boringproxy's HTTPS/SNI router.
- `true`: requests an external bind such as `0.0.0.0:10993`; required for raw protocols such as IMAPS.

`tls_termination: "client"` is not passthrough. It makes boringproxy-client terminate HTTPS and forward plaintext HTTP. For nginx:443 or dovecot:993 to receive the original TLS stream, use `passthrough`.

## OpenSSH configuration

Create `/etc/ssh/sshd_config.d/boringproxy.conf`:

```text
GatewayPorts clientspecified
```

Validate and reload:

```bash
sudo sshd -t
sudo sshd -T | grep -E '^(gatewayports|allowtcpforwarding|disableforwarding|permitlisten) '
sudo systemctl reload ssh
```

Expected effective values include:

```text
gatewayports clientspecified
allowtcpforwarding yes
disableforwarding no
permitlisten any
```

`GatewayPorts clientspecified` is needed because `allow_external_tcp: true` asks OpenSSH to bind `0.0.0.0`. It does not authorize arbitrary forwarding by itself; each tunnel key is restricted using `permitlisten`.

The relevant generated `authorized_keys` restrictions are conceptually:

```text
permitlisten="127.0.0.1:<HTTPS_TUNNEL_PORT>" ... boringproxy-notes-dev.handsfree.vc-<HTTPS_TUNNEL_PORT>
permitlisten="0.0.0.0:10993" ... boringproxy-notes-dev.handsfree.vc-10993
permitlisten="0.0.0.0:12588" ... boringproxy-notes-dev.handsfree.vc.12588-12588
```

Keep the complete generated lines, including their public keys and restrictive command/options. Do not copy only the snippets above. In the current installation `<HTTPS_TUNNEL_PORT>` is `46811`, but it must match the database rather than this historical value.

### Direct database edits and stale authorized keys

Directly changing `tunnel_port`, hostname, or map keys in `boringproxy_db.json` may not regenerate `authorized_keys`. If client logs say:

```text
ssh: tcpip-forward request denied by peer
```

compare all three values:

1. `tunnel_port` in the database.
2. The address/port requested in the boringproxy-client log.
3. `permitlisten` in the matching `authorized_keys` line.

They must agree. The SSH server journal gives a more precise error than the client:

```bash
sudo journalctl --since '-10 minutes' | grep -Ei 'sshd|remote forward|cannot listen|denied|permission denied'
```

## Why public mail ports use unprivileged tunnel ports

> **Production and development on one host:** reserve public port 993 for the
> production Dovecot service and use public port 994 for the development
> boringproxy tunnel. In that layout, substitute 994 for every public-facing
> 993 in the UFW translation rules below, but keep the internal SSH tunnel on
> 10993. The development app must advertise `PUBLIC_IMAP_PORT=994`.

An SSH remote-forward listener is created by an `sshd` child running as the authenticated user (`olpa`). It cannot bind privileged port 993. The capability on the boringproxy binary applies only to boringproxy, not to that `sshd` child.

SMTP development uses the same pattern even though public port 588 is already
unprivileged: keeping the public listener on the tunnel host means the
application-side Docker/Dovecot listener can remain loopback-only. Public 588
is translated to SSH tunnel port 12588.

Do not solve this by:

- running the entire boringproxy server as root;
- lowering `net.ipv4.ip_unprivileged_port_start` system-wide;
- authenticating the tunnel as root.

Instead, OpenSSH binds unprivileged port 10993 and the firewall narrowly translates public 993 to it. TLS bytes are unchanged.

## Persistent UFW port translation

The setup supports IPv4 and IPv6. Add this block before the `*filter` section in `/etc/ufw/before.rules`:

```text
# boringproxy IMAPS: public 993 to unprivileged SSH tunnel 10993
*nat
:PREROUTING ACCEPT [0:0]
:OUTPUT ACCEPT [0:0]
-A PREROUTING -p tcp --dport 993 -j REDIRECT --to-ports 10993
-A OUTPUT -p tcp -d 195.201.133.151 --dport 993 -j REDIRECT --to-ports 10993
-A PREROUTING -p tcp --dport 588 -j REDIRECT --to-ports 12588
-A OUTPUT -p tcp -d 195.201.133.151 --dport 588 -j REDIRECT --to-ports 12588
COMMIT
```

`PREROUTING` handles connections arriving from other machines. Connections
originating on the boringproxy/firewall host traverse `OUTPUT` instead, so the
second rule is required for host-local clients and verification commands. Keep
the `OUTPUT` rule restricted to the public address of the server; an unrestricted
destination match could unexpectedly redirect connections intended for other
IMAP servers.

Immediately after the loopback INPUT acceptance in the same file, add:

```text
# Accept only connections translated from public IMAPS 993; reject direct external 10993
-A ufw-before-input -p tcp --dport 10993 -m conntrack --ctorigdstport 993 --ctdir ORIGINAL -j ACCEPT
-A ufw-before-input -p tcp --dport 10993 -j DROP
-A ufw-before-input -p tcp --dport 12588 -m conntrack --ctorigdstport 588 --ctdir ORIGINAL -j ACCEPT
-A ufw-before-input -p tcp --dport 12588 -j DROP
```

Add the equivalent NAT block before `*filter` in `/etc/ufw/before6.rules`, using
the public IPv6 address of the server for its `OUTPUT` rule, then add after its
loopback INPUT rule:

```text
-A ufw6-before-input -p tcp --dport 10993 -m conntrack --ctorigdstport 993 --ctdir ORIGINAL -j ACCEPT
-A ufw6-before-input -p tcp --dport 10993 -j DROP
-A ufw6-before-input -p tcp --dport 12588 -m conntrack --ctorigdstport 588 --ctdir ORIGINAL -j ACCEPT
-A ufw6-before-input -p tcp --dport 12588 -j DROP
```

The DROP rules prevent clients from bypassing the translated public ports and
connecting directly to 10993 or 12588. Loopback access remains allowed because
the normal loopback ACCEPT precedes them.

Back up the UFW files before editing, then validate/reload:

```bash
sudo cp -a /etc/ufw/before.rules /etc/ufw/before.rules.backup
sudo cp -a /etc/ufw/before6.rules /etc/ufw/before6.rules.backup
sudo ufw --dry-run reload
sudo ufw reload
```

Verify live rules:

```bash
sudo iptables -t nat -S PREROUTING | grep -E '10993|12588'
sudo iptables -t nat -S OUTPUT | grep -E '10993|12588'
sudo iptables -S ufw-before-input | grep -E '10993|12588'
sudo ip6tables -t nat -S PREROUTING | grep -E '10993|12588'
sudo ip6tables -t nat -S OUTPUT | grep -E '10993|12588'
sudo ip6tables -S ufw6-before-input | grep -E '10993|12588'
```

The host also needs its normal UFW allowances for SSH, HTTP, and HTTPS. Public
10993 and 12588 must not be generally allowed.

## Safe migration/restart order

Direct edits while the server is running can be overwritten by boringproxy's in-memory state. Use this order:

1. Stop boringproxy-server.
2. Back up `boringproxy_db.json`.
3. Restore/edit the database and set ownership/mode.
4. Restore/check the matching `authorized_keys` restrictions.
5. Validate and reload sshd and UFW.
6. Start boringproxy-server from the directory containing the intended database.
7. Restart boringproxy-client on the application machine.
8. If the application holds stale long-lived connections, restart the application stack too.

After editing the database, verify the server did not rewrite it:

```bash
stat boringproxy_db.json
jq '.tunnels | to_entries[] | {key: .key, domain: .value.domain, tunnel_port: .value.tunnel_port}' boringproxy_db.json
```

## Verification

Read the dynamically assigned HTTPS tunnel port, then inspect the server listeners:

```bash
HTTPS_TUNNEL_PORT=$(jq -r '.tunnels["notes-dev.handsfree.vc"].tunnel_port' boringproxy_db.json)
sudo ss -lntp | grep -E ":(80|443|10993|12588|${HTTPS_TUNNEL_PORT})\\b"
```

Expected while the client is connected:

- boringproxy owns public 80/443.
- `sshd` children own 10993 and 12588.
- no process needs to listen directly on 993/994 or 588 because NAT acts before
  INPUT.

HTTPS passthrough:

```bash
curl -v https://notes-dev.handsfree.vc/
openssl s_client -connect notes-dev.handsfree.vc:443 -servername notes-dev.handsfree.vc
```

IMAPS passthrough on the standard client port, tested from another machine or
from the boringproxy host when the matching `OUTPUT` redirect is installed:

```bash
openssl s_client -connect notes-dev.handsfree.vc:993 -servername notes-dev.handsfree.vc
openssl s_client -starttls smtp -connect notes-dev.handsfree.vc:588 -servername notes-dev.handsfree.vc
```

The certificate shown by these commands should be the application-side nginx/Dovecot certificate, not a boringproxy-generated certificate.

Because 993 is redirected rather than directly bound, `ss`/`netstat` shows
10993, not 993. A successful TLS connection on 993 is the correct end-to-end
verification; no process is expected to listen directly on 993.

## Troubleshooting map

### Port 993 is refused only when tested on the boringproxy host

If external connections work but this command fails locally with
`BIO_connect: Connection refused`:

```bash
openssl s_client -connect notes-dev.handsfree.vc:993 -servername notes-dev.handsfree.vc
```

check both NAT hooks:

```bash
sudo iptables -t nat -S PREROUTING | grep 10993
sudo iptables -t nat -S OUTPUT | grep 10993
```

An inbound-only `PREROUTING` redirect does not process connections generated on
the same host. Add the narrowly scoped `OUTPUT` redirect shown in the UFW
section. The downstream tunnel can be checked independently on port 10993, but
mail clients should continue using standard IMAPS port 993.

### `tcpip-forward request denied by peer`

Read the server's sshd journal. Common distinct causes:

- `Received request ... but the request was denied`: `GatewayPorts` or `permitlisten` mismatch.
- `bind [0.0.0.0]:993: Permission denied`: attempted to bind a privileged port as `olpa`; use 10993 plus firewall translation.
- Request still mentions 993 after changing the database: the running server/client has stale state, or the server is reading another database working directory. Stop server, edit, start server, restart client.

### `dial tcp [::1]:<HTTPS_TUNNEL_PORT>: connect: connection refused`

There is no active HTTPS reverse-forward listener. Confirm with:

```bash
HTTPS_TUNNEL_PORT=$(jq -r '.tunnels["notes-dev.handsfree.vc"].tunnel_port' boringproxy_db.json)
sudo ss -lntp | grep ":${HTTPS_TUNNEL_PORT}"
```

Restart boringproxy-client and inspect its logs. Existing browser keep-alive connections can make ordinary navigation appear functional while a new recording/WebSocket connection fails. In the incident that prompted this note, restarting the application/client restored recording.

### HTTP `400 Bad Request` after enabling passthrough

Ensure the web tunnel is:

```text
client_address: nginx
client_port: 443
tls_termination: passthrough
```

Using `tls_termination: client` with nginx:443 makes boringproxy-client terminate TLS and send plaintext HTTP to an HTTPS socket, producing a 400 response.

### Tunnel hostname/key collision

Both tunnels may share `domain: notes-dev.handsfree.vc`, but JSON object keys must be unique. Keep:

```text
notes-dev.handsfree.vc          # HTTPS record
notes-dev.handsfree.vc.10993    # IMAPS record identifier
```

The `.10993` suffix is an internal database identifier, not a DNS name.
