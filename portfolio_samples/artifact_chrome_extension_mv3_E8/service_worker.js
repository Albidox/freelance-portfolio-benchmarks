/**
 * Background Service Worker (Manifest V3)
 * Non-persistent event-driven lifecycle, messaging bridge, and export queue manager.
 */

import { ExportEngine } from './export_engine.js';

const CONFIG = {
  MAX_QUEUE_SIZE: 10000,
  BASE_BACKOFF_MS: 1000,
  MAX_BACKOFF_MS: 60000,
  ALARM_SYNC_NAME: 'E8_SYNC_ALARM'
};

class ServiceWorkerCoordinator {
  constructor() {
    this.syncQueue = [];
    this.consecutiveFailures = 0;
    this.currentBackoffMs = CONFIG.BASE_BACKOFF_MS;
    this.initListeners();
  }

  initListeners() {
    // Chrome Extension lifecycle events
    if (typeof chrome !== 'undefined' && chrome.runtime) {
      chrome.runtime.onInstalled.addListener(details => {
        console.log('[E8 SW] Extension installed/updated:', details.reason);
        this.initializeStorage();
      });

      // Message router
      chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
        this.handleMessage(message, sender)
          .then(res => sendResponse(res))
          .catch(err => sendResponse({ success: false, error: err.message }));
        return true; // Keep channel open for async response
      });

      // Alarms for scheduled background sync
      if (chrome.alarms) {
        chrome.alarms.onAlarm.addListener(alarm => {
          if (alarm.name === CONFIG.ALARM_SYNC_NAME) {
            this.processSyncQueue();
          }
        });
      }
    }
  }

  async initializeStorage() {
    if (typeof chrome !== 'undefined' && chrome.storage && chrome.storage.local) {
      await chrome.storage.local.set({
        e8_version: '1.0.0',
        e8_total_exported: 0,
        e8_active_jobs: []
      });
    }
  }

  async handleMessage(message, sender) {
    const action = message.action || '';
    const payload = message.payload || {};

    switch (action) {
      case 'PING':
        return { success: true, status: 'PONG', timestamp: Date.now() };

      case 'QUEUE_EXPORT_BATCH': {
        const records = Array.isArray(payload.records) ? payload.records : [];
        for (const r of records) {
          if (this.syncQueue.length < CONFIG.MAX_QUEUE_SIZE) {
            this.syncQueue.push(r);
          }
        }
        return {
          success: true,
          queuedCount: records.length,
          totalInQueue: this.syncQueue.length
        };
      }

      case 'GET_QUEUE_STATUS':
        return {
          success: true,
          queueDepth: this.syncQueue.length,
          backoffMs: this.currentBackoffMs,
          failures: this.consecutiveFailures
        };

      case 'GENERATE_CSV': {
        const records = payload.records || [];
        const mappings = payload.columnMappings || null;
        const csvText = ExportEngine.toCsv(records, mappings);
        return {
          success: true,
          format: 'CSV',
          rowCount: records.length,
          csv: csvText
        };
      }

      case 'GENERATE_JSON': {
        const records = payload.records || [];
        const pretty = !!payload.pretty;
        const jsonText = ExportEngine.toJson(records, pretty);
        return {
          success: true,
          format: 'JSON',
          rowCount: records.length,
          json: jsonText
        };
      }

      default:
        return { success: false, error: `Unknown action: ${action}` };
    }
  }

  calculateBackoff(statusCode) {
    if (statusCode === 429 || statusCode === 503) {
      this.consecutiveFailures++;
      const delay = Math.min(
        CONFIG.MAX_BACKOFF_MS,
        CONFIG.BASE_BACKOFF_MS * Math.pow(2, this.consecutiveFailures - 1)
      );
      this.currentBackoffMs = delay;
      return delay;
    }
    this.consecutiveFailures = 0;
    this.currentBackoffMs = CONFIG.BASE_BACKOFF_MS;
    return 0;
  }

  async processSyncQueue() {
    if (this.syncQueue.length === 0) return;
    console.log(`[E8 SW] Processing ${this.syncQueue.length} records in queue...`);
  }
}

// Instantiate singleton service worker coordinator
export const coordinator = new ServiceWorkerCoordinator();
