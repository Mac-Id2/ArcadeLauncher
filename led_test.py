#!/usr/bin/env python3
"""
led_test.py — Interaktives Testtool für ESP32-LED-Effekte.
Sendet JSON-Kommandos direkt über die serielle Schnittstelle.
"""

import json
import sys
import threading
import time
from typing import Optional

try:
    import serial
    import serial.tools.list_ports
except ImportError:
    print("FEHLER: pyserial nicht installiert.  pip install pyserial")
    sys.exit(1)

BAUD = 115_200

SEGMENTS: dict[str, str] = {
    "0":  "marquee",
    "1":  "monitor_top",
    "2":  "monitor_right",
    "3":  "monitor_bottom",
    "4":  "monitor_left",
    "5":  "control_panel",
    "99": "alle",
}

EFFECT_TYPES = ["fill", "scanner", "sparkle", "wipe", "chase", "blink", "off"]

PRESETS: list[dict] = [
    {"name": "Scanner  – alle,          Gelb  ", "type": "scanner", "segment": 99, "r": 255, "g": 255, "b":   0, "speed": 50, "length": 5, "repeat": 3},
    {"name": "Sparkle  – alle,          Cyan  ", "type": "sparkle", "segment": 99, "r":   0, "g": 255, "b": 255, "speed": 50, "length": 5, "repeat": 5},
    {"name": "Fill     – alle,          Weiß  ", "type": "fill",    "segment": 99, "r": 255, "g": 255, "b": 255, "speed": 50, "length": 5, "repeat": 1},
    {"name": "Fill     – alle,          Grün  ", "type": "fill",    "segment": 99, "r":  57, "g": 255, "b":  20, "speed": 50, "length": 5, "repeat": 1},
    {"name": "Fill     – alle,          Lila  ", "type": "fill",    "segment": 99, "r": 255, "g":   0, "b": 255, "speed": 50, "length": 5, "repeat": 1},
    {"name": "Wipe     – marquee,       Blau  ", "type": "wipe",    "segment":  0, "r":   0, "g": 100, "b": 200, "speed": 55, "length": 5, "repeat": 2},
    {"name": "Chase    – monitor_top,   Pink  ", "type": "chase",   "segment":  1, "r": 255, "g":  20, "b": 147, "speed": 80, "length": 5, "repeat": 3},
    {"name": "Blink    – control_panel, Rot   ", "type": "blink",   "segment":  5, "r": 255, "g":   0, "b":   0, "speed": 30, "length": 5, "repeat": 5},
    {"name": "OFF      – alle                 ", "type": "off",     "segment": 99, "r":   0, "g":   0, "b":   0, "speed": 50, "length": 5, "repeat": 1},
]


class SerialConnection:
    def __init__(self, port: str, baud: int = BAUD) -> None:
        self._ser = serial.Serial(port, baud, timeout=1)
        self._lock = threading.Lock()
        self._running = True
        threading.Thread(target=self._reader, daemon=True, name="LED-RX").start()
        time.sleep(0.5)

    def send(self, payload: dict) -> None:
        line = json.dumps(payload, separators=(",", ":")) + "\n"
        with self._lock:
            self._ser.write(line.encode("utf-8"))
        print(f"  → {line.strip()}")

    def _reader(self) -> None:
        while self._running:
            try:
                raw = self._ser.readline().decode("utf-8", errors="ignore").strip()
                if raw:
                    print(f"\n  ← ESP32: {raw}\n  > ", end="", flush=True)
            except Exception:
                break

    def close(self) -> None:
        self._running = False
        with self._lock:
            if self._ser.is_open:
                self._ser.close()


def build_payload(
    effect_type: str,
    segment: int,
    r: int, g: int, b: int,
    speed: int = 50,
    length: int = 5,
    repeat: int = 1,
) -> dict:
    return {
        "cmd":      "effect",
        "chain":    "A",
        "type":     effect_type,
        "segment":  segment,
        "color":    {"r": r, "g": g, "b": b},
        "speed":    speed,
        "length":   length,
        "repeat":   repeat,
        "priority": 3,
    }


def detect_port() -> Optional[str]:
    keywords = ("cp210", "ch340", "esp32", "uart", "usb serial", "usb-serial", "silicon labs")
    for info in serial.tools.list_ports.comports():
        desc = (info.description or "").lower()
        mfr  = (info.manufacturer or "").lower()
        if any(k in desc or k in mfr for k in keywords):
            return info.device
    return None


def select_port() -> str:
    auto  = detect_port()
    ports = [p.device for p in serial.tools.list_ports.comports()]

    if auto:
        print(f"\n  ESP32 erkannt: {auto}")
        choice = input("  [Enter] verwenden oder anderen Port eingeben: ").strip()
        return choice if choice else auto

    if ports:
        print("\n  Verfügbare Ports:")
        for i, p in enumerate(ports, 1):
            info = next(x for x in serial.tools.list_ports.comports() if x.device == p)
            print(f"    {i}. {p}  ({info.description})")
        raw = input("  Nummer oder Port direkt eingeben: ").strip()
        if raw.isdigit() and 1 <= int(raw) <= len(ports):
            return ports[int(raw) - 1]
        return raw

    return input("  Kein Port erkannt. Manuell eingeben (z.B. /dev/ttyACM0): ").strip()


def prompt_int(label: str, default: int) -> int:
    raw = input(f"    {label} [{default}]: ").strip()
    return int(raw) if raw.lstrip("-").isdigit() else default


def custom_effect(conn: SerialConnection) -> None:
    print("\n  ── Custom Effekt ──────────────────────────────")
    print(f"  Typen: {', '.join(EFFECT_TYPES)}")
    effect_type = input("  Typ [fill]: ").strip() or "fill"
    print(f"  Segmente: {', '.join(f'{k}={v}' for k, v in SEGMENTS.items())}")
    segment = prompt_int("Segment", 99)
    r       = prompt_int("R", 0)
    g       = prompt_int("G", 255)
    b       = prompt_int("B", 0)
    speed   = prompt_int("Speed",  50)
    length  = prompt_int("Length",  5)
    repeat  = prompt_int("Repeat",  1)
    conn.send(build_payload(effect_type, segment, r, g, b, speed, length, repeat))


def print_header(port: str) -> None:
    print("\n" + "=" * 55)
    print("  LED TEST TOOL")
    print(f"  Port: {port} @ {BAUD} Baud")
    print("=" * 55)
    print("  Segmente:  " + "  ".join(f"{k}={v}" for k, v in SEGMENTS.items()))
    print()


def print_menu() -> None:
    print("  PRESETS")
    for i, p in enumerate(PRESETS, 1):
        print(f"    {i:>2}. {p['name']}")
    print()
    print("    c. Custom Effekt eingeben")
    print("    q. Beenden")
    print()


def run_menu(conn: SerialConnection, port: str) -> None:
    while True:
        print_header(port)
        print_menu()
        choice = input("  > ").strip().lower()

        if choice == "q":
            break
        elif choice == "c":
            custom_effect(conn)
        elif choice.isdigit() and 1 <= int(choice) <= len(PRESETS):
            p = PRESETS[int(choice) - 1]
            conn.send(build_payload(
                p["type"], p["segment"],
                p["r"], p["g"], p["b"],
                p.get("speed", 50), p.get("length", 5), p.get("repeat", 1),
            ))
        else:
            print("  Ungültige Eingabe.")
            time.sleep(0.5)
            continue

        time.sleep(0.3)


def main() -> None:
    print("\n  LED Test Tool — ESP32 Seriell")
    port = select_port()
    if not port:
        print("  Kein Port gewählt. Abbruch.")
        sys.exit(1)

    try:
        conn = SerialConnection(port)
        print(f"  Verbunden mit {port}")
    except Exception as e:
        print(f"  Verbindung fehlgeschlagen: {e}")
        sys.exit(1)

    try:
        run_menu(conn, port)
    except KeyboardInterrupt:
        print("\n  Abgebrochen.")
    finally:
        conn.close()
        print("  Verbindung getrennt.")


if __name__ == "__main__":
    main()
