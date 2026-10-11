import { Directory } from "@/components/directory";
import { serverApi } from "@/lib/server-api";
import type { MineralFacet } from "@/types";
export const revalidate = 300;
export default async function Page() {
  return (
    <Directory
      kind="minerals"
      initial={await serverApi<MineralFacet[]>("/minerals")}
    />
  );
}
