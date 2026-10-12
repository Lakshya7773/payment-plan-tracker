# License System for Payment Plan Tracker Pro

## Overview

Single-use license key system. Each key can only be activated on **one device** (browser fingerprint). Prevents sharing/copying.

## Components

| File | Purpose |
|------|---------|
| `license_generator.py` | Generate, list, revoke license keys |
| `license_server.py` | HTTP server for activation/validation (port 8765) |
| `licenses.db` | SQLite database storing keys + activations |

## License Key Format

```
PPT-XXXX-XXXX-XXXX-XXXX
```

- `PPT` = prefix
- 12 random chars (A-Z, 0-9)
- 4-char HMAC signature (prevents key guessing)

## How It Works

1. **Buyer purchases** on Gumroad → receives license key via email
2. **Buyer opens** the Pro HTML file → sees license activation modal
3. **Buyer enters** key → app sends key + browser fingerprint to license server
4. **Server validates** key → if valid and unused, activates for that browser
5. **App stores** key in localStorage → validates on each startup
6. **If key used** on different browser → rejected with "already activated on another device"

## Setup

### 1. Change the Secret Key

Edit both files and change `SECRET_KEY`:
- `license_generator.py` line: `SECRET_KEY = b'ppt_pro_2026_a7f3k9m2x8q1'`
- `license_server.py` line: `SECRET_KEY = b'ppt_pro_2026_a7f3k9m2x8q1'`

**Use a long random string.** This is the HMAC signing key — anyone who knows it can generate valid keys.

### 2. Generate License Keys

```bash
python license_generator.py generate buyer@email.com "Buyer Name"
```

Output:
```
License Key: PPT-A7B3-C9D2-E4F5-G6H7
Buyer: Buyer Name <buyer@email.com>
Status: unused
```

### 3. Start the License Server

```bash
python license_server.py
```

Server runs on `http://localhost:8765`

### 4. Update the HTML

In `index.html`, change:
```javascript
const LICENSE_SERVER = 'http://localhost:8765';
```
to your server's public URL (e.g., `https://yourdomain.com`).

## API Endpoints

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/health` | GET | Server health check |
| `/activate` | POST | Activate a license key |
| `/validate` | GET | Validate an existing activation |

### Activate
```json
POST /activate
{
  "key": "PPT-A7B3-C9D2-E4F5-G6H7",
  "fingerprint": "abc123..."
}
```

Response:
```json
{
  "success": true,
  "message": "License activated successfully!"
}
```

### Validate
```
GET /validate?key=PPT-A7B3-C9D2-E4F5-G6H7&fingerprint=abc123...
```

Response:
```json
{
  "valid": true,
  "message": "License valid"
}
```

## Management Commands

```bash
# List all keys
python license_generator.py list

# Revoke a key
python license_generator.py revoke PPT-A7B3-C9D2-E4F5-G6H7

# Export to CSV
python license_generator.py export

# Validate key format
python license_generator.py validate PPT-A7B3-C9D2-E4F5-G6H7
```

## Security Notes

- **SECRET_KEY** must be kept private — anyone with it can generate valid keys
- **Browser fingerprint** is based on: user agent, language, screen size, color depth, timezone, hardware concurrency, device memory
- **Single-use enforcement**: one key = one browser fingerprint. If someone tries to use the same key on a different browser, it's rejected
- **Grace period**: if the license server is down, the app allows access if a key exists in localStorage (prevents lockout during server maintenance)
- **HMAC signature**: prevents key guessing — keys are cryptographically signed

## Deployment Options

### Option A: Same VPS (simplest)
Run `license_server.py` on the same VPS as the app. Use `http://localhost:8765` in the HTML.

### Option B: Separate server
Deploy `license_server.py` to a small VPS or Raspberry Pi. Use the public URL in the HTML.

### Option C: Serverless (advanced)
Convert the activation logic to a serverless function (Cloudflare Workers, Vercel Edge Functions) with a KV store instead of SQLite.

## Gumroad Integration

When someone buys on Gumroad:
1. Gumroad sends you a webhook (or you check the dashboard)
2. Run: `python license_generator.py generate buyer@email.com "Buyer Name"`
3. Send the key to the buyer (email, Gumroad message, or automated via Zapier/Make)

## Troubleshooting

| Problem | Solution |
|---------|----------|
| "Cannot connect to license server" | Make sure `license_server.py` is running |
| "License key already activated on another device" | Key was used on a different browser. Revoke and re-generate if needed. |
| "Invalid license key" | Check the key format. Keys are case-insensitive (auto-uppercased). |
| "License key has been revoked" | Key was revoked by admin. Generate a new one. |
| Keys not persisting | Check `licenses.db` file permissions |
