from fastapi import FastAPI, WebSocketDisconnect, WebSocket, HTTPException, Depends, UploadFile, File
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.middleware.cors import CORSMiddleware
from src.database import init_db, get_or_create_user, close_db
from src.schemas import ChatSummary, UserCreate, UserOut
from src.models import User, Group, GroupMember, Message, UserCreatePydantic, GroupCreatePydantic, GroupMemberPydantic, MessageCreatePydantic, MediaType
from firebase_admin import auth, credentials, initialize_app
from firebase_admin._auth_utils import InvalidIdTokenError
import os
import json
import time
import aiofiles
from contextlib import asynccontextmanager
import uuid
from pathlib import Path
from dotenv import load_dotenv
import logging
from tortoise.expressions import Q

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s", force=True)
os.environ["PYTHONUNBUFFERED"] = "1"
logger = logging.getLogger(__name__)

load_dotenv()
security = HTTPBearer()

# Initialize Firebase Admin SDK
try:
    logger.info("Initializing Firebase Admin SDK...")
    cred = credentials.Certificate(json.loads(os.getenv("FIREBASE_CREDENTIALS")))
    initialize_app(cred)
    logger.info("Firebase Admin SDK initialized successfully")
except Exception as e:
    logger.error(f"Firebase initialization failed: {str(e)}")
    raise

# Allow CORS from any origin
origins = ["*"]

# WebSocket group storage
group_connections = {}

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting application...")
    try:
        await init_db()
        os.makedirs(os.getenv("UPLOAD_DIR", "./uploads"), exist_ok=True)
        logger.info("Application startup complete")
        # anything above is equivalent to on_event("startup")
        yield
        # anything below is equivalent to on_event("shutdown")
        await close_db()
    except Exception as e:
        logger.error(f"Startup failed: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("Shutting down application...")

app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

@app.post("/users", response_model=UserOut)
async def create_users(user: UserCreate, credentials: HTTPAuthorizationCredentials = Depends(security)):
    logger.info(f"Creating user: {user.model_dump()}")
    try:
        # Verify Firebase token and match UID
        decoded_token = auth.verify_id_token(credentials.credentials)
        if user.uid != decoded_token["uid"]:
            logger.error(f"UID mismatch: input={user.uid}, token={decoded_token['uid']}")
            raise HTTPException(status_code=403, detail="UID does not match Firebase token")
        logger.info(f"Firebase token verified for UID: {user.uid}")
        
        # Validate input data
        if not user.email:
            logger.error("Email is required")
            raise HTTPException(status_code=400, detail="Email is required")
        if not user.uid:
            logger.error("UID is required")
            raise HTTPException(status_code=400, detail="UID is required")
        
        # Check for existing user
        existing_user = await User.filter(uid=user.uid).first()
        if existing_user:
            logger.warning(f"User already exists: {user.uid}")
            raise HTTPException(status_code=400, detail="User already exists")
        
        # Create new user
        try:
            new_user = await User.create(
                uid=user.uid,
                email=user.email,
                username=user.username,
                public_key=user.public_key
            )
            logger.info(f"User created: ID={new_user.id}, UID={new_user.uid}")
            return UserOut(
                id=new_user.id,
                uid=new_user.uid,
                email=new_user.email,
                username=new_user.username or "",
                public_key=new_user.public_key
            )
        except Exception as db_error:
            logger.error(f"Database insert failed: {str(db_error)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
    except Exception as e:
        logger.error(f"User creation failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"User creation failed: {str(e)}")

@app.get("/users/{uid}", dependencies=[Depends(security)], response_model=UserOut)
async def get_user_public_key(uid: int, credentials: HTTPAuthorizationCredentials = Depends(security)):
    decoded_token = auth.verify_id_token(credentials.credentials)
    user_id = await get_or_create_user(
        decoded_token["uid"], decoded_token.get("email", ""), decoded_token.get("name", None)
    )
    try:
        self_user = await User.get(id=user_id)
        if not self_user:
            raise HTTPException(status_code=404, detail="Self does not exist")
        user = await User.get(id=uid)
        if not user:
            raise HTTPException(status_code=404, detail="User does not exist")
        return UserOut.model_validate(user)
    except Exception as e:
        logger.error(f"Get user failed: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error: {str(e)}")

@app.get("/users", dependencies=[Depends(security)])
async def list_users(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        decoded_token = auth.verify_id_token(credentials.credentials)
        user_id = await get_or_create_user(
            decoded_token["uid"], decoded_token.get("email", ""), decoded_token.get("name", None)
        )
        user = await User.get(id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User does not exist")
        users = await User.all().values("id", "username")
        logger.info(f"Listed users for user ID={user_id}: {len(users)} users found")
        return [{"userID": u["id"], "username": u.get("username") or ""} for u in users]
    except InvalidIdTokenError as e:
        logger.error(f"Invalid Firebase token: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid Firebase token")
    except Exception as e:
        logger.error(f"List users failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed: {str(e)}")

@app.post("/groups")
async def create_groups(
    group: GroupCreatePydantic,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    decoded_token = auth.verify_id_token(credentials.credentials)
    creator_id = await get_or_create_user(
        decoded_token["uid"], decoded_token.get("email", ""), decoded_token.get("name", None)
    )
    try:
        creator = await User.get(id=creator_id)
        new_group = await Group.create(group_name=group.group_name, group_creator=creator)
        await GroupMember.create(group_user=creator, group=new_group)
        return {"group_id": new_group.group_id, "message": "Group created"}
    except Exception as e:
        logger.error(f"Group creation failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Group creation failed: {str(e)}")

@app.post("/groups/{group_id}/member")
async def add_group_members(
    group_id: int,
    member: GroupMemberPydantic,
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    decoded_token = auth.verify_id_token(credentials.credentials)
    requester_id = await get_or_create_user(
        decoded_token["uid"], decoded_token.get("email", ""), decoded_token.get("name", None)
    )
    try:
        group = await Group.get(group_id=group_id)
        requester = await User.get(id=requester_id)
        if group.group_creator != requester:
            raise HTTPException(status_code=403, detail="Only group creator can add members")
        new_member = await User.get(id=member.group_user_id)
        existing_member = await GroupMember.filter(group=group, group_user=new_member).first()
        if existing_member:
            raise HTTPException(status_code=400, detail="User already in group")
        await GroupMember.create(group=group, group_user=new_member)
        return {"message": f"User {new_member.id} added to group {group_id}"}
    except User.DoesNotExist:
        raise HTTPException(status_code=404, detail="User or group not found")
    except Exception as e:
        logger.error(f"Add group member failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed to add member: {str(e)}")

@app.post("/media")
async def upload_media(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security)
):
    decoded_token = auth.verify_id_token(credentials.credentials)
    await get_or_create_user(
        decoded_token["uid"], decoded_token.get("email", ""), decoded_token.get("name", None)
    )
    try:
        file_extension = file.filename.rsplit(".", 1)[-1].lower()
        media_type = MediaType.IMAGE if file_extension in ["jpg", "jpeg", "png"] else MediaType.VIDEO
        file_name = f"{uuid.uuid4()}.{file_extension}"
        file_path = Path(os.getenv("UPLOAD_DIR", "./uploads")) / file_name
        async with aiofiles.open(file_path, "wb") as f:
            await f.write(await file.read())
        media_url = f"/uploads/{file_name}"
        return {"media_url": media_url, "media_type": media_type}
    except Exception as e:
        logger.error(f"Media upload failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Media upload failed: {str(e)}")

@app.websocket("/chat/{receiver_id}")
async def individual_chat(websocket: WebSocket, receiver_id: int):
    token = websocket.headers.get("authorization")
    if not token or not token.startswith("Bearer "):
        await websocket.close(code=1000, reason="Authorization header missing or malformed")
        return
    token = token.removeprefix("Bearer ").strip()
    try:
        decoded_token = auth.verify_id_token(token)
        sender_id = await get_or_create_user(
            decoded_token["uid"], decoded_token.get("email", ""), decoded_token.get("name", None)
        )
        sender = await User.filter(id=sender_id).first()
        receiver = await User.filter(id=receiver_id).first()
        if not sender or not receiver:
            await websocket.close(code=1008, reason="Sender or receiver not found")
            return
        await websocket.accept()
        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)
            content = payload.get("content")
            if not content:
                await websocket.send_text("Invalid payload")
                continue
            await Message.create(
                sender=sender,
                receiver=receiver,
                message_content=content
            )
            msg = {
                "sender_id": sender.id,
                "content": content,
                "timestamp": int(time.time() * 1000)
            }
            await websocket.send_text(json.dumps(msg))
    except WebSocketDisconnect:
        logger.info(f"User {sender_id} disconnected")
    except Exception as e:
        logger.error(f"Individual chat error: {str(e)}")
        await websocket.close(code=1008, reason=f"Error: {str(e)}")

@app.websocket("/chat/group/{group_id}")
async def group_chat(websocket: WebSocket, group_id: int):
    token = websocket.headers.get("authorization")
    if not token or not token.startswith("Bearer "):
        await websocket.close(code=1008, reason="Authorization header missing or malformed")
        return
    token = token.removeprefix("Bearer ").strip()
    try:
        decoded_token = auth.verify_id_token(token)
        sender_id = await get_or_create_user(
            decoded_token["uid"], decoded_token.get("email", ""), decoded_token.get("name", None)
        )
        sender = await User.filter(id=sender_id).first()
        group = await Group.filter(group_id=group_id).first()
        membership = await GroupMember.filter(group=group, group_user=sender).first()
        if not sender or not group or not membership:
            await websocket.close(code=1008, reason="Group not found or user not a member")
            return
        if group_id not in group_connections:
            group_connections[group_id] = {}
        group_connections[group_id][sender_id] = websocket
        await websocket.accept()
        while True:
            raw = await websocket.receive_text()
            data = json.loads(raw)
            content = data.get("content")
            if not content:
                await websocket.send_text("Invalid payload")
                continue
            await Message.create(
                sender=sender,
                group=group,
                message_content=content
            )
            msg = {
                "sender_id": sender.id,
                "group_id": group_id,
                "content": content,
                "timestamp": int(time.time() * 1000)
            }
            for member_id, member_ws in group_connections.get(group_id, {}).items():
                try:
                    await member_ws.send_text(json.dumps(msg))
                except Exception as e:
                    logger.error(f"Failed to send to {member_id}: {str(e)}")
    except WebSocketDisconnect:
        logger.info(f"User {sender_id} disconnected from group {group_id}")
    except Exception as e:
        logger.error(f"Group chat error: {str(e)}")
        await websocket.send_text(f"Error: {str(e)}")
    finally:
        group_connections[group_id].pop(sender_id, None)
        if not group_connections[group_id]:
            del group_connections[group_id]
        await websocket.close()

@app.get("/chats", dependencies=[Depends(security)])
async def list_chats(credentials: HTTPAuthorizationCredentials = Depends(security)):
    try:
        decoded_token = auth.verify_id_token(credentials.credentials)
        user_id = await get_or_create_user(
            decoded_token["uid"], decoded_token.get("email", ""), decoded_token.get("name", None)
        )
        user = await User.get(id=user_id)
        if not user:
            raise HTTPException(status_code=404, detail="User does not exist")
        
        chat_summaries = []
        
        # Group chats: Fetch groups where user is a member
        group_members = await GroupMember.filter(group_user_id=user_id).prefetch_related("group")
        group_ids = [gm.group_id for gm in group_members]
        group_messages = await Message.filter(group_id__in=group_ids).order_by("-timestamp").prefetch_related("group", "sender")
        
        # Build group chat summaries
        seen_groups = set()
        for message in group_messages:
            group = message.group
            if group.id in seen_groups:
                continue
            seen_groups.add(group.id)
            chat_summaries.append({
                "group_id": group.id,
                "group_name": group.name,
                "is_direct": False,
                "last_message": message.content,
                "timestamp": message.timestamp.isoformat(),
                "sender_username": message.sender.username if message.sender else ""
            })
        
        # Direct chats: Fetch messages where user is sender or receiver, group_id is NULL
        direct_messages = await Message.filter(
            Q(sender_id=user_id) | Q(receiver_id=user_id),
            group_id__isnull=True
        ).order_by("-timestamp").prefetch_related("sender", "receiver")
        
        # Build direct chat summaries by unique conversation (sender/receiver pair)
        seen_conversations = set()
        for message in direct_messages:
            # Identify the other user in the conversation
            other_user_id = message.receiver_id if message.sender_id == user_id else message.sender_id
            conversation_key = tuple(sorted([user_id, other_user_id]))  # Unique pair
            if conversation_key in seen_conversations:
                continue
            seen_conversations.add(conversation_key)
            chat_summaries.append({
                "group_id": None,
                "group_name": "",  # Frontend will format using sender_id/receiver_id
                "is_direct": True,
                "last_message": message.content,
                "timestamp": message.timestamp.isoformat(),
                "sender_username": message.sender.username if message.sender else "",
                "sender_id": message.sender_id,
                "receiver_id": message.receiver_id
            })
        
        logger.info(f"Listed chats for user ID={user_id}: {len(chat_summaries)} chats found")
        return chat_summaries
    except InvalidIdTokenError as e:
        logger.error(f"Invalid Firebase token: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid Firebase token")
    except Exception as e:
        logger.error(f"List chats failed: {str(e)}")
        raise HTTPException(status_code=400, detail=f"Failed: {str(e)}")
    

@app.put("/users", response_model=UserOut)
async def update_user(user: UserCreate, credentials: HTTPAuthorizationCredentials = Depends(security)):
    logger.info(f"Updating user: {user.model_dump()}")
    try:
        decoded_token = auth.verify_id_token(credentials.credentials)
        if user.uid != decoded_token["uid"]:
            logger.error(f"UID mismatch: input={user.uid}, token={decoded_token['uid']}")
            raise HTTPException(status_code=403, detail="UID does not match Firebase token")
        logger.info(f"Firebase token verified for UID: {user.uid}")
        
        existing_user = await User.filter(uid=user.uid).first()
        if not existing_user:
            logger.warning(f"User not found: UID={user.uid}")
            raise HTTPException(status_code=404, detail="User not found")
        
        try:
            existing_user.email = user.email
            existing_user.username = user.username
            existing_user.public_key = user.public_key
            await existing_user.save()
            logger.info(f"User updated: ID={existing_user.id}, UID={user.uid}")
            return UserOut(
                id=existing_user.id,
                uid=existing_user.uid,
                email=existing_user.email,
                username=existing_user.username or "",
                public_key=existing_user.public_key
            )
        except Exception as db_error:
            logger.error(f"Database update failed: {str(db_error)}", exc_info=True)
            raise HTTPException(status_code=500, detail=f"Database error: {str(db_error)}")
    except InvalidIdTokenError as e:
        logger.error(f"Invalid Firebase token: {str(e)}")
        raise HTTPException(status_code=401, detail="Invalid Firebase token")
    except Exception as e:
        logger.error(f"User update failed: {str(e)}", exc_info=True)
        raise HTTPException(status_code=400, detail=f"User update failed: {str(e)}")