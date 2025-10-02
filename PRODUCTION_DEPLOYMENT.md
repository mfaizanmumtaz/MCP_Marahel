# Production Deployment Guide

## 🏭 Production Build & Deployment Commands

### **Quick Start (Production):**

```bash
# 1. Build all production images
make prod-build

# 2. Start all production services
make prod-up

# 3. Check status
make prod-status

# 4. View logs
make prod-logs

# 5. Stop production
make prod-down
```

---

## 📋 Available Commands

### **Development Commands:**
```bash
make start        # Start PostgreSQL + Gotenberg (dev mode)
make stop         # Stop dev services
make dev          # Run FastAPI locally with hot reload
make status       # Show dev service status + URLs
make logs         # View dev logs
```

### **Production Commands:**
```bash
make prod-build   # Build all Docker images (MCP Client + MCP Servers)
make prod-up      # Start all production services
make prod-down    # Stop all production services
make prod-restart # Restart all production services
make prod-status  # Show production service status + URLs
make prod-logs    # View production logs
```

### **GitLab Registry:**
```bash
make build        # Build single image for GitLab
make push         # Push to GitLab registry
make login        # Login to GitLab registry
```

---

## 🌐 Service URLs

### **After `make prod-up`:**

```
╔══════════════════════════════════════════════════════════════╗
║             Production Service Status                        ║
╚══════════════════════════════════════════════════════════════╝

NAME              STATUS          PORTS
postgres-pgvector Up              0.0.0.0:5432->5432/tcp
gotenberg         Up              0.0.0.0:3000->3000/tcp
mcp-servers       Up              0.0.0.0:9697->9697/tcp
mcp-client        Up              0.0.0.0:9696->9696/tcp

🌐 Production URLs:
  📊 PostgreSQL (pgvector)  : localhost:5432
  📄 Gotenberg API          : http://localhost:3000
  🔧 MCP Servers API        : http://localhost:9697
  🚀 MCP Client API         : http://localhost:9696
  📖 API Documentation      : http://localhost:9696/docs

💡 All services running in production mode
```

---

## 🔧 Architecture (Production)

### **Services:**

1. **PostgreSQL + pgvector** (Port 5432)
   - Vector database for embeddings
   - Persistent storage with Docker volume
   - Health checks enabled

2. **Gotenberg** (Port 3000)
   - DOCX → PDF conversion
   - Stateless service
   - Health checks enabled

3. **MCP Servers** (Port 9697)
   - RAG Server
   - CAG Server
   - Translation Server
   - Summarization Server
   - Health checks enabled

4. **MCP Client** (Port 9696)
   - Main API gateway
   - Supervisor Agent
   - Document ingestion API
   - Health checks enabled
   - Volume mount for file storage

---

## 📦 What Gets Built

### **Production Images:**

1. **mcp-client** (from `services/mcp_client/Dockerfile`)
   - Multi-stage build (builder + runtime)
   - Python 3.13 Alpine
   - Optimized with `uv` package manager
   - ~100MB final image

2. **mcp-servers** (from `services/mcp_servers/Dockerfile`)
   - Multi-stage build
   - Python 3.13 Alpine
   - Includes all MCP server tools
   - ~120MB final image

3. **Pre-built Images:**
   - `pgvector/pgvector:pg16` (pulled from Docker Hub)
   - `gotenberg/gotenberg:8` (pulled from Docker Hub)

---

## 🔐 Environment Variables

Create a `.env` file in the root directory:

```bash
# Database
PG_NAME=marahel
PG_USER_NAME=postgres
PG_PASSWORD=your_secure_password
PG_PORT=5432

# AI Services
OPENAI_API_KEY=sk-...
CLAUDE_API_KEY=sk-ant-...
OPENROUTER_API_KEY=sk-or-v1-...

# MCP Configuration
MCP_SERVER_HOST=mcp-servers
MCP_SERVER_PORT=9697

# Gotenberg
GOTENBERG_URL=http://gotenberg:3000

# Application
HOST=0.0.0.0
PORT=9696
```

---

## 🚀 Deployment Workflow

### **First-Time Setup:**

```bash
# 1. Clone repository
git clone <your-repo>
cd MCP_Marahel

# 2. Create .env file
cp .env.example .env
# Edit .env with your credentials

# 3. Build production images
make prod-build

# 4. Start all services
make prod-up

# 5. Verify everything is running
make prod-status

# 6. Test the API
curl http://localhost:9696/health
curl http://localhost:9696/docs
```

### **Daily Operations:**

