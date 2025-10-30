# extract_pdf.py
# Shawn-safe: no Java, parses pages 3–4 into one row per district.

import re
import pdfplumber
import pandas as pd
from pathlib import Path

PDF_PATH = Path(r"C:\Users\sbaum\ABC Branch List.pdf")          # <- adjust if needed
OUT_XLSX = Path(r"C:\Users\sbaum\ABC_Branch_List_Pg3_4.xlsx")   # output file

# Known region names found in the doc (expandable)
REGION_CANDIDATES = {
    "Northeast", "Mid Atlantic", "Northern Ohio", "Eastern New England",
    "Southern Virginia", "New York Metro", "Eastern PA", "S Jersey-Delaware",
    "Chicago", "Ohio Valley"
}

CITY_STATE_ZIP_RE = re.compile(r"^\s*([A-Za-z .'\-]+),\s*([A-Z]{2})\s+(\d{5}(?:-\d{4})?)\s*$")
DISTRICT_LINE_RE  = re.compile(r"^\s*(\d{3,4})\s*-\s*(.+?)\s*(?:Dist|District)?\s*$", re.IGNORECASE)
MANAGER_LINE_RE   = re.compile(r"^\s*(.+?)\s*-\s*District Manager\s*$", re.IGNORECASE)

def normalize(s: str) -> str:
    return re.sub(r"\s+", " ", s or "").strip()

def collapse_lines(lines):
    """Trim blank/whitespace-only lines and normalize spacing."""
    return [normalize(x) for x in lines if normalize(x)]

def chunk_blocks(lines):
    """
    Split the page lines into logical 'district blocks' using the '... - District Manager' marker.
    Each block will start with the manager line and include everything until the next manager line.
    """
    blocks = []
    cur = []
    for ln in lines:
        if MANAGER_LINE_RE.match(ln):
            if cur:
                blocks.append(cur)
                cur = []
        cur.append(ln)
    if cur:
        blocks.append(cur)
    return blocks

def extract_field(joined_text, label):
    """
    Extracts phone-like fields by label: 'P-', 'F-', 'Cell-', 'eFax-'.
    Returns '' if not found.
    """
    # Accept forms like: "P- 215-721-3930", "F- 866-265-3880", "Cell- 207-232-5465", "eFax- 888-123-4567"
    m = re.search(rf"{label}\s*([0-9()\- ]+)", joined_text)
    return normalize(m.group(1)) if m else ""

def parse_block(block_lines):
    """
    Parse one district block into a dict of fields.
    We look for:
      Manager, District #, District Name, Region (best effort), Address, City, State, Zip,
      P-, F-, Cell-, eFax-, Branch List
    """
    out = {
        "Region": "",
        "District #": "",
        "District Name": "",
        "Manager Name": "",
        "Address": "",
        "City": "",
        "State": "",
        "ZIP": "",
        "Phone (P-)": "",
        "Fax (F-)": "",
        "Cell": "",
        "eFax": "",
        "Branch List": ""
    }

    # 1) Manager line
    for ln in block_lines:
        mm = MANAGER_LINE_RE.match(ln)
        if mm:
            out["Manager Name"] = normalize(mm.group(1))
            break

    # 2) District line (usually right after manager)
    for ln in block_lines:
        dm = DISTRICT_LINE_RE.match(ln)
        if dm:
            out["District #"] = normalize(dm.group(1))
            out["District Name"] = normalize(dm.group(2).replace("Dist","").replace("District",""))
            break

    # 3) Region (best effort): a line that is exactly a known region name
    for ln in block_lines:
        if ln in REGION_CANDIDATES:
            out["Region"] = ln
            break

    # 4) Address + City/State/ZIP
    # Find the line that matches City,State Zip and take the previous non-empty as Street Address
    prev = ""
    for ln in block_lines:
        m = CITY_STATE_ZIP_RE.match(ln)
        if m:
            out["City"], out["State"], out["ZIP"] = m.groups()
            out["Address"] = prev  # the line just before City/State/ZIP
            break
        prev = ln if ln else prev

    # 5) Phones: Parse from a single joined string for robustness
    joined = " ".join(block_lines)
    out["Phone (P-)"] = extract_field(joined, "P-")
    out["Fax (F-)"]   = extract_field(joined, "F-")
    out["Cell"]       = extract_field(joined, "Cell-")
    out["eFax"]       = extract_field(joined, "eFax-")

    # 6) Branch list: everything after City/State/ZIP that looks like "<num> <name>"
    # Combine tail text and pull items like "531 Tinton Falls"
    tail_idx = -1
    for i, ln in enumerate(block_lines):
        if CITY_STATE_ZIP_RE.match(ln):
            tail_idx = i + 1
            break
    if tail_idx != -1:
        tail = " ".join(block_lines[tail_idx:])
        # Capture patterns like: "531 Tinton Falls"
        branches = re.findall(r"\b(\d{1,4})\s+([A-Za-z][A-Za-z &\-\']+)", tail)
        if branches:
            out["Branch List"] = ", ".join([f"{num} {name.strip()}" for num, name in branches])

    return out

def main():
    if not PDF_PATH.exists():
        raise FileNotFoundError(f"PDF not found: {PDF_PATH}")

    rows = []
    with pdfplumber.open(PDF_PATH) as pdf:
        # pages are 0-indexed; pages 3–4 => indices 2 and 3
        for pidx in (2, 3):
            page = pdf.pages[pidx]
            raw = page.extract_text() or ""
            # normalize and split into lines
            lines = collapse_lines(raw.splitlines())
            # break into district blocks
            blocks = chunk_blocks(lines)
            for b in blocks:
                record = parse_block(b)
                # Only keep blocks that look valid (have a manager + district)
                if record["Manager Name"] or record["District #"]:
                    rows.append(record)

    if not rows:
        raise RuntimeError("No district blocks were parsed. Verify pages 3–4 contain the district listings.")

    df = pd.DataFrame(rows, columns=[
        "Region", "District #", "District Name", "Manager Name",
        "Address", "City", "State", "ZIP",
        "Phone (P-)", "Fax (F-)", "Cell", "eFax", "Branch List"
    ])

    # Final tidy
    for col in df.columns:
        df[col] = df[col].astype(str).str.strip().str.replace(r"\s+", " ", regex=True)

    df.to_excel(OUT_XLSX, index=False)
    print(f"✅ Done! Wrote {len(df)} rows to: {OUT_XLSX}")

if __name__ == "__main__":
    main()
