# -----------------------------------------------------
# Importation des librairies
# -----------------------------------------------------

# Librairies Python
import os
import json
import base64
from time import sleep

# Variables d'environnement
from dotenv import load_dotenv

# API Minecraft
from mcstatus import *

# MOTD
from html2image import Html2Image

# Premium ou crack
import socket
import struct

# Envoie sur Discord
import requests
from datetime import datetime, timezone

# Scan des IP d'internet
import asyncio
import ipaddress
import geoip2.database
import itertools

# -----------------------------------------------------
# Initialisation des variables d'environnement
# -----------------------------------------------------

# Chargement de l'environnement
load_dotenv()

# Récupération des variables d'environnement
MC_EDITION=os.getenv('MC_EDITION')
MC_PORTS = os.getenv('MC_PORTS', 'default').lower().strip()
COUNTRIES=os.getenv('COUNTRIES')
MIN_ONLINE=int(os.getenv('MIN_ONLINE'))
AUTH_TYPE=os.getenv('AUTH_TYPE')
DISCORD_WEBHOOK=os.getenv('DISCORD_WEBHOOK')

if MC_PORTS == 'default':
    MC_PORTS = [25565]
else:
    MC_PORTS = [int(p.strip()) for p in MC_PORTS.split(',')]

# Scan des ip d'internet
NETWORK=ipaddress.ip_network('0.0.0.0/0')
MAX_CONNECTIONS=1000
CHECKPOINT_FILE='data/checkpoint.txt'
DISCORD_WEBHOOK=os.getenv('DISCORD_WEBHOOK')

# -----------------------------------------------------
# Définition des fonctions
# -----------------------------------------------------

# Test du serveur
def getServer(ip, port):
    try:
        server = JavaServer(ip, port, timeout=2) if MC_EDITION != 'bedrock' else BedrockServer(ip, port, timeout=2)
        return server.status()
    except Exception as e:
        return e

# Récupération du "Message Of The Day (MOTD)" du serveur
def getMotd(server, output_folder='data', image='motd.png'):
    try:
        html_motd = server.motd.to_html()

        motd_bg = os.path.join(os.getcwd(), 'src/motd_bg.png')
        css = """
            body {
                background: url('"""+motd_bg+"""');
                background-repeat: repeat;
                background-size: contain;
                text-align: center;
            }
        """

        hti = Html2Image(
            custom_flags=[
                '--no-sandbox', 
                '--disable-gpu', 
                '--log-level=3', 
                '--disable-software-rasterizer',
                '--disable-dev-shm-usage'
            ],
            output_path=output_folder,
            browser='chromium',
            browser_executable='/usr/bin/chromium'
        )

        hti.screenshot(
            html_str=html_motd,
            save_as=image,
            css_str=css,
            size=(400, 50)
        )

        return os.path.join(output_folder, image)
    except:
        return

# Vérification du type d'authentification du serveur ( premium ou crack )
def checkPremium(ip, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5.0)

        sock.connect((ip, port))
        
        payload = b'\x00' + b'\xfb\x05' + len(ip).to_bytes(1, 'big') + ip.encode() + port.to_bytes(2, 'big') + b'\x02'
        sock.send(len(payload).to_bytes(1, 'big') + payload)

        user = 'PenTaist'
        login_start = b'\x00' + len(user).to_bytes(1, 'big') + user.encode() + b'\x00'
        sock.send(len(login_start).to_bytes(1, 'big') + login_start)

        response = sock.recv(1024)
        packet_id = response[1]

        if packet_id == 0x01:
            return True
        return
    except:
        return

# Récupération du code et du nom du pays
def getCountry(ip):
    try:
        with geoip2.database.Reader('src/GeoLite2-Country.mmdb') as reader:
            response = reader.country(ip)
            return [response.country.iso_code.lower(), response.country.name]
    except:
        return

# Envoie du message final sur Discord
async def sendDiscord(ip, port, country, server, auth_label, image_path):
    try:
        now = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")

        country_text = f':flag_{country[0].lower()}: {country[1]}' if country[0] == 'un' and country[1] == 'Unknown' else ':man_shrugging: Inconnu'

        embed = {
            "title": "🥳 Nouveau serveur trouvé !",
            "color": 3447003,
            "timestamp": now,
            "thumbnail": {"url": f'https://eu.mc-api.net/v3/server/favicon/{ip}'},
            "image": {"url": "attachment://motd.png"},
            "fields": [
                {"name": 'Pays', "value": country_text, "inline": True},
                {"name": 'IP', "value": f'```{ip}:{port}```', "inline": False},
                {"name": "Version", "value": str(server.version.name), "inline": True},
                {"name": "Joueurs", "value": f"{server.players.online}/{server.players.max}", "inline": True},
                {"name": "Auth", "value": auth_label, "inline": True}
            ]
        }

        payload = {"payload_json": json.dumps({"username": "MSS", "embeds": [embed]})}

        with open(image_path, "rb") as f:
            files = {"file": ("motd.png", f, "image/png")}

            response = await asyncio.to_thread(
                requests.post, 
                DISCORD_WEBHOOK, 
                data=payload, 
                files=files
            )

        if response.status_code not in [200, 204]:
            print(f"⚠️ Discord a répondu avec l'erreur {response.status_code}: {response.text}")

        return response.status_code

    except Exception as e:
        print(f"Erreur Discord: {e}")
        return

