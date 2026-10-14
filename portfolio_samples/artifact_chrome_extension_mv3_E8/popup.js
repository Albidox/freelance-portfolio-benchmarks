/**
 * Minimalist Brutalist Control Popup Logic
 * Interacts with content script, service worker, and ExportEngine.
 */

import { ExportEngine } from './export_engine.js';

let discoveredTables = [];
let selectedTableIndex = 0;

function logStatus(msg) {
  const log = document.getElementById('status-log');
  if (log) {
    const timestamp = new Date().toLocaleTimeString();
    log.textContent = `[${timestamp}] ${msg}`;
  }
}

function updateStats(tableCount, rowCount) {
  const statTables = document.getElementById('stat-tables');
  const statRows = document.getElementById('stat-rows');
  if (statTables) statTables.textContent = String(tableCount);
  if (statRows) statRows.textContent = String(rowCount);
}

function populateTableDropdown(tables) {
  const select = document.getElementById('table-select');
  if (!select) return;

  select.innerHTML = '';
  if (tables.length === 0) {
    const opt = document.createElement('option');
    opt.value = '';
    opt.textContent = 'No tables detected';
    select.appendChild(opt);
    return;
  }

  tables.forEach((t, idx) => {
    const opt = document.createElement('option');
    opt.value = String(idx);
    opt.textContent = `Table #${idx + 1} (${t.rowCount} rows, ${t.columns.length} cols)`;
    select.appendChild(opt);
  });
}

function triggerDownload(content, filename, mimeType) {
  const blob = new Blob([content], { type: mimeType });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = filename;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  setTimeout(() => URL.revokeObjectURL(url), 2000);
}

document.addEventListener('DOMContentLoaded', () => {
  const btnScan = document.getElementById('btn-scan');
  const btnExportCsv = document.getElementById('btn-export-csv');
  const btnExportJson = document.getElementById('btn-export-json');
  const btnCopyClipboard = document.getElementById('btn-copy-clipboard');
  const tableSelect = document.getElementById('table-select');

  if (tableSelect) {
    tableSelect.addEventListener('change', (e) => {
      selectedTableIndex = parseInt(e.target.value, 10) || 0;
      if (discoveredTables[selectedTableIndex]) {
        updateStats(discoveredTables.length, discoveredTables[selectedTableIndex].rowCount);
        logStatus(`Selected Table #${selectedTableIndex + 1} (${discoveredTables[selectedTableIndex].rowCount} rows)`);
      }
    });
  }

  if (btnScan) {
    btnScan.addEventListener('click', async () => {
      logStatus('Scanning DOM for tables & grids...');
      try {
        if (typeof chrome !== 'undefined' && chrome.tabs && chrome.tabs.query) {
          const [activeTab] = await chrome.tabs.query({ active: true, currentWindow: true });
          if (!activeTab || !activeTab.id) {
            logStatus('Error: No active tab found.');
            return;
          }

          chrome.tabs.sendMessage(activeTab.id, { action: 'SCAN_TABLES' }, (response) => {
            if (chrome.runtime.lastError) {
              logStatus('Notice: Content script not injected yet. Reload tab or check permissions.');
              return;
            }

            if (response && response.success) {
              discoveredTables = response.tables || [];
              const totalRows = discoveredTables.reduce((sum, t) => sum + t.rowCount, 0);
              updateStats(discoveredTables.length, totalRows);
              populateTableDropdown(discoveredTables);
              logStatus(`Scan complete. Found ${discoveredTables.length} tables with ${totalRows} total rows.`);
            } else {
              logStatus('Scan returned no tables.');
            }
          });
        } else {
          logStatus('Mock environment detected. Active tab querying simulated.');
        }
      } catch (err) {
        logStatus(`Scan error: ${err.message}`);
      }
    });
  }

  if (btnExportCsv) {
    btnExportCsv.addEventListener('click', () => {
      const activeTable = discoveredTables[selectedTableIndex];
      if (!activeTable || !activeTable.data || activeTable.data.length === 0) {
        logStatus('Export error: No table data selected. Scan tab first.');
        return;
      }

      logStatus(`Generating RFC 4180 CSV for ${activeTable.data.length} records...`);
      const csvContent = ExportEngine.toCsv(activeTable.data);
      const filename = `export_table_${selectedTableIndex + 1}_${Date.now()}.csv`;
      triggerDownload(csvContent, filename, 'text/csv;charset=utf-8;');
      logStatus(`Exported ${activeTable.data.length} rows to ${filename}`);
    });
  }

  if (btnExportJson) {
    btnExportJson.addEventListener('click', () => {
      const activeTable = discoveredTables[selectedTableIndex];
      if (!activeTable || !activeTable.data || activeTable.data.length === 0) {
        logStatus('Export error: No table data selected. Scan tab first.');
        return;
      }

      logStatus(`Generating JSON for ${activeTable.data.length} records...`);
      const jsonContent = ExportEngine.toJson(activeTable.data, true);
      const filename = `export_table_${selectedTableIndex + 1}_${Date.now()}.json`;
      triggerDownload(jsonContent, filename, 'application/json;charset=utf-8;');
      logStatus(`Exported ${activeTable.data.length} rows to ${filename}`);
    });
  }

  if (btnCopyClipboard) {
    btnCopyClipboard.addEventListener('click', async () => {
      const activeTable = discoveredTables[selectedTableIndex];
      if (!activeTable || !activeTable.data || activeTable.data.length === 0) {
        logStatus('Copy error: No table data selected.');
        return;
      }

      const csvContent = ExportEngine.toCsv(activeTable.data);
      try {
        await navigator.clipboard.writeText(csvContent);
        logStatus(`Copied ${activeTable.data.length} rows (RFC 4180 CSV) to clipboard.`);
      } catch (err) {
        logStatus(`Clipboard write failed: ${err.message}`);
      }
    });
  }
});