```bash
# View logs
make prod-logs

# Restart services
make prod-restart

# Stop everything
make prod-down
```

### **Updates & Redeployment:**

```bash
# Pull latest code
git pull

# Rebuild images
make prod-build

# Restart with new images
make prod-down
make prod-up

# Verify
make prod-status
```

---

## 📊 Health Checks

All services have health checks configured:

- **PostgreSQL**: `pg_isready` every 10s
- **Gotenberg**: HTTP health endpoint every 30s
- **MCP Servers**: HTTP health endpoint every 30s
- **MCP Client**: HTTP health endpoint every 30s

Services depend on each other:
```
MCP Client → MCP Servers → PostgreSQL
          → Gotenberg
```

---

## 💾 Data Persistence

### **Volumes:**

1. **Database Data:**
   - Volume: `pgdata`
   - Persists PostgreSQL database
   - Survives container restarts

2. **File Storage:**
   - Host mount: `./storage → /app/src/storage`
   - Stores uploaded files, PDFs, thumbnails
   - Accessible from host machine

### **Backup Strategy:**

```bash
# Backup database
docker exec postgres-pgvector pg_dump -U postgres marahel > backup.sql

# Backup files
tar -czf storage_backup.tar.gz storage/

# Restore database
docker exec -i postgres-pgvector psql -U postgres marahel < backup.sql

# Restore files
tar -xzf storage_backup.tar.gz
```

---

## 🔍 Monitoring

### **View Container Logs:**

```bash
# All services
make prod-logs

# Specific service
docker-compose -f docker-compose.prod.yml logs -f mcp-client
docker-compose -f docker-compose.prod.yml logs -f mcp-servers
docker-compose -f docker-compose.prod.yml logs -f postgres
docker-compose -f docker-compose.prod.yml logs -f gotenberg
```

### **Check Resource Usage:**

```bash
# CPU & Memory usage
docker stats

# Disk usage
docker system df
```

---

## 🐛 Troubleshooting

### **Service Won't Start:**

```bash
# Check logs
make prod-logs

# Check specific service
docker-compose -f docker-compose.prod.yml logs mcp-client

# Restart individual service
docker-compose -f docker-compose.prod.yml restart mcp-client
```

### **Database Connection Issues:**

```bash
# Check PostgreSQL is running
docker ps | grep postgres

# Test connection
docker exec -it postgres-pgvector psql -U postgres -d marahel

# Check environment variables
docker-compose -f docker-compose.prod.yml config
```

### **File Storage Issues:**

```bash
# Check storage directory exists
ls -la storage/

# Create if missing
mkdir -p storage

# Check permissions
chmod -R 755 storage/
```

---

## 🌍 Production Deployment (Server)

### **On Production Server:**

```bash
# 1. Install Docker & Docker Compose
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER

# 2. Clone repository
git clone <your-repo>
cd MCP_Marahel

# 3. Setup environment
cp .env.example .env
nano .env  # Edit with production credentials

# 4. Deploy
make prod-build
make prod-up

# 5. Setup auto-restart
# Services have restart: always in docker-compose.prod.yml
```

### **Reverse Proxy (Nginx):**

```nginx
server {
    listen 80;
    server_name api.yourdomain.com;

    location / {
        proxy_pass http://localhost:9696;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}
```

---

## 📈 Scaling Considerations

### **Current Setup:**
- Single server deployment
- Local file storage
- Suitable for: 10-100 concurrent users

### **To Scale Further:**
1. **Database:** PostgreSQL replication or managed service (AWS RDS)
2. **File Storage:** Move to S3/Azure Blob
3. **Load Balancer:** Multiple MCP Client instances
4. **Cache:** Add Redis for session management
5. **Queue:** Add RabbitMQ for async jobs

---

## ✅ Production Checklist

- [ ] `.env` file created with production credentials
- [ ] PostgreSQL password changed from default
- [ ] All API keys configured
- [ ] Storage directory created with correct permissions
- [ ] Docker and Docker Compose installed
- [ ] `make prod-build` completed successfully
- [ ] `make prod-up` running all services
- [ ] Health checks passing
- [ ] API accessible at http://localhost:9696/health
- [ ] Backup strategy configured
- [ ] Monitoring setup (optional)
- [ ] SSL/TLS configured (optional with reverse proxy)

---

## 🎯 Summary

**Development:**
```bash
make start    # PostgreSQL + Gotenberg
make dev      # FastAPI local server
```

**Production:**
```bash
make prod-build   # Build images
make prod-up      # Start all services
make prod-status  # Check everything is running
```

**All services running in containers with health checks and auto-restart!** 🚀
