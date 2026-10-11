# Market Standards for Client Data Deliverables: Excel & Interactive HTML Previews

## 1. Executive Summary & Market Economics

On platforms such as Upwork, Contra, Fiverr Pro, and Topmate, client perception of value is disproportionately governed by presentation ergonomics rather than pipeline complexity.

### The Pricing Asymmetry
* Tier 1 ($10 - $25, Commodity Scrape): Raw, unformatted `.csv` dumped into chat. Columns are unpadded, headers are unformatted lowercase strings, numbers are unparsed floats (`35.070000000001`), missing fields produce visual raggedness, and non-technical clients must spend 2 to 4 hours cleaning and formatting before presenting to stakeholders.
* Tier 2 ($50 - $100, Standard Delivery): Cleaned `.csv` accompanied by a default Excel file created via basic `Ctrl+T`. Uses default Calibri 11pt, stock Excel blue styling, and unaligned currency.
* Tier 3 ($150 - $350+, Premium Agency & Enterprise Freelance): Multi-format delivery pack containing clean `.csv`, compressed `.parquet` for database engineers, a bespoke styled `.xlsx` workbook adhering to corporate typography and color systems, and a standalone, zero-dependency interactive `.html` preview dashboard.

Clients rate Tier 3 deliverables with 5 stars because the deliverable is immediate executive-ready collateral. The buyer can forward the workbook or open the HTML file directly inside a board meeting, client presentation, or internal team sync without touching a formatting toolbar.

---

## 2. Theoretical Grounding & Design Systems

### Spreadsheet Ergonomics
According to primary design research from Big Excel Energy:
* Canonical Source: `https://bigexcelenergy.com/excel-dashboard-design-principles/`
* Quotation: "choose one clean typeface (two at most), set a deliberate size scale (big for KPIs, medium for headings, small for labels) and format numbers consistently (same decimals, thousands separators, right-aligned in columns). Add padding inside every card."
* Quotation: "set a column-and-gutter grid and snap every element to it, so card edges, chart edges, and text baselines line up... Not that: elements floating a few pixels off from each other. The eye notices misalignment even when it can't name it, and it quietly undermines trust in the data."

### Single-File Standalone Architecture
According to the zero-dependency dashboard engineering standard:
* Canonical Source: `https://raw.githubusercontent.com/d-padmanabhan/agent-engineering-handbook/main/skills/single-file-dashboard/SKILL.md`
* Quotation: "One file. Zero dependencies. No CDN, no remote scripts, no web fonts, no images. Inlined CSS, inlined JS, inlined data, inlined SVG."
* Quotation: "Escape user content. Every string pulled from data must be HTML-escaped. Never bypass. Renders identically offline. Test by disabling network; the dashboard must look unchanged."

---

## 3. Five Production Excel Workbook Themes

All openpyxl workbooks must enforce:
1. `ws.views.sheetView[0].showGridLines = True` (preserves explicit structure).
2. `ws.freeze_panes = 'A2'` (locks header row during scrolling).
3. Auto-fit column widths with padding: `width = max(max_len + 3, 10)`.
4. Right-aligned numerical and currency cells (`Alignment(horizontal='right')`).
5. Native Excel number formatting (`cell.number_format = '£#,##0.00'`).

```
+------------------------------------------------------------------------------------------------------------------------------------------+
| Theme Name & Target File      | Header Hex / Text | Zebra Fill | Border Hex | Accent / Badge Fill | Typography Stack   | Psychological Appeal      |
+------------------------------------------------------------------------------------------------------------------------------------------+
| 01. Corporate Slate           | #1E293B / #FFFFFF | #F8FAFC    | #CBD5E1    | #3B82F6 (Muted Blue)| Segoe UI 11pt/9pt  | Institutional authority,  |
| (01_corporate_slate.xlsx)     |                   |            |            |                     | Header 11pt Bold   | executive trust           |
+------------------------------------------------------------------------------------------------------------------------------------------+
| 02. Emerald Growth            | #065F46 / #FFFFFF | #F0FDF4    | #A7F3D0    | #10B981 (Soft Sage) | Aptos / Arial 11pt | Modern SaaS, growth,      |
| (02_emerald_growth.xlsx)      |                   |            |            | Badge: #DCFCE7      | Header 11pt Bold   | sustainability, fresh     |
+------------------------------------------------------------------------------------------------------------------------------------------+
| 03. Fintech Navy              | #0F172A / #FFFFFF | #F1F5F9    | #94A3B8    | #2563EB (Navy Blue) | Segoe UI 10.5pt    | Wall Street precision,    |
| (03_fintech_navy.xlsx)        |                   |            |            | Data: High contrast | Numbers: Right-num | audit-ready rigor         |
+------------------------------------------------------------------------------------------------------------------------------------------+
| 04. Minimal Monochrome        | #27272A / #FFFFFF | #F4F4F5    | #E4E4E7    | #71717A (Neutral)   | Arial / Calibri 10 | Scandinavian minimalism,  |
| (04_minimal_monochrome.xlsx)  |                   |            |            | Low-saturation gray | Understated light  | pure focus on raw facts   |
+------------------------------------------------------------------------------------------------------------------------------------------+
| 05. Executive Summary KPI     | Tab 1: Slate Hero | Cards:     | #E2E8F0    | KPI Accent: #1E40AF | Aptos Display 18pt | Board-level synthesis,    |
| (05_executive_summary_kpi.xlsx| Tab 2: Clean Grid | #F8FAFC    | Thin Gray  | Status: #16A34A     | Body: Segoe UI 11pt| instant insight delivery  |
+------------------------------------------------------------------------------------------------------------------------------------------+
```

