# 🌐 MCP MikroTik — RouterOS AI Bridge

> A lightweight Model Context Protocol (MCP) server that lets AI assistants like **Claude** interact directly with your **MikroTik router** via the native RouterOS API.

Tested on a **MikroTik RB5009** running **RouterOS 7.20.6** — but compatible with any RouterOS 6.43+ device.

---

## ✨ What is this?

This project bridges the gap between AI assistants and network infrastructure. Instead of logging into Winbox or SSH to inspect your router, you can simply ask Claude:

- *"What devices are currently connected on DHCP?"*
- *"Show me all the running interfaces."*
- *"What's the router's current CPU and memory usage?"*
- *"Run `/ip/firewall/filter/print` and summarize the rules."*

The server implements the **RouterOS API wire protocol** from scratch — no third-party RouterOS library required, just Python's standard `socket` and `struct` modules.

---

## 🛠️ Available MCP Tools

| Tool | Description |
|---|---|
| `mikrotik_run_command` | Execute **any** RouterOS API command with optional attributes and query filters |
| `mikrotik_get_interfaces` | List all interfaces with name, type, running state and MTU |
| `mikrotik_get_system_resources` | Get CPU load, RAM usage, uptime and RouterOS version |
| `mikrotik_get_dhcp_leases` | List active DHCP leases (IP, MAC, hostname, status) |

### `mikrotik_run_command` in detail

This is the power tool. It exposes the full RouterOS API to Claude, enabling read and write operations across the entire router configuration.

```python
# Parameters:
# command  (str)            – API path, e.g. "/ip/address/print"
# args     (dict, optional) – Attributes, e.g. {"address": "10.0.0.1/24"}
# queries  (list, optional) – Filters,    e.g. ["type=ether", "running=true"]
```

**Example prompts you can use with Claude:**

```
# Read firewall rules
/ip/firewall/filter/print

# Add a DNS entry
command: /ip/dns/static/add  |  args: {"name": "myserver.home", "address": "192.168.1.100"}

# Reboot the router
/system/reboot

# List only ethernet interfaces
command: /interface/print  |  queries: ["type=ether"]
```

---

## 📋 Prerequisites

- **Python 3.10+**
- A MikroTik router running **RouterOS 6.43 or later** (tested on 7.x)
- The RouterOS **API service enabled** on the router

### Enable the API on your router

Via the RouterOS terminal or SSH:

```
/ip service enable api
```

> **Tip:** For enhanced security, restrict the API service to a specific source IP:
> ```
> /ip service set api address=192.168.1.0/24
> ```

---

## 🚀 Installation

### 1. Clone the repository

```bash
git clone https://github.com/Mattieug/mcp-mikrotik.git
cd mcp-mikrotik
```

### 2. Create a virtual environment

```bash
python -m venv .venv

# Linux / macOS
source .venv/bin/activate

# Windows
.venv\Scripts\activate
```

### 3. Install dependencies

```bash
pip install mcp
```

