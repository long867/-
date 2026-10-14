/** @param {unknown} value */
function line(value) {
  return String(value || "")
    .replace(/[\r\n]+/g, " ")
    .trim();
}

/** @param {import("../types/frontier").FrontierPaper} paper */
export function researchCitation(paper) {
  const authors = paper.authors.slice(0, 3).map(line).join(", ");
  const names = authors + (paper.authors.length > 3 ? ", et al." : "");
  return (
    [
      names,
      line(paper.title),
      line(paper.journal),
      paper.published_date?.slice(0, 4),
      `DOI: ${line(paper.doi)}`,
    ]
      .filter(Boolean)
      .join(". ") + "."
  );
}

/** @param {import("../types/frontier").FrontierPaper[]} papers */
export function researchRis(papers) {
  return papers
    .map((paper) =>
      [
        "TY  - JOUR",
        `TI  - ${line(paper.title)}`,
        `T2  - ${line(paper.journal)}`,
        ...paper.authors.map((author) => `AU  - ${line(author)}`),
        ...(paper.published_date
          ? [`PY  - ${paper.published_date.slice(0, 4)}`]
          : []),
        `DO  - ${line(paper.doi)}`,
        `UR  - ${line(paper.url)}`,
        ...(paper.title_zh ? [`N1  - 中文题名：${line(paper.title_zh)}`] : []),
        "ER  - ",
        "",
      ].join("\r\n"),
    )
    .join("\r\n");
}
