import socket
import struct
import ssl
import os
from typing import Optional, Dict, List, Any
from mcp.server.fastmcp import FastMCP

# Initialisation du serveur MCP
mcp = FastMCP("MikroTik_RB5009_Manager")

class RouterOSAPI:
    """
    Client de communication avec l'API RouterOS implémentant le protocole
    décrit dans la documentation officielle de MikroTik.
    """
    def __init__(self, host: str, user: str, password: str, port: int = 8728, use_ssl: bool = False):
        self.host = host
        self.user = user
        self.password = password
        self.port = port
        self.use_ssl = use_ssl
        self.sk = None

    def connect(self):
        """Établit la connexion TCP/SSL et effectue l'authentification (post v6.43)."""
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
        """Ferme la connexion proprement."""
        if self.sk:
            self.sk.close()
            self.sk = None

    def _encode_length(self, length: int) -> bytes:
        """
        Encode la longueur du mot selon la table du protocole API :
        - 1 byte pour < 0x80
        - 2 bytes pour < 0x4000
        - 3 bytes pour < 0x200000
        - 4 bytes pour < 0x10000000
        - 5 bytes pour >= 0x10000000
        """
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
        """Décode la longueur du mot reçu depuis le flux réseau."""
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
        """Envoie un mot encodé (longueur + données)."""
        encoded_word = word.encode('utf-8')
        self.sk.sendall(self._encode_length(len(encoded_word)))
        self.sk.sendall(encoded_word)

    def _read_word(self) -> str:
        """Lit un mot complet depuis le réseau."""
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
        """Envoie une phrase complète (liste de mots), terminée par un mot vide."""
        for w in words:
            self._write_word(w)
        self._write_word("") # Mot de longueur zéro pour terminer

    def read_sentence(self) -> List[str]:
        """Lit une phrase complète jusqu'à rencontrer un mot vide."""
        sentence = []
        while True:
            w = self._read_word()
            if w == "":
                break
            sentence.append(w)
        return sentence

    def _login(self):
        """Procédure de connexion pour RouterOS >= 6.43 (nom/mot de passe en clair)."""
        self.send_sentence(["/login", "=name=" + self.user, "=password=" + self.password])
        reply = self.read_sentence()
        if reply and reply[0] == '!trap':
            raise Exception(f"Échec de l'authentification : {reply}")

    def call(self, command: str, args: Optional[Dict[str, str]] = None, queries: Optional[List[str]] = None) -> List[Dict[str, str]]:
        """
        Exécute une commande sur le routeur et retourne les réponses.
        Gère les réponses !re (données), !done (fin), !trap (erreur).
        """
        words = [command]
        
        # Ajout des attributs (ex: =name=ether1)
        if args:
            for k, v in args.items():
                words.append(f"={k}={v}")
                
        # Ajout des requêtes (ex: ?type=ether)
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
    """Récupère les identifiants depuis l'environnement et instancie le client."""
    host = os.environ.get("ROUTEROS_HOST", "192.168.88.1")
    user = os.environ.get("ROUTEROS_USER", "admin")
    password = os.environ.get("ROUTEROS_PASSWORD", "")
    port = int(os.environ.get("ROUTEROS_PORT", "8728"))
    use_ssl = os.environ.get("ROUTEROS_USE_SSL", "false").lower() == "true"
    
    api = RouterOSAPI(host, user, password, port, use_ssl)
    api.connect()
    return api


# --- Définition des Outils MCP (Tools) ---

@mcp.tool()
def mikrotik_run_command(command: str, args: Optional[Dict[str, str]] = None, queries: Optional[List[str]] = None) -> List[Dict[str, str]]:
    """
    Exécute n'importe quelle commande API sur le routeur MikroTik.
    Utile pour lire des informations ou modifier la configuration.
    
    :param command: La commande API (ex: "/ip/address/print" ou "/system/reboot").
    :param args: Dictionnaire d'attributs (ex: {"proplist": "address,interface"} ou {"address": "10.0.0.1/24"}).
    :param queries: Liste de filtres (ex: ["type=ether", "#!"]).
    """
    api = get_api_client()
    try:
        return api.call(command, args, queries)
    finally:
        api.disconnect()

@mcp.tool()
def mikrotik_get_interfaces() -> List[Dict[str, str]]:
    """
    Récupère la liste de toutes les interfaces du routeur (nom, type, état).
    """
    api = get_api_client()
    try:
        return api.call("/interface/print", args={".proplist": ".id,name,type,disabled,running,mtu"})
    finally:
        api.disconnect()

@mcp.tool()
def mikrotik_get_system_resources() -> List[Dict[str, str]]:
    """
    Récupère l'utilisation des ressources système (CPU, mémoire, uptime, version de RouterOS).
    """
    api = get_api_client()
    try:
        return api.call("/system/resource/print")
    finally:
        api.disconnect()

@mcp.tool()
def mikrotik_get_dhcp_leases() -> List[Dict[str, str]]:
    """
    Récupère la liste des baux DHCP actifs attribués par le routeur.
    """
    api = get_api_client()
    try:
        return api.call("/ip/dhcp-server/lease/print", args={".proplist": "address,mac-address,host-name,status,bound-to"})
    finally:
        api.disconnect()


if __name__ == "__main__":
    # Point d'entrée pour démarrer le serveur MCP
    mcp.run()