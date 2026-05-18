
import asyncio
import json
import math
import time
import websockets
from SimConnect import SimConnect, AircraftRequests

async def ws_handler(websocket):
    # Handle ngrok browser warning header
    if websocket.request_headers.get("ngrok-skip-browser-warning") is None:
        pass  # ngrok handles this automatically for WSS
# ─────────────────────────────────────────────────────────────────
#  CONFIGURATION
# ─────────────────────────────────────────────────────────────────

WS_HOST      = "localhost"
WS_PORT      = 8765

# Your aircraft max fuel in gallons — A320 typical max ~5200 gal
FUEL_MAX_GAL = 5200

# How often to push data to the UI (seconds)
PUSH_INTERVAL = 1.0

# ─────────────────────────────────────────────────────────────────
#  A320 SPEED TABLE  (Airbus FCOM, weights in kg)
# ─────────────────────────────────────────────────────────────────

SPEED_TABLE = {
    #  GW_KG : (F1,  F2,  F3, Vref)
    55000:     (178, 164, 150, 133),
    60000:     (185, 170, 155, 138),
    65000:     (192, 176, 161, 143),
    70000:     (199, 182, 167, 148),
    75000:     (205, 188, 172, 152),
}


def get_a320_speeds(gw_kg: float) -> dict:
    """Interpolate A320 approach speeds from gross weight."""
    weights = sorted(SPEED_TABLE.keys())
    gw_kg   = max(weights[0], min(weights[-1], gw_kg))

    for i in range(len(weights) - 1):
        lo, hi = weights[i], weights[i + 1]
        if lo <= gw_kg <= hi:
            r = (gw_kg - lo) / (hi - lo)
            f1, f2, f3, vr = [
                round(SPEED_TABLE[lo][j] + r * (SPEED_TABLE[hi][j] - SPEED_TABLE[lo][j]))
                for j in range(4)
            ]
            return {"f1": f1, "f2": f2, "f3": f3, "vref": vr, "vapp": vr + 5}

    vals = SPEED_TABLE[weights[-1]]
    return {"f1": vals[0], "f2": vals[1], "f3": vals[2],
            "vref": vals[3], "vapp": vals[3] + 5}

# ─────────────────────────────────────────────────────────────────
#  TOD CALCULATION
# ─────────────────────────────────────────────────────────────────

def calc_tod(current_alt: float, target_alt: float,
             ground_speed_kts: float, gradient_deg: float = 3.0) -> dict:
    """
    Returns TOD distance (NM) and ETA (minutes).
    Formula: distance (NM) = alt_delta / (tan(gradient°) × 6076.115)
    """
    alt_delta = max(0.0, current_alt - target_alt)
    if alt_delta == 0 or ground_speed_kts <= 0:
        return {"tod_nm": 0.0, "eta_min": 0.0, "alt_delta": 0.0}

    grad_rad = math.radians(gradient_deg)
    tod_nm   = alt_delta / (math.tan(grad_rad) * 6076.115)
    eta_min  = (tod_nm / ground_speed_kts) * 60

    return {
        "tod_nm":    round(tod_nm, 2),
        "eta_min":   round(eta_min, 2),
        "alt_delta": round(alt_delta, 0),
    }

# ─────────────────────────────────────────────────────────────────
#  SIMCONNECT — READ AIRCRAFT DATA
# ─────────────────────────────────────────────────────────────────

def connect_simconnect():
    """Keep trying to connect until MSFS is running."""
    while True:
        try:
            print("[SimConnect] Connecting to MSFS...")
            sc = SimConnect()
            aq = AircraftRequests(sc, _time=2000)
            print("[SimConnect] Connected ✓")
            return sc, aq
        except Exception as e:
            print(f"[SimConnect] Not ready ({e}) — retrying in 5s...")
            time.sleep(5)


