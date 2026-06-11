import Link from "next/link";
import { fetchAnalytics, fetchVenue } from "@/lib/api";
import SummaryCards from "@/components/analytics/SummaryCards";
import RevenueChart from "@/components/analytics/RevenueChart";
import TopDishesChart from "@/components/analytics/TopDishesChart";
import OrdersTable from "@/components/analytics/OrdersTable";
import PeriodFilter from "@/components/analytics/PeriodFilter";

interface Props {
  params: { id: string };
  searchParams: { from?: string; to?: string };
}

export default async function AnalyticsPage({ params, searchParams }: Props) {
  const [venue, analytics] = await Promise.all([
    fetchVenue(params.id),
    fetchAnalytics(params.id, searchParams.from, searchParams.to),
  ]);
  return (
    <div className="p-8 space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <nav className="text-sm text-gray-500 mb-1">
            <Link href="/venues" className="hover:text-orange-500">Заведения</Link>
            <span className="mx-2">/</span>
            <span className="text-gray-900">{venue.name}</span>
          </nav>
          <h1 className="text-2xl font-bold text-gray-900">Аналитика</h1>
        </div>
        <PeriodFilter />
      </div>

      <SummaryCards summary={analytics.summary} />

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-4">Выручка по дням</h2>
          <RevenueChart data={analytics.daily} />
        </div>
        <div className="bg-white rounded-xl border border-gray-200 p-6">
          <h2 className="font-semibold text-gray-900 mb-4">Топ блюд</h2>
          <TopDishesChart data={analytics.top_dishes} />
        </div>
      </div>

      <div className="bg-white rounded-xl border border-gray-200 p-6">
        <h2 className="font-semibold text-gray-900 mb-4">История заказов</h2>
        <OrdersTable venueId={params.id} />
      </div>
    </div>
  );
}
