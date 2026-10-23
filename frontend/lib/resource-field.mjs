/** A bounded coverage diagram; coordinates are layout positions, not geography. */
export function resourceNodes(facets = [], limit = 8) {
  const values = new Map();
  for (const facet of facets) {
    if (
      !facet ||
      typeof facet.name !== "string" ||
      !facet.name.trim() ||
      !Number.isSafeInteger(facet.count) ||
      facet.count <= 0
    )
      continue;
    const previous = values.get(facet.name);
    if (!previous || previous.count < facet.count)
      values.set(facet.name, facet);
  }
  const ordered = [...values.values()]
    .sort(
      (a, b) =>
        b.count - a.count || (a.name > b.name ? 1 : a.name < b.name ? -1 : 0),
    )
    .slice(0, Math.min(8, Math.max(1, limit)));
  return ordered.map((facet, index) => {
    const angle = -Math.PI / 2 + (index * Math.PI * 2) / ordered.length;
    return {
      ...facet,
      x: 300 + Math.cos(angle) * 224,
      y: 230 + Math.sin(angle) * 167,
    };
  });
}

/** Exact tags connect the preview to actual published material, without inference. */
export function resourcePreview(articles = [], kind, name) {
  if (typeof name !== "string" || !name) return [];
  const field = kind === "regions" ? "regions" : "minerals";
  const seen = new Set();
  return articles
    .filter((article) => {
      if (
        !article ||
        article.status !== "published" ||
        !article.id ||
        seen.has(article.id) ||
        !article[field]?.includes(name)
      )
        return false;
      seen.add(article.id);
      return true;
    })
    .slice(0, 3);
}
