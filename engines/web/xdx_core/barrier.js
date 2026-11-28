// XDX asset load barrier: frame 0 may be rendered only after every registered font/texture/model promise has settled.
export function createAssetLoadBarrier() {
  const items = [];
  return {
    require(label, promise) {
      const rec = { label, state: "pending" };
      rec.p = Promise.resolve(promise).then(() => { rec.state = "loaded"; }, (e) => { rec.state = "failed"; rec.error = String(e); });
      items.push(rec);
      return rec.p;
    },
    async settle() { await Promise.all(items.map((i) => i.p)); },
    report() { return items.map(({ label, state, error }) => ({ label, state, error })); },
    pending() { return items.filter((i) => i.state === "pending").length; },
    failed() { return items.filter((i) => i.state === "failed").length; },
  };
}
