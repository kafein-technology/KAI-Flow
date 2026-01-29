from app.core.constants import API_VERSION
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional
import logging
from app.core.constants import API_START,API_VERSION

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

router = APIRouter(prefix=f"/{API_START}/{API_VERSION}/test", tags=["Test"])

class TestRequest(BaseModel):
    message: Optional[str] = "Hello World"
    name: Optional[str] = "User"

class TestResponse(BaseModel):
    status: str
    message: str
    received_data: dict
    timestamp: str

@router.get("", response_model=TestResponse)
async def test_get():
    """Basit GET endpoint - print döner"""
    import datetime
    
    response_data = {
        "status": "success",
        "message": "GET request received successfully!",
        "received_data": {"method": "GET", "endpoint": f"/{API_START}/{API_VERSION}/test/"},
        "timestamp": datetime.datetime.now().isoformat()
    }

    # Log to file instead of logger
    logger.info(f"GET Request received at {response_data['timestamp']}")
    logger.info(f"Response: {response_data}")
    logger.info(f"GET request received: {response_data}")
    return TestResponse(**response_data)

@router.get("/hello/{name}", response_model=TestResponse)
async def test_get_with_param(name: str):
    """Parametreli GET endpoint"""
    import datetime
    
    response_data = {
        "status": "success",
        "message": f"Hello {name}!",
        "received_data": {"method": "GET", "name": name, "endpoint": f"/{API_START}/{API_VERSION}/test/hello/{name}"},
        "timestamp": datetime.datetime.now().isoformat()
    }

    # Log to file instead of logger
    logger.info(f"GET Request with param received at {response_data['timestamp']}")
    logger.info(f"Hello {name}!")
    logger.info(f"Response: {response_data}")
    logger.info(f"GET request with param received: {response_data}")
    return TestResponse(**response_data)

@router.get("/status/{status_code}")
async def test_status_code(status_code: int):
    """Status code test endpoint"""
    import datetime
    
    if status_code < 100 or status_code > 599:
        raise HTTPException(status_code=400, detail="Invalid status code")
    
    response_data = {
        "status": "success",
        "message": f"Status code {status_code} returned",
        "received_data": {"method": "GET", "status_code": status_code, "endpoint": f"/{API_START}/{API_VERSION}/test/status/{status_code}"},
        "timestamp": datetime.datetime.now().isoformat()
    }

    # logger to console
    logger.info(
        f"GET Request with status code {status_code} received at {response_data['timestamp']}"
    )
    logger.info(f"Response: {response_data}")

    # Log to file
    logger.info(f"GET request with status code received: {response_data}")

    return response_data


@router.get("/delay/{seconds}")
async def test_delay(seconds: int):
    """Delay test endpoint"""
    import datetime
    import asyncio
    
    if seconds < 0 or seconds > 60:
        raise HTTPException(status_code=400, detail="Delay must be between 0 and 60 seconds")

    logger.info(f"Starting delay of {seconds} seconds...")
    await asyncio.sleep(seconds)

    response_data = {
        "status": "success",
        "message": f"Delay completed after {seconds} seconds",
        "received_data": {"method": "GET", "delay_seconds": seconds, "endpoint": f"/{API_START}/{API_VERSION}/test/delay/{seconds}"},
        "timestamp": datetime.datetime.now().isoformat()
    }

    # logger to console
    logger.info(f"Delay completed at {response_data['timestamp']}")
    logger.info(f"Response: {response_data}")

    # Log to file
    logger.info(f"Delay request completed: {response_data}")
    
    return response_data

# Basit webhook endpoint'i (authentication olmadan)
@router.post("/webhook")
async def test_webhook(request: TestRequest):
    """Basit webhook endpoint - authentication olmadan"""
    import datetime
    
    response_data = {
        "status": "success",
        "message": "Webhook received successfully!",
        "received_data": {
            "method": "POST",
            "endpoint": f"/{API_START}/{API_VERSION}/test/webhook",
            "message": request.message,
            "name": request.name
        },
        "timestamp": datetime.datetime.now().isoformat()
    }
    # logger to console
    logger.info(f"Webhook POST Request received at {response_data['timestamp']}")
    logger.info(f"Message: {request.message}")
    logger.info(f"Name: {request.name}")
    logger.info(f"Response: {response_data}")
    # Log to file
    logger.info(f"Webhook request received: {response_data}")
    return response_data

# Authentication ile webhook endpoint'i
@router.post("/webhook-auth")
async def test_webhook_with_auth(request: TestRequest):
    """Authentication ile webhook endpoint"""
    import datetime
    response_data = {
        "status": "success",
        "message": "Authenticated webhook received successfully!",
        "received_data": {
            "method": "POST",
            "endpoint": f"/{API_START}/{API_VERSION}/test/webhook-auth",
            "message": request.message,
            "name": request.name,
            "authenticated": True
        },
        "timestamp": datetime.datetime.now().isoformat(),
    }
    # logger to console
    logger.info(
        f" Authenticated Webhook POST Request received at {response_data['timestamp']}"
    )
    logger.info(f"Authentication: Required")
    logger.info(f"Message: {request.message}")
    logger.info(f"Name: {request.name}")
    logger.info(f"Response: {response_data}")

    # Log to file
    logger.info(f"Authenticated webhook request received: {response_data}")
    
    return response_data 