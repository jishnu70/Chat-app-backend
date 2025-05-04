from fastapi import WebSocketException, HTTPException
import firebase_admin
from firebase_admin import auth, credentials
import os
import asyncio
import json
import logging
from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", force=True)
os.environ["PYTHONUNBUFFERED"] = "1"
logger = logging.getLogger(__name__)

try:
    logger.info("Initializing Firebase Admin SDK...")
    firebase_credentials = json.loads(os.getenv("FIREBASE_CREDENTIALS"))
    cred = credentials.Certificate(firebase_credentials)
    firebase_admin.initialize_app(cred)
    logger.info("Firebase Admin SDK initialized successfully")
except Exception as e:
    logger.error(f"Firebase initialization failed: {str(e)}", exc_info=True)
    raise Exception(f"Firebase initialization failed: {str(e)}")

async def verify_firebase_token_websocket(token: str):
    try:
        logger.info("Verifying Firebase token...")
        decoded_token = await asyncio.to_thread(auth.verify_id_token, token)
        logger.info(f"Token verified: {decoded_token['uid']}")
        return decoded_token
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise WebSocketException(code=1008, reason=f"Invalid token: {str(e)}")
    
async def verify_firebase_token(token: str):
    try:
        logger.info("Verifying Firebase token...")
        decoded_token = await asyncio.to_thread(auth.verify_id_token, token)
        logger.info(f"Token verified: {decoded_token['uid']}")
        return decoded_token
    except Exception as e:
        logger.error(f"Token verification failed: {str(e)}")
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")