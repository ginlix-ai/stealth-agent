# Open PTC Agent REST API

This directory contains the FastAPI REST API server for Open PTC Agent, designed to be consumed by frontend applications (React, Vue, etc.).

## Quick Start

### Run the API Server

```bash
# From project root
python run_api.py

# Or using uvicorn directly
uvicorn api.main:app --host 0.0.0.0 --port 8080 --reload
```

The API will be available at:
- **API Base**: http://localhost:8080
- **Interactive Docs**: http://localhost:8080/docs (Swagger UI)
- **Alternative Docs**: http://localhost:8080/redoc (ReDoc)

### Test the Hello Endpoint

```bash
curl http://localhost:8080/hello
# Returns: "Hello!"

curl http://localhost:8080/
# Returns: {"message": "Open PTC Agent API", "version": "0.1.0", "status": "running"}
```

## Project Structure

```
api/
├── __init__.py           # Package initialization
├── main.py               # FastAPI app and main endpoints
├── routers/              # API route modules (for organizing endpoints)
│   ├── __init__.py
│   ├── agent.py         # Agent-related endpoints (future)
│   ├── tasks.py         # Task management endpoints (future)
│   └── files.py         # File operations endpoints (future)
├── models/               # Pydantic models for request/response schemas (future)
│   ├── __init__.py
│   ├── agent.py
│   └── task.py
└── services/             # Business logic layer (future)
    ├── __init__.py
    └── agent_service.py
```

## Adding New Endpoints

### Simple GET Endpoint

Add to `api/main.py`:

```python
@app.get("/your-endpoint")
async def your_endpoint():
    """Your endpoint description."""
    return {"message": "Your response"}
```

### POST Endpoint with Request Body

```python
from pydantic import BaseModel

class YourRequest(BaseModel):
    field1: str
    field2: int

@app.post("/your-endpoint")
async def create_something(request: YourRequest):
    """Create something with request body."""
    return {
        "received": request.field1,
        "number": request.field2
    }
```

### Endpoint with Path Parameters

```python
@app.get("/items/{item_id}")
async def get_item(item_id: int):
    """Get item by ID."""
    return {"item_id": item_id}
```

### Endpoint with Query Parameters

```python
@app.get("/search")
async def search(query: str, limit: int = 10):
    """Search with query parameters."""
    return {"query": query, "limit": limit}
```

### Organizing Endpoints in Routers

For better organization, create separate router files:

1. Create `api/routers/agent.py`:

```python
from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])

@router.post("/chat")
async def chat(message: str):
    """Chat with the agent."""
    # Your agent logic here
    return {"response": "Agent response here"}
```

2. Include router in `api/main.py`:

```python
from api.routers import agent

app.include_router(agent.router)
```

## Integration with PTC Agent

### Example: Chat Endpoint with PTC Agent

```python
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from ptc_agent import AgentConfig, PTCAgent
from ptc_agent.core import SessionManager

router = APIRouter(prefix="/api/v1/agent", tags=["agent"])

class ChatRequest(BaseModel):
    message: str
    agent_id: str = "default"

class ChatResponse(BaseModel):
    response: str
    tokens_used: int | None = None

# Initialize agent (you might want to cache this)
async def get_agent():
    config = await AgentConfig.load_from_files()
    return PTCAgent(config)

@router.post("/chat", response_model=ChatResponse)
async def chat_with_agent(request: ChatRequest):
    """Chat with the PTC agent."""
    try:
        # Get or create agent
        agent = await get_agent()
        config = agent.config
        
        # Get or create session
        session = SessionManager.get_session(request.agent_id, config.to_core_config())
        await session.initialize()
        
        # Create agent graph
        ptc_agent = agent.create_agent(
            sandbox=session.sandbox,
            mcp_registry=session.mcp_registry,
        )
        
        # Invoke agent
        result = await ptc_agent.ainvoke({
            "messages": [{
                "role": "user",
                "content": request.message
            }]
        })
        
        # Extract response (adjust based on your result structure)
        response_text = result.get("messages", [])[-1].get("content", "")
        
        return ChatResponse(response=response_text)
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
```

## CORS Configuration

CORS is already configured in `api/main.py` to allow all origins. For production:

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",  # React dev server
        "https://yourdomain.com",  # Production frontend
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

## Error Handling

FastAPI automatically handles validation errors. For custom error handling:

```python
from fastapi import HTTPException

@app.get("/items/{item_id}")
async def get_item(item_id: int):
    if item_id < 0:
        raise HTTPException(status_code=400, detail="Item ID must be positive")
    # Your logic here
    return {"item_id": item_id}
```

## Testing

### Using curl

```bash
# GET request
curl http://localhost:8080/hello

# POST request
curl -X POST http://localhost:8080/api/v1/agent/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello agent!"}'
```

### Using Python requests

```python
import requests

response = requests.get("http://localhost:8080/hello")
print(response.text)  # "Hello!"

response = requests.post(
    "http://localhost:8080/api/v1/agent/chat",
    json={"message": "Hello agent!"}
)
print(response.json())
```

## Deployment

### Development

```bash
python run_api.py  # Uses reload=True for auto-reload
```

### Production

```bash
# Use uvicorn with workers for production
uvicorn api.main:app --host 0.0.0.0 --port 8080 --workers 4

# Or use gunicorn with uvicorn workers
gunicorn api.main:app -w 4 -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8080
```

## Next Steps

1. **Add agent endpoints**: Create `/api/v1/agent/chat` endpoint
2. **Add file management**: Endpoints for downloading/uploading files from sandbox
3. **Add task management**: Endpoints for managing agent tasks
4. **Add authentication**: JWT tokens or API keys
5. **Add WebSocket support**: For real-time agent responses

## Resources

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Uvicorn Documentation](https://www.uvicorn.org/)
- [PTC Agent SDK Documentation](../README.md)

