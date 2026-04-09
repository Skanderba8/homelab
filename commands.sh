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