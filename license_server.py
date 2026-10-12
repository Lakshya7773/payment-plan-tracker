#!/usr/bin/env python3
"""
License Activation Server for Payment Plan Tracker Pro
Runs on port 8765 — handles license key validation and activation.
"""
import http.server
import json
import sqlite3
import hmac
import hashlib
import secrets
import string
import os
from datetime import datetime
from urllib.parse import urlparse, parse_qs

DB_PATH = os.path.join(os.path.dirname(__file__), 'licenses.db')
SECRET_KEY = b'ppt_pro_2026_a7f3k9m2x8q1'  # Must match license_generator.py

def init_db():
    conn = sqlite3.connect(DB_PATH)
    conn.execute('''
        CREATE TABLE IF NOT EXISTS licenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT UNIQUE NOT NULL,
            buyer_email TEXT,
            buyer_name TEXT,
            status TEXT DEFAULT 'unused',
            activated_at TEXT,
            activated_browser TEXT,
            created_at TEXT DEFAULT (datetime('now'))
        )
    ''')
    conn.execute('''
        CREATE TABLE IF NOT EXISTS activations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            license_key TEXT NOT NULL,
            browser_fingerprint TEXT NOT NULL,
            activated_at TEXT DEFAULT (datetime('now')),
            UNIQUE(license_key, browser_fingerprint)
        )
    ''')
    conn.commit()
    conn.close()

def is_valid_key(key):
    if not key or not key.startswith('PPT-'):
        return False
    parts = key.split('-')
    if len(parts) != 5:
        return False
    raw = ''.join(parts[1:4])
    expected_sig = hmac.new(SECRET_KEY, raw.encode(), hashlib.sha256).hexdigest()[:4].upper()
    return parts[4] == expected_sig

def activate_key(key, browser_fingerprint):
    conn = sqlite3.connect(DB_PATH)
    
    row = conn.execute('SELECT status FROM licenses WHERE license_key = ?', (key,)).fetchone()
    if not row:
        conn.close()
        return False, 'Invalid license key', 404
    
    if row[0] == 'revoked':
        conn.close()
        return False, 'License key has been revoked', 403
    
    # Check if already activated on this browser
    existing = conn.execute(
        'SELECT id FROM activations WHERE license_key = ? AND browser_fingerprint = ?',
        (key, browser_fingerprint)
    ).fetchone()
    
    if existing:
        conn.close()
        return True, 'License already activated on this device', 200
    
    # Check if activated on a different browser
    other = conn.execute(
        'SELECT browser_fingerprint FROM activations WHERE license_key = ?',
        (key,)
    ).fetchone()
    
    if other and other[0] != browser_fingerprint:
        conn.close()
        return False, 'License key already activated on another device. Contact support.', 409
    
    # Activate
    conn.execute(
        'INSERT INTO activations (license_key, browser_fingerprint) VALUES (?, ?)',
        (key, browser_fingerprint)
    )
    conn.execute(
        "UPDATE licenses SET status = 'activated', activated_at = datetime('now'), activated_browser = ? WHERE license_key = ?",
        (browser_fingerprint, key)
    )
    conn.commit()
    conn.close()
    return True, 'License activated successfully!', 200

def validate_key(key, browser_fingerprint):
    """Validate an existing activation (for app startup check)."""
    conn = sqlite3.connect(DB_PATH)
    
    row = conn.execute('SELECT status FROM licenses WHERE license_key = ?', (key,)).fetchone()
    if not row:
        conn.close()
        return False, 'Invalid license key', 404
    
    if row[0] == 'revoked':
        conn.close()
        return False, 'License key has been revoked', 403
    
    # Check if activated on this browser
    existing = conn.execute(
        'SELECT id FROM activations WHERE license_key = ? AND browser_fingerprint = ?',
        (key, browser_fingerprint)
    ).fetchone()
    
    conn.close()
    
    if existing:
        return True, 'License valid', 200
    
    # Check if activated elsewhere
    if row[0] == 'activated':
        return False, 'License activated on another device', 409
    
    return False, 'License not activated', 400

class LicenseHandler(http.server.BaseHTTPRequestHandler):
    def do_OPTIONS(self):
        self.send_response(200)
        self.send_header('Access-Control-Allow-Origin', '*')
        self.send_header('Access-Control-Allow-Methods', 'POST, GET, OPTIONS')
        self.send_header('Access-Control-Allow-Headers', 'Content-Type')
        self.end_headers()
    
    def do_GET(self):
        parsed = urlparse(self.path)
        path = parsed.path
        params = parse_qs(parsed.query)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        if path == '/health':
            self.wfile.write(json.dumps({'status': 'ok', 'service': 'license-server'}).encode())
        
        elif path == '/validate':
            key = params.get('key', [''])[0]
            fingerprint = params.get('fingerprint', [''])[0]
            success, message, code = validate_key(key, fingerprint)
            self.wfile.write(json.dumps({
                'valid': success,
                'message': message
            }).encode())
        
        else:
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())
    
    def do_POST(self):
        parsed = urlparse(self.path)
        path = parsed.path
        
        content_length = int(self.headers.get('Content-Length', 0))
        body = self.rfile.read(content_length)
        
        self.send_response(200)
        self.send_header('Content-Type', 'application/json')
        self.send_header('Access-Control-Allow-Origin', '*')
        self.end_headers()
        
        if path == '/activate':
            try:
                data = json.loads(body)
                key = data.get('key', '').strip().upper()
                fingerprint = data.get('fingerprint', '')
                
                if not key:
                    self.wfile.write(json.dumps({
                        'success': False,
                        'message': 'License key is required'
                    }).encode())
                    return
                
                if not is_valid_key(key):
                    self.wfile.write(json.dumps({
                        'success': False,
                        'message': 'Invalid license key format'
                    }).encode())
                    return
                
                success, message, code = activate_key(key, fingerprint)
                self.send_response(code)
                self.wfile.write(json.dumps({
                    'success': success,
                    'message': message
                }).encode())
            
            except json.JSONDecodeError:
                self.wfile.write(json.dumps({
                    'success': False,
                    'message': 'Invalid request'
                }).encode())
        
        else:
            self.wfile.write(json.dumps({'error': 'Not found'}).encode())

def run_server(port=8765):
    init_db()
    server = http.server.HTTPServer(('0.0.0.0', port), LicenseHandler)
    print(f"License server running on port {port}")
    server.serve_forever()

if __name__ == '__main__':
    run_server()
