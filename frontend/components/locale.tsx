/** Both locales are server-rendered; the root language selects the visible text. */
export function Locale({ zh, en }: { zh: string; en: string }) {
  return (
    <>
      <span className="locale-zh">{zh}</span>
      <span className="locale-en">{en}</span>
    </>
  );
}
