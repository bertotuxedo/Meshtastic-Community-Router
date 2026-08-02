# Meshtastic Community Router (MCR)

> Dynamic MQTT routing, encrypted packet forwarding, and community management for Meshtastic.

Meshtastic Community Router (MCR) is an open-source platform that allows Meshtastic communities to grow beyond a single MQTT topic.

Instead of manually maintaining MQTT bridges or static routing scripts, MCR dynamically routes encrypted Meshtastic packets between community topics while preventing routing loops and duplicate packets.

Originally developed for the **Flag & Torch Society (FATS)**, the router is designed to support **any Meshtastic community** through configuration rather than code changes.

---

# Features

## Current Features

- Dynamic MQTT routing
- Multi-root community support
- Encrypted packet forwarding
- Duplicate packet detection
- Automatic MQTT subscriptions
- SQLite database
- Database migrations
- Plugin architecture
- REST API
- Live Dashboard
- Activity monitoring
- Background scheduler
- Topic registration workflow
- Community chatbot
- Docker deployment

---

# How It Works

Every packet entering the router follows the same workflow.

```text
Meshtastic Node
        │
        ▼
 MQTT Broker
        │
        ▼
Meshtastic Community Router
        │
        ├── Validate Packet
        ├── Detect Duplicates
        ├── Determine Community
        ├── Route to Registered Roots
        ├── Update Statistics
        ├── Notify Plugins
        └── Process Bot Commands
```

The router never decrypts or modifies Meshtastic payloads.

Instead, it intelligently routes encrypted packets between registered MQTT topics while preserving the original packet.

---

# Architecture

```text
                 Meshtastic Nodes
                        │
                 MQTT Broker
                        │
        ┌────────────────────────────────┐
        │  Meshtastic Community Router   │
        ├────────────────────────────────┤
        │ MQTT Router                    │
        │ Database                       │
        │ Scheduler                      │
        │ Plugin Manager                 │
        │ REST API                       │
        │ Live Dashboard                 │
        └────────────────────────────────┘
                        │
          ┌─────────────┼─────────────┐
          │             │             │
      Chatbot      Registration   Future Plugins
```

---

# Quick Start

## Requirements

Before starting, you'll need:

- Docker
- Docker Compose
- Git
- MQTT Broker
- Meshtastic MQTT credentials
- Meshtastic channel PSK

---

## Clone the Repository

```bash
git clone https://github.com/bertotuxedo/Meshtastic-Community-Router.git

cd Meshtastic-Community-Router
```

---

## Create Configuration Files

Copy the provided examples.

```bash
cp config/config.example.yaml config/config.yaml

cp secrets/router.env.example secrets/router.env
```

---

## Configure the Router

Open:

```text
config/config.yaml
```

Example:

```yaml
communities:
  mycommunity:
    display_name: My Community
    channel_name: MYCOMMUNITY
    rendezvous_root: msh/US/MYCOMMUNITY

    initial_roots:
      - msh/US/MYCOMMUNITY
```

You can add additional static routing roots under `initial_roots`.

---

## Configure MQTT Credentials

Open:

```text
secrets/router.env
```

Fill in your MQTT information.

```text
MCR_MQTT_HOST=mqtt.example.com
MCR_MQTT_PORT=1883
MCR_MQTT_USERNAME=myusername
MCR_MQTT_PASSWORD=mypassword

MCR_FATS_PSK_BASE64=YOUR_BASE64_CHANNEL_PSK
```

The PSK must match the Meshtastic channel being routed.

---

## Generate a Bot Node ID

Every router should identify itself as its own virtual Meshtastic node.

Generate a random Node ID:

```bash
printf '!%08x\n' "$((0x$(openssl rand -hex 4)))"
```

Example:

```text
!40e95c88
```

Place that value into:

```yaml
bot:
  node_id: "!40e95c88"
```

You can also customize the bot name.

```yaml
bot:
  name: FATBOT
```

---

## Build and Start

```bash
docker compose up -d --build
```

View logs:

```bash
docker compose logs -f
```

---

## Verify the Router

Verify the REST API.

```bash
curl http://localhost:8008/api/status | python3 -m json.tool
```

Example response:

```json
{
    "status": "running",
    "routing": {
        "enabled": true
    },
    "bot": {
        "enabled": true,
        "name": "FATBOT"
    }
}
```

---

## Open the Dashboard

Browse to

```
http://YOUR_SERVER_IP:8008
```

The dashboard displays:

- Router Status
- Active Nodes
- Active Rooms
- Registered Routing Roots
- Packet Counters
- Loaded Plugins
- Scheduler Status
- Database Version

---

# Bot Commands

The chatbot only responds on the configured rendezvous topic.

| Command | Description |
|----------|-------------|
| `!help` | Display available commands |
| `!status` | Display router status |
| `!topics` | Show available routing topics |
| `!mytopics` | List your registered topics |
| `!register <mqtt_root>` | Register a routing topic |
| `!confirm <code>` | Confirm a pending registration |
| `!unregister <mqtt_root>` | Remove a routing topic |

---

# Project Structure

```text
src/
└── mcr/
    ├── api/
    ├── bot/
    ├── broker/
    ├── commands/
    ├── crypto/
    ├── database/
    ├── events/
    ├── migrations/
    ├── plugins/
    ├── scheduler/
    ├── services/
    ├── web/
    └── main.py

config/
data/
secrets/
```

---

# API

The router exposes a read-only REST API.

## Health

```
GET /health
```

## Router Status

```
GET /api/status
```

Returns:

- Router status
- Active nodes
- Active rooms
- Routing roots
- Plugin health
- Scheduler health
- Database version
- Packet counters

---

# Updating

Pull the latest version.

```bash
git pull
```

Rebuild the container.

```bash
docker compose up -d --build
```

Database migrations are applied automatically during startup.

---

# Roadmap

## Version 1.0

- ✅ MQTT Router
- ✅ Multi-root routing
- ✅ Duplicate detection
- ✅ Registration workflow
- ✅ REST API
- ✅ Dashboard
- ✅ Plugin system
- ✅ Scheduler
- ✅ Activity monitoring
- ✅ FATBOT

## Version 1.1

- Generic community support
- Community discovery
- Administrative improvements

## Version 1.2

- WebSocket dashboard
- Historical analytics
- Live packet visualization

## Version 2.0

- Router federation
- Distributed community routing
- Plugin marketplace

---

# Contributing

Contributions are welcome.

If you'd like to report a bug, suggest a feature, or contribute code, please open an Issue or Pull Request.

---

# License

This project is released under the MIT License.
