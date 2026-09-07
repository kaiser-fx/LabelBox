/**
 * LabelBox Offline Queue — IndexedDB-backed scan queue with auto-sync.
 */
const OfflineQueue = (() => {
  const DB_NAME = 'labelbox_offline_db';
  const STORE_NAME = 'pending_scans';
  const DB_VERSION = 1;

  let db = null;

  function open() {
    return new Promise((resolve, reject) => {
      if (db) return resolve(db);
      const req = indexedDB.open(DB_NAME, DB_VERSION);
      req.onupgradeneeded = () => {
        const store = req.result.createObjectStore(STORE_NAME, { keyPath: 'id', autoIncrement: true });
        store.createIndex('sessionId', 'sessionId', { unique: false });
      };
      req.onsuccess = () => { db = req.result; resolve(db); };
      req.onerror = () => reject(req.error);
    });
  }

  async function enqueue(sessionId, imageBlob) {
    const database = await open();
    return new Promise((resolve, reject) => {
      const tx = database.transaction(STORE_NAME, 'readwrite');
      tx.objectStore(STORE_NAME).add({
        sessionId,
        imageBlob,
        timestamp: new Date().toISOString(),
        status: 'pending',
      });
      tx.oncomplete = () => {
        updateBadge();
        resolve();
      };
      tx.onerror = () => reject(tx.error);
    });
  }

  async function getAll() {
    const database = await open();
    return new Promise((resolve, reject) => {
      const tx = database.transaction(STORE_NAME, 'readonly');
      const req = tx.objectStore(STORE_NAME).getAll();
      req.onsuccess = () => resolve(req.result);
      req.onerror = () => reject(req.error);
    });
  }

  async function remove(id) {
    const database = await open();
    return new Promise((resolve, reject) => {
      const tx = database.transaction(STORE_NAME, 'readwrite');
      tx.objectStore(STORE_NAME).delete(id);
      tx.oncomplete = () => { updateBadge(); resolve(); };
      tx.onerror = () => reject(tx.error);
    });
  }

  async function count() {
    const items = await getAll();
    return items.length;
  }

  async function syncAll() {
    const items = await getAll();
    if (items.length === 0) return { synced: 0, failed: 0 };

    let synced = 0;
    let failed = 0;

    for (const item of items) {
      try {
        await API.submitScan(item.sessionId, item.imageBlob, item.timestamp);
        await remove(item.id);
        synced++;
      } catch (err) {
        console.warn('Offline sync failed for item', item.id, err);
        failed++;
      }
    }

    updateBadge();
    return { synced, failed };
  }

  function setBannerMessage(message) {
    const messageEl = document.getElementById('offline-message');
    if (messageEl) messageEl.textContent = message;
  }

  function updateBadge() {
    count().then((n) => {
      const banner = document.getElementById('offline-banner');
      if (banner) {
        banner.classList.toggle('hidden', n === 0 && navigator.onLine);
        if (n > 0 && navigator.onLine) {
          setBannerMessage(`${n} scan(s) waiting to sync`);
        } else if (!navigator.onLine) {
          setBannerMessage(`Offline — ${n} scan(s) queued for sync`);
        }
      }
    });
  }

  // Auto-sync when coming online
  window.addEventListener('online', () => {
    setBannerMessage('Syncing queued scans…');
    syncAll().then(({ synced, failed }) => {
      if (synced > 0 && typeof App !== 'undefined') {
        App.showToast(`Synced ${synced} offline scan(s)`, 'success');
      }
      if (failed > 0 && typeof App !== 'undefined') {
        App.showToast(`${failed} scan(s) still need to sync`, 'warning');
      }
    });
  });

  window.addEventListener('offline', () => {
    const banner = document.getElementById('offline-banner');
    if (banner) banner.classList.remove('hidden');
    count().then((n) => setBannerMessage(`Offline — ${n} scan(s) queued for sync`));
  });

  return { enqueue, getAll, remove, count, syncAll, updateBadge, open };
})();
