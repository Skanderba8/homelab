# Health check
curl http://localhost:8000/health

# Add
curl -X POST http://localhost:8000/add \
  -H "Content-Type: application/json" \
  -d '{"a": 10, "b": 5}'

# Divide (try div by zero too)
curl -X POST http://localhost:8000/divide \
  -H "Content-Type: application/json" \
  -d '{"a": 10, "b": 0}'

  # Build the image
docker build -t homelab .

# Run it
docker run -d -p 8000:8000 --name homelab homelab

# Test it
curl http://localhost:8000/health

# Check it's running
docker ps

# See logs
docker logs homelab

# Stop it
docker stop homelab

cd ~/homelab
docker compose down
docker compose up -d --build