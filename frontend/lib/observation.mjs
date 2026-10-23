/** Keep a small, deduplicated browser-local list; storage never grants access. */
export function normalizeWatchlist(value) {
  if (!Array.isArray(value)) return [];
  return [
    ...new Set(
      value.filter(
        (name) =>
          typeof name === "string" &&
          name.trim() === name &&
          name.length > 0 &&
          name.length <= 40 &&
          !/[\u0000-\u001f<>]/u.test(name),
      ),
    ),
  ].slice(0, 12);
}

/** Pick an actual dated, finite quote; never turn absent values into zero. */
export function latestQuotation(prices = []) {
  return (
    [...prices]
      .filter(
        (price) =>
          price &&
          (typeof price.price === "string" ||
            typeof price.price === "number") &&
          String(price.price).trim() !== "" &&
          Number.isFinite(Number(price.price)) &&
          Number(price.price) > 0 &&
          typeof price.date === "string" &&
          Number.isFinite(Date.parse(price.date)),
      )
      .sort((a, b) => b.date.localeCompare(a.date))[0] ?? null
  );
}

/** Preserve the reader's order, including explicitly watched unquoted minerals. */
export function observationItems(items = [], names = []) {
  const watched = normalizeWatchlist(names);
  if (watched.length) {
    const byName = new Map(items.map((item) => [item.name, item]));
    return watched.map((name) => byName.get(name)).filter(Boolean);
  }
  return items.filter((item) => latestQuotation(item.prices)).slice(0, 4);
}
