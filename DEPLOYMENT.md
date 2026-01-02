# Deployment Guide

This guide covers deploying the Expense Tracker to various platforms.

## Prerequisites

- Python 3.8+ installed locally
- Expenses Tracker project cloned and tested locally
- Git installed (for most deployments)

---

## Local Development (Windows/macOS/Linux)

### Quick Start

1. **Activate virtual environment**
   ```powershell
   # Windows
   venv\Scripts\Activate.ps1
   
   # macOS/Linux
   source venv/bin/activate
   ```

2. **Run the app**
   ```bash
   python app.py
   ```
   Visit http://127.0.0.1:5000

3. **Run tests**
   ```bash
   pytest -q
   ```

---

## Docker (Local Container)

### Build & Run Image

1. **Build the image**
   ```bash
   docker build -t expense-tracker:latest .
   ```

2. **Run the container**
   ```bash
   docker run -d -p 5000:8000 --name expense-tracker expense-tracker:latest
   ```

3. **Access the app**
   Open http://localhost:5000

4. **Stop the container**
   ```bash
   docker stop expense-tracker
   docker rm expense-tracker
   ```

### Using Docker Compose

1. **Start services**
   ```bash
   docker-compose up -d
   ```

2. **View logs**
   ```bash
   docker-compose logs -f
   ```

3. **Stop services**
   ```bash
   docker-compose down
   ```

---

## Heroku (PaaS)

### Deployment Steps

1. **Install Heroku CLI**
   - Download from https://devcenter.heroku.com/articles/heroku-cli

2. **Login to Heroku**
   ```bash
   heroku login
   ```

3. **Create a Heroku app**
   ```bash
   heroku create your-app-name
   ```

4. **Set environment variables**
   ```bash
   heroku config:set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
   heroku config:set FLASK_ENV=production
   ```

5. **Deploy via Git**
   ```bash
   git push heroku main
   ```

6. **View logs**
   ```bash
   heroku logs --tail
   ```

7. **Open the app**
   ```bash
   heroku open
   ```

### Persistent Database

By default, Heroku's ephemeral filesystem deletes the SQLite database on restart. Use PostgreSQL instead:

```bash
heroku addons:create heroku-postgresql:hobby-dev
heroku config
```

Then update `app.py`:
```python
DATABASE_URL = os.environ.get('DATABASE_URL', 'sqlite:///expenses.db')
if DATABASE_URL.startswith('postgres://'):
    DATABASE_URL = DATABASE_URL.replace('postgres://', 'postgresql://')
app.config['SQLALCHEMY_DATABASE_URI'] = DATABASE_URL
```

---

## AWS EC2 (Linux)

### Setup & Deployment

1. **Launch an EC2 instance**
   - AMI: Ubuntu 20.04 LTS
   - Instance type: t2.micro (free tier eligible)
   - Security group: Allow HTTP (80), HTTPS (443), SSH (22)

2. **SSH into the instance**
   ```bash
   ssh -i your-key.pem ubuntu@your-instance-ip
   ```

3. **Install dependencies**
   ```bash
   sudo apt update
   sudo apt install python3 python3-pip python3-venv git nginx
   ```

4. **Clone the repository**
   ```bash
   git clone <repo-url> expense-tracker
   cd expense-tracker
   ```

5. **Setup Python environment**
   ```bash
   python3 -m venv venv
   source venv/bin/activate
   pip install -r requirements.txt
   ```

6. **Create environment file**
   ```bash
   cp .env.example .env
   nano .env  # Edit SECRET_KEY and other settings
   ```

7. **Test the app**
   ```bash
   python app.py
   ```

8. **Setup Gunicorn as systemd service**

   Create `/etc/systemd/system/expense-tracker.service`:
   ```ini
   [Unit]
   Description=Expense Tracker Flask App
   After=network.target
   
   [Service]
   Type=notify
   User=ubuntu
   WorkingDirectory=/home/ubuntu/expense-tracker
   ExecStart=/home/ubuntu/expense-tracker/venv/bin/gunicorn --bind 0.0.0.0:8000 app:app
   EnvironmentFile=/home/ubuntu/expense-tracker/.env
   Restart=always
   RestartSec=10
   
   [Install]
   WantedBy=multi-user.target
   ```