### Theme 1: Corporate Slate (`01_corporate_slate.xlsx`)
* Target File: `output/excel_variants/01_corporate_slate.xlsx`
* Color Specification:
  * Header Fill: Dark Slate `#1E293B` (ARGB: `FF1E293B`)
  * Header Text: Pure White `#FFFFFF`, Font Size 11pt, Bold
  * Zebra Row Striping (Even Rows): Ice Slate `#F8FAFC` (ARGB: `FFF8FAFC`)
  * Data Text: Dark Navy/Charcoal `#0F172A`
  * Gridline / Cell Borders: Thin light slate `#CBD5E1`
  * Rating Representation: Solid star Unicode glyphs (`★` and `☆`)
* Formatting Mechanics:
  * Header row height: 26pt. Data row height: 20pt.
  * Price column formatted as native currency: `cell.number_format = '£#,##0.00'`.
  * Freeze Panes: Row 1 frozen (`ws.freeze_panes = 'A2'`).
  * Auto-filters enabled across row 1 columns A through F.
* Psychological Impact: Conveys corporate maturity, enterprise software alignment, and calm, unopinionated authority. Favored by corporate procurement and management consultancies.

### Theme 2: Emerald Growth (`02_emerald_growth.xlsx`)
* Target File: `output/excel_variants/02_emerald_growth.xlsx`
* Color Specification:
  * Header Fill: Deep Emerald `#065F46` (ARGB: `FF065F46`)
  * Header Text: Pure White `#FFFFFF`, Font Size 11pt, Bold
  * Zebra Row Striping: Soft Mint `#F0FDF4` (ARGB: `FFF0FDF4`)
  * Status Badge Fill ("In Stock"): Pastel Sage `#DCFCE7` (ARGB: `FFDCFCE7`) with dark green text `#166534`
  * Cell Borders: Subtle pale emerald `#A7F3D0`
* Formatting Mechanics:
  * Row height: Header 28pt, rows 20pt.
  * Currency format: `cell.number_format = '£#,##0.00'`.
  * Stock status column converted to pill-like styled text with centered alignment.
* Psychological Impact: Associated with profit, growth metrics, sustainable commerce, and modern venture-backed SaaS tools (Shopify, Stripe Climate). E-commerce founders love this styling.

### Theme 3: Fintech Navy (`03_fintech_navy.xlsx`)
* Target File: `output/excel_variants/03_fintech_navy.xlsx`
* Color Specification:
  * Header Fill: High-Contrast Midnight Navy `#0F172A` (ARGB: `FF0F172A`)
  * Header Text: Pure White `#FFFFFF`, Font Size 10.5pt, Bold
  * Zebra Row Striping: Pale Slate `#F1F5F9` (ARGB: `FFF1F5F9`)
  * Data Text: Deep Carbon `#020617`
  * Cell Borders: Defined medium-thin slate `#94A3B8`
  * Currency Column Header: Accent blue text `#2563EB`
* Formatting Mechanics:
  * Font: Segoe UI or Arial 10pt with strict right-alignment on all numerical values.
  * Explicit decimal precision: `£#,##0.00` with zero decimal clipping.
  * Page number and URL columns formatted with clean centered alignment.
* Psychological Impact: Signals institutional hedge-fund rigor, strict audit readiness, and zero computational ambiguity. Common standard for quantitative research deliverables.

