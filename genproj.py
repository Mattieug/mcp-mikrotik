import os

# Dictionnaire contenant le nom des fichiers et leur contenu exact
files_to_create = {
    "mikrotik_mcp.py": r"""import socket
import struct
import ssl
import os
from typing import Optional, Dict, List, Any
from mcp.server.fastmcp import FastMCP

# Initialisation du serveur MCP
mcp = FastMCP("MikroTik_RB5009_Manager")

class RouterOSAPI:
    \"\"\"
    Client de communication avec l'API RouterOS implémentant le protocole
    décrit dans la documentation officielle de MikroTik.
    \"\"\"
    def __init__(self, host: str, user: str, password: str, port: int = 8728, use_ssl: bool = False):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self.sk = None

    def connect(self):
        self.sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sk.settimeout(10.0)
        
        if self.use_ssl:
            context = ssl.create_default_context()
            context.check_hostname = False
            context.verify_mode = ssl.CERT_NONE
            self.sk = context.wrap_socket(self.sk)
            
        self.sk.connect((self.host, self.port))
        self._login()

    def disconnect(self):
        if self.sk:
            self.sk.close()
            self.sk = None

    def _encode_length(self, length: int) -> bytes:
        if length < 0x80:
            return struct.pack('!B', length)
        elif length < 0x4000:
            length |= 0x8000
            return struct.pack('!H', length)
        elif length < 0x200000:
            length |= 0xC00000
            return struct.pack('!I', length)[1:4]
        elif length < 0x10000000:
            length |= 0xE0000000
            return struct.pack('!I', length)
        else:
            return struct.pack('!B', 0xF0) + struct.pack('!I', length)

    def _read_length(self) -> int:
        r = self.sk.recv(1)
        if not r: return 0
        c = ord(r)
        if (c & 0x80) == 0x00:
            return c
        elif (c & 0xC0) == 0x80:
            r += self.sk.recv(1)
            return struct.unpack('!H', r)[0] & ~0x8000
        elif (c & 0xE0) == 0xC0:
            r += self.sk.recv(2)
            return struct.unpack('!I', b'\x00' + r)[0] & ~0xC00000
        elif (c & 0xF0) == 0xE0:
            r += self.sk.recv(3)
            return struct.unpack('!I', r)[0] & ~0xE0000000
        elif (c & 0xF8) == 0xF0:
            r = self.sk.recv(4)
            return struct.unpack('!I', r)[0]
        return 0

    def _write_word(self, word: str):
        encoded_word = word.encode('utf-8')
        self.sk.sendall(self._encode_length(len(encoded_word)))
        self.sk.sendall(encoded_word)

    def _read_word(self) -> str:
        l = self._read_length()
        if l == 0:
            return ""
        data = b""
        while len(data) < l:
            chunk = self.sk.recv(l - len(data))
            if not chunk: break
            data += chunk
        return data.decode('utf-8', errors='replace')

    def send_sentence(self, words: List[str]):
        for w in words:
            self._write_word(w)
        self._write_word("") 

    def read_sentence(self) -> List[str]:
        sentence = []
        while True:
            w = self._read_word()
            if w == "":
                break
            sentence.append(w)
        return sentence

    def _login(self):
        self.send_sentence(["/login", "=name=" + self.user, "=password=" + self.password])
        reply = self.read_sentence()
        if reply and reply[0] == '!trap':
            raise Exception(f"Échec de l'authentification : {reply}")

    def call(self, command: str, args: Optional[Dict[str, str]] = None, queries: Optional[List[str]] = None) -> List[Dict[str, str]]:
        words = [command]
        if args:
            for k, v in args.items():
                words.append(f"={k}={v}")
        if queries:
            for q in queries:
                words.append(f"?{q}")
                
        self.send_sentence(words)

        responses = []
        while True:
            sentence = self.read_sentence()
            if not sentence:
                continue
                
            reply_type = sentence[0]
            if reply_type == '!done':
                break
            elif reply_type == '!re':
                parsed = {}
                for w in sentence[1:]:
                    if w.startswith('='):
                        parts = w[1:].split('=', 1)
                        if len(parts) == 2:
                            parsed[parts[0]] = parts[1]
                        else:
                            parsed[parts[0]] = ""
                responses.append(parsed)
            elif reply_type == '!trap':
                error_msg = next((w.split('=', 1)[1] for w in sentence if w.startswith('=message=')), "Erreur inconnue")
                raise Exception(f"Erreur de commande RouterOS : {error_msg} ({sentence})")
            elif reply_type == '!fatal':
                raise Exception(f"Erreur fatale, connexion fermée : {sentence}")
                
        return responses

def get_api_client() -> RouterOSAPI:
    host = os.environ.get("ROUTEROS_HOST", "192.168.88.1")
    user = os.environ.get("ROUTEROS_USER", "admin")
    password = os.environ.get("ROUTEROS_PASSWORD", "")
    port = int(os.environ.get("ROUTEROS_PORT", "8728"))
    use_ssl = os.environ.get("ROUTEROS_USE_SSL", "false").lower() == "true"
    
    api = RouterOSAPI(host, user, password, port, use_ssl)
    api.connect()
    return api

@mcp.tool()
def mikrotik_run_command(command: str, args: Optional[Dict[str, str]] = None, queries: Optional[List[str]] = None) -> List[Dict[str, str]]:
    \"\"\"Exécute n'importe quelle commande API sur le routeur MikroTik.\"\"\"
    api = get_api_client()
    try:
        return api.call(command, args, queries)
    finally:
        api.disconnect()

@mcp.tool()
def mikrotik_get_interfaces() -> List[Dict[str, str]]:
    \"\"\"Récupère la liste de toutes les interfaces du routeur.\"\"\"
    api = get_api_client()
    try:
        return api.call("/interface/print", args={".proplist": ".id,name,type,disabled,running,mtu"})
    finally:
        api.disconnect()

@mcp.tool()
def mikrotik_get_system_resources() -> List[Dict[str, str]]:
    \"\"\"Récupère l'utilisation des ressources système (CPU, mémoire, etc.).\"\"\"
    api = get_api_client()
    try:
        return api.call("/system/resource/print")
    finally:
        api.disconnect()

@mcp.tool()
def mikrotik_get_dhcp_leases() -> List[Dict[str, str]]:
    \"\"\"Récupère la liste des baux DHCP actifs.\"\"\"
    api = get_api_client()
    try:
        return api.call("/ip/dhcp-server/lease/print", args={".proplist": "address,mac-address,host-name,status,bound-to"})
    finally:
        api.disconnect()

if __name__ == "__main__":
    mcp.run()
""",

    "README.md": r"""# 🚀 Serveur MCP MikroTik (RouterOS)

[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![RouterOS](https://img.shields.io/badge/RouterOS-7.20%2B-lightgrey.svg)](https://mikrotik.com/software)

Ce projet implémente un serveur **Model Context Protocol (MCP)** permettant aux assistants IA (comme Claude) d'interagir nativement avec les routeurs MikroTik fonctionnant sous RouterOS (testé sur un MikroTik RB5009 avec RouterOS 7.20.6).

Il utilise l'API native de RouterOS pour exécuter des commandes, récupérer l'état des interfaces, lire les baux DHCP, et surveiller l'utilisation du système.

## ✨ Fonctionnalités (Outils MCP)
* `mikrotik_run_command` : Exécute n'importe quelle commande API personnalisée avec support des attributs et des requêtes (filtres).
* `mikrotik_get_interfaces` : Récupère la liste de toutes les interfaces et leur statut.
* `mikrotik_get_system_resources` : Affiche l'utilisation CPU, la RAM, l'uptime et la version de RouterOS.
* `mikrotik_get_dhcp_leases` : Liste les baux DHCP actifs sur le réseau.

## 📋 Prérequis
1.  **Python 3.10** ou supérieur.
2.  Un routeur **MikroTik** avec l'API activée (`/ip service enable api`).

## 🛠️ Installation
1. Créez un environnement virtuel (recommandé) :
   ```bash
   python -m venv .venv
   # Sur Windows : .venv\Scripts\activate
   ```
2. Installez les dépendances :
   ```bash
   pip install -r requirements.txt
   ```
3. Configurez vos variables d'environnement en modifiant le fichier `.env` généré avec vos identifiants.

## ⚙️ Configuration pour Claude Desktop
Modifiez votre fichier de configuration `claude_desktop_config.json` :

```json
{
  "mcpServers": {
    "mikrotik_manager": {
      "command": "C:\\Chemin\\Vers\\Votre\\Projet\\.venv\\Scripts\\python.exe",
      "args": ["C:\\Chemin\\Vers\\Votre\\Projet\\mikrotik_mcp.py"],
      "env": {
        "ROUTEROS_HOST": "192.168.88.1",
        "ROUTEROS_USER": "admin",
        "ROUTEROS_PASSWORD": "votre_mot_de_passe",
        "ROUTEROS_PORT": "8728",
        "ROUTEROS_USE_SSL": "false"
      }
    }
  }
}
```

## 📄 Licence
Ce projet est sous licence MIT.
""",

    ".gitignore": r"""# Byte-compiled / optimized / DLL files
__pycache__/
*.py[cod]
*$py.class

# Environnements Virtuels
.env
.venv
env/
venv/
ENV/

# Configuration IDE
.vscode/
.idea/

# Fichiers système
.DS_Store
Thumbs.db
""",

    "requirements.txt": r"""mcp>=1.0.0
fastmcp>=0.1.0
""",

    ".env.example": r"""# Adresse IP du routeur MikroTik (ex: 192.168.88.1)
ROUTEROS_HOST=192.168.88.1

# Nom d'utilisateur
ROUTEROS_USER=admin

# Mot de passe de l'utilisateur (à ne jamais pousser sur Git !)
ROUTEROS_PASSWORD=votre_mot_de_passe_securise

# Port de l'API (Défaut: 8728, ou 8729 si SSL/TLS)
ROUTEROS_PORT=8728

# Activer ou non le SSL (true / false)
ROUTEROS_USE_SSL=false
""",

    "LICENSE": r"""MIT License

Copyright (c) 2024

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
"""
}

def create_files():
    print("🚀 Création des fichiers du projet...")
    for filename, content in files_to_create.items():
        with open(filename, "w", encoding="utf-8") as f:
            f.write(content.strip() + "\n")
        print(f"✅ Fichier créé : {filename}")
    
    # Créer le fichier .env réel à partir de l'exemple pour faciliter l'installation
    if not os.path.exists(".env"):
        with open(".env", "w", encoding="utf-8") as f:
            f.write(files_to_create[".env.example"].strip() + "\n")
        print(f"✅ Fichier créé : .env (Prêt à être rempli)")

    print("\n🎉 Terminé ! Votre dossier de projet est maintenant complet.")
    print("👉 Il ne vous reste plus qu'à remplir vos identifiants dans le fichier '.env'.")

if __name__ == "__main__":
    create_files()