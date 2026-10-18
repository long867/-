import { SceneGlyph } from "@/components/scene-glyph";
import { SkeletonCards } from "@/components/ui/states";
import { Locale } from "@/components/locale";

export default function Loading() {
  return (
    <main className="workspace loading-scene" aria-busy="true">
      <SceneGlyph />
      <p className="subtitle" role="status">
        <Locale
          zh="正在读取情报页面…"
          en="Loading your intelligence workspace…"
        />
      </p>
      <SkeletonCards count={3} />
    </main>
  );
}
