# Prediction Models

This document explains how the app predicts **Removal** (how much material was
polished off a wafer, measured in Angstroms) from experiment settings.  Two
models are available: **Ridge Regression** and **Random Forest**.  Both share
the same preprocessing steps, then diverge in how they learn.

---

## 1  Data Preprocessing

### What goes in

Every imported file that has a Removal value greater than zero becomes one row.
Files without Removal data are skipped.  The app requires at least **5** such
rows before it will train a model.

A single row looks like this (example with 4 files):

| File        | Pressure PSI | Polish Time | Wafer | Pad    | Slurry | Conditioner | Removal |
|-------------|-------------|-------------|-------|--------|--------|-------------|---------|
| run_01.dat  | 3.0         | 2.0         | SiC   | IC1000 | CeO2   | DIA         | 3200    |
| run_02.dat  | 5.0         | 4.0         | Si3N4 | IC1000 | Al2O3  | CB          | 5800    |
| run_03.dat  | 3.0         | 3.0         | SiC   | FS-C   | CeO2   | DIA         | 2400    |
| run_04.dat  | 5.0         | 2.0         | Si3N4 | FS-C   | Al2O3  | CB          | 4100    |

**Numerical features:** `Pressure PSI`, `Polish Time`
**Categorical features:** `Wafer`, `Pad`, `Slurry`, `Conditioner`
**Target (what we predict):** `Removal`

Any blank categorical value is replaced with `"Unknown"`.

### Step A — Interaction term (Ridge only)

For Ridge Regression, a new column is added:

```
P_x_T = Pressure PSI × Polish Time
```

| File       | Pressure PSI | Polish Time | P_x_T |
|------------|-------------|-------------|-------|
| run_01.dat | 3.0         | 2.0         | 6.0   |
| run_02.dat | 5.0         | 4.0         | 20.0  |
| run_03.dat | 3.0         | 3.0         | 9.0   |
| run_04.dat | 5.0         | 2.0         | 10.0  |

This lets Ridge capture the combined effect of pressure and time (higher
pressure *and* longer time removes more material).  Random Forest discovers
interactions on its own, so it skips this step.

### Step B — Scale numerical features

**StandardScaler** transforms each numerical column so its mean is 0 and its
standard deviation is 1.

Formula for each value:

```
scaled = (value - mean) / std
```

Example for `Pressure PSI` (values: 3, 5, 3, 5):
- mean = 4.0, std = 1.0
- 3.0 → (3 − 4) / 1 = **−1.0**
- 5.0 → (5 − 4) / 1 = **+1.0**

Example for `Polish Time` (values: 2, 4, 3, 2):
- mean = 2.75, std ≈ 0.83
- 2.0 → (2 − 2.75) / 0.83 ≈ **−0.90**
- 4.0 → (4 − 2.75) / 0.83 ≈ **+1.51**

Without scaling, a feature measured in large numbers (like Removal ~3000)
would dominate a feature measured in small numbers (like Pressure ~4).

### Step C — Encode categorical features

**OneHotEncoder** turns each category into binary (0/1) columns.

| File       | Wafer_SiC | Wafer_Si3N4 | Pad_IC1000 | Pad_FS-C | Slurry_CeO2 | Slurry_Al2O3 | Cond_DIA | Cond_CB |
|------------|-----------|-------------|------------|----------|-------------|-------------|----------|---------|
| run_01.dat | 1         | 0           | 1          | 0        | 1           | 0           | 1        | 0       |
| run_02.dat | 0         | 1           | 1          | 0        | 0           | 1           | 0        | 1       |
| run_03.dat | 1         | 0           | 0          | 1        | 1           | 0           | 1        | 0       |
| run_04.dat | 0         | 1           | 0          | 1        | 0           | 1           | 0        | 1       |

If a new prediction uses a category the model has never seen, all its
one-hot columns become 0 (the model treats it as "none of the above").

### Full pipeline

```
Raw table
  │
  ├─[Ridge only]──► Add P_x_T column
  │
  ├─► StandardScaler on numerical columns ──► scaled numbers
  │
  └─► OneHotEncoder on categorical columns ──► binary columns
                                                    │
                                          ┌─────────┴─────────┐
                                          │  Final feature     │
                                          │  matrix X          │
                                          │                    │
                                          │  Rows = files      │
                                          │  Cols = scaled     │
                                          │   numerics + one-  │
                                          │   hot categoricals │
                                          └────────────────────┘
```

---

## 2  Ridge Regression

### Core idea

Ridge Regression fits a straight-line equation (a weighted sum) to predict
Removal from all the features:

```
Removal = w₁·(Pressure) + w₂·(Time) + w₃·(P_x_T)
        + w₄·(Wafer_SiC) + w₅·(Wafer_Si3N4) + ...
        + bias
```

Each weight (w) tells you how much that feature pushes the prediction up or
down.  The model finds the weights that minimize prediction error.

### Example with numbers

Suppose the model learns these weights (on scaled data):

| Feature       | Weight (w) |
|---------------|-----------|
| Pressure PSI  | +820      |
| Polish Time   | +640      |
| P_x_T         | +310      |
| Wafer_SiC     | −450      |
| Wafer_Si3N4   | +450      |
| Pad_IC1000    | +200      |
| Pad_FS-C      | −200      |
| Slurry_CeO2   | −180      |
| Slurry_Al2O3   | +180      |
| Cond_DIA      | −100      |
| Cond_CB       | +100      |
| bias          | 3875      |

For run_02 (Pressure=5, Time=4, Si3N4, IC1000, Al2O3, CB):
- Scaled Pressure = +1.0, Scaled Time = +1.51, Scaled P_x_T ≈ +1.42

```
Predicted = 820×(1.0) + 640×(1.51) + 310×(1.42)
          + 450 + 200 + 180 + 100 + 3875
          = 820 + 966 + 440 + 450 + 200 + 180 + 100 + 3875
          = 7031 Å
```

**Interpreting weights:**
- Positive weight → feature increases Removal (e.g., higher Pressure → more removal)
- Negative weight → feature decreases Removal (e.g., SiC wafer → less removal)
- Larger absolute value → stronger effect

### The Ridge penalty

Plain linear regression can overfit when there are many features (especially
one-hot columns).  Ridge adds a penalty that shrinks weights toward zero:

```
Loss = Σ(actual - predicted)² + α × Σ(w²)
       ─────────────────────    ──────────
       prediction error          penalty
```

- **α (alpha)** controls the penalty strength.
  - α = 0 → no penalty, same as ordinary linear regression
  - α = 1000 → heavy penalty, all weights squeezed toward zero
- The penalty discourages any single weight from growing too large, which
  prevents overfitting.

### How alpha is chosen

The app uses **RidgeCV**, which tests 50 alpha values logarithmically
spaced from 0.001 to 1000:

```
0.001, 0.0014, 0.002, ..., 1.0, ..., 100, ..., 1000
```

For each alpha, RidgeCV uses **leave-one-out cross-validation**: it hides one
row, trains on the rest, predicts the hidden row, then repeats for every row.
The alpha with the lowest average error wins.

---

## 3  Random Forest

### Core idea

A Random Forest is a committee of 100 decision trees.  Each tree learns its
own set of if/then rules, and the final prediction is the **average** of all
100 trees' answers.

### How one tree decides

Each tree is trained on a random sample of the data (some rows may repeat,
others are left out — this is called **bootstrapping**).  At every split, the
tree picks the feature and threshold that best separates high-Removal files
from low-Removal ones.

Example mini-tree:

```
                    ┌─────────────────────────┐
                    │  Pressure PSI ≥ 4.0 ?   │
                    └────────┬────────┬────────┘
                        yes  │        │  no
                    ┌────────▼──┐  ┌──▼────────┐
                    │ Time ≥ 3? │  │ Predict:  │
                    │           │  │ 2800 Å    │
                    └──┬─────┬──┘  └───────────┘
                  yes  │     │  no
               ┌───────▼┐  ┌▼───────┐
               │Predict: │  │Predict:│
               │ 5800 Å  │  │ 4100 Å │
               └─────────┘  └────────┘
```

For run_02 (Pressure=5, Time=4):
1. Pressure 5 ≥ 4? → **yes**, go left
2. Time 4 ≥ 3? → **yes**, go left
3. Predict **5800 Å**

### How 100 trees vote

Each tree sees slightly different data and features, so they make slightly
different predictions.  The forest averages them:

```
Tree  1 → 5600 Å
Tree  2 → 6100 Å
Tree  3 → 5400 Å
  ...
Tree 100 → 5900 Å
─────────────────
Average  → 5742 Å   ← final prediction
```

### Why randomness helps

| What is randomized        | Why it helps                              |
|---------------------------|-------------------------------------------|
| Each tree trains on a random subset of rows (bootstrap) | Prevents all trees from memorizing the same noise |
| Each split considers a random subset of features | Prevents one dominant feature from appearing in every tree |

If every tree were identical, averaging wouldn't help.  Diversity among trees
is what makes the forest more accurate than any single tree.

### Hyperparameters

| Setting           | Value | Meaning                                    |
|-------------------|-------|--------------------------------------------|
| n_estimators      | 100   | Number of trees in the forest              |
| min_samples_leaf  | 3     | Every leaf must contain at least 3 files   |
| random_state      | 42    | Fixed seed so results are reproducible     |

`min_samples_leaf = 3` prevents a tree from creating a leaf for just one file,
which would be overfitting.

### Prediction uncertainty

For Random Forest, uncertainty is the **standard deviation** across the
100 individual tree predictions:

```
Tree predictions: 5600, 6100, 5400, ..., 5900
Mean  = 5742 Å  (the prediction)
Std   =  280 Å  (the uncertainty)
→ reported as: 5742 ± 280 Å
```

A narrow spread means the trees agree (high confidence).  A wide spread means
they disagree (low confidence — the input may be unusual).  Because each new
input produces a different set of 100 tree predictions, the uncertainty
**changes per prediction** — unusual inputs cause more disagreement among
trees, yielding a wider ± range.

For Ridge Regression, uncertainty is the **RMSE from cross-validation** — the
average prediction error measured during training.  Because Ridge is a single
equation (not an ensemble), there is no per-prediction disagreement to
measure.  The same RMSE applies to every prediction regardless of input, so
the ± value is **always the same**.  This means Ridge cannot warn you when a
particular input is unusual.

---

## 4  Diagnostic Graphs

After training, the app shows 4 graphs.  All are computed using **5-fold
cross-validation**: the data is split into 5 groups, and each group takes a
turn being the test set while the other 4 groups train the model.  This means
every file gets a prediction made *without* the model having seen it.

### Residuals

A **residual** is the gap between what actually happened and what the model
predicted.  It answers: "how far off was the model for this file?"

```
Residual = Actual − Predicted
```

- **Positive residual** → the model **under-predicted** (actual was higher)
- **Negative residual** → the model **over-predicted** (actual was lower)
- **Zero** → perfect prediction

A good model has small residuals scattered randomly around zero.  If residuals
show a pattern (e.g., always positive for high-removal files), the model has a
systematic blind spot.

### Shared example data

These 5 files will be used in all graph examples below:

| File   | Actual (Å) | Predicted (Å) | Residual (Å) |
|--------|------------|---------------|---------------|
| run_01 | 3200       | 3000          | +200          |
| run_02 | 5800       | 6100          | −300          |
| run_03 | 2400       | 2500          | −100          |
| run_04 | 4100       | 3900          | +200          |
| run_05 | 4500       | 4600          | −100          |

For example, run_01 had 3200 Å actual removal but the model predicted 3000 Å,
so the residual is 3200 − 3000 = +200 Å (the model was 200 Å too low).

### Graph 1: Predicted vs Actual

```
  Predicted (Å)
  6500 ┤
       │          ╱
  6000 ┤        ·╱          · = run_02 (6100 vs 5800)
       │       ╱
  5000 ┤     ╱
       │    ╱  ·                · = run_05 (4600 vs 4500)
  4000 ┤  ╱·                    · = run_04 (3900 vs 4100)
       │╱
  3000 ┤·                       · = run_01 (3000 vs 3200)
       ·
  2500 ┤                        · = run_03 (2500 vs 2400)
       └──┬──────┬──────┬──────┬──
        2000   3000   4000   5000   6000
                        Actual (Å)
```

- **X-axis:** Actual Removal
- **Y-axis:** Predicted Removal
- **Dashed diagonal:** The perfect-prediction line (predicted = actual)
- **Point color:** Darker red = larger |residual|

**What to look for:**
- Good: Points cluster tightly around the diagonal
- Bad: Points scattered far from the diagonal, or systematic drift to one side

### Graph 2: Feature Importance

This graph looks different depending on the model.

**Ridge Regression** — horizontal bar chart of **coefficients**:

```
  Pressure PSI  ████████████████████  +820
    Polish Time  ███████████████      +640
   Wafer_Si3N4  ██████████           +450
          P_x_T  ███████             +310
     Pad_IC1000  █████               +200
  Slurry_Al2O3  ████                +180
       Cond_CB  ██                  +100
     Cond_DIA  ██                  −100
  Slurry_CeO2  ████                −180
     Pad_FS-C  █████               −200
     Wafer_SiC  ██████████           −450
               ─┼─────────────────────►
              −500   0   +500   +1000
                  Coefficient value
```

- Bars extend left (negative) or right (positive)
- Sorted by absolute value (largest effect at top)

**Random Forest** — horizontal bar chart of **importance scores** (0 to 1):

```
  Pressure PSI  ████████████████████  0.42
    Polish Time  ██████████████       0.28
          Wafer  ████████             0.14
            Pad  █████                0.08
         Slurry  ████                 0.05
    Conditioner  ██                   0.03
                └──────────────────────►
                0.0     0.2     0.4
                   Importance
```

- All bars go right (importance is always positive)
- Scores sum to 1.0

### Graph 3: Residuals vs Predicted

```
  Residual (Å)
   +300 ┤  ·                         · = run_01 (+200)
        │       ·                    · = run_04 (+200)
      0 ┤─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─ ─   (zero line)
        │            ·               · = run_03 (−100)
   −100 ┤                 ·          · = run_05 (−100)
        │
   −300 ┤                      ·     · = run_02 (−300)
        └──┬──────┬──────┬──────┬──
         2500   3500   4500   5500   6500
                  Predicted (Å)
```

- **X-axis:** Predicted Removal
- **Y-axis:** Residual (Actual − Predicted)
- **Dashed horizontal line:** zero (perfect residual)

**What to look for:**
- Good: Points scattered randomly around zero, no pattern
- Bad — funnel shape: Errors grow as predictions grow (the model is less reliable for high-removal experiments)
- Bad — curve: A U-shape or trend means the model is systematically wrong in some range

### Graph 4: Residual Distribution

```
  Count
    3 ┤
      │  ┌───┐
    2 ┤  │   │  ┌───┐
      │  │   │  │   │
    1 ┤  │   │  │   │
      │  │   │  │   │
    0 ┤──┴───┴──┴───┴──
      −300  −100  +100  +200
             Residual (Å)
```

- **X-axis:** Residual value (Å)
- **Y-axis:** How many files fall in each bin
- **Annotation** in the top-left corner shows:
  - **Mean residual:** average error direction (0 Å means unbiased)
  - **Std residual:** spread of errors

Using the example data:
- Mean = (+200 − 300 − 100 + 200 − 100) / 5 = **−20 Å**
- Std ≈ **210 Å**

**What to look for:**
- Good: Bell-shaped, centered near zero
- Bad — shifted: Mean far from zero means the model consistently over- or under-predicts
- Bad — wide: Large standard deviation means predictions are unreliable

---

## 5  Metric Formulas

Three numbers summarize model quality.  All are computed via 5-fold
cross-validation (each file is predicted once while held out from training).

### R-squared (R²)

Measures what fraction of the variation in Removal the model explains.

```
         Σ(actualᵢ − predictedᵢ)²
R² = 1 − ─────────────────────────
           Σ(actualᵢ − mean_actual)²
```

Using the example (mean actual = 4000):

```
Numerator   = 200² + 300² + 100² + 200² + 100²
            = 40000 + 90000 + 10000 + 40000 + 10000 = 190,000

Denominator = (3200−4000)² + (5800−4000)² + (2400−4000)² + (4100−4000)² + (4500−4000)²
            = 640000 + 3240000 + 2560000 + 10000 + 250000 = 6,700,000

R² = 1 − 190000 / 6700000 = 1 − 0.028 = 0.972
```

- **R² = 1.0** → perfect predictions
- **R² = 0.0** → model is no better than always guessing the average
- **R² < 0** → model is worse than guessing the average

### RMSE (Root Mean Squared Error)

Average error magnitude, in Angstroms.  Penalizes large errors more heavily.

```
RMSE = √( Σ(actualᵢ − predictedᵢ)² / n )
```

```
RMSE = √(190000 / 5) = √38000 ≈ 195 Å
```

### MAE (Mean Absolute Error)

Average error magnitude, in Angstroms.  Treats all errors equally.

```
MAE = Σ|actualᵢ − predictedᵢ| / n
```

```
MAE = (200 + 300 + 100 + 200 + 100) / 5 = 900 / 5 = 180 Å
```

### Comparing RMSE and MAE

| Scenario           | RMSE  | MAE  | What it tells you                  |
|--------------------|-------|------|------------------------------------|
| All errors similar | ≈ MAE | —    | Errors are consistent              |
| RMSE >> MAE        | high  | low  | A few files have very large errors |

---

## Ridge vs Random Forest — When to Use Which

| Criterion             | Ridge Regression             | Random Forest                    |
|-----------------------|------------------------------|----------------------------------|
| Interpretability      | High — coefficients show direction and magnitude | Medium — importance scores show magnitude only |
| Handles interactions  | Needs explicit P_x_T column  | Discovers interactions automatically |
| Risk of overfitting   | Low (Ridge penalty)          | Low (100 averaged trees, min 3 per leaf) |
| Prediction uncertainty| Single RMSE value for all predictions | Per-prediction (tree disagreement) |
| Small datasets (<20)  | Often better                 | May underperform                 |
| Large datasets (50+)  | Good                         | Often better                     |
