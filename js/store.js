// حفظ التصنيفات الخاصة (صور المستخدم) بـ IndexedDB على نفس الجهاز
(function () {
  const DB = 'showtime', STORE = 'custom';
  let dbp;

  function db() {
    if (!dbp) {
      dbp = new Promise((res, rej) => {
        const r = indexedDB.open(DB, 1);
        r.onupgradeneeded = () => r.result.createObjectStore(STORE, { keyPath: 'id' });
        r.onsuccess = () => res(r.result);
        r.onerror = () => rej(r.error);
      });
    }
    return dbp;
  }

  async function tx(mode, fn) {
    const d = await db();
    return new Promise((res, rej) => {
      const t = d.transaction(STORE, mode);
      const out = fn(t.objectStore(STORE));
      t.oncomplete = () => res(out && out.result !== undefined ? out.result : out);
      t.onerror = () => rej(t.error);
    });
  }

  // كل تصنيف: { id, name, prompt, items: [{ id, a, blob? , url? }] }
  window.CustomStore = {
    async all() {
      try { return await tx('readonly', s => s.getAll()); } catch (e) { console.warn(e); return []; }
    },
    save: cat => tx('readwrite', s => s.put(cat)),
    remove: id => tx('readwrite', s => s.delete(id)),
  };
})();
