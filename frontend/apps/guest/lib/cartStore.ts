import { create } from "zustand";

export interface CartItem {
  cart_item_id: string;
  dish_id: string;
  dish_name: string;
  unit_price: number;
  quantity: number;
  comment: string;
  guest_id: string;
  guest_name: string;
}

export interface Guest {
  guest_id: string;
  guest_name: string;
}

interface CartStore {
  guestId: string;
  guestName: string;
  setGuestName: (name: string) => void;

  cart: CartItem[];
  total: number;
  guests: Guest[];
  sessionId: string | null;

  wsStatus: "disconnected" | "connecting" | "connected";
  setWsStatus: (status: "disconnected" | "connecting" | "connected") => void;

  setCart: (cart: CartItem[], total: number) => void;
  setGuests: (guests: Guest[]) => void;
  setSessionId: (id: string) => void;

  lastOrder: { order_id: string; status: string; total_amount: number } | null;
  setLastOrder: (order: { order_id: string; status: string; total_amount: number }) => void;
  updateOrderStatus: (order_id: string, status: string) => void;
}

function getOrCreateGuestId(): string {
  if (typeof window === "undefined") return "guest-ssr";
  let id = localStorage.getItem("menuscan_guest_id");
  if (!id) {
    id = crypto.randomUUID();
    localStorage.setItem("menuscan_guest_id", id);
  }
  return id;
}

export const useCartStore = create<CartStore>((set, get) => ({
  guestId: getOrCreateGuestId(),
  guestName: typeof window !== "undefined" ? localStorage.getItem("menuscan_guest_name") ?? "" : "",
  setGuestName: (name) => {
    if (typeof window !== "undefined") localStorage.setItem("menuscan_guest_name", name);
    set({ guestName: name });
  },

  cart: [],
  total: 0,
  guests: [],
  sessionId: null,
  wsStatus: "disconnected",

  setWsStatus: (wsStatus) => set({ wsStatus }),
  setCart: (cart, total) => set({ cart, total }),
  setGuests: (guests) => set({ guests }),
  setSessionId: (sessionId) => set({ sessionId }),

  lastOrder: null,
  setLastOrder: (order) => set({ lastOrder: order }),
  updateOrderStatus: (order_id, status) => {
    const o = get().lastOrder;
    if (o && o.order_id === order_id) set({ lastOrder: { ...o, status } });
  },
}));
