# AR Email Automation -- Deployment Guide

This guide walks through three ways to get the AR Email Tool running so Laura
can access it from her browser.  Pick the option that fits your situation.

---

## Option A: Streamlit Community Cloud (Recommended -- FREE)

This puts the app on the internet with a permanent URL.  Laura opens a link
in Chrome and it just works.  No software to install on her machine.

### Prerequisites

- A GitHub account (free)
- A Streamlit Community Cloud account (free, sign in with GitHub)

### Steps

1. **Create a private GitHub repo**

   Go to https://github.com/new and create a new repository:
   - Name: `picc-ar-email-automation`
   - Visibility: **Private**
   - Do NOT initialize with README (we will push our files)

2. **Push the code**

   Open a terminal in the `ar-email-automation/` folder and run:

   ```bash
   git init
   git add .
   git commit -m "Initial commit: AR Email Automation"
   git branch -M main
   git remote add origin https://github.com/YOUR_USERNAME/picc-ar-email-automation.git
   git push -u origin main
   ```

   The `.gitignore` is already configured to exclude `data/`, `output/`,
   `agent-outputs/`, and `.streamlit/secrets.toml`.

3. **Deploy on Streamlit Community Cloud**

   - Go to https://share.streamlit.io
   - Click **"New app"**
   - Connect your GitHub account (first time only)
   - Select:
     - Repository: `YOUR_USERNAME/picc-ar-email-automation`
     - Branch: `main`
     - Main file path: `app.py`
   - Click **"Deploy!"**

4. **Add secrets (if using SMTP sending later)**

   On the Streamlit Cloud dashboard for your app:
   - Click the three-dot menu > **Settings** > **Secrets**
   - Paste the contents of `.streamlit/secrets.toml.template` and fill in
     real values

5. **Share the URL with Laura**

   Streamlit will give you a URL like:
   ```
   https://your-username-picc-ar-email-automation-app-xxxxx.streamlit.app
   ```

   Send that link to Laura.  She bookmarks it and opens it whenever she needs
   to generate AR emails.

### Updating the App

When you make changes, just push to GitHub:

```bash
git add .
git commit -m "Update email templates"
git push
```

Streamlit Cloud will automatically redeploy within a couple of minutes.

---

## Option B: Local Network (No Internet Required)

Run the app on Joe's PC and let Laura connect over the office WiFi/LAN.
Good if you want to keep everything on-premises.

### Prerequisites

- Python 3.11+ installed on Joe's PC
- Joe's PC and Laura's PC on the same network

### Steps

1. **Start the server on Joe's PC**

   Double-click `start_server.bat` in the `ar-email-automation/` folder.

   The script will:
   - Install dependencies automatically
   - Start the Streamlit web server
   - Print the URL Laura should use

   You will see output like:
   ```
   Laura can access the tool at:

     Same PC:  http://localhost:8501
     Network:  http://192.168.1.42:8501
   ```

2. **Laura opens the URL in Chrome**

   On Laura's computer, open Chrome and go to the network URL shown in
   Joe's terminal (e.g., `http://192.168.1.42:8501`).

3. **Windows Firewall (if Laura cannot connect)**

   If Laura sees "site can't be reached", you need to allow port 8501
   through the Windows Firewall on Joe's PC:

   Open PowerShell as Admin and run:
   ```powershell
   New-NetFirewallRule -DisplayName "Streamlit AR Tool" -Direction Inbound -Protocol TCP -LocalPort 8501 -Action Allow
   ```

4. **Create a desktop shortcut for Laura**

   On Laura's PC:
   - Right-click the desktop > **New** > **Shortcut**
   - Location: `http://192.168.1.42:8501` (use Joe's real IP)
   - Name: `AR Email Tool`

   Or copy the `AR Email Tool.url` file to Laura's desktop after editing
   the IP address inside it.

### Keeping the Server Running

The server runs as long as the terminal window is open.  If Joe restarts his
PC, he needs to double-click `start_server.bat` again.

To run it automatically at login, create a shortcut to `start_server.bat` in:
```
C:\Users\smith\AppData\Roaming\Microsoft\Windows\Start Menu\Programs\Startup
```

---

## Option C: Railway or Heroku (Paid Cloud Fallback)

If Streamlit Community Cloud is down or you need more resources, deploy to
Railway ($5/mo) or Heroku ($7/mo).

### Railway

1. Install the Railway CLI: https://docs.railway.app/develop/cli
2. From the `ar-email-automation/` folder:
   ```bash
   railway login
   railway init
   railway up
   ```
3. Railway reads the `Procfile` and `runtime.txt` automatically.

### Heroku

1. Install the Heroku CLI: https://devcenter.heroku.com/articles/heroku-cli
2. From the `ar-email-automation/` folder:
   ```bash
   heroku login
   heroku create picc-ar-email
   git push heroku main
   ```
3. Open the app: `heroku open`

---

## File Inventory

These files were added for deployment:

| File | Purpose |
|------|---------|
| `.streamlit/config.toml` | Streamlit server settings and PICC theme colors |
| `.streamlit/secrets.toml.template` | Template for SMTP credentials (copy to `secrets.toml`) |
| `.gitignore` | Prevents committing secrets, customer data, and caches |
| `Procfile` | Tells Railway/Heroku how to start the app |
| `runtime.txt` | Pins Python version for cloud platforms |
| `requirements.txt` | Pinned Python dependencies for reproducible installs |
| `start_server.bat` | One-click launcher for local network deployment |
| `AR Email Tool.url` | Desktop shortcut Laura can double-click |
| `DEPLOY_GUIDE.md` | This file |

---

## Troubleshooting

**"ModuleNotFoundError: No module named 'streamlit'"**
Run `pip install -r requirements.txt` from the `ar-email-automation/` folder.

**Laura sees a blank page or error**
Check that Joe's terminal is still running `start_server.bat`.  The server
must be running for Laura to connect.

**"Address already in use" error**
Another process is using port 8501.  Either close it or change the port:
```bash
streamlit run app.py --server.port 8502
```

**Streamlit Cloud shows "app is sleeping"**
Free-tier Streamlit apps sleep after inactivity.  Laura just needs to reload
the page and wait 30 seconds for it to wake up.

**Changes not showing on Streamlit Cloud**
Make sure you pushed to the `main` branch.  Streamlit Cloud only watches
the branch you selected during setup.
