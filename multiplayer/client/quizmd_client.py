#!/usr/bin/env python3
import argparse
import asyncio
import contextlib
import importlib
import json
import os
import sys
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse, urlunparse

import requests
import websockets

DEFAULT_SERVER = "https://quizmd-server-1096434233875.europe-west1.run.app"
DEFAULT_QUIZ_FILE = os.path.join(os.path.dirname(__file__), "examples", "sample-5q.json")


def _norm_http(url: str) -> str:
    if not url:
        return url
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    if scheme == "http" and host.endswith(".run.app"):
        return urlunparse(parsed._replace(scheme="https"))
    return url


def _norm_ws(url: str) -> str:
    if not url:
        return url
    parsed = urlparse(url)
    scheme = parsed.scheme.lower()
    host = (parsed.hostname or "").lower()
    force_tls = host.endswith(".run.app")
    if scheme == "ws" and force_tls:
        return urlunparse(parsed._replace(scheme="wss"))
    if scheme == "http" and force_tls:
        return urlunparse(parsed._replace(scheme="wss"))
    if scheme == "https":
        return urlunparse(parsed._replace(scheme="wss"))
    if scheme == "http":
        return urlunparse(parsed._replace(scheme="ws"))
    return url


def _server_base(server: str) -> str:
    return _norm_http(server.rstrip("/"))


