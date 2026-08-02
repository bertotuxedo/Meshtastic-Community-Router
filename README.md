# Meshtastic Community Platform (MCP)

> Build, connect, and grow Meshtastic communities—without writing custom infrastructure.

Meshtastic Community Platform (MCP) is an open-source framework for creating, managing, and interconnecting Meshtastic communities over MQTT. It provides dynamic routing, community discovery, plugin-based automation, and management tools that allow communities to scale beyond a single MQTT topic or broker.

Originally developed for the **Flag & Torch Society (FATS)**, MCP has evolved into a general-purpose platform that any organization, club, emergency communications group, or hobbyist community can deploy.

---

## Vision

Meshtastic has made it incredibly easy to build local mesh networks. MCP extends that idea into the cloud by providing the services needed to build thriving communities around those networks.

Rather than maintaining static MQTT configurations or custom scripts, MCP provides a platform where communities can:

- Discover each other
- Dynamically register MQTT topics
- Bridge conversations between communities
- Automate administrative tasks
- Extend functionality through plugins
- Monitor network health through a web dashboard
- Build custom community experiences without modifying the core platform

The long-term goal is to create a federated ecosystem where Meshtastic communities around the world can discover, collaborate, and grow together.

---

# Current Features

- MQTT broker integration
- Dynamic topic routing
- Multi-topic community bridging
- Packet deduplication
- Meshtastic encrypted packet support
- Plugin architecture
- Command framework
- SQLite-backed configuration
- Dynamic MQTT subscriptions
- Community chatbot framework (FATBOT)

---

# Planned Features

## Community Management

- Dynamic topic registration
- Community discovery
- Topic confirmation workflow
- User-maintained routing tables
- Automatic subscription management

## Plugins

- Registration plugin
- Statistics plugin
- Weather plugin
- APRS integration
- Discord bridge
- Bulletin board
- AI assistant
- Emergency notification system

## Dashboard

- Community management
- Live MQTT monitoring
- Node statistics
- Plugin management
- Routing visualization
- Broker health
- Network analytics

## Federation

- Community advertisements
- Trusted community discovery
- Cross-community routing
- Signed announcements
- Distributed community directory

---

# Architecture

```
                    Meshtastic Nodes
                            │
                     Meshtastic MQTT
                            │
                    ┌────────────────┐
                    │      MCP       │
                    ├────────────────┤
                    │ MQTT Broker    │
                    │ Router         │
                    │ Event Bus      │
                    │ Database       │
                    │ Plugin Manager │
                    └────────────────┘
                            │
        ┌───────────────────┼────────────────────┐
        │                   │                    │
   Chat Plugin      Registration Plugin    Statistics
        │                   │                    │
   Weather Plugin      Dashboard API      Discord Plugin
```

The core platform is intentionally minimal. Nearly all functionality is implemented as plugins, allowing communities to customize MCP without modifying the core.

---

# Why MCP?

Many Meshtastic communities rely on manually maintained MQTT topics, custom scripts, or one-off automation. As communities grow, those approaches become increasingly difficult to manage.

MCP provides a common platform that separates infrastructure from community-specific logic.

Instead of writing new software for every community, administrators configure MCP and install the plugins they need.

---

# Project Goals

- Keep the core lightweight
- Everything is plugin-driven
- Configuration over customization
- Dynamic instead of static
- Community-first architecture
- Open ecosystem for third-party plugins
- Easy deployment with Docker Compose

---

# Project Status

MCP is currently under active development.

The routing engine, plugin framework, command system, and encrypted Meshtastic packet handling are functional. Registration, federation, dashboard, and additional plugins are actively being developed.

Early adopters and contributors are welcome.

---

# Contributing

Contributions, feature requests, bug reports, and plugin ideas are encouraged.

If you're interested in helping build the future of Meshtastic community infrastructure, we'd love to have your help.

---

# License

This project is released under the MIT License.
