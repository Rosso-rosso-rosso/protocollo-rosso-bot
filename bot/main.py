"""Entry point — polling + health su PORT (Render free)."""

from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from telegram import BotCommand, Update
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    PicklePersistence,
    filters,
)

from bot.config import LOG_LEVEL, PERSISTENCE_PATH, require_token
from bot.corpo import cmd_corpo, corpo_tasto
from bot.db import init_db
from bot.handlers import build_command_handlers, build_conversation_handlers, cmd_unknown, messaggio_libero
from bot.menu_rrr import CHIUDI, cmd_chiudi_menu, cmd_rrr
from bot.metodo import cmd_metodo
from bot.palestra import build_palestra_conversation, cmd_scheda
from bot.scacchiera_flow import (
    build_libro_conversation,
    build_scacchiera_conversation,
    scacchiera_command_handlers,
)
from bot import sdq1
from bot.identity import manifest
from bot.terzo import build_terzo_conversations

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    level=getattr(logging, LOG_LEVEL, logging.INFO),
    stream=sys.stdout,
)
logger = logging.getLogger("protocollo")

COMMANDS = [
    BotCommand("rrr", "Sottomenu con tutti i comandi"),
    BotCommand("palestra", "Peso ideale, kcal, settimane"),
    BotCommand("scheda", "Rivedi il profilo salvato"),
    BotCommand("corpo", "Sonno, luce, integratori"),
    BotCommand("metodo", "Il ciclo: ipotesi, atto, esito"),
    BotCommand("testimone", "Un atto che un terzo può vedere"),
    BotCommand("fuori", "Una cosa fatta oggi, fuori da qui"),
    BotCommand("azione", "Registra un atto verificabile"),
    BotCommand("aiuto", "Le tre cose che contano"),
    BotCommand("ping", "Il processo è vivo"),
    BotCommand("annulla", "Esci da un flusso"),
]


class _Health(BaseHTTPRequestHandler):
    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self) -> None:
        path = (self.path or "/").split("?", 1)[0]
        if path in ("/identity", "/r3/identity"):
            payload = json.dumps(manifest(), ensure_ascii=False).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8")
            return
        if path in ("/sdq1/health", "/ask/health"):
            payload = json.dumps(sdq1.health(), ensure_ascii=False).encode("utf-8")
            self._send(200, payload, "application/json; charset=utf-8")
            return
        self._send(200, b"ok protocollo-rosso-bot 1.6.6", "text/plain; charset=utf-8")

    def do_POST(self) -> None:
        path = (self.path or "/").split("?", 1)[0]
        if path != "/ask":
            self._send(404, b'{"error":"not found"}', "application/json")
            return
        n = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(n) if n else b"{}"
        try:
            data = json.loads(raw.decode("utf-8") or "{}")
        except json.JSONDecodeError:
            self._send(400, b'{"error":"json"}', "application/json")
            return
        out = sdq1.ask(str(data.get("testo") or ""), data.get("run_id"))
        self._send(200, json.dumps(out, ensure_ascii=False).encode("utf-8"), "application/json; charset=utf-8")

    def do_HEAD(self) -> None:
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args) -> None:
        return


def start_health(port: int) -> None:
    server = ThreadingHTTPServer(("0.0.0.0", port), _Health)
    threading.Thread(target=server.serve_forever, daemon=True, name="health").start()
    logger.info("Health ok su 0.0.0.0:%s", port)


async def on_error(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
    logger.exception("Errore non gestito: %s", context.error)
    if isinstance(update, Update) and update.effective_message:
        await update.effective_message.reply_text(
            "Qualcosa si è interrotto nello strato tecnico del bot. "
            "Riprova. Nessuna possibilità è stata chiusa."
        )


async def cmd_sdq(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    testo = " ".join(context.args or []).strip()
    if not testo:
        await update.message.reply_text("Uso: /sdq <testo>\nNucleo locale, zero agenti.")
        return
    out = await asyncio.to_thread(sdq1.ask, testo)
    await update.message.reply_text(out["risposta"][:3900])


async def on_testo(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if await corpo_tasto(update, context):
        return
    await messaggio_libero(update, context)


async def post_init(application: Application) -> None:
    await application.bot.delete_webhook(drop_pending_updates=False)
    await application.bot.set_my_commands(COMMANDS)
    await application.bot.set_my_description(
        "Tenere aperta una possibilità senza spacciarla per un fatto. "
        "Poi una cosa vera, che un altro possa vedere."
    )
    await application.bot.set_my_short_description("Protocollo Rosso · bordo, non abitante")
    me = await application.bot.get_me()
    logger.info("Collegato come @%s. Polling.", me.username)


def build_application() -> Application:
    token = require_token()
    init_db()
    persistence = PicklePersistence(filepath=PERSISTENCE_PATH)
    app = (
        Application.builder()
        .token(token)
        .persistence(persistence)
        .post_init(post_init)
        .build()
    )
    app.add_handler(build_palestra_conversation())
    app.add_handler(build_libro_conversation())
    app.add_handler(build_scacchiera_conversation())
    for h in build_terzo_conversations():
        app.add_handler(h)
    for h in build_conversation_handlers():
        app.add_handler(h)
    for h in build_command_handlers():
        app.add_handler(h)
    app.add_handler(CommandHandler("scheda", cmd_scheda))
    app.add_handler(CommandHandler("rrr", cmd_rrr))
    app.add_handler(CommandHandler("metodo", cmd_metodo))
    app.add_handler(CommandHandler("corpo", cmd_corpo))
    app.add_handler(CommandHandler("sdq", cmd_sdq))
    for h in scacchiera_command_handlers():
        app.add_handler(h)
    app.add_handler(MessageHandler(filters.Regex(f"^{CHIUDI}$"), cmd_chiudi_menu))
    app.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, on_testo))
    app.add_handler(MessageHandler(filters.COMMAND, cmd_unknown))
    app.add_error_handler(on_error)
    return app


def main() -> None:
    port = os.getenv("PORT")
    if port:
        start_health(int(port))
    app = build_application()
    logger.info("Long polling. Ctrl+C per fermare.")
    app.run_polling(allowed_updates=Update.ALL_TYPES, drop_pending_updates=False)


if __name__ == "__main__":
    main()
