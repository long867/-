import { EventWorkspace } from "@/components/event-workspace";
export default function EventDetail({ params }: { params: { id: string } }) {
  return <EventWorkspace id={params.id} />;
}
