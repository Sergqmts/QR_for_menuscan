import { notFound } from "next/navigation";
import { fetchMenu, fetchTableInfo } from "@/lib/api";
import MenuView from "./menu-view";

interface Props {
  params: { slug: string; tableNumber: string };
}

export default async function TablePage({ params }: Props) {
  const tableNumber = parseInt(params.tableNumber, 10);
  if (isNaN(tableNumber)) return notFound();

  let menu, tableInfo;
  try {
    [menu, tableInfo] = await Promise.all([
      fetchMenu(params.slug),
      fetchTableInfo(params.slug, tableNumber),
    ]);
  } catch {
    return notFound();
  }

  return (
    <MenuView
      menu={menu}
      tableInfo={tableInfo}
      venueSlug={params.slug}
    />
  );
}
