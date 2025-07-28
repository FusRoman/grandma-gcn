# Deploying a Flask API with `nginx-proxy` and Let's Encrypt (Docker Compose on OpenStack)

This documentation explains how we successfully deployed a Flask API behind a **dynamic Nginx reverse proxy** with automatic TLS certificates from **Let's Encrypt**.
It is a step-by-step explanation, including all the debugging and configuration steps that were necessary to make it work in an OpenStack environment.

---

## Context

The goal was to expose a Flask app (running with Gunicorn) on:

```
https://slackbot-grandma.ijclab.in2p3.fr
```

We wanted:

- Automatic handling of virtual hosts and certificates
- HTTPS support with Let's Encrypt
- The app running behind **nginx-proxy** so we don’t manually manage Nginx configs

---

## 1. Pre-requisites

- **OpenStack VM** (Linux)
- **Docker and Docker Compose installed**
- A **DNS record** already pointing to your VM’s public IP
- Access to **OpenStack CLI** to manage firewall/security groups

---

## 2. Security Groups: Allowing Ports 80 and 443

**Problem:** Initially, ports 80 and 443 were closed by default on the VM, so external requests timed out.

We checked which security groups were assigned to the VM:

```bash
openstack server show grandma-gcn -c security_groups
```

Then we inspected the `default` group:

```bash
openstack security group rule list default
```

We added **ingress rules for 80 and 443** if they didn’t exist:

```bash
openstack security group rule create --proto tcp --dst-port 80 default
openstack security group rule create --proto tcp --dst-port 443 default
```

> **Important:** Without these rules, Let's Encrypt cannot validate your domain.

---

## 3. Docker Compose Configuration

We used three main services:

1. **flask_api** – Runs our app on port 5000
2. **nginx-proxy** – Automatically detects VIRTUAL_HOST and serves the right container
3. **nginx-proxy-acme** – Handles SSL/TLS and automatically generates Let's Encrypt certificates

---

### 3.1 Environment variables

In `.env`:

```
VIRTUAL_HOST=slackbot-grandma.ijclab.in2p3.fr
LETSENCRYPT_HOST=slackbot-grandma.ijclab.in2p3.fr
LETSENCRYPT_EMAIL=your.email@example.com
NGINX_PROXY_NAME=nginx-proxy-grandma
```

---

### 3.2 Docker Compose File

We used `container_name` to ensure acme-companion can find the proxy container.

```yaml
version: "3.8"

services:
  flask_api:
    image: grandma_gcn_app
    env_file:
      - .env
    environment:
      VIRTUAL_HOST: ${VIRTUAL_HOST}
      LETSENCRYPT_HOST: ${LETSENCRYPT_HOST}
      LETSENCRYPT_EMAIL: ${LETSENCRYPT_EMAIL}
    expose:
      - "5000"
    depends_on:
      - db
      - redis
    restart: unless-stopped

  nginx-proxy:
    container_name: ${NGINX_PROXY_NAME}
    image: jwilder/nginx-proxy:latest
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - certs:/etc/nginx/certs
      - vhost:/etc/nginx/vhost.d
      - html:/usr/share/nginx/html
      - /var/run/docker.sock:/tmp/docker.sock:ro

  nginx-proxy-acme:
    container_name: nginx-proxy-acme-grandma
    image: nginxproxy/acme-companion:latest
    depends_on:
      - nginx-proxy
    environment:
      - NGINX_PROXY_CONTAINER=${NGINX_PROXY_NAME}
    volumes:
      - certs:/etc/nginx/certs
      - vhost:/etc/nginx/vhost.d
      - html:/usr/share/nginx/html
      - /var/run/docker.sock:/var/run/docker.sock:ro

volumes:
  certs:
  vhost:
  html:
```

---

## 4. Launching the Stack

Bring everything up:

```bash
docker compose -f compose_prod.yml down
docker compose -f compose_prod.yml up -d
```

---

## 5. Debugging Steps

### 5.1 Check Docker is listening on 80/443

```bash
sudo ss -tlnp | grep -E ':80|:443'
```

Expected:

```
LISTEN 0 4096 0.0.0.0:80 ...
LISTEN 0 4096 0.0.0.0:443 ...
```

---

### 5.2 Use `nmap` externally

From your laptop:

```bash
nmap -p 80,443 slackbot-grandma.ijclab.in2p3.fr
```

Before fixing security groups and DNS, ports were **closed**.
Afterwards, ports showed as **open**.

---

### 5.3 Monitor container logs

```bash
docker compose -f compose_prod.yml logs -f nginx-proxy
docker compose -f compose_prod.yml logs -f nginx-proxy-acme
```

Look for lines about:

- Detecting your container and generating `/etc/nginx/conf.d/default.conf`
- Certificate validation attempts

---

## 6. Let’s Encrypt Process

The acme-companion container:

1. Waits for the proxy to be up
2. Requests a certificate from Let's Encrypt
3. Serves a **challenge** at `http://yourdomain/.well-known/acme-challenge/...`
4. Once validated, installs the certificate and reloads Nginx

If the firewall or security group blocks port 80, validation fails.

---

## 7. Testing

Check HTTP:

```bash
curl -I http://slackbot-grandma.ijclab.in2p3.fr
```

Check HTTPS:

```bash
curl -I https://slackbot-grandma.ijclab.in2p3.fr
```

---

## 8. Lessons Learned (Key Points)

- **Always allow ports 80/443 in OpenStack security groups**
- **Set a fixed container name for nginx-proxy** so acme-companion knows which proxy to talk to
- Use `ss`, `nmap`, and container logs to troubleshoot connectivity and TLS issues

---

After these steps, the Flask API is available at:

```
https://slackbot-grandma.ijclab.in2p3.fr
```

with an automatically renewed Let's Encrypt certificate.