### Theme 4: Minimal Monochrome (`04_minimal_monochrome.xlsx`)
* Target File: `output/excel_variants/04_minimal_monochrome.xlsx`
* Color Specification:
  * Header Fill: Charcoal Matte Black `#27272A` (ARGB: `FF27272A`)
  * Header Text: Pure White `#FFFFFF`, Font Size 10pt, Bold
  * Zebra Row Striping: Whisper Gray `#F4F4F5` (ARGB: `FFF4F4F5`)
  * Data Text: Deep Slate `#18181B`
  * Cell Borders: Hairline light gray `#E4E4E7`
* Formatting Mechanics:
  * Compact row height: Header 24pt, rows 18pt.
  * Extremely clean, distraction-free visual canvas with no colored highlights.
  * Understated headers, perfectly centered star glyphs.
* Psychological Impact: Scandinavian executive design aesthetic. Popular among design agencies, DTC luxury brands, and executive directors who find colorful tables loud or unprofessional.

### Theme 5: Executive Summary KPI (`05_executive_summary_kpi.xlsx`)
* Target File: `output/excel_variants/05_executive_summary_kpi.xlsx`
* Architectural Structure: Two-tab workbook.
  * Tab 1: `Executive Summary` (Strategic Dashboard)
  * Tab 2: `Full Dataset` (1,000 Records)
* Tab 1 Layout:
  * Title Block (Row 2): 18pt Bold `Books to Scrape: Market Intelligence & Catalog Analysis`, subtitle with timestamp and record counts.
  * KPI Card Row (Rows 5 to 7): 4 structured KPI cards side-by-side:
    * Card 1: `Total Products` = `1,000` (Bold 20pt, border card)
    * Card 2: `Average Price` = `£35.07` (Bold 20pt, border card)
    * Card 3: `In-Stock Availability` = `100.0%` (Bold 20pt, soft green indicator)
    * Card 4: `Catalog Scope` = `50 Pages` (Bold 20pt, border card)
  * Breakdown Table (Rows 10 to 17): Star Rating Distribution Table:
    * 1 Star: 226 books (22.6%)
    * 2 Stars: 196 books (19.6%)
    * 3 Stars: 203 books (20.3%)
    * 4 Stars: 179 books (17.9%)
    * 5 Stars: 196 books (19.6%)
* Tab 2 Layout:
  * Clean corporate table layout with auto-filters, freeze panes, and custom auto-fit widths.
* Psychological Impact: High-ticket agency deliverable archetype. The client CEO or VP does not need to analyze 1,000 rows to extract key answers; the summary tab delivers instant answers for immediate stakeholder reporting.

---

## 4. Five Standalone Interactive HTML Preview Themes

All 5 HTML variants must be 100% standalone, self-contained single files. They must render identically when opened via local file protocol (`file:///path/to/file.html`) without requiring a web server or active internet connection.

```
+------------------------------------------------------------------------------------------------------------------------------------------+
| Theme Name & Target File      | Surface & Canvas  | Text & Accents    | Interactive Components         | Core Technical Pattern                  |
+------------------------------------------------------------------------------------------------------------------------------------------+
| 01. Tailwind Clean            | Canvas: #F8FAFC   | Text: #0F172A     | Live search input, sortable    | Lightweight modern Tailwind CDN with    |
| (01_tailwind_clean.html)      | Surface: #FFFFFF  | Accent: #2563EB   | headers, stock badge chips     | pure inline JS sorting engine fallback  |
+------------------------------------------------------------------------------------------------------------------------------------------+
| 02. Stripe Dashboard          | Canvas: #F6F9FC   | Text: #32325D     | Metrics ribbon, pagination     | Enterprise SaaS UI, page size selector  |
| (02_stripe_dashboard.html)    | Surface: #FFFFFF  | Accent: #635BFF   | (25/50/100), copy to clipboard | (25/50/100), copy CSV button            |
+------------------------------------------------------------------------------------------------------------------------------------------+
| 03. Dark Fintech              | Canvas: #0F172A   | Text: #F8FAFC     | Interactive star rating filter | High-contrast dark mode, glowing badges,|
| (03_dark_fintech.html)        | Surface: #1E293B  | Accent: #38BDF8   | buttons, instant search        | neon stock pills (#22C55E)              |
+------------------------------------------------------------------------------------------------------------------------------------------+
| 04. Dense Analytics           | Canvas: #FFFFFF   | Text: #111827     | Sticky table header, compact   | Bloomberg/terminal density, quick       |
| (04_dense_analytics.html)     | Surface: #F9FAFB  | Accent: #1F2937   | rows (28px), summary footer    | statistics summary ribbon               |
+------------------------------------------------------------------------------------------------------------------------------------------+
| 05. Card Grid Hybrid          | Canvas: #F3F4F6   | Text: #1F2937     | View mode toggle (Table vs     | Interactive view switcher, responsive   |
| (05_card_grid_hybrid.html)    | Surface: #FFFFFF  | Accent: #4F46E5   | Cards), live search, sort      | CSS grid of product cards with stars    |
+------------------------------------------------------------------------------------------------------------------------------------------+
```

