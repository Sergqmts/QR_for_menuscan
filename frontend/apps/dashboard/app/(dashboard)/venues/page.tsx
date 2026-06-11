import Link from "next/link";
import { fetchVenues } from "@/lib/api";

export default async function VenuesPage() {
  const { venues } = await fetchVenues();
  return (
    <div className="p-8">
      <h1 className="text-2xl font-bold text-gray-900 mb-8">Мои заведения</h1>
      {venues.length === 0 ? (
        <div className="text-center py-16 text-gray-400">
          <p className="text-lg font-medium">Нет заведений</p>
          <p className="text-sm mt-1">Создайте заведение через API</p>
        </div>
      ) : (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {venues.map((venue) => (
            <div key={venue.id} className="bg-white rounded-xl border border-gray-200 p-6 shadow-sm">
              <div className="flex items-start justify-between">
                <div>
                  <h2 className="font-bold text-gray-900">{venue.name}</h2>
                  {venue.address && <p className="text-gray-500 text-sm mt-0.5">{venue.address}</p>}
                </div>
                <span className={`text-xs px-2 py-1 rounded-full font-medium ${venue.is_active ? "bg-green-100 text-green-700" : "bg-gray-100 text-gray-500"}`}>
                  {venue.is_active ? "Активно" : "Неактивно"}
                </span>
              </div>
              <p className="text-sm text-gray-500 mt-2">{venue.table_count} столов · {venue.slug}</p>
              <div className="flex gap-2 mt-4">
                <Link href={`/venues/${venue.id}/menu`} className="flex-1 text-center text-sm font-medium bg-orange-500 text-white py-2 rounded-lg hover:bg-orange-600 transition-colors">
                  Меню
                </Link>
                <Link href={`/venues/${venue.id}/tables`} className="flex-1 text-center text-sm font-medium border border-gray-200 text-gray-700 py-2 rounded-lg hover:bg-gray-50 transition-colors">
                  Столы
                </Link>
                <Link href={`/venues/${venue.id}/analytics`} className="flex-1 text-center text-sm font-medium border border-gray-200 text-gray-700 py-2 rounded-lg hover:bg-gray-50 transition-colors">
                  Аналитика
                </Link>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}