def _load_quiz_file(path: str) -> tuple[str, list[dict[str, Any]]]:
    with open(path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError("Quiz file must be a JSON object.")
    title = data.get("quiz_title")
    questions = data.get("questions")
    if not isinstance(title, str) or not title.strip():
        raise ValueError("Quiz file requires non-empty 'quiz_title'.")
    if not isinstance(questions, list) or not questions:
        raise ValueError("Quiz file requires non-empty 'questions' list.")
    return title.strip(), questions


def _friendly_http_error(exc: requests.HTTPError) -> str:
    response = exc.response
    if response is None:
        return str(exc)
    detail = ""
    try:
        payload = response.json()
        if isinstance(payload, dict):
            if "detail" in payload:
                detail = str(payload["detail"])
            else:
                detail = json.dumps(payload)
    except Exception:
        detail = response.text.strip()
    if not detail:
        detail = response.reason or "HTTP error"
    return f"{response.status_code} {detail}"


@dataclass
class RoomInfo:
    room_code: str
    room_name: str
    room_token: str
    host_player_id: str
    host_player_token: str
    host_display_name: str
    join_url: str
    ws_url: str


class QuizmdClient:
    def __init__(
        self,
        server: str,
        theme_name: str = "auto",
        no_color: bool = False,
        full_screen: bool = False,
    ):
        self.server = _server_base(server)
        self.theme_name = theme_name
        self.no_color = no_color
        self.full_screen = full_screen
        self._quiz_ui: dict[str, Any] | None = None

    def _load_quiz_ui(self) -> dict[str, Any]:
        if self._quiz_ui is not None:
            return self._quiz_ui

        candidates = [None, str(Path(__file__).resolve().parents[2])]
        last_error: Exception | None = None
        for candidate in candidates:
            try:
                if candidate and candidate not in sys.path:
                    sys.path.insert(0, candidate)
                module = importlib.import_module("quizmd")
                self._quiz_ui = {
                    "ask_question": getattr(module, "ask_question"),
                    "select_theme": getattr(module, "select_theme"),
                    "is_no_color_requested": getattr(module, "is_no_color_requested"),
                }
                return self._quiz_ui
            except Exception as exc:  # pragma: no cover - import environment dependent
                last_error = exc

        raise RuntimeError(
            "Could not load shared quiz UI from 'quizmd'. "
            "Install quizmd and prompt_toolkit/rich dependencies."
        ) from last_error

    async def _prompt_with_shared_quiz_ui(
        self,
        question_payload: dict[str, Any],
        question_index: int,
        total_questions: int,
    ) -> list[int] | None:
        ui = self._load_quiz_ui()
        ask_question = ui["ask_question"]
        select_theme = ui["select_theme"]
        is_no_color_requested = ui["is_no_color_requested"]

        theme = select_theme(self.theme_name)
        no_color = is_no_color_requested(self.no_color)

        # Reuse quizmd's exact interactive selector UI.
        q = {
            "title": f"Question {question_index}",
            "question": question_payload.get("question", ""),
            "options": list(question_payload.get("options", [])),
            "correct": [-1],  # Unknown client-side; server is source of truth.
            "type": "multiple" if str(question_payload.get("type", "single")) == "multiple" else "single",
            "time_limit": int(question_payload.get("time_limit") or 30),
            "explanation": "",
            "imposters": [],
        }
        _perfect, answers, _imposters, _grading = await ask_question(
            q,
            theme,
            question_index=question_index,
            total_questions=total_questions,
            no_color=no_color,
            compact=False,
            full_screen=self.full_screen,
        )
        return answers

    def doctor(self) -> int:
        print(f"Server: {self.server}")
        openapi_ok = False
        health_ok = False

        try:
            r = requests.get(f"{self.server}/openapi.json", timeout=10)
            if r.ok:
                openapi_ok = True
                print("PASS: /openapi.json reachable")
            else:
                print(f"FAIL: /openapi.json status={r.status_code}")
        except Exception as exc:
            print(f"FAIL: /openapi.json error={exc}")

        try:
            r = requests.get(f"{self.server}/healthz", timeout=10)
            if r.ok:
                health_ok = True
                print("PASS: /healthz reachable")
            else:
                print(f"WARN: /healthz status={r.status_code}")
        except Exception as exc:
            print(f"WARN: /healthz error={exc}")

        return 0 if openapi_ok else 1

    def create_room(
        self,
        host_name: str,
        room_name: str,
        mode: str = "compete",
        quiz_title: str = "Beta Trial",
        questions: list[dict[str, Any]] | None = None,
    ) -> RoomInfo:
        if questions is None:
            questions = [
                {
                    "title": "Warmup",
                    "question": "2 + 2 = ?",
                    "options": ["3", "4", "5", "6"],
                    "correct": [2],
                    "type": "single",
                    "time_limit": 20,
                    "explanation": "2 + 2 is 4",
                }
            ]
        payload = {
            "mode": mode,
            "room_name": room_name,
            "quiz_title": quiz_title,
            "host_name": host_name,
            "questions": questions,
        }
        r = requests.post(f"{self.server}/rooms", json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        return RoomInfo(
            room_code=data["room_code"],
            room_name=data["room_name"],
            room_token=data["room_token"],
            host_player_id=data["host_player_id"],
            host_player_token=data["host_player_token"],
            host_display_name=data["host_display_name"],
            join_url=_norm_http(data.get("join_url", "")),
            ws_url=_norm_ws(data.get("ws_url", "")),
        )

    def join_room(self, room_code: str, room_token: str, player_name: str) -> dict[str, Any]:
        payload = {"room_token": room_token, "player_name": player_name}
        r = requests.post(f"{self.server}/rooms/{room_code}/join", json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        data["ws_url"] = _norm_ws(data.get("ws_url", ""))
        return data

    def join_room_by_name(self, room_name: str, player_name: str) -> dict[str, Any]:
        payload = {"player_name": player_name}
        r = requests.post(f"{self.server}/rooms/by-name/{room_name}/join", json=payload, timeout=15)
        r.raise_for_status()
        data = r.json()
        data["ws_url"] = _norm_ws(data.get("ws_url", ""))
        return data

    def _build_ws_url(self, ws_base: str, room_code: str, player_id: str, token: str) -> str:
        normalized = _norm_ws(ws_base)
        parsed = urlparse(normalized)
        if parsed.path.endswith("/ws"):
            path = parsed.path
        else:
            path = f"/rooms/{room_code}/ws"
        return urlunparse(
            parsed._replace(
                path=path,
                query=f"player_id={player_id}&token={token}",
            )
        )

    async def ws_ping(self, ws_base: str, room_code: str, player_id: str, token: str) -> None:
        ws_url = self._build_ws_url(ws_base, room_code, player_id, token)
        async with websockets.connect(ws_url, open_timeout=10, close_timeout=5) as ws:
            hello = await ws.recv()
            print("WS event:", hello)
            await ws.send(json.dumps({"type": "ping", "nonce": str(uuid.uuid4())}))
            pong = await ws.recv()
            print("WS event:", pong)

    @staticmethod
    def _connected_names(payload: dict[str, Any]) -> list[str]:
        players = payload.get("players", [])
        names = [p.get("name", "Unknown") for p in players if p.get("connected")]
        return sorted(names, key=lambda n: n.lower())

    @staticmethod
    def _fmt_indexes(values: list[int]) -> str:
        if not values:
            return "-"
        return ", ".join(str(v) for v in values)

    async def waiting_room(
        self,
        ws_base: str,
        room_code: str,
        player_id: str,
        token: str,
        display_name: str,
        room_name: str,
        is_host: bool,
    ) -> int:
        ws_url = self._build_ws_url(ws_base, room_code, player_id, token)
        stop = asyncio.Event()
        connected_names: list[str] = []
        known_connected: set[str] = set()
        in_quiz = False
        current_question_index: int | None = None
        current_total_questions = 0

        async with websockets.connect(ws_url, open_timeout=10, close_timeout=5) as ws:
            print(f"\nConnected as {display_name}.")
            print(f'Share "{room_name}" with your friends.')
            if is_host:
                print("Type /start when you are ready.")
            print("Chat enabled. Type message and press Enter.")
            print("Commands: /start (host), /players, /help, /quit")

            await ws.send(json.dumps({"type": "ready_toggle", "payload": {"ready": True}}))

            async def recv_loop() -> None:
                nonlocal connected_names, known_connected
                nonlocal in_quiz, current_question_index
                nonlocal current_total_questions
                while not stop.is_set():
                    try:
                        raw = await ws.recv()
                    except Exception:
                        stop.set()
                        return
                    try:
                        event = json.loads(raw)
                    except Exception:
                        continue
                    etype = event.get("type")
                    payload = event.get("payload", {})
                    if etype == "chat_message":
                        sender = payload.get("from", "Unknown")
                        text = payload.get("text", "")
                        print(f"[{sender}] {text}")
                        continue
                    if etype in {"connected", "lobby_update"}:
                        connected_names = self._connected_names(payload)
                        current_set = set(connected_names)
                        for name in sorted(current_set - known_connected):
                            print(f"{name} joined.")
                        for name in sorted(known_connected - current_set):
                            print(f"{name} left.")
                        known_connected = current_set
                        continue
                    if etype == "game_started":
                        print("Game is starting now.")
                        in_quiz = True
                        continue
                    if etype == "question":
                        in_quiz = True
                        q = payload.get("question", {})
                        current_question_index = int(payload.get("question_index", 0))
                        current_total_questions = int(payload.get("total_questions", 0))
                        try:
                            answers = await self._prompt_with_shared_quiz_ui(
                                question_payload=q,
                                question_index=current_question_index + 1,
                                total_questions=max(1, current_total_questions),
                            )
                        except KeyboardInterrupt:
                            await ws.send(json.dumps({"type": "leave_room", "payload": {}}))
                            stop.set()
                            return
                        except RuntimeError as exc:
                            print(f"Runtime error: {exc}")
                            stop.set()
                            return

                        if answers:
                            await ws.send(
                                json.dumps(
                                    {
                                        "type": "submit_answer",
                                        "payload": {
                                            "question_index": current_question_index,
                                            "answers": answers,
                                        },
                                    }
                                )
                            )
                            print(f"Submitted: {self._fmt_indexes(answers)}")
                        else:
                            print("No answer submitted. Waiting for round result...")
                        continue
                    if etype == "round_result":
                        qidx = int(payload.get("question_index", -1))
                        print("")
                        print(f"Round {qidx + 1} result:")
                        print(f"Correct options: {self._fmt_indexes(payload.get('correct_indexes', []))}")
                        players = payload.get("players", [])
                        if isinstance(players, list):
                            for row in players:
                                name = row.get("name", "Unknown")
                                is_correct = bool(row.get("is_correct", False))
                                delta = row.get("delta")
                                score = row.get("score")
                                mark = "correct" if is_correct else "wrong"
                                if delta is not None and score is not None:
                                    print(f"  - {name}: {mark}, delta={delta}, score={score}")
                                else:
                                    print(f"  - {name}: {mark}")
                        continue
                    if etype == "consensus_retry":
                        print("")
                        print(payload.get("message", "Not consensus, try again"))
                        wrong = payload.get("wrong_names", [])
                        missing = payload.get("missing_names", [])
                        if wrong:
                            print("Wrong answers from: " + ", ".join(wrong))
                        if missing:
                            print("Missing answers from: " + ", ".join(missing))
                        continue
                    if etype == "scoreboard":
                        print("")
                        print("Scoreboard:")
                        rows = payload.get("players", [])
                        if isinstance(rows, list):
                            for row in rows:
                                print(f"  - {row.get('name', 'Unknown')}: {row.get('score', 0)}")
                        continue
                    if etype == "game_finished":
                        print("")
                        print("Game finished.")
                        reason = payload.get("reason")
                        if reason:
                            print(f"Reason: {reason}")
                        stop.set()
                        return
                    if etype == "error":
                        print(f"Server: {payload.get('message', 'Unknown error')}")
                        continue
                    if etype == "host_reconnected":
                        print("Host reconnected.")
                        continue

            recv_task = asyncio.create_task(recv_loop())
            try:
                while not stop.is_set():
                    if in_quiz:
                        await asyncio.sleep(0.1)
                        continue
                    try:
                        line = await asyncio.to_thread(input, "")
                    except EOFError:
                        break
                    text = line.strip()
                    if not text:
                        continue
                    if text == "/quit":
                        await ws.send(json.dumps({"type": "leave_room", "payload": {}}))
                        stop.set()
                        break
                    if text == "/help":
                        if in_quiz:
                            print("Quiz in progress: use quiz controls (↑/↓, Space, Enter).")
                            print("Commands: /players, /help, /quit")
                        else:
                            print("Commands: /start (host), /players, /help, /quit")
                        continue
                    if text == "/players":
                        if connected_names:
                            print("Connected: " + ", ".join(connected_names))
                        else:
                            print("No connected players shown yet.")
                        continue
                    if text == "/start":
                        if not is_host:
                            print("Only the room host can start.")
                            continue
                        await ws.send(json.dumps({"type": "start_game", "payload": {}}))
                        continue
                    if text == "/ready":
                        await ws.send(json.dumps({"type": "ready_toggle", "payload": {"ready": True}}))
                        continue
                    if text.startswith("/chat "):
                        msg = text[len("/chat ") :].strip()
                        if msg:
                            await ws.send(json.dumps({"type": "chat_message", "payload": {"text": msg}}))
                        continue
                    if text.startswith("/"):
                        print("Unknown command. Type /help.")
                        continue

                    await ws.send(json.dumps({"type": "chat_message", "payload": {"text": text}}))
            finally:
                stop.set()
                recv_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await recv_task
        return 0

    async def watch_lobby(self, ws_base: str, room_code: str, player_id: str, token: str) -> None:
        ws_url = self._build_ws_url(ws_base, room_code, player_id, token)
        known_connected: set[str] = set()
        async with websockets.connect(ws_url, open_timeout=10, close_timeout=5) as ws:
            print("Watching lobby events (Ctrl+C to stop)...")
            while True:
                raw = await ws.recv()
                try:
                    event = json.loads(raw)
                except Exception:
                    continue
                etype = event.get("type")
                if etype == "player_joined":
                    name = event.get("payload", {}).get("name", "Unknown")
                    print(f"Joined: {name}")
                    continue
                if etype == "player_left":
                    name = event.get("payload", {}).get("name", "Unknown")
                    print(f"Left: {name}")
                    continue
                if etype not in {"connected", "lobby_update"}:
                    continue
                payload = event.get("payload", {})
                players = payload.get("players", [])
                connected = {p.get("name", "Unknown") for p in players if p.get("connected")}
                for name in sorted(connected - known_connected):
                    print(f"Joined: {name}")
                for name in sorted(known_connected - connected):
                    print(f"Left: {name}")
                known_connected = connected

    async def smoke(
        self,
        host_name: str,
        guest_name: str,
        room_name: str,
        quiz_title: str = "Beta Trial",
        questions: list[dict[str, Any]] | None = None,
    ) -> int:
        room = self.create_room(host_name=host_name, room_name=room_name, quiz_title=quiz_title, questions=questions)
        print("Room created:")
        print(json.dumps(room.__dict__, indent=2))

        guest = self.join_room(room.room_code, room.room_token, guest_name)
        print("Guest joined:")
        print(json.dumps(guest, indent=2))

        host_task = self.ws_ping(room.ws_url, room.room_code, room.host_player_id, room.host_player_token)
        guest_task = self.ws_ping(guest["ws_url"], room.room_code, guest["player_id"], guest["player_token"])
        await asyncio.gather(host_task, guest_task)
        print("Smoke test complete")
        return 0


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="quizmd server beta client")
    parser.add_argument("--server", default=DEFAULT_SERVER, help="quizmd-server base URL")
    parser.add_argument("--theme", choices=["auto", "light", "dark"], default="auto", help="shared quiz theme")
    parser.add_argument("--no-color", action="store_true", help="disable colors (or respect NO_COLOR)")
    parser.add_argument("--full-screen", action="store_true", help="full-screen question rendering")
    sub = parser.add_subparsers(dest="cmd", required=True)

    sub.add_parser("doctor", help="check server endpoints")

    create = sub.add_parser("create", help="create room")
    create.add_argument("--name", default="Host")
    create.add_argument("--room-name", default="berlin-elephant")
    create.add_argument("--mode", choices=["compete", "collaborate"], default="compete")
    create.add_argument("--quiz", default=DEFAULT_QUIZ_FILE, help="path to quiz JSON file")

    join = sub.add_parser("join", help="join room")
    join.add_argument("--room", required=True)
    join.add_argument("--token", required=True)
    join.add_argument("--name", default="Guest")

    smoke = sub.add_parser("smoke", help="end-to-end smoke flow")
    smoke.add_argument("--name", default="Host")
    smoke.add_argument("--guest-name", default="Guest")
    smoke.add_argument("--room-name", default="berlin-elephant")
    smoke.add_argument("--quiz", default=DEFAULT_QUIZ_FILE, help="path to quiz JSON file")

    room = sub.add_parser("room", help="simple room flow (no explicit token typing)")
    room_mode = room.add_mutually_exclusive_group(required=True)
    room_mode.add_argument("--create", metavar="ROOM_NAME", help="create room and wait")
    room_mode.add_argument("--join", metavar="ROOM_NAME", help="join room and wait")
    room.add_argument("--name", default="", help="display name (optional)")
    room.add_argument("--mode", choices=["compete", "collaborate"], default="compete")
    room.add_argument("--quiz", default=DEFAULT_QUIZ_FILE, help="path to quiz JSON file (create only)")

    return parser


def main() -> int:
    parser = _build_parser()
    args = parser.parse_args()
    client = QuizmdClient(
        args.server,
        theme_name=args.theme,
        no_color=args.no_color,
        full_screen=args.full_screen,
    )

    try:
        if args.cmd == "doctor":
            return client.doctor()

        if args.cmd == "create":
            quiz_title, questions = _load_quiz_file(args.quiz)
            room = client.create_room(
                host_name=args.name,
                room_name=args.room_name,
                mode=args.mode,
                quiz_title=quiz_title,
                questions=questions,
            )
            print(json.dumps(room.__dict__, indent=2))
            return 0

        if args.cmd == "join":
            data = client.join_room(room_code=args.room, room_token=args.token, player_name=args.name)
            print(json.dumps(data, indent=2))
            return 0

        if args.cmd == "smoke":
            quiz_title, questions = _load_quiz_file(args.quiz)
            return asyncio.run(
                client.smoke(
                    host_name=args.name,
                    guest_name=args.guest_name,
                    room_name=args.room_name,
                    quiz_title=quiz_title,
                    questions=questions,
                )
            )

        if args.cmd == "room":
            if args.create:
                room_name = args.create.strip().lower()
                if not room_name:
                    print("Invalid room name.")
                    return 2
                host_name = args.name or "Host"
                quiz_title, questions = _load_quiz_file(args.quiz)
                room = client.create_room(
                    host_name=host_name,
                    room_name=room_name,
                    mode=args.mode,
                    quiz_title=quiz_title,
                    questions=questions,
                )
                print(f"Room created by: {room.host_display_name}")
                print(f"Room name: {room.room_name}")
                print(f"Quiz: {quiz_title} ({len(questions)} questions)")
                print(f'Share "{room.room_name}" with your friends.')
                return asyncio.run(
                    client.waiting_room(
                        ws_base=room.ws_url,
                        room_code=room.room_code,
                        player_id=room.host_player_id,
                        token=room.host_player_token,
                        display_name=room.host_display_name,
                        room_name=room.room_name,
                        is_host=True,
                    )
                )
            if args.join:
                room_name = args.join.strip().lower()
                if not room_name:
                    print("Invalid room name.")
                    return 2
                player_name = args.name or "Guest"
                data = client.join_room_by_name(room_name=room_name, player_name=player_name)
                print(f'Joined room "{data["room_name"]}" as {data["display_name"]}.')
                return asyncio.run(
                    client.waiting_room(
                        ws_base=data["ws_url"],
                        room_code=data["room_code"],
                        player_id=data["player_id"],
                        token=data["player_token"],
                        display_name=data["display_name"],
                        room_name=data["room_name"],
                        is_host=False,
                    )
                )
    except requests.HTTPError as exc:
        print(f"Request failed: {_friendly_http_error(exc)}")
        return 1

    parser.error("unknown command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