### Theme 1: Tailwind Clean (`01_tailwind_clean.html`)
* Target File: `output/html_variants/01_tailwind_clean.html`
* Visual Design:
  * Background: Slate-50 `#F8FAFC`, Cards: Pure White `#FFFFFF` with subtle border `#E2E8F0` and shadow `0 1px 3px rgba(0,0,0,0.05)`.
  * Primary Text: Slate-900 `#0F172A`, Subtext: Slate-500 `#64748B`.
  * Top KPI Grid: 4 metric cards (Total Count: 1,000, Average Price: £35.07, In-Stock Rate: 100%, Price Range: £10.00 to £59.99).
* Interactivity:
  * Real-time search filter input listening to `keyup` and `search` events.
  * Clickable sort headers with ascending/descending chevron indicators.
  * Stock badge chips (`In Stock` pill in emerald green `#DEF7EC` with `#03543F` text).
  * Direct clickable links to book details.

### Theme 2: Stripe Dashboard (`02_stripe_dashboard.html`)
* Target File: `output/html_variants/02_stripe_dashboard.html`
* Visual Design:
  * Stripe signature background `#F6F9FC` with purple accent `#635BFF`.
  * Clean typography stack: `-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif`.
  * Top navigation bar with project title, live record counter, and "Copy CSV to Clipboard" button.
* Interactivity:
  * Client-side pagination: User can toggle between 25, 50, and 100 records per page.
  * Previous / Next navigation controls with current page indicator.
  * Live status toast notification ("Table data copied to clipboard in CSV format").

### Theme 3: Dark Fintech (`03_dark_fintech.html`)
* Target File: `output/html_variants/03_dark_fintech.html`
* Visual Design:
  * Background: Slate-900 `#0F172A`, Table Container: Slate-800 `#1E293B`, Borders: Slate-700 `#334155`.
  * Text: High-contrast Slate-100 `#F1F5F9`, Muted: Slate-400 `#94A3B8`.
  * Accents: Cyan `#38BDF8` and Neon Emerald `#22C55E`.
* Interactivity:
  * Filter pills for Star Rating: "All", "5 Stars", "4 Stars", "3 Stars", "2 Stars", "1 Star".
  * Instant reactive table filter updates on button click without reloading.
  * Glowing hover states on table rows (`background: #334155`).

### Theme 4: Dense Analytics (`04_dense_analytics.html`)
* Target File: `output/html_variants/04_dense_analytics.html`
* Visual Design:
  * Ultra-compact Bloomberg/terminal aesthetic designed for financial analysts and data scientists.
  * Row height: 28px, Font: 12px monospace/tabular numerals.
  * Fixed sticky header (`position: sticky; top: 0; background: #1F2937; color: white`).
* Interactivity:
  * Column-level summary footer calculating Min Price (£10.00), Average Price (£35.07), and Max Price (£59.99) dynamically based on currently visible/filtered rows.
  * Compact input filters for instant text matching.

### Theme 5: Card Grid Hybrid (`05_card_grid_hybrid.html`)
* Target File: `output/html_variants/05_card_grid_hybrid.html`
* Visual Design:
  * Dual-mode layout: Seamless toggle button switching between "Table View" and "E-Commerce Card Grid View".
  * Card View: Responsive CSS Grid (`grid-template-columns: repeat(auto-fill, minmax(240px, 1fr))`).
  * Each card renders: Title, Price in large bold font, Golden Star Rating (`★★★★★`), "In Stock" chip, and detail URL action button.
* Interactivity:
  * Switching views maintains the active search query and active sort order.
  * Ideal for non-technical retail and e-commerce clients who prefer visual browsing.

---

## 5. Technical Implementation Playbook for `generate_presentation_variants.py`

