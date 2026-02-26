🚀 Serveur MCP MikroTik (RouterOS)Ce projet implémente un serveur Model Context Protocol (MCP) permettant aux assistants IA (comme Claude) d'interagir nativement avec les routeurs MikroTik fonctionnant sous RouterOS (testé sur un MikroTik RB5009 avec RouterOS 7.20.6).Il utilise l'API native de RouterOS pour exécuter des commandes, récupérer l'état des interfaces, lire les baux DHCP, et surveiller l'utilisation du système.✨ Fonctionnalités (Outils MCP)mikrotik_run_command : Exécute n'importe quelle commande API personnalisée avec support des attributs et des requêtes (filtres).mikrotik_get_interfaces : Récupère la liste de toutes les interfaces et leur statut.mikrotik_get_system_resources : Affiche l'utilisation CPU, la RAM, l'uptime et la version de RouterOS.mikrotik_get_dhcp_leases : Liste les baux DHCP actifs sur le réseau.📋 PrérequisPython 3.10 ou supérieur.Un routeur MikroTik avec l'API activée.Pour activer l'API via le terminal du routeur : /ip service enable api🛠️ InstallationClonez ce dépôt :git clone [https://github.com/votre-nom/mikrotik-mcp-server.git](https://github.com/votre-nom/mikrotik-mcp-server.git)
cd mikrotik-mcp-server
Créez un environnement virtuel (recommandé) :python -m venv .venv
# Sur Windows : .venv\Scripts\activate
# Sur Linux/Mac : source .venv/bin/activate
Installez les dépendances :pip install -r requirements.txt
Configurez vos variables d'environnement en copiant le fichier d'exemple :cp .env.example .env
Remplissez le fichier .env avec les identifiants de votre routeur.⚙️ Configuration pour Claude DesktopPour utiliser ce serveur avec l'application de bureau Claude, modifiez votre fichier de configuration claude_desktop_config.json (accessible via Settings > Developer > Edit Config) :Sous Windows :{
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
Note: Assurez-vous de bien doubler les antislashs \\ dans le fichier JSON.🔒 SécuritéNe commitez jamais vos mots de passe. Utilisez toujours des variables d'environnement. Il est fortement recommandé de créer un utilisateur spécifique sur votre routeur MikroTik avec des droits restreints (groupe read ou API-only) plutôt que d'utiliser le compte administrateur complet.📄 LicenceCe projet est sous licence MIT. Voir le fichier LICENSE pour plus de détails.