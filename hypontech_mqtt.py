#!/usr/bin/env python3
import datetime
import json
import os
import socket
import struct
import threading

LISTEN_HOST = os.getenv("LISTEN_HOST", "0.0.0.0")
LISTEN_PORT = int(os.getenv("LISTEN_PORT", 51100))

MQTT_HOST = os.getenv("MQTT_HOST", "")
MQTT_PORT = int(os.getenv("MQTT_PORT", 1883))
MQTT_USER = os.getenv("MQTT_USER", "")
MQTT_PASS = os.getenv("MQTT_PASS", "")
DISCOVERY_PREFIX = os.getenv("DISCOVERY_PREFIX", "homeassistant")

SENSORS = {
    "ac_power_w":         ("AC Power",         "W",   "power",          "measurement"),
    "apparent_power_va":  ("Apparent Power",   "VA",  "apparent_power", "measurement"),
    "reactive_power_var": ("Reactive Power",   "var", "reactive_power", "measurement"),
    "power_factor_pct":   ("Power Factor",     "%",   "power_factor",   "measurement"),
    "daily_kwh":          ("Daily Energy",     "kWh", "energy",         "total_increasing"),
    "total_kwh":          ("Total Energy",     "kWh", "energy",         "total_increasing"),
    "pv1_v":              ("PV1 Voltage",      "V",   "voltage",        "measurement"),
    "pv1_a":              ("PV1 Current",      "A",   "current",        "measurement"),
    "grid_v":             ("Grid Voltage",     "V",   "voltage",        "measurement"),
    "grid_a":             ("Grid Current",     "A",   "current",        "measurement"),
    "grid_hz":            ("Grid Frequency",   "Hz",  "frequency",      "measurement"),
    "bus_v":              ("DC Bus Voltage",   "V",   "voltage",        "measurement"),
    "temp1_c":            ("Temperature 1",    "°C",  "temperature",    "measurement"),
    "temp2_c":            ("Temperature 2",    "°C",  "temperature",    "measurement"),
}

discovered_sns = set()
lock = threading.Lock()

def mqtt_rem_len(n: int) -> bytes:
    out = bytearray()
    while True:
        b = n % 128
        n //= 128
        if n > 0:
            b |= 0x80
        out.append(b)
        if n == 0:
            break
    return bytes(out)

def mqtt_str(s: str) -> bytes:
    b = s.encode("utf-8")
    return struct.pack(">H", len(b)) + b

def mqtt_publish_batch(messages: list[tuple[str, str, bool]]):
    flags = 0x02
    payload = mqtt_str("hypontech-bridge")
    if MQTT_USER:
        flags |= 0x80
        payload += mqtt_str(MQTT_USER)
        if MQTT_PASS:
            flags |= 0x40
            payload += mqtt_str(MQTT_PASS)

    var_hdr = b"\x00\x04MQTT\x04" + bytes([flags]) + struct.pack(">H", 60)
    connect_pkt = b"\x10" + mqtt_rem_len(len(var_hdr) + len(payload)) + var_hdr + payload

    with socket.create_connection((MQTT_HOST, MQTT_PORT), timeout=10) as m:
        m.sendall(connect_pkt)
        connack = m.recv(4)
        if len(connack) < 4 or connack[0] != 0x20 or connack[3] != 0x00:
            raise RuntimeError(f"MQTT CONNACK failed: {connack.hex()}")
        for topic, body, retain in messages:
            hdr0 = 0x31 if retain else 0x30
            pkt_body = mqtt_str(topic) + body.encode("utf-8")
            m.sendall(bytes([hdr0]) + mqtt_rem_len(len(pkt_body)) + pkt_body)
        m.sendall(b"\xe0\x00")

def ensure_discovery(sn: str, model: str = "HPS-3000DL"):
    with lock:
        if sn in discovered_sns:
            return
        state_topic = f"hypontech/{sn}/state"
        device = {
            "identifiers": [f"hypontech_{sn}"],
            "name": f"Hypontech {model} ({sn})",
            "manufacturer": "Hypontech",
            "model": model,
        }
        msgs = []
        for key, (name, unit, dev_cls, state_cls) in SENSORS.items():
            cfg_topic = f"{DISCOVERY_PREFIX}/sensor/hypontech_{sn}/{key}/config"
            payload = {
                "name": name,
                "unique_id": f"hypontech_{sn}_{key}",
                "state_topic": state_topic,
                "value_template": f"{{{{ value_json.{key} }}}}",
                "unit_of_measurement": unit,
                "device_class": dev_cls,
                "state_class": state_cls,
                "device": device,
            }
            msgs.append((cfg_topic, json.dumps(payload), True))
        mqtt_publish_batch(msgs)
        discovered_sns.add(sn)
        print(f"[+] Published HA MQTT discovery for {sn}")

def recv_exact(conn: socket.socket, n: int) -> bytes:
    buf = bytearray()
    while len(buf) < n:
        chunk = conn.recv(n - len(buf))
        if not chunk:
            raise EOFError("Connection closed")
        buf.extend(chunk)
    return bytes(buf)

def make_reply(cmd: bytes, seq: bytes, payload: bytes = b"") -> bytes:
    return b"\xa5\x06\xa1" + cmd + b"\x00\x00\x00" + seq + struct.pack(">H", len(payload)) + payload

def decode_telemetry(p: bytes) -> dict:
    sn = p[0:26].split(b"\x00", 1)[0].decode("ascii", errors="replace")
    yy, mo, dd, hh, mm, ss = p[26:32]
    return {
        "sn": sn,
        "timestamp": f"20{yy:02d}-{mo:02d}-{dd:02d} {hh:02d}:{mm:02d}:{ss:02d}",
        "ac_power_w": struct.unpack_from(">i", p, 37)[0],
        "apparent_power_va": struct.unpack_from(">i", p, 41)[0],
        "reactive_power_var": struct.unpack_from(">i", p, 45)[0],
        "power_factor_pct": struct.unpack_from(">H", p, 49)[0],
        "daily_kwh": struct.unpack_from(">I", p, 55)[0] / 10.0,
        "total_kwh": round(struct.unpack_from(">f", p, 145)[0], 2),
        "pv1_v": struct.unpack_from(">H", p, 75)[0] / 10.0,
        "pv1_a": struct.unpack_from(">H", p, 77)[0] / 10.0,
        "grid_v": struct.unpack_from(">H", p, 99)[0] / 10.0,
        "grid_a": struct.unpack_from(">H", p, 101)[0] / 10.0,
        "grid_hz": struct.unpack_from(">H", p, 117)[0] / 100.0,
        "bus_v": struct.unpack_from(">H", p, 119)[0] / 10.0,
        "temp1_c": struct.unpack_from(">h", p, 129)[0] / 10.0,
        "temp2_c": struct.unpack_from(">h", p, 131)[0] / 10.0,
    }

def handle_client(conn: socket.socket, addr):
    print(f"[+] Stick connected from {addr}")
    conn.settimeout(180)
    model = "HPS-3000DL"
    try:
        with conn:
            while True:
                hdr = recv_exact(conn, 11)
                if hdr[0:2] != b"\xa5\x06":
                    print(f"[!] Unexpected header from {addr}: {hdr.hex()}")
                    break
                cmd, seq = hdr[3:5], hdr[8:9]
                length = struct.unpack(">H", hdr[9:11])[0]
                payload = recv_exact(conn, length) if length else b""

                if cmd == b"\x01\x00":
                    now = datetime.datetime.now()
                    tbytes = bytes([now.year % 100, now.month, now.day, now.hour, now.minute, now.second]) + b"\x00\x28"
                    conn.sendall(make_reply(b"\x01\x01", seq, tbytes))
                    print(f"[*] {addr} Login OK")
                elif cmd == b"\x07\x00":
                    conn.sendall(make_reply(b"\x07\x01", seq))
                elif cmd == b"\x02\x01":
                    conn.sendall(make_reply(b"\x02\x01", seq, payload[:16].split(b"\x00", 1)[0]))
                elif cmd == b"\x02\x02":
                    inv_sn = payload[:26].split(b"\x00", 1)[0]
                    model = payload[46:62].decode("ascii", errors="ignore").strip() or model
                    conn.sendall(make_reply(b"\x02\x03", seq, inv_sn))
                    try:
                        ensure_discovery(inv_sn.decode(errors="replace"), model)
                    except Exception as e:
                        print(f"[!] MQTT discovery error: {e}")
                elif cmd == b"\x04\x04":
                    conn.sendall(make_reply(b"\x04\x01", seq, payload[6:22].split(b"\x00", 1)[0]))
                elif cmd == b"\x09\x02":
                    print(f"[RAW 0902] len={len(payload)} hex={payload.hex()}")
                    data = decode_telemetry(payload)
                    conn.sendall(make_reply(b"\x09\x01", seq))
                    try:
                        ensure_discovery(data["sn"], model)
                        mqtt_publish_batch([(f"hypontech/{data['sn']}/state", json.dumps(data), True)])
                        print(f"[>] Published: {data}")
                    except Exception as e:
                        print(f"[!] MQTT publish error: {e}")
                elif cmd == b"\x0a\x02":
                    conn.sendall(make_reply(b"\x0a\x01", seq))
                    print(f"[*] {addr} Acked inverter config (0a02 -> 0a01)")
                elif cmd == b"\x00\x00":
                    conn.sendall(b"\xa5\x02\x02\x00\x00\x00\x00\x00\x00\x00\x00")
                    print(f"[.] {addr} Keepalive seq={seq.hex()}")
                else:
                    print(f"[?] {addr} Unknown cmd={cmd.hex()} len={length} payload={payload.hex()}")
    except Exception as e:
        print(f"[-] Session {addr} ended: {e}")

def main():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as srv:
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((LISTEN_HOST, LISTEN_PORT))
        srv.listen(16)
        print(f"Listening on {LISTEN_HOST}:{LISTEN_PORT} -> MQTT {MQTT_HOST}:{MQTT_PORT}")
        while True:
            conn, addr = srv.accept()
            threading.Thread(target=handle_client, args=(conn, addr), daemon=True).start()

if __name__ == "__main__":
    main()