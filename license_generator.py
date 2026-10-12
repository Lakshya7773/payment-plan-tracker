#!/usr/bin/env python3
"""
License Key Generator for Payment Plan Tracker Pro
Generates single-use license keys and tracks them in SQLite.
"""
import sqlite3
import hmac
import hashlib
import secrets
import string
import os

DB_PATH = os.path.join(os.path.dirname(__file__), 'licenses.db')
SECRET_KEY = b'ppt_pro_2026_a7f3k9m2x8q1'  # Change this to your own secret!

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

def generate_key():
    """Generate a license key in format: PPT-XXXX-XXXX-XXXX"""
    part1 = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    part2 = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    part3 = ''.join(secrets.choice(string.ascii_uppercase + string.digits) for _ in range(4))
    
    raw = f"{part1}{part2}{part3}"
    signature = hmac.new(SECRET_KEY, raw.encode(), hashlib.sha256).hexdigest()[:4].upper()
    
    return f"PPT-{part1}-{part2}-{part3}-{signature}"

def is_valid_key(key):
    """Validate a license key's signature."""
    if not key or not key.startswith('PPT-'):
        return False
    parts = key.split('-')
    if len(parts) != 5:
        return False
    raw = ''.join(parts[1:4])
    expected_sig = hmac.new(SECRET_KEY, raw.encode(), hashlib.sha256).hexdigest()[:4].upper()
    return parts[4] == expected_sig

def add_key(buyer_email='', buyer_name=''):
    """Generate and store a new license key."""
    conn = sqlite3.connect(DB_PATH)
    key = generate_key()
    while True:
        try:
            conn.execute(
                'INSERT INTO licenses (license_key, buyer_email, buyer_name) VALUES (?, ?, ?)',
                (key, buyer_email, buyer_name)
            )
            conn.commit()
            break
        except sqlite3.IntegrityError:
            key = generate_key()
    conn.close()
    return key

def activate_key(key, browser_fingerprint):
    """Activate a license key for a specific browser. Returns (success, message)."""
    conn = sqlite3.connect(DB_PATH)
    
    # Check if key exists
    row = conn.execute('SELECT status FROM licenses WHERE license_key = ?', (key,)).fetchone()
    if not row:
        conn.close()
        return False, 'Invalid license key'
    
    if row[0] == 'revoked':
        conn.close()
        return False, 'License key has been revoked'
    
    # Check if already activated on this browser
    existing = conn.execute(
        'SELECT id FROM activations WHERE license_key = ? AND browser_fingerprint = ?',
        (key, browser_fingerprint)
    ).fetchone()
    
    if existing:
        # Already activated on this browser — OK
        conn.close()
        return True, 'License already activated on this device'
    
    # Check if activated on a different browser (single-use enforcement)
    other = conn.execute(
        'SELECT browser_fingerprint FROM activations WHERE license_key = ?',
        (key,)
    ).fetchone()
    
    if other and other[0] != browser_fingerprint:
        conn.close()
        return False, 'License key already activated on another device. Contact support.'
    
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
    return True, 'License activated successfully!'

def list_keys():
    """List all license keys."""
    conn = sqlite3.connect(DB_PATH)
    rows = conn.execute('''
        SELECT l.license_key, l.buyer_email, l.buyer_name, l.status, l.activated_at,
               COUNT(a.id) as activation_count
        FROM licenses l
        LEFT JOIN activations a ON l.license_key = a.license_key
        GROUP BY l.license_key
        ORDER BY l.created_at DESC
    ''').fetchall()
    conn.close()
    return rows

def revoke_key(key):
    """Revoke a license key."""
    conn = sqlite3.connect(DB_PATH)
    conn.execute("UPDATE licenses SET status = 'revoked' WHERE license_key = ?", (key,))
    conn.commit()
    conn.close()

if __name__ == '__main__':
    import sys
    
    init_db()
    
    if len(sys.argv) < 2:
        print("Usage:")
        print("  python license_generator.py generate [email] [name]  — Generate new key")
        print("  python license_generator.py validate <key>            — Validate key format")
        print("  python license_generator.py list                      — List all keys")
        print("  python license_generator.py revoke <key>              — Revoke a key")
        print("  python license_generator.py export                    — Export keys to CSV")
        sys.exit(1)
    
    cmd = sys.argv[1]
    
    if cmd == 'generate':
        email = sys.argv[2] if len(sys.argv) > 2 else ''
        name = sys.argv[3] if len(sys.argv) > 3 else ''
        key = add_key(email, name)
        print(f"License Key: {key}")
        if email:
            print(f"Buyer: {name} <{email}>")
        print(f"Status: unused")
    
    elif cmd == 'validate':
        key = sys.argv[2]
        if is_valid_key(key):
            print(f"VALID: {key}")
        else:
            print(f"INVALID: {key}")
    
    elif cmd == 'list':
        rows = list_keys()
        print(f"{'Key':<30} {'Email':<25} {'Name':<20} {'Status':<12} {'Activated':<20} {'Devices'}")
        print('-' * 130)
        for row in rows:
            print(f"{row[0]:<30} {row[1] or '-':<25} {row[2] or '-':<20} {row[3]:<12} {row[4] or '-':<20} {row[5]}")
        print(f"\nTotal: {len(rows)} keys")
    
    elif cmd == 'revoke':
        key = sys.argv[2]
        revoke_key(key)
        print(f"Revoked: {key}")
    
    elif cmd == 'export':
        import csv
        rows = list_keys()
        with open('licenses.csv', 'w', newline='') as f:
            writer = csv.writer(f)
            writer.writerow(['License Key', 'Buyer Email', 'Buyer Name', 'Status', 'Activated At', 'Device Count'])
            for row in rows:
                writer.writerow(row)
        print(f"Exported {len(rows)} keys to licenses.csv")
    
    else:
        print(f"Unknown command: {cmd}")
