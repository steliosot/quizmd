# Multiplayer Beta (Server + Client)

This folder contains a runnable end-to-end multiplayer beta:

- `server/`: FastAPI + WebSocket room/game backend
- `client/`: CLI room/join/chat/play client

## Quick Local Run

Terminal 1 (server):

```bash
cd /Users/stelios/Documents/quizmd/multiplayer/server
python3.13 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --host 127.0.0.1 --port 8020
```

Terminal 2 (host):

```bash
cd /Users/stelios/Documents/quizmd/multiplayer/client
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python quizmd_client.py --server http://127.0.0.1:8020 room --create "berlin-elephant" --name "Mary" --quiz examples/sample-5q.json
```

Terminal 3 (join):

```bash
cd /Users/stelios/Documents/quizmd/multiplayer/client
source .venv/bin/activate
python quizmd_client.py --server http://127.0.0.1:8020 room --join "berlin-elephant" --name "Stelios"
```

Terminal 4 (join):

```bash
cd /Users/stelios/Documents/quizmd/multiplayer/client
source .venv/bin/activate
python quizmd_client.py --server http://127.0.0.1:8020 room --join "berlin-elephant" --name "Tim"
```

## Controls

- Lobby:
  - `/start` (host only)
  - `/players`
  - `/help`
  - `/quit`
- Quiz:
  - single-choice answer: `2`
  - multi-choice answer: `1,3`
  - chat message: `/chat hello`

## Quiz Payload Rule

- For online rooms, each question `time_limit` must be `>= 5` seconds.

## Cloud Run Note

Rooms are currently stored in-memory. For reliable beta behavior on Cloud Run, keep service to a single instance.
