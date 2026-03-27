# Correlation Explorer — How the Graphs Are Made

## Data Sources

Each `.dat` file contains per-frame sensor readings (Fy, Fz1-Fz4, Pad RPM, IR Temperature, etc.). These are sampled at the file's recording rate (Hz). All computed values use only the **analysis interval** (default 7–57 s) of each file.

### User-Provided Values (entered in File Attributes panel)

| Field | Used In |
|-------|---------|
| **Pressure PSI** | Grouping — each line on the graph connects files at the same pressure setpoint |
| **Polish Time** (min) | Removal Rate = Removal / Polish Time |
| **Removal** (Å) | Removal Rate, Preston's Plot, Arrhenius Plot |
| **WIWNU** (%) | WIWNU vs P·V graph |

### Auto-Computed Values (from sensor data)

All computed per-frame, then averaged over the analysis interval.

| Value | Formula | Unit |
|-------|---------|------|
| **Fz Total** | (Fz1 + Fz2 + Fz3 + Fz4) − baseline_Fz | lbf |
| **Fy Total** | Fy − baseline_Fy | lbf |
| **Fz (N)** | Fz Total × 4.44822 | N |
| **Area** | π × (wafer_diameter / 2)² | m² |
| **Pressure** | Fz (N) / Area | Pa |
| **Pad Rotation Rate** | Pad RPM × 2π / 60 | rad/s |
| **Sliding Velocity** | Pad Rotation Rate × pad_to_wafer_ratio | m/s |
| **COF** | Fy Total / Fz Total | dimensionless |
| **P·V** | Pressure × Sliding Velocity | Pa·m/s |
| **Sommerfeld** | Sliding Velocity / Pressure | m/(Pa·s) |
| **Mean Temp** | mean of IR Temperature in interval | °C |
| **Removal Rate** | Removal / Polish Time | Å/min |

Default constants: `wafer_diameter = 0.3 m`, `pad_to_wafer_ratio = 0.225`, `pound_force = 4.44822 N/lbf`.

## The 6 Graphs

Each graph shows one data point per file. Points are connected by lines within each **Pressure PSI** group (sorted by X value), so you can see the trend as velocity changes at a fixed pressure.

### 1. Stribeck Curve
- **X:** Pseudo-Sommerfeld number (m/Pa·s)
- **Y:** Mean COF
- Shows how friction varies with the velocity-to-pressure ratio. Classic tribology relationship.

### 2. COF vs P·V
- **X:** P·V (Pa·m/s)
- **Y:** Mean COF
- Friction response to the pressure-velocity product.

### 3. Mean Pad Temp vs P·V
- **X:** P·V (Pa·m/s)
- **Y:** Mean Pad Temp (°C)
- Higher P·V generates more frictional heat. Should trend upward.

### 4. Arrhenius Plot
- **X:** 1/T (1/K) — where T = Mean Temp + 273.15
- **Y:** ln(Removal Rate)
- Tests whether removal follows Arrhenius kinetics (thermally activated process). A linear trend indicates an activation energy relationship.

### 5. Preston's Plot
- **X:** P·V (Pa·m/s)
- **Y:** Mean Removal Rate (Å/min)
- Preston's equation: RR = k_p × P × V. A linear trend validates the Preston model.

### 6. WIWNU vs P·V
- **X:** P·V (Pa·m/s)
- **Y:** WIWNU (%)
- Shows how within-wafer non-uniformity changes with polishing aggressiveness.
