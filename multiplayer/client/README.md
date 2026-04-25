# quizmd-client (beta)

Standalone beta client to test `quizmd-server` without touching the main `quizmd` CLI.

## Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Commands

```bash
python quizmd_client.py doctor --server https://quizmd-server-1096434233875.europe-west1.run.app
python quizmd_client.py create --name Stelios --room-name berlin-elephant --quiz examples/sample-5q.json
python quizmd_client.py join --room ROOMCODE --token ROOMTOKEN --name Guest
python quizmd_client.py smoke --name Host --guest-name Guest --room-name berlin-elephant --quiz examples/sample-5q.json
```

## Simple Room Flow (No Token Typing)

```bash
python quizmd_client.py room --create "berlin-elephant" --name "Mary" --quiz examples/sample-5q.json
python quizmd_client.py room --join "berlin-elephant" --name "Tom"
# optional visual flags:
python quizmd_client.py --theme light --full-screen room --create "berlin-elephant" --name "Mary" --quiz examples/sample-5q.json
```

- Both users stay connected in a waiting room.
- Chat while waiting by typing a message and pressing Enter.
- Host can type `/start` to begin.
- Commands: `/start`, `/players`, `/help`, `/quit`
- During quiz it reuses the standard `quizmd` interactive selector:
  - `↑/↓` move
  - `Space` select
  - `Enter` submit
  - `Ctrl+C` exit

## Notes

- The client normalizes server-returned URLs:
  - `http://...` -> `https://...`
  - `ws://...` -> `wss://...`
- This is a beta harness for protocol testing, not the final UX client.