def read_aircraft_data(aq: AircraftRequests) -> dict:
    """Read all required SimVars and return a clean dict for the UI."""
    try:
        alt        = aq.get("PLANE_ALTITUDE")             or 0.0   # feet MSL
        spd_ms     = aq.get("GPS_GROUND_SPEED")           or 0.0   # m/s → convert to kts
        vs         = aq.get("VERTICAL_SPEED")             or 0.0   # ft/min
        hdg        = aq.get("PLANE_HEADING_DEGREES_TRUE") or 0.0   # degrees
        lat        = aq.get("GPS_POSITION_LAT")           or 0.0   # decimal degrees
        lon        = aq.get("GPS_POSITION_LON")           or 0.0   # decimal degrees
        fuel_qty   = aq.get("FUEL_TOTAL_QUANTITY")        or 0.0   # gallons
        fuel_flow  = aq.get("ENG_FUEL_FLOW_GPH:1")        or 0.0   # gal/hr per engine
        gw_lbs     = aq.get("TOTAL_WEIGHT")               or 130000 # lbs → convert to kg
        oat        = aq.get("AMBIENT_TEMPERATURE")        or 0.0   # °C

        spd_kts    = spd_ms * 1.94384        # m/s → knots
        gw_kg      = gw_lbs * 0.453592       # lbs → kg
        total_flow = fuel_flow * 2           # both engines (symmetric assumption)
        fuel_qty_kg = fuel_qty * 3.04

        return {
            "alt":      round(float(alt),      0),
            "spd":      round(float(spd_kts),  1),
            "vs":       round(float(vs),       0),
            "hdg":      round(float(hdg),      1),
            "lat":      round(float(lat),      4),
            "lon":      round(float(lon),      4),
            "fuelQty":  round(float(fuel_qty_kg), 0),
            "fuelMax":  FUEL_MAX_GAL,
            "fuelFlow": round(float(total_flow), 0),
            "gw_kg":    round(float(gw_kg),    0),
            "oat":      round(float(oat),      0),
        }
    except Exception as e:
        print(f"[SimConnect] Read error: {e}")
        return {}

# ─────────────────────────────────────────────────────────────────
#  SIMCONNECT — EXECUTE DESCENT
# ─────────────────────────────────────────────────────────────────

def execute_descent(sc: SimConnect, aq: AircraftRequests,
                    target_alt: int, vs: int, spd: int, variant: str):
    """
    Send SimConnect events to initiate a managed descent.
    Sequence:
      1. Set FCU altitude to target
      2. Set managed speed (Flap 1 speed)
      3. Disengage altitude hold → aircraft pitches down
      4. Set and engage VS mode at requested rate
    """
    print(f"[Descent] → ALT:{target_alt}ft  VS:{vs}fpm  SPD:{spd}kts  [{variant.upper()}]")

    try:
        # Step 1 — set target altitude in autopilot
        aq.set("AUTOPILOT_ALTITUDE_LOCK_VAR", target_alt)
        time.sleep(0.2)

        # Step 2 — set managed descent speed
        aq.set("AUTOPILOT_AIRSPEED_HOLD_VAR", spd)
        time.sleep(0.2)

        # Step 3 — release altitude hold (aircraft begins descent)
        sc.send_event("AP_ALT_HOLD_OFF")
        time.sleep(0.15)

        # Step 4 — engage VS at requested rate
        sc.send_event("AP_VS_VAR_SET_ENGLISH", abs(vs))
        time.sleep(0.1)
        sc.send_event("AP_VS_HOLD_ON")

        print(f"[Descent] Events sent ✓  ({variant.upper()})")

        # FBW / Fenix note: standard SimConnect events work for basic AP.
        # For full managed modes (OP DES / VNAV) on FBW install the
        # Mobiflight WASM module to access LVARs directly.

    except Exception as e:
        print(f"[Descent] SimConnect error: {e}")

# ─────────────────────────────────────────────────────────────────
#  SHARED STATE
# ─────────────────────────────────────────────────────────────────

state = {
    "target_alt": 10000,
    "gradient":   3.0,
    "variant":    "default",
    "last_ac":    {},
    "sc":         None,
    "aq":         None,
}

# ─────────────────────────────────────────────────────────────────
#  WEBSOCKET — PUSH LIVE DATA TO UI
# ─────────────────────────────────────────────────────────────────

async def push_data(websocket):
    """Push aircraft SimVar data to the UI every PUSH_INTERVAL seconds."""
    while True:
        try:
            aq = state.get("aq")
            if aq:
                ac = read_aircraft_data(aq)
                if ac:
                    state["last_ac"] = ac
                    await websocket.send(json.dumps(ac))
            await asyncio.sleep(PUSH_INTERVAL)

        except websockets.exceptions.ConnectionClosed:
            break
        except Exception as e:
            print(f"[Push] Error: {e}")
            await asyncio.sleep(2)

# ─────────────────────────────────────────────────────────────────
#  WEBSOCKET — HANDLE INCOMING COMMANDS FROM UI
# ─────────────────────────────────────────────────────────────────

async def ws_handler(websocket):
    """Handle one connected browser client."""
    client = websocket.remote_address
    print(f"[WS] Client connected: {client}")

    # Start pushing data in background for this client
    push_task = asyncio.create_task(push_data(websocket))

    try:
        async for raw in websocket:
            try:
                msg = json.loads(raw)
                cmd = msg.get("command", "")

                # ── DESCEND ──────────────────────────────────────
                if cmd == "DESCEND":
                    target_alt = int(msg.get("target_alt", 10000))
                    vs         = int(msg.get("vs",         -1800))
                    spd        = int(msg.get("spd",        210))
                    variant    = msg.get("variant",        "default")
                    gw_kg      = float(msg.get("gw_kg",   65000))

                    state["target_alt"] = target_alt
                    state["variant"]    = variant

                    sc = state["sc"]
                    aq = state["aq"]

                    if sc and aq:
                        # Run blocking SimConnect calls in a thread
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(
                            None, execute_descent,
                            sc, aq, target_alt, vs, spd, variant
                        )
                        speeds = get_a320_speeds(gw_kg)
                        await websocket.send(json.dumps({
                            "status":     "DESCEND_CONFIRMED",
                            "target_alt": target_alt,
                            "vs":         vs,
                            "speeds":     speeds,
                        }))
                        print(f"[WS] Descent confirmed → {target_alt}ft / {vs}fpm")
                    else:
                        await websocket.send(json.dumps({
                            "status":  "DESCEND_CONFIRMED",
                            "target_alt": target_alt,
                            "vs":      vs,
                            "note":    "SimConnect not connected — events not sent"
                        }))
                        print("[WS] Descent ACK (SimConnect not connected)")

                # ── CONFIG UPDATE ─────────────────────────────────
                elif cmd == "CONFIG":
                    state["target_alt"] = int(msg.get("target_alt",   state["target_alt"]))
                    state["gradient"]   = float(msg.get("gradient",   state["gradient"]))
                    print(f"[WS] Config → ALT={state['target_alt']}  GRAD={state['gradient']}")

                else:
                    print(f"[WS] Unknown command: {cmd}")

            except json.JSONDecodeError:
                print("[WS] Received invalid JSON")

    except websockets.exceptions.ConnectionClosed:
        print(f"[WS] Client disconnected: {client}")
    finally:
        push_task.cancel()

# ─────────────────────────────────────────────────────────────────
#  SIMCONNECT RECONNECT LOOP (background)
# ─────────────────────────────────────────────────────────────────

async def simconnect_loop():
    """Maintain a persistent SimConnect connection, auto-reconnect on drop."""
    while True:
        try:
            loop = asyncio.get_event_loop()
            sc, aq = await loop.run_in_executor(None, connect_simconnect)
            state["sc"] = sc
            state["aq"] = aq

            # Health-check every 5 seconds
            while True:
                await asyncio.sleep(5)
                try:
                    _ = aq.get("PLANE_ALTITUDE")   # lightweight ping
                except Exception:
                    print("[SimConnect] Connection lost — reconnecting...")
                    state["sc"] = None
                    state["aq"] = None
                    break

        except Exception as e:
            print(f"[SimConnect] Fatal error: {e} — retry in 10s")
            await asyncio.sleep(10)

# ─────────────────────────────────────────────────────────────────
#  MAIN
# ─────────────────────────────────────────────────────────────────

async def main():
    print("=" * 55)
    print("  A320 TOD CALCULATOR — SimConnect Bridge")
    print(f"  WebSocket  :  ws://{WS_HOST}:{WS_PORT}")
    print(f"  Fuel max   :  {FUEL_MAX_GAL} gal")
    print(f"  Push rate  :  {PUSH_INTERVAL}s")
    print("=" * 55)

    sim_task = asyncio.create_task(simconnect_loop())

    async with websockets.serve(ws_handler, WS_HOST, WS_PORT):
        print(f"\n[WS] Server ready — open tod_calculator.html and click CONNECT WS\n")
        await asyncio.gather(sim_task)


if __name__ == "__main__":
    asyncio.run(main())
