import { serverApi } from "@/lib/server-api";
import { DigestWorkspace } from "@/components/digest-workspace";
import type { Digest } from "@/types";
export const revalidate = 300;
export default async function Digests() {
  return (
    <DigestWorkspace
      initial={await serverApi<Digest>("/digest/daily?scope=previous")}
    />
  );
}
