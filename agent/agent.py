"""
AI-OS Agent: Main event loop and system API stubs (prototype)
"""
import time
from agent.input.text_input import get_text_input
from agent.input.voice_input import get_voice_input
from agent.input.gesture_input import get_gesture_input

# System API stubs
class SystemAPI:
    def list_files(self, path="."):
        # Placeholder for file listing
        import os
        return os.listdir(path)
    def get_time(self):
        import datetime
        return datetime.datetime.now().isoformat()
    def echo(self, msg):
        return msg


def main():
    api = SystemAPI()
    print("[AI-OS Agent] Starting event loop (prototype)...")
    while True:
        print("[AI-OS Agent] Waiting for input/event...")
        # Try text input first
        cmd = get_text_input()
        if cmd.strip() == "exit":
            print("[AI-OS Agent] Exiting event loop.")
            break
        elif cmd.strip() == "time":
            print(f"[AI-OS Agent] System time: {api.get_time()}")
        elif cmd.strip().startswith("ls"):
            path = cmd.strip().split(" ",1)[1] if " " in cmd else "."
            print(f"[AI-OS Agent] Files: {api.list_files(path)}")
        elif cmd.strip().startswith("echo"):
            msg = cmd.strip().split(" ",1)[1] if " " in cmd else ""
            print(f"[AI-OS Agent] Echo: {api.echo(msg)}")
        else:
            print(f"[AI-OS Agent] Unknown command: {cmd}")
        # Placeholders for voice/gesture input (future)
        # voice = get_voice_input()
        # gesture = get_gesture_input()
        time.sleep(1)

if __name__ == "__main__":
    main()
