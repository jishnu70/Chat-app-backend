from fastapi import WebSocketException, HTTPException
import firebase_admin
from firebase_admin import auth, credentials
import asyncio

try:
    if not firebase_admin._apps:
        cred = credentials.Certificate("firebase-service-account.json")
        firebase_admin.initialize_app(cred)
except Exception as e:
    raise Exception(f"Firebase initialization failed: {str(e)}")

async def verify_firebase_token_websocket(token: str):
    try:
        decoded_token = await asyncio.to_thread(auth.verify_id_token, token)
        return decoded_token
    except Exception as e:
        raise WebSocketException(code=1008, reason=f"Invalid token: {str(e)}")
    
async def verify_firebase_token(token: str):
    try:
        decoded_token = await asyncio.to_thread(auth.verify_id_token, token)
        return decoded_token
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"Invalid token: {str(e)}")