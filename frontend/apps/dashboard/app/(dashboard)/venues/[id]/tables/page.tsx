import Link from "next/link";
import { fetchTables, fetchVenue } from "@/lib/api";
import TableGrid from "@/components/tables/TableGrid";

interface Props {
  params: { id: string };
}

export default async function TablesPage({ params }: Props) {
  const [venue, { tables }] = await Promise.all([fetchVenue(params.id), fetchTables(params.id)]);
  return (
    <div className="p-8">
      <div className="mb-8">
        <nav className="text-sm text-gray-500 mb-1">
          <Link href="/venues" className="hover:text-orange-500">Заведения</Link>
          <span className="mx-2">/</span>
          <span className="text-gray-900">{venue.name}</span>
        </nav>
        <h1 className="text-2xl font-bold text-gray-900">Столы и QR-коды</h1>
      </div>
      <TableGrid venueId={params.id} initialTables={tables} />
    </div>
  );
}
