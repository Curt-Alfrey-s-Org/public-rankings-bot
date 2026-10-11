# Director Import: Manual Entry and File Upload

Directors and Admins can add rankings data in two ways from the **Data input** page (sidebar → Data input).

**Primary source:** Sanctioned updates use **file upload, manual entry, and (for WPBA/WPA) the tournament-import workflow** on this page. Scraping and super-admin tooling are optional; they are not required for associations to publish official lists. Imports are **audit-logged** (see below).

## Association isolation

- Each **director** account has one or more **associations** (for example `WPBA_Women`, `WPA_Women`, `WPA_Men`), stored in `user_associations` and set when an admin creates or edits the user (**Settings → Users**).
- Those associations map to **scopes** (WPBA, WPA, CP, LOCAL). A director may import or copy rankings **only** into systems that belong to their scopes. **Admins** and **super_admins** are not restricted.
- If no association is assigned, Data input shows a message and the API returns `403` on import routes until an admin assigns at least one association.
- **Eligibility:** `GET /api/rankings/import/eligibility` returns the systems and scopes the current user may use (the Data input UI uses this).

## Manual entry

1. Choose **System:** one of the columns you are allowed to update (WPBA/WPA/CP variants, etc.).
2. Fill in the table: **Rank**, **Name**, **Points**, **Country** (country optional).
3. Use **Add row** to add more rows; use **−** to remove a row.
4. Click **Submit N row(s)**. Data is saved as a new snapshot; rankings and Movement will reflect the new data.

Empty name rows are skipped. All submitted rows become the new ranking list for that system on today’s date.

## Import from file

1. Choose **System:** same as manual entry (filtered by your associations if you are a director).
2. Click **Choose file** and select a file. Allowed types:
   - **PDF** — tables or text with rank, name, points (and optionally country)
   - **DOCX** — Word documents (tables or paragraphs)
   - **XLSX** — Excel spreadsheets (first sheet)
   - **XML** — XML with row/item/player elements containing rank, name, points, country
   - **CSV** / **TXT** — comma- or tab-separated; optional header line (Position/Rank, Name, Points, Country)
3. Click **Upload and import**. The file is parsed; extracted rows are saved as a new snapshot. If parsing fails, check that the file has columns like Rank/Position, Name, Points, and optionally Country.

**Note:** `.doc` (old Word) is not supported; use **Save as .docx** in Word or LibreOffice.

## Audit

All imports (manual and file) are recorded in the audit log (visible on the same page under **Recent activity**). Each entry shows who submitted and how many rows were imported. Tournament merges from confirmed imports are logged separately.

## Sales / positioning (short)

- **Formats:** PDF, DOCX, XLSX, XML, CSV, TXT for bulk import; manual grid entry; optional CSV endpoints under `/api/csv-import/*` (same association rules as `/api/rankings/import`).
- **Governance:** Role-based access, per-association write scope for directors, full audit trail on imports and tournament-driven ranking updates.
- **Multi-association:** One product supports WPBA, WPA, CP, and related systems; directors only touch the data their organization is assigned.

## See also

- [How rankings are calculated](RANKINGS_CALCULATION.md) — Tournament file (`final_results.txt`), WPBA/WPA sources.
- Data input page also explains the **tournament results import** flow (place `final_results.txt` in `tournament_tools/`, then Refresh).
