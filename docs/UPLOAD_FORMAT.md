# Upload format for rankings and tournament results

When you **upload a file** or use **manual entry** on the Data Input page, the app expects a consistent column structure. The same structure is used when creating tournaments from the wizard or from uploads.

## Required columns (all file types)

| Column   | Description                    | Example   |
|----------|--------------------------------|-----------|
| **Rank** or **Position** | Finishing place (integer) | 1, 2, 3 |
| **Name** | Player full name               | Jane Doe  |
| **Points** | Ranking points (numeric)     | 1250.5    |

## Optional columns

- **Country** — 2–4 letter code or full name  
- **License number** — WPA/org license  
- **Stops played** — number of events (e.g. for WPBA)

## By file type

### CSV / TXT

- First row can be a header: `Rank` or `Position`, `Name`, `Points`, and optionally `Country`, `License`, `Stops`.
- Separator: comma or tab.
- Example:
  ```text
  Rank,Name,Points,Country
  1,Player One,1500,USA
  2,Player Two,1400,GBR
  ```

### Spreadsheet (XLSX)

- Use the **first sheet**. Same column names as above.
- For **WPA Men** or **WPA Women**: you can upload a sheet with **multiple point columns** (e.g. “8-ball”, “9-ball”, “10-ball”, “Yalin 8-Ball World Championship 2025”). The app will map each column to the matching ranking button and create one ranking list per column (no combining).

### PDF / DOCX

- Tables are extracted automatically. Keep columns clearly separated (Rank, Name, Points, Country).
- Layout should look like a table; messy or image-only PDFs may not parse correctly.

### XML

- Table or list structure with elements for rank, name, points (and optional country).

## After upload

- **WPA Men**: After you import into **WPA Men** (file or manual), the app automatically splits that snapshot into **one button per event column** (e.g. Yalin 8-Ball, Predator 10-Ball, 9-Ball World Champs). You do not need to run a separate step.

## Same columns everywhere

The app uses this column set consistently:

- Rankings tables (overall and per-event buttons)
- Tournaments created from the **Tournament Wizard**
- Tournaments created from **uploaded results**

So any rankings or tournament you create from upload or the wizard keeps the same columns (Rank, Name, Points, Country, and optional fields).
