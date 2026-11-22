"""Imita `claude -p --output-format stream-json`: lee el prompt de stdin y emite eventos JSON."""
import json
import os
import sys

modo = os.environ.get("FAKE_CC_MODO", "ok")
prompt = sys.stdin.buffer.read().decode("utf-8")
args = sys.argv[1:]
with open(os.environ["FAKE_CC_REGISTRO"], "w", encoding="utf-8") as f:
    json.dump({"args": args, "prompt": prompt, "api_key": os.environ.get("ANTHROPIC_API_KEY")}, f)


def out(d):
    print(json.dumps(d), flush=True)


out({"type": "system", "subtype": "init"})
if modo == "login":
    out({"type": "result", "is_error": True, "result": "Not logged in · Please run /login"})
    sys.exit(1)
modelo = args[args.index("--model") + 1]
out({"type": "stream_event", "event": {"type": "message_start", "message": {"model": modelo}}})
out({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "thinking_delta",
                                                                                "thinking": "Pienso."}}})
for t in ("Hola ", "desde ", "la suscripción"):
    out({"type": "stream_event", "event": {"type": "content_block_delta", "delta": {"type": "text_delta", "text": t}}})
out({"type": "result", "is_error": False, "stop_reason": "end_turn",
     "usage": {"input_tokens": 3, "cache_read_input_tokens": 10, "output_tokens": 7}})
