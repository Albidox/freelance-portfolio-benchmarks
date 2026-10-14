/**
 * Content Script: DOM Table Parser, Pagination Follower & Clean Text Extractor
 * Operates in host page context under document_idle.
 */

(function () {
  'use strict';

  /**
   * Neutralize spreadsheet formula injection attacks.
   */
  function sanitizeCellText(text) {
    if (!text) return '';
    const clean = text.trim();
    if (!clean) return '';
    const dangerous = ['=', '+', '-', '@', '\t'];
    if (dangerous.includes(clean[0]) || clean.charCodeAt(0) === 13) {
      return "'" + clean;
    }
    return clean;
  }

  /**
   * Extract clean inner text from a DOM element, stripping scripts and styles.
   */
  function cleanElementText(element) {
    if (!element) return '';
    // Clone and strip unwanted tags
    const clone = element.cloneNode(true);
    const unwanted = clone.querySelectorAll('script, style, noscript, svg');
    unwanted.forEach(el => el.remove());
    return (clone.innerText || clone.textContent || '').replace(/\s+/g, ' ').trim();
  }

  /**
   * Extract rows from standard HTML table element.
   */
  function parseTableElement(table) {
    const records = [];
    const rows = Array.from(table.querySelectorAll('tr'));
    if (rows.length === 0) return records;

    // Detect headers
    let headerRow = table.querySelector('thead tr') || rows[0];
    const headerCells = Array.from(headerRow.querySelectorAll('th, td'));
    const headers = headerCells.map((th, idx) => {
      const text = cleanElementText(th);
      return text || `Column_${idx + 1}`;
    });

    const dataRows = (headerRow === rows[0]) ? rows.slice(1) : rows;

    for (const r of dataRows) {
      const cells = Array.from(r.querySelectorAll('td, th'));
      if (cells.length === 0) continue;
      const record = {};
      let hasData = false;

      cells.forEach((cell, idx) => {
        const header = headers[idx] || `Column_${idx + 1}`;
        const raw = cleanElementText(cell);
        if (raw) hasData = true;
        record[header] = sanitizeCellText(raw);
      });

      if (hasData) {
        records.push(record);
      }
    }

    return records;
  }

  /**
   * Detect ARIA / CSS grid-based tabular data structures.
   */
  function parseAriaGridTables() {
    const records = [];
    const gridElements = document.querySelectorAll('[role="grid"], [role="table"]');

    gridElements.forEach(grid => {
      const rows = grid.querySelectorAll('[role="row"]');
      if (rows.length < 2) return;

      const headerCells = rows[0].querySelectorAll('[role="columnheader"], [role="gridcell"]');
      const headers = Array.from(headerCells).map((c, i) => cleanElementText(c) || `Col_${i + 1}`);

      for (let i = 1; i < rows.length; i++) {
        const cells = rows[i].querySelectorAll('[role="gridcell"], [role="cell"]');
        if (cells.length === 0) continue;
        const record = {};
        cells.forEach((cell, idx) => {
          const key = headers[idx] || `Col_${idx + 1}`;
          record[key] = sanitizeCellText(cleanElementText(cell));
        });
        records.push(record);
      }
    });

    return records;
  }

  /**
   * Detect pagination link or next button.
   */
  function findNextPaginationElement() {
    const nextSelectors = [
      'a[rel="next"]',
      'a.next',
      'button.next',
      'a[aria-label="Next"]',
      'button[aria-label="Next"]',
      'li.next a',
      'a:has(span:contains("Next"))',
      '.pagination-next',
      '.next-page'
    ];

    for (const sel of nextSelectors) {
      try {
        const el = document.querySelector(sel);
        if (el && el.offsetParent !== null) {
          return el;
        }
      } catch (e) {
        // Selector syntax error fallback
      }
    }

    // Heuristic link text search
    const links = Array.from(document.querySelectorAll('a, button'));
    for (const l of links) {
      const txt = (l.textContent || '').trim().toLowerCase();
      if (['next', 'next >', 'next »', 'older', 'continue'].includes(txt)) {
        return l;
      }
    }

    return null;
  }

  /**
   * Scan active page DOM for all tabular data.
   */
  function scanPageTables() {
    const results = [];
    const tables = document.querySelectorAll('table');

    tables.forEach((table, index) => {
      const rows = parseTableElement(table);
      if (rows.length > 0) {
        results.push({
          tableIndex: index,
          tableId: table.id || `table_${index + 1}`,
          rowCount: rows.length,
          columns: Object.keys(rows[0]),
          data: rows
        });
      }
    });

    const ariaGrids = parseAriaGridTables();
    if (ariaGrids.length > 0) {
      results.push({
        tableIndex: tables.length,
        tableId: 'aria_grid_0',
        rowCount: ariaGrids.length,
        columns: Object.keys(ariaGrids[0]),
        data: ariaGrids
      });
    }

    return results;
  }

  // Listen for messages from popup or background service worker
  if (typeof chrome !== 'undefined' && chrome.runtime && chrome.runtime.onMessage) {
    chrome.runtime.onMessage.addListener((request, sender, sendResponse) => {
      if (request.action === 'SCAN_TABLES') {
        const tableResults = scanPageTables();
        const nextBtn = findNextPaginationElement();
        sendResponse({
          success: true,
          url: window.location.href,
          title: document.title,
          tablesFound: tableResults.length,
          hasNextPage: !!nextBtn,
          tables: tableResults
        });
        return true;
      }

      if (request.action === 'CLICK_NEXT_PAGE') {
        const nextBtn = findNextPaginationElement();
        if (nextBtn) {
          nextBtn.click();
          sendResponse({ success: true, message: 'Next button clicked' });
        } else {
          sendResponse({ success: false, message: 'Next page control not found' });
        }
        return true;
      }

      return false;
    });
  }

  // Expose global test interface if running in browser or headless probe
  window.__E8_DOM_EXPORTER__ = {
    cleanElementText,
    sanitizeCellText,
    parseTableElement,
    scanPageTables,
    findNextPaginationElement
  };
})();