### OpenPyXL Construction Standards
1. Import Pattern:
   ```python
   import openpyxl
   from openpyxl.styles import PatternFill, Font, Alignment, Border, Side
   from openpyxl.utils import get_column_letter
   ```
2. Safe Column Auto-Fit:
   ```python
   for col in ws.columns:
       max_len = 0
       col_letter = get_column_letter(col[0].column)
       for cell in col:
           val_str = str(cell.value or "")
           if len(val_str) > max_len:
               max_len = len(val_str)
       ws.column_dimensions[col_letter].width = max(max_len + 3, 11)
   ```
3. Numerical Precision:
   Always parse `float(row['price_gbp'])` into a native Python float before writing to the cell. Never write string formatted numbers (e.g. `'51.77'`) because Excel treats them as text and disables mathematical operations.

### HTML Construction Standards
1. Zero External Dependency Invariant:
   Embed dataset directly into the HTML as an inline JSON array inside a `<script>` tag:
   ```html
   <script>
   const DATASET = [ ... ];
   </script>
   ```
2. XSS Sanitization Rule:
   All string interpolations into DOM must pass through a strict escaping utility:
   ```javascript
   function escapeHtml(str) {
     return String(str)
       .replace(/&/g, '&amp;')
       .replace(/</g, '&lt;')
       .replace(/>/g, '&gt;')
       .replace(/"/g, '&quot;')
       .replace(/'/g, '&#39;');
   }
   ```
3. Sorting Algorithm:
   Support both numeric and string comparisons with locale-safe fallback:
   ```javascript
   data.sort((a, b) => {
     let vA = a[sortCol], vB = b[sortCol];
     if (typeof vA === 'number' && typeof vB === 'number') {
       return sortAsc ? vA - vB : vB - vA;
     }
     return sortAsc ? String(vA).localeCompare(String(vB)) : String(vB).localeCompare(String(vA));
   });
   ```

---

## 6. Primary Receipts & Canonical Reference Ledger

* Big Excel Energy Dashboard Principles:
  * Canonical URL: `https://bigexcelenergy.com/excel-dashboard-design-principles/`
  * Verbatim Receipt: "choose one clean typeface (two at most), set a deliberate size scale (big for KPIs, medium for headings, small for labels) and format numbers consistently (same decimals, thousands separators, right-aligned in columns). Add padding inside every card."
* Big Excel Energy Color Palettes:
  * Canonical URL: `https://bigexcelenergy.com/excel-dashboard-color-palette/`
  * Verbatim Receipt: "01 Corporate Blue Executive, finance, and general business reporting It reads like a report, not a spaceship: a neutral page, one reliable focal blue, and no decorative rainbow. Canvas #F5F7FA Surface #FFFFFF Text #172033 Muted #667085 Accent #2563EB Support #0F2A4A Positive #1E8E5A Warning #B7791F"
* Single-File Zero-Dependency Dashboard Specification:
  * Canonical URL: `https://raw.githubusercontent.com/d-padmanabhan/agent-engineering-handbook/main/skills/single-file-dashboard/SKILL.md`
  * Verbatim Receipt: "One file. Zero dependencies. No CDN, no remote scripts, no web fonts, no images. Inlined CSS, inlined JS, inlined data, inlined SVG. Escape user content. Every string pulled from data must be HTML-escaped. Never bypass."
* OpenPyXL Styles Documentation:
  * Canonical URL: `https://openpyxl.readthedocs.io/en/stable/styles.html`
  * Verbatim Receipt: "Styles are used to change the look of your data while displayed on screen. They are also used to determine the formatting for numbers. Styles can be applied to the following aspects: font to set font size, color, underlining, etc. fill to set a pattern or color gradient border to set borders on a cell cell alignment"
* OpenPyXL Worksheet Tables Documentation:
  * Canonical URL: `https://openpyxl.readthedocs.io/en/stable/worksheet_tables.html`
  * Verbatim Receipt: "Table names must be unique within a workbook. By default tables are created with a header from the first row and filters for all the columns and table headers and column headings must always contain strings."
* Professional Excel Formatting Standards:
  * Canonical URL: `https://www.exceldemy.com/5-formatting-tricks-that-instantly-make-your-excel-sheets-look-professional/`
  * Verbatim Receipt: "Freeze your header row (View -> Freeze Panes -> Freeze Top Row) so formatting payoff remains visible while scrolling. Select cells with currency data. Go to the Home tab >> select Currency or Accounting from the Number group. Set decimal places to 2."
