import { fetchCategories, fetchDishes, fetchVenue } from "@/lib/api";
import MenuEditor from "@/components/menu/MenuEditor";
import MenuPageHeader from "@/components/menu/MenuPageHeader";

interface Props {
  params: { id: string };
}

export default async function MenuPage({ params }: Props) {
  const [venue, { categories }, { dishes }] = await Promise.all([
    fetchVenue(params.id),
    fetchCategories(params.id),
    fetchDishes(params.id),
  ]);
  return (
    <div className="p-8 flex flex-col h-full">
      <MenuPageHeader venue={venue} venueId={params.id} />
      <div className="flex-1 mt-6 min-h-0 overflow-hidden">
        <MenuEditor venueId={params.id} initialCategories={categories} initialDishes={dishes} />
      </div>
    </div>
  );
}