9. **Enable and start the service**
   ```bash
   sudo systemctl enable expense-tracker
   sudo systemctl start expense-tracker
   sudo systemctl status expense-tracker
   ```

10. **Setup Nginx reverse proxy**

    Create `/etc/nginx/sites-available/expense-tracker`:
    ```nginx
    server {
        listen 80;
        server_name your-domain.com;
    
        location / {
            proxy_pass http://127.0.0.1:8000;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }
    }
    ```

    Enable the site:
    ```bash
    sudo ln -s /etc/nginx/sites-available/expense-tracker /etc/nginx/sites-enabled/
    sudo nginx -t
    sudo systemctl restart nginx
    ```

11. **Setup HTTPS with Let's Encrypt**
    ```bash
    sudo apt install certbot python3-certbot-nginx
    sudo certbot --nginx -d your-domain.com
    ```

---

## DigitalOcean App Platform (PaaS)

### Deployment Steps

1. **Push code to GitHub**
   ```bash
   git add .
   git commit -m "Ready for deployment"
   git push origin main
   ```

2. **Go to DigitalOcean Dashboard**
   - Click "Apps" → "Create App"
   - Connect your GitHub repository
   - Select the branch (main)

3. **Configure the app**
   - **Name:** expense-tracker
   - **Source:** GitHub repository
   - **Resource Type:** Basic (shared CPU, 512MB RAM)

4. **Add environment variables**
   - SECRET_KEY: `<generate-secure-key>`
   - FLASK_ENV: production

5. **Deploy**
   - Click "Deploy"
   - Wait for build and deployment (2-5 minutes)
   - App will be available at `your-app-name.ondigitalocean.app`

---

## DigitalOcean Droplet (VPS)

Similar to AWS EC2 above, but using DigitalOcean's Ubuntu 20.04 Droplet. Follow the AWS EC2 steps, replacing the public IP with your Droplet's IP.

---

## Production Checklist

Before deploying to production:

- [ ] Change `SECRET_KEY` to a secure random value (use `secrets` module or OpenSSL)
- [ ] Set `FLASK_ENV=production`
- [ ] Set `FLASK_DEBUG=False`
- [ ] Configure a persistent database (PostgreSQL, MySQL) instead of SQLite
- [ ] Setup HTTPS/TLS (Let's Encrypt, AWS ACM, etc.)
- [ ] Configure a reverse proxy (Nginx, Apache)
- [ ] Setup automated backups for the database
- [ ] Monitor logs and errors (Sentry, CloudWatch, etc.)
- [ ] Use a production WSGI server (Gunicorn, Waitress)
- [ ] Keep dependencies updated (`pip install --upgrade -r requirements.txt`)

---

## Troubleshooting

**Port Already in Use**
```bash
# Find and kill process using port 5000
lsof -ti:5000 | xargs kill -9   # macOS/Linux
Get-Process -Id (Get-NetTCPConnection -LocalPort 5000).OwningProcess | Stop-Process -Force  # Windows
```

**Database Locked Error**
- Stop the Flask app
- Delete `expenses.db`
- Restart the app (database will be recreated)

**Import Errors**
- Ensure virtual environment is activated
- Reinstall dependencies: `pip install -r requirements.txt`

**Migrations Not Applied**
```bash
python -m flask --app app.py db upgrade
```

---

## Additional Resources

- [Flask Deployment Guide](https://flask.palletsprojects.com/en/2.3.x/deploying/)
- [Gunicorn Documentation](https://docs.gunicorn.org/)
- [Heroku Python Buildpack](https://devcenter.heroku.com/articles/buildpacks)
- [DigitalOcean App Platform Docs](https://docs.digitalocean.com/products/app-platform/)

