import { serverApi } from "@/lib/server-api";
import { PolicyWorkspace } from "@/components/policy-workspace";
import type { PolicyPage } from "@/types";
export const revalidate = 300;
export default async function Policies() {
  return (
    <PolicyWorkspace
      initial={await serverApi<PolicyPage>("/policies?page_size=12")}
    />
  );
}
