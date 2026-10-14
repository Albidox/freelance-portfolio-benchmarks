/**
 * Export Engine: RFC 4180 Compliant CSV & JSON Generation
 * Features formula injection protection and memory-efficient streaming chunking.
 */

export class ExportEngine {
  /**
   * Neutralize spreadsheet formula injection attacks.
   * Prepends single quote if the value begins with '=', '+', '-', '@', '\t', or '\r'.
   * @param {*} value
   * @returns {string}
   */
  static sanitizeCsvCell(value) {
    if (value === null || value === undefined) {
      return '';
    }
    const s = String(value).trim();
    if (!s) {
      return '';
    }
    const dangerousPrefixes = ['=', '+', '-', '@', '\t'];
    if (dangerousPrefixes.includes(s[0]) || s.charCodeAt(0) === 13) {
      return "'" + s;
    }
    return s;
  }

  /**
   * Escape individual CSV field strictly per RFC 4180.
   * Encloses in quotes if containing comma, double-quote, or newline.
   * Doubles internal quotes.
   * @param {*} value
   * @returns {string}
   */
  static escapeCsvField(value) {
    if (value === null || value === undefined) {
      return '""';
    }
    const s = String(value);
    const needsQuoting = s.includes(',') || s.includes('"') || s.includes('\n') || s.includes('\r');
    if (needsQuoting) {
      const escaped = s.replace(/"/g, '""');
      return `"${escaped}"`;
    }
    return s;
  }

  /**
   * Convert array of record objects to RFC 4180 CSV string.
   * Uses CRLF (\r\n) row terminators per specification.
   * @param {Array<Object>} records
   * @param {Array<Object>} [columnMappings] Optional mapping array [{ sourceField, targetColumn }]
   * @returns {string}
   */
  static toCsv(records, columnMappings = null) {
    if (!records || records.length === 0) {
      return '';
    }

    let headers = [];
    let keys = [];

    if (columnMappings && columnMappings.length > 0) {
      headers = columnMappings.map(m => m.targetColumn);
      keys = columnMappings.map(m => m.sourceField);
    } else {
      keys = Object.keys(records[0]);
      headers = keys;
    }

    const lines = [];
    // Header row
    lines.push(headers.map(h => this.escapeCsvField(h)).join(','));

    // Data rows
    for (const record of records) {
      const row = keys.map(k => {
        const rawVal = record[k] !== undefined ? record[k] : '';
        const sanitizedVal = this.sanitizeCsvCell(rawVal);
        return this.escapeCsvField(sanitizedVal);
      });
      lines.push(row.join(','));
    }

    return lines.join('\r\n') + '\r\n';
  }

  /**
   * Convert records to JSON array or newline-delimited JSON (NDJSON).
   * @param {Array<Object>} records
   * @param {boolean} [pretty=false]
   * @param {boolean} [ndjson=false]
   * @returns {string}
   */
  static toJson(records, pretty = false, ndjson = false) {
    if (ndjson) {
      return records.map(r => JSON.stringify(r)).join('\n');
    }
    return JSON.stringify(records, null, pretty ? 2 : 0);
  }

  /**
   * Chunk array of records to bound memory in browser context.
   * @param {Array} array
   * @param {number} [size=2000]
   * @returns {Array<Array>}
   */
  static chunk(array, size = 2000) {
    const chunks = [];
    for (let i = 0; i < array.length; i += size) {
      chunks.push(array.slice(i, i + size));
    }
    return chunks;
  }
}