> The server only depends on [`mcp`](https://pypi.org/project/mcp/) (for `FastMCP`) plus Python's standard library.

---

## ⚙️ Configuration for Claude Desktop

Open your Claude Desktop config file:

| OS | Path |
|---|---|
| Windows | `%APPDATA%\Claude\claude_desktop_config.json` |
| macOS | `~/Library/Application Support/Claude/claude_desktop_config.json` |

You can also reach it via **Claude Desktop → Settings → Developer → Edit Config**.

### Windows example

```json
{
  "mcpServers": {
    "mikrotik_manager": {
      "command": "C:\\mcp-mikrotik\\.venv\\Scripts\\python.exe",
      "args": ["C:\\mcp-mikrotik\\mcp-mikrotik.py"],
      "env": {
        "ROUTEROS_HOST": "192.168.88.1",
        "ROUTEROS_USER": "admin",
        "ROUTEROS_PASSWORD": "your_password",
        "ROUTEROS_PORT": "8728",
        "ROUTEROS_USE_SSL": "false"
      }
    }
  }
}
```

### macOS / Linux example

```json
{
  "mcpServers": {
    "mikrotik_manager": {
      "command": "/path/to/mcp-mikrotik/.venv/bin/python",
      "args": ["/path/to/mcp-mikrotik/mcp-mikrotik.py"],
      "env": {
        "ROUTEROS_HOST": "192.168.88.1",
        "ROUTEROS_USER": "admin",
        "ROUTEROS_PASSWORD": "your_password",
        "ROUTEROS_PORT": "8728",
        "ROUTEROS_USE_SSL": "false"
      }
    }
  }
}
```

> A ready-to-edit template is provided in [`mcp-mikrotik.json`](./mcp-mikrotik.json).

---

## 🔧 Environment Variables

| Variable | Default | Description |
|---|---|---|
| `ROUTEROS_HOST` | `192.168.88.1` | Router IP address or hostname |
| `ROUTEROS_USER` | `admin` | RouterOS API username |
| `ROUTEROS_PASSWORD` | *(empty)* | RouterOS API password |
| `ROUTEROS_PORT` | `8728` | API port (`8728` plain, `8729` SSL) |
| `ROUTEROS_USE_SSL` | `false` | Set to `true` to use an encrypted SSL connection |

---

## 🔒 Security Best Practices

**Never commit credentials.** Always pass them via environment variables (as shown above), never hardcode them in source files.

**Create a dedicated read-only user** on your router rather than using the `admin` account:

```
/user group add name=mcp-readonly policy=read,api,test
/user add name=mcp-claude group=mcp-readonly password=strong_random_password
```

**Restrict API access by source IP** to limit the attack surface:

```
/ip service set api address=127.0.0.1/32
```

**Use SSL** if you're connecting over an untrusted network:
```
ROUTEROS_PORT=8729
ROUTEROS_USE_SSL=true
```

---

## 🏗️ Architecture

The server is a single Python file implementing two things:

### 1. `RouterOSAPI` — Native wire protocol client

A pure-Python implementation of the [RouterOS API protocol](https://help.mikrotik.com/docs/display/ROS/API), handling:

- TCP connection with optional SSL wrapping
- **Length-encoded word framing** (1–5 byte variable-length prefix)
- Sentence-based request/response model (`!re`, `!done`, `!trap`, `!fatal`)
- Plain-text authentication (RouterOS ≥ 6.43)

This means there is **no external RouterOS library dependency** — the protocol is implemented directly on top of Python's `socket` module.

### 2. MCP Tools — FastMCP server

Built with [`FastMCP`](https://github.com/jlowin/fastmcp), the tools are thin wrappers around `RouterOSAPI.call()`. Each tool opens a connection, executes its command, and closes the connection — keeping the server stateless.

```
Claude (AI Assistant)
       │  MCP protocol (stdio)
       ▼
 FastMCP Server  (mcp-mikrotik.py)
       │  RouterOS API protocol (TCP/8728 or TCP/8729)
       ▼
 MikroTik RouterOS
```

---

## 💡 Example Interactions

Once connected, you can have conversations like:

> **You:** "Which devices are connected to my router right now?"
>
> **Claude:** *(calls `mikrotik_get_dhcp_leases`)* "I can see 7 active leases: your NAS at 192.168.1.10, your Proxmox server at 192.168.1.20…"

> **You:** "Is the router under any load?"
>
> **Claude:** *(calls `mikrotik_get_system_resources`)* "CPU is at 3%, 512 MB RAM free, uptime is 14 days. Everything looks healthy."

> **You:** "List all firewall rules that accept traffic on port 443."
>
> **Claude:** *(calls `mikrotik_run_command` with `/ip/firewall/filter/print`)* "I found 3 rules matching…"

---

## 📁 Repository Structure

```
mcp-mikrotik/
├── mcp-mikrotik.py       # MCP server — RouterOS protocol + tool definitions
├── mcp-mikrotik.json     # Claude Desktop config template
└── README.md             # This file
```

---

## 🗺️ Roadmap

Ideas for future tools:

- [ ] `mikrotik_get_firewall_rules` — List and filter firewall rules
- [ ] `mikrotik_get_routes` — Show the routing table
- [ ] `mikrotik_get_wireless_clients` — List connected Wi-Fi clients
- [ ] `mikrotik_get_logs` — Retrieve recent system logs
- [ ] `mikrotik_get_vlan_interfaces` — List VLAN interfaces
- [ ] `mikrotik_ping` — Trigger a ping from the router and return results

Contributions are welcome — feel free to open a PR or an issue!

---

## 📄 License

This project is licensed under the **MIT License** — free to use, modify and distribute.
See [LICENSE](./LICENSE) for full details.

---

## 🙏 Acknowledgements

- [MikroTik RouterOS API documentation](https://help.mikrotik.com/docs/display/ROS/API)
- [FastMCP](https://github.com/jlowin/fastmcp) — the Python framework for building MCP servers
- [Model Context Protocol](https://modelcontextprotocol.io) — the open standard enabling AI-tool integration