# Fonction pour récupérer les serveurs dans le fichier data/servers.json
def loadServers(filepath):
    if not os.path.exists(filepath) or os.stat(filepath).st_size == 0:
        return set()
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
            return {s['ip'] for s in data} if isinstance(data, list) else set()
    except:
        return set()

# Fonction pour sauvegarder les serveurs déjà analysés
def saveServer(ip, port, country, server, auth_label):
    path = 'data/servers.json'
    os.makedirs('data', exist_ok=True)
    all_servers = []

    if os.path.exists(path):
        try:
            with open(path, 'r', encoding='utf-8') as f:
                all_servers = json.load(f)
        except: pass

    new_entry = {
        "ip": ip,
        "port": port,
        "country": country,
        "version": server.version.name,
        "online_players": f"{server.players.online}/{server.players.max}",
        "auth": auth_label
    }
    all_servers.append(new_entry)

    with open(path, 'w', encoding='utf-8') as f:
        json.dump(all_servers, f, indent=4, ensure_ascii=False)

def getCheckpoint():
    if os.path.exists(CHECKPOINT_FILE):
        with open(CHECKPOINT_FILE, "r") as f:
            content = f.read().strip()
            if ":" in content:
                parts = content.split(":")
                return parts[0], int(parts[1])
    return None, None

def saveCheckpoint(ip, port):
    with open(CHECKPOINT_FILE, "w") as f:
        f.write(f"{ip}:{port}")

# Fonction de pré-scan TCP
async def preScan(ip, port):
    try:
        conn = asyncio.open_connection(ip, port)
        reader, writer = await asyncio.wait_for(conn, timeout=1.0)
        writer.close()

        return await writer.wait_closed()
    except:
        return

# Fonction pour scanner un serveur
async def checkPort(ip, port, semaphore, known_ips):
    async with semaphore:
        try:
            if not await preScan(ip, port):
                return

            server = await asyncio.to_thread(getServer, ip, port)
            
            if server and server.players.online >= MIN_ONLINE:
                country = getCountry(ip) or ["un", "Unknown"]

                if COUNTRIES != 'ALL' and country[0].upper() not in COUNTRIES:
                    return

                is_premium = await asyncio.to_thread(checkPremium, ip, port)
                auth_label = "Premium" if is_premium else "Crack/Open"
                
                if AUTH_TYPE == 'ALL' or (AUTH_TYPE == 'premium' and is_premium) or (AUTH_TYPE == 'crack' and not is_premium):
                    img_path = await asyncio.to_thread(getMotd, server)

                    if img_path:
                        print(f"\n✅ Serveur trouvé : {ip}:{port}")
                        saveServer(ip=ip, port=port, country=country, server=server, auth_label=auth_label)
                        await sendDiscord(ip=ip, port=port, country=country, server=server, auth_label=auth_label, image_path=img_path)
                        known_ips.add(str(ip))
        except Exception:
            pass

# Boucle de lancement principale
async def main():
    last_ip, last_port = getCheckpoint()
    found_resume_point = True if last_ip is None else False

    if not found_resume_point:
        print(f"🚀 Reprise du scan à partir de : {last_ip}")
    else:
        print(f"🚀 Début du scan sur {NETWORK}...")

    known_ips = loadServers('data/servers.json')
    semaphore = asyncio.Semaphore(MAX_CONNECTIONS)
    tasks = set() 
    
    current_ip_int = int(ipaddress.ip_address(last_ip)) if last_ip else 0
    end_ip_int = int(ipaddress.ip_address("255.255.255.255"))

    for i in range(current_ip_int, end_ip_int + 1):
        ip = ipaddress.ip_address(i)
        
        if not ip.is_global or str(ip) in known_ips:
            continue

        for port in MC_PORTS:
            task = asyncio.create_task(checkPort(str(ip), port, semaphore, known_ips))
            tasks.add(task)
            task.add_done_callback(tasks.discard)

            if i % 100 == 0:
                print(f"\r🧭 Analyse de {ip}:{port} | Tâches actives: {len(tasks)} ", end="", flush=True)
                saveCheckpoint(str(ip), port)

            if len(tasks) >= MAX_CONNECTIONS * 2:
                await asyncio.sleep(0.01)

    if tasks:
        await asyncio.gather(*tasks)

# -----------------------------------------------------
# Lancement du script
# -----------------------------------------------------

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n🛑 Arrêt du scan...")