# WhatsApp-Like Chat Backend (FastAPI)

Backend for a WhatsApp-style chat app built with **FastAPI**, **Tortoise ORM**, **PostgreSQL**, and **Firebase Authentication**. It supports individual/group chats, media uploads, and real-time WebSocket messaging. Designed for modularity, security, and easy deployment with Docker and Render.

---

## 🔧 Features

- **User Management**: Create users using Firebase UID, email, and display name.
- **1-on-1 Chats**: Real-time private chats (`/chat/{receiver_id}`).
- **Group Chats**: Real-time group chats (`/chat/group/{group_id}`).
- **Media Uploads**: Supports image/video uploads (`POST /media`).
- **Firebase Auth**: Secures all endpoints and WebSockets via ID tokens.
- **Tortoise ORM**: Easy PostgreSQL interaction, no raw SQL.
- **Lifespan Events**: Uses `lifespan` instead of deprecated `@on_event`.
- **Docker & Render Ready**: Containerized and deployable in one click.

---

## 📁 Project Structure

```
chat-backend/
├── .env
├── .dockerignore
├── .gitignore
├── Dockerfile
├── requirements.txt
├── firebase-service-account.json  # Ignored
├── uploads/
└── src/
    ├── __init__.py
    ├── auth.py
    ├── database.py
    ├── models.py
    └── main.py
```

---

## ⚙️ Prerequisites

- Python 3.10+
- PostgreSQL (local or via Render)
- Firebase project with Authentication
- Tools: Git, Postman, pgAdmin (optional)
- Docker (optional)

---

## 🚀 Setup Instructions

### 1. Clone the Repo
```bash
git clone https://github.com/jishnu70/Chat-app-backend.git
cd chat-backend
```

### 2. Configure `.env`
```
DATABASE_HOST=localhost
DATABASE_PORT=5432
DATABASE_NAME=chat_app
DATABASE_USER=your_user
DATABASE_PASSWORD=your_password
UPLOAD_DIR=./uploads
```

### 3. Install Dependencies
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 4. Set Up Firebase
- Enable Firebase Authentication (Google Sign-In or others)
- Download service account JSON from:
  `Project Settings > Service Accounts`
- Save it as `firebase-service-account.json` in project root

### 5. PostgreSQL Setup
#### Local:
- Create DB: `CREATE DATABASE chat_app;`
- Update `.env` accordingly

#### Render:
- Create PostgreSQL instance
- Copy credentials into `.env`

### 6. Run the App
```bash
uvicorn src.main:app --reload
```
Docs: [http://localhost:8000/docs](http://localhost:8000/docs)

---

## 🧪 Example Usage

### Create User
```bash
curl -X POST http://localhost:8000/users -H "Content-Type: application/json" \
-d '{"firebase_uid": "uid_1", "email": "user1@example.com", "display_name": "User 1"}'
```

### Create Group
```bash
curl -X POST http://localhost:8000/groups \
-H "Authorization: Bearer YOUR_TOKEN" \
-d '{"name": "Study Group"}'
```

### Add Group Member
```bash
curl -X POST http://localhost:8000/groups/1/members \
-H "Authorization: Bearer YOUR_TOKEN" \
-d '{"user_id": 2}'
```

### Upload Media
```bash
curl -X POST http://localhost:8000/media \
-H "Authorization: Bearer YOUR_TOKEN" \
-F "file=@/path/to/image.jpg"
```

---

## 🔌 WebSocket Testing

### 1-on-1 Chat:
- `ws://localhost:8000/chat/{receiver_id}?token=YOUR_TOKEN`

### Group Chat:
- `ws://localhost:8000/chat/group/{group_id}?token=YOUR_TOKEN`

---

## 🗃️ Database Models (via Tortoise ORM)

**Users**
- `user_id (PK)`
- `firebase_uid (unique)`
- `email (unique)`
- `display_name`
- `created_at`

**Groups**
- `group_id (PK)`
- `name`
- `creator_id (FK)`
- `created_at`

**GroupMembers**
- `user_id (FK)`
- `group_id (FK)`
- `(user_id, group_id)` → unique

**Messages**
- `message_id (PK)`
- `sender_id (FK)`
- `receiver_id (nullable FK)`
- `group_id (nullable FK)`
- `message_content`
- `media_url (optional)`
- `media_type ("image", "video")`
- `timestamp`

---

## 🐳 Docker

### Local Docker Run
```bash
docker build -t chat-backend .
docker run -p 8000:8000 --env-file .env -v $(pwd)/uploads:/app/uploads chat-backend
```

### Deploy on Render
- Push to GitHub
- Create new **Web Service** on Render
- Use Docker runtime
- Add env vars and a **disk for `/app/uploads`**

---

## 📬 API Summary

| Method | Endpoint                          | Auth      | Description              |
|--------|-----------------------------------|-----------|--------------------------|
| POST   | `/users`                          | ❌        | Create user              |
| POST   | `/groups`                         | ✅        | Create group             |
| POST   | `/groups/{group_id}/members`      | ✅        | Add member to group      |
| POST   | `/media`                          | ✅        | Upload media             |
| WS     | `/chat/{receiver_id}`            | ✅ (query)| 1-on-1 chat              |
| WS     | `/chat/group/{group_id}`         | ✅ (query)| Group chat               |

---

## 🧠 Notes

- **Media Storage**: Local or Render volume. Use S3 in production.
- **E2EE**: Planned.
- **Message History**: Add `GET /messages` (future).
- **Errors**: Logs + HTTPException handling.

---

## 🧩 Troubleshooting

- **DB Issues**: Check `.env`, PostgreSQL status, and logs.
- **Firebase Errors**: Validate JSON, token, and Firebase config.
- **WebSocket Drops**: Confirm token + group/user exists.

---

## 🤝 Contributing

```bash
git checkout -b feature-name
git commit -m "Add feature"
git push origin feature-name
```
Open a Pull Request 🚀

---

## 📄 License

MIT License. See `LICENSE`.

---

## 📚 Resources

- [FastAPI Docs](https://fastapi.tiangolo.com/)
- [Tortoise ORM](https://tortoise-orm.readthedocs.io/)
- [Firebase Auth](https://firebase.google.com/docs/auth)
- [Render Deployments](https://render.com/docs)
- [Docker Docs](https://docs.docker.com/)