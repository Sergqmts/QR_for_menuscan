import { redirect } from "next/navigation";
import { getServerSession } from "@/lib/auth";
import Sidebar from "@/components/Sidebar";

export default async function DashboardLayout({ children }: { children: React.ReactNode }) {
  const session = await getServerSession();
  if (!session) redirect("/login");
  return (
    <div className="flex h-screen bg-gray-50 overflow-hidden">
      <Sidebar userEmail={session.email} />
      <main className="flex-1 overflow-y-auto">{children}</main>
    </div>
  );
}
