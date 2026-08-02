# Meshtastic Community Router (MCR)

> Dynamic MQTT routing, community management, and plugin framework for Meshtastic communities.

Meshtastic Community Router (MCR) is an open-source platform that allows Meshtastic communities to grow beyond a single static MQTT topic.

Instead of manually maintaining MQTT bridges, routing scripts, or static routing tables, MCR dynamically manages routing between community topics while preserving Meshtastic's encrypted packet format.

Originally developed for the **Flag & Torch Society (FATS)**, MCR is designed to support **any Meshtastic community** through configuration rather than code changes.

---

# Features

## Current Features

- Dynamic MQTT topic routing
- Multi-root community routing
- Packet deduplication and loop prevention
- SQLite-backed configuration and state
- Automatic MQTT subscription management
- Plugin architecture
- Chatbot framework
- Topic registration and confirmation workflow
- Activity tracking
- Background scheduler
- REST API
- Live web dashboard
- Docker Compose deployment
- Database migration framework
- Encrypted Meshtastic packet support

## Planned Features

- Community discovery
- Router federation
- Discord bridge
- APRS integration
- Weather plugin
- AI assistant
- Bulletin board
- WebSocket dashboard
- Administrative web interface
- Historical statistics

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

MCR is intentionally modular. Most functionality is implemented through plugins so new features can be added without modifying the routing engine.

---

# Installation

## Requirements

- Docker
- Docker Compose
- MQTT Broker
- Meshtastic MQTT credentials
- Meshtastic channel PSK

## Clone the Repository

```bash
git clone https://github.com/bertotuxedo/Meshtastic-Community-Router.git

cd Meshtastic-Community-Router
```

## Create Configuration Files

Copy the provided examples.

```bash
cp config/config.example.yaml config/config.yaml

cp secrets/router.env.example secrets/router.env
```

## Configure `config/config.yaml`

Set your community information.

```yaml
communities:
  mycommunity:
    display_name: My Community
    channel_name: MYCHANNEL
    rendezvous_root: msh/US/MYCOMMUNITY

    initial_roots:
      - msh/US/MYCOMMUNITY
```

## Configure `secrets/router.env`

Populate the required values.

```text
MCR_MQTT_HOST=
MCR_MQTT_PORT=
MCR_MQTT_USERNAME=
MCR_MQTT_PASSWORD=
MCR_FATS_PSK_BASE64=
```

## Start the Router

```bash
docker compose up -d
```

View logs:

```bash
docker compose logs -f
```

---

# Dashboard

Once running, the dashboard is available at:

```
http://YOUR_SERVER:8008
```

The dashboard displays:

- Router status
- Active nodes
- Active rooms
- Registered routing roots
- Packet statistics
- Scheduler health
- Plugin health
- Database schema version

---

# Configuration

## application

General application settings.

| Option | Description |
|---------|-------------|
| `log_level` | Logging verbosity |

## mqtt

MQTT broker connection.

| Option | Description |
|---------|-------------|
| `host` | MQTT hostname |
| `port` | MQTT port |
| `client_id` | MQTT client ID |
| `keepalive` | Keepalive interval |

## communities

Community configuration.

| Option | Description |
|---------|-------------|
| `display_name` | Human-readable community name |
| `channel_name` | Meshtastic channel name |
| `rendezvous_root` | Primary MQTT routing root |
| `initial_roots` | Default routed roots |

## routing

Routing engine configuration.

| Option | Description |
|---------|-------------|
| `deduplication_seconds` | Duplicate retention period |
| `root_reload_seconds` | Root reload interval |
| `maximum_registered_roots` | Maximum registered roots |

## registration

Registration workflow.

| Option | Description |
|---------|-------------|
| `confirmation_expiration_seconds` | Confirmation timeout |
| `cleanup_interval_seconds` | Cleanup interval |
| `maximum_roots_per_node` | Maximum registrations per node |

## activity

Controls activity tracking.

| Option | Description |
|---------|-------------|
| `active_window_seconds` | Time window for active nodes |

## scheduler

Background scheduler.

| Option | Description |
|---------|-------------|
| `poll_interval_seconds` | Scheduler polling interval |

## bot

Community chatbot.

| Option | Description |
|---------|-------------|
| `enabled` | Enable or disable bot |
| `name` | Bot display name |
| `node_id` | Virtual node ID |
| `hop_limit` | Reply hop limit |

## api

REST API configuration.

| Option | Description |
|---------|-------------|
| `enabled` | Enable API |
| `host` | Listen address |
| `port` | API port |

---

# Bot Commands

| Command | Description |
|---------|-------------|
| `!help` | Show available commands |
| `!status` | Show router status |
| `!topics` | List available topics |
| `!mytopics` | List your registered topics |
| `!register <mqtt_root>` | Register a new routing topic |
| `!confirm <code>` | Confirm registration |
| `!unregister <mqtt_root>` | Remove a registered topic |

---

# Project Structure

```text
src/
└── mcr/
    ├── api/
    ├── bot/
    ├── broker/
    ├── commands/
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

# Roadmap

## Version 1.0

- ✅ Dynamic MQTT routing
- ✅ Registration workflow
- ✅ REST API
- ✅ Live dashboard
- ✅ Plugin architecture
- ✅ Activity tracking
- ✅ FATBOT

## Version 1.1

- Community discovery
- Generic community support
- Improved administration

## Version 1.2

- WebSocket dashboard
- Historical statistics
- Enhanced analytics

## Version 2.0

- Router federation
- Distributed routing
- Plugin marketplace

---

# Contributing

Contributions are welcome.

If you have ideas, bug reports, feature requests, or would like to build plugins, please open an Issue or Pull Request.

---

# License

This project is released under the MIT License.
