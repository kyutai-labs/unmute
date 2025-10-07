# Expose Localhost to Internet

## Quick Setup with Cloudflare Tunnel

### 1. Install cloudflared
```bash
wget https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64.deb
sudo dpkg -i cloudflared-linux-amd64.deb
```

### 2. Start your application
```bash
docker-compose up -d
```

### 3. Expose to internet (no auth required)
```bash
cloudflared tunnel --url http://localhost:80
```

### 4. Share the URL
You'll get a public URL like: `https://random-words-123.trycloudflare.com`

Share this URL with anyone to access your localhost application over the internet.

## Notes
- No account or auth token required for quick tunnels
- URL changes each time you restart the tunnel
- Free and works immediately
- Press `Ctrl+C` to stop the tunnel
- Your machine acts as the server