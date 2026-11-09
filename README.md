# IR correction

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24082268.svg)](https://doi.org/10.5281/zenodo.24082268)

A simple desktop program that applies **IR (ohmic) correction** to potential-current data from an Excel or CSV file, and optionally calculates the **Tafel slope** from the IR-corrected data.

Developed by **Omnia M. Salem**.

## Equations

```
IR drop = i x Rs
```

| Measurement | IR-corrected potential |
|---|---|
| Applied potential (CV, LSV) | `E_corrected = E_measured - i x Rs` |
| Fuel cell discharge (e.g. DMFC) | `E_corrected = E_measured + i x Rs` |

- `i` = current in amperes (if you enter current density `j`, then `i = j x A`, where `A` is the active area in cm2)
- `Rs` = ohmic resistance from EIS (high-frequency intercept on the Nyquist plot)
- Use **Rs only, not Rct**.
- IR correction changes the **potential**, not the current.

## Download (Windows)

Download **IR correction.exe** from the [Releases](../../releases) page and double-click it. No Python needed.

Windows may show "Windows protected your PC" because the file is not digitally signed. Click **More info**, then **Run anyway**.

**SHA-256 hash of IR correction.exe:**

```
5f613c05916c5457a451dd40b6a50e009227a6bf33016241ccb97d0052305595
```

To check your download, run this in Command Prompt and compare the result:

```
certutil -hashfile "IR correction.exe" SHA256
```

## Run from source

```
pip install -r requirements.txt
python IR_GUI.py
```

## How to use

1. Click **Browse** and select your Excel or CSV file (first row = column names).
2. Select the potential column, the current column, and the current unit.
3. Enter the active area and Rs.
4. Choose the measurement type.
5. (Optional) Tick **Tafel slope** and enter the fit window (mA/cm2).
6. Click **Calculate**, then **Save Excel** and/or **Show plots**.

The saved Excel file contains your original columns plus `i (A)`, `j (mA/cm2)`, `IR drop (V)` and `E IR-corrected (V)`. Your original file is never changed.

## Notes

- Anodic current should be positive in your file. Cathodic (negative) current is also supported.
- For a CV, use the forward scan for the Tafel fit (default).
- Choose a Tafel window that is linear on the Tafel plot and spans at least one decade of current.
- Always check the results against a manual calculation for your own data.

## Citation

> Salem, O. M. (2026). *IR correction* (Version 1.0.0) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.24082268

## License

See the `LICENSE` file.
