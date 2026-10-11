import type { Metadata } from "next";
import { NotificationCenter } from "@/components/notification-center";
export const metadata: Metadata = { title: "消息中心" };
export default function Page() {
  return <NotificationCenter />;
}
