import socket
import os
import urllib.request
from urllib.error import URLError

def run_network_autopsy():
    print("\n[!] ================= NETWORK AUTOPSY ENGINE ================= [!]")
    
    # 1. HARDWARE IP CHECK
    print("[*] TEST 1: Identifying Physical Network Adapters...")
    hostname = socket.gethostname()
    local_ips = socket.gethostbyname_ex(hostname)[2]
    
    active_ip = None
    for ip in local_ips:
        if ip.startswith("172.") or ip.startswith("192."):
            active_ip = ip
            print(f"    -> Found Valid Local IP: {ip}")
            
    if active_ip != "172.20.10.13":
        print(f"\n[-] CRITICAL FAILURE: Your laptop's actual IP ({active_ip}) does NOT match the IP your phone is trying to reach (172.20.10.13).")
        print("[-] FIX: Update the Backend IP in your React Native app to match your laptop's current IP.")
        return
    else:
        print("[+] SUCCESS: Laptop IP matches the React Native target IP.")

    # 2. LOCALHOST PORT CHECK
    print("\n[*] TEST 2: Checking if Uvicorn is actually alive on Port 8000...")
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    result = sock.connect_ex(('127.0.0.1', 8000))
    if result == 0:
        print("[+] SUCCESS: FastAPI is running and Port 8000 is listening locally.")
    else:
        print("[-] CRITICAL FAILURE: Port 8000 is DEAD.")
        print("[-] FIX: You did not start your server, or it crashed. Run: uvicorn main:app --host 0.0.0.0 --port 8000")
        sock.close()
        return
    sock.close()

    # 3. EXTERNAL BINDING CHECK
    print("\n[*] TEST 3: Checking 0.0.0.0 External Binding...")
    try:
        req = urllib.request.urlopen(f"http://{active_ip}:8000/docs", timeout=3)
        if req.getcode() == 200:
            print("[+] SUCCESS: The server is successfully accepting external traffic on your IP.")
    except URLError as e:
        print(f"[-] CRITICAL FAILURE: The server is ignoring traffic to {active_ip}.")
        print(f"[-] REASON: {e.reason}")
        print("[-] FIX: You likely started uvicorn without '--host 0.0.0.0'. Restart it with the correct flags.")
        return

    print("\n[+] ================= AUTOPSY COMPLETE ================= [+]")
    print("[!] If all 3 tests say SUCCESS, your Python code is perfect.")
    print("[!] THE TIMEOUT IS BEING CAUSED BY WINDOWS FIREWALL DROPPING THE PACKETS.")

if __name__ == "__main__":
    run_network_autopsy()