import logging
import httpx
from fastapi import FastAPI, Request, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("pico-music")

app = FastAPI(title="Pico Music")

# Simple config storage
CONFIG_FILE = "services/pico_music/config.json"
import json
import os

def load_config():
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                return json.load(f)
        except:
            pass
    return {}

def save_config(config):
    with open(CONFIG_FILE, 'w') as f:
        json.dump(config, f)

config = load_config()


# Mount static files
app.mount("/static", StaticFiles(directory="services/pico_music/static"), name="static")

# Templates
templates = Jinja2Templates(directory="services/pico_music/templates")

# YTM API Configuration
YTM_API_BASE_URL = "http://localhost:26538"



@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    """Serve the main UI."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.api_route("/proxy/{path:path}", methods=["GET", "POST", "DELETE", "PATCH", "PUT"])
async def proxy_ytm_api(request: Request, path: str):
    """
    Proxy requests to the YTM Desktop API.
    The client sends requests to /proxy/api/v1/..., and we forward them to localhost:26538/api/v1/...
    """
    target_url = f"{YTM_API_BASE_URL}/{path}"
    
    # Forward headers
    headers = dict(request.headers)
    headers.pop("host", None)
    headers.pop("content-length", None)
    headers.pop("authorization", None) # Remove any client-sent auth



    try:
        async with httpx.AsyncClient() as client:
            # Forward the request body if present
            content = await request.body()
            
            response = await client.request(
                method=request.method,
                url=target_url,
                headers=headers,
                content=content,
                timeout=5.0
            )
            
            # Return the response from YTM API
            return JSONResponse(
                content=response.json() if response.content else None,
                status_code=response.status_code,
            )
    except httpx.RequestError as exc:
        logger.error(f"An error occurred while requesting {exc.request.url!r}.")
        raise HTTPException(status_code=502, detail="Error connecting to YTM API")
    except Exception as e:
        logger.error(f"Proxy error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

if __name__ == "__main__":
    import uvicorn
    # Run on port 8003 to avoid conflicts
    uvicorn.run(app, host="0.0.0.0", port=8003)
