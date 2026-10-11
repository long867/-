import "server-only";
/** Cache public, anonymous data only. Credentials never enter the Next data cache. */
export async function serverApi<T>(path: string): Promise<T | undefined> {
  try {
    const response = await fetch(
      `${process.env.API_INTERNAL_URL || "http://127.0.0.1:8001"}/api${path}`,
      { next: { revalidate: 300 }, signal: AbortSignal.timeout(2500) },
    );
    return response.ok ? ((await response.json()) as T) : undefined;
  } catch {
    return undefined;
  }
}
