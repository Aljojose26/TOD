# ✈️ A320 TOD Calculator — MSFS SimConnect

A real-time **Top of Descent calculator** for the Airbus A320 in Microsoft Flight Simulator 2020/2024. Connects directly to MSFS via SimConnect, displays live aircraft data, calculates your TOD distance and ETA, shows weight-based A320 speed schedules, and can initiate an autopilot descent with a single button click.

![A320 TOD Calculator](https://img.shields.io/badge/MSFS-2020%20%2F%202024-blue?style=flat-square) ![Python](https://img.shields.io/badge/Python-3.10%2B-yellow?style=flat-square) ![SimConnect](https://img.shields.io/badge/SimConnect-SDK-orange?style=flat-square) ![License](https://img.shields.io/badge/License-MIT-green?style=flat-square)

---

## 📸 Features

- 🛫 **Live Aircraft Data** — Altitude, ground speed, vertical speed, heading, GPS position, OAT, gross weight
- ⛽ **Fuel Status** — Total fuel, fuel %, fuel flow, estimated endurance with visual progress bar
- 📐 **TOD Calculation** — Real-time distance (NM) and ETA to top of descent using standard 3° formula
- 🎯 **A320 Speed Schedule** — Auto-calculated Flap 1/2/3, Vref and Vapp based on live gross weight
- ▼ **One-Click Descent** — Sends SimConnect events to set AP altitude, engage VS mode and managed speed
- 🎮 **Multi-Variant Support** — Works with Default MSFS A320, FlyByWire A32NX, and Fenix A320
- 📊 **Configurable Descent** — Choose gradient (2.5° to 5.0°) and VS rate (−1200 to −2800 fpm)
- 🟢 **Live Event Log** — Real-time WebSocket command log in the UI
- 🖥️ **Demo Mode** — Fully functional without MSFS for testing and UI preview

---

## 🗂️ Project Structure

```
a320-tod-calculator/
├── server.py             ← SimConnect WebSocket bridge (Python)
├── tod_calculator.html   ← Browser UI
└── README.md
```

---

## ⚙️ Requirements

| Requirement | Version |
|---|---|
| Microsoft Flight Simulator | 2020 or 2024 |
| Python | 3.10 or newer |
| SimConnect SDK | Included with MSFS Developer Mode |
| Browser | Chrome or Edge (for WebSocket support) |

---

## 🚀 Installation

### 1. Clone the Repository

```bash
git clone https://github.com/YOURUSERNAME/a320-tod-calculator.git
cd a320-tod-calculator
```

### 2. Install Python Dependencies

```bash
pip install SimConnect websockets
```

### 3. Enable MSFS Developer Mode

In MSFS go to:
```
Options → General → Developer Mode → ON
```
This installs the SimConnect SDK automatically.

---

## ▶️ Usage

Always launch in this order:

**1. Launch MSFS** and load into any flight

**2. Start the server:**
```bash
python server.py
```

You should see:
```
=======================================================
  A320 TOD CALCULATOR — SimConnect Bridge
  WebSocket  :  ws://localhost:8765
  Fuel max   :  5200 gal
  Push rate  :  1.0s
=======================================================
[SimConnect] Connecting to MSFS...
[SimConnect] Connected ✓
[WS] Server ready — open tod_calculator.html and click CONNECT WS
```

**3. Open the UI:**

Open `tod_calculator.html` in Chrome or Edge.

**4. Click `⟳ CONNECT WS`** in the UI — the status dot turns green and live data starts flowing.

---

## 🛠️ Configuration

Open `server.py` and edit the configuration block at the top:

```python
WS_HOST      = "localhost"   # Change to "0.0.0.0" for network access
WS_PORT      = 8765
FUEL_MAX_GAL = 5200          # A320 max fuel — adjust per airframe
PUSH_INTERVAL = 1.0          # Data push rate in seconds
```

---

## 📐 TOD Formula

```
Distance (NM) = Alt Difference (ft) ÷ (tan(gradient°) × 6076.115)
ETA (min)     = TOD Distance ÷ Ground Speed × 60
```

**Simplified at 3°:**
```
Distance (NM) ≈ Alt Difference (ft) ÷ 318.5
```

---

## 🎯 A320 Speed Schedule

Speeds are interpolated from the Airbus FCOM table based on live gross weight:

| Gross Weight | Flap 1 | Flap 2 | Flap 3 | Vref | Vapp |
|---|---|---|---|---|---|
| 55,000 kg | 178 kts | 164 kts | 150 kts | 133 kts | 138 kts |
| 60,000 kg | 185 kts | 170 kts | 155 kts | 138 kts | 143 kts |
| 65,000 kg | 192 kts | 176 kts | 161 kts | 143 kts | 148 kts |
| 70,000 kg | 199 kts | 182 kts | 167 kts | 148 kts | 153 kts |
| 75,000 kg | 205 kts | 188 kts | 172 kts | 152 kts | 157 kts |

**Vapp = Vref + 5 kts** (standard calm wind correction)

---

## 🚦 Flap Gate Altitudes

| Altitude | Action |
|---|---|
| FL100 | Flap 1 + Slats — reduce below 250 kts |
| 4,000 ft | Flap 2 |
| 3,000 ft | Flap 3 + Gear Down |
| 2,000 ft | FULL — establish Vapp |

---

## 🎮 A320 Variant Support

| Variant | Descent Method | Notes |
|---|---|---|
| Default MSFS | Standard SimConnect events | Full support |
| FlyByWire A32NX | SimConnect + LVAR | Install Mobiflight WASM for full managed modes |
| Fenix A320 | SimConnect events | Basic AP control supported |

---

## 📡 SimConnect Variables Used

| SimVar | Description |
|---|---|
| `PLANE_ALTITUDE` | Current altitude in feet MSL |
| `GPS_GROUND_SPEED` | Ground speed in m/s (converted to knots) |
| `VERTICAL_SPEED` | Vertical speed in ft/min |
| `PLANE_HEADING_DEGREES_TRUE` | True heading in degrees |
| `GPS_POSITION_LAT / LON` | GPS coordinates in decimal degrees |
| `FUEL_TOTAL_QUANTITY` | Total fuel in gallons |
| `ENG_FUEL_FLOW_GPH:1` | Engine 1 fuel flow in gal/hr |
| `TOTAL_WEIGHT` | Gross weight in lbs (converted to kg) |
| `AMBIENT_TEMPERATURE` | Outside air temperature in °C |

---

## 🔌 Architecture

```
MSFS 2020/2024
      ↕ SimConnect SDK
  server.py  (Python WebSocket server)
      ↕ ws://localhost:8765
  tod_calculator.html  (Browser UI)
```

---

## ❗ Troubleshooting

| Problem | Cause | Fix |
|---|---|---|
| `SimConnect not connected` | MSFS not running or not in a flight | Launch MSFS and load a flight first |
| `WS: ERROR` in UI | server.py not running | Check terminal — run `python server.py` |
| Descent button does nothing | Autopilot not engaged | Engage AP manually in sim first |
| Wrong fuel percentage | Incorrect `FUEL_MAX_GAL` | Update value in `server.py` for your airframe |
| FBW descent not fully managed | FBW uses LVARs | Install Mobiflight WASM module |

---

## 🗺️ Roadmap

- [ ] Wind correction for Vapp calculation
- [ ] Multi-engine fuel flow support
- [ ] METAR integration for destination weather
- [ ] Flight log / landing report
- [ ] Mobile responsive layout

---

## 📄 License

MIT License — free to use, modify and distribute.

---

## 🙏 Credits

- [SimConnect Python Library](https://github.com/odwdinc/Python-SimConnect)
- [Airbus A320 FCOM](https://www.airbus.com) — speed schedule reference
- [Microsoft Flight Simulator SDK](https://docs.flightsimulator.com)

---

<div align="center">
Built for flight simmers who want real procedures, not guesswork.
</div>
