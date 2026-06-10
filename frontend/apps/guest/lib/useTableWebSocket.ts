"use client";

import { useEffect, useRef, useCallback } from "react";
import { useCartStore } from "./cartStore";

const WS_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
  .replace(/^http/, "ws");

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000];

export function useTableWebSocket(tableId: string, venueId: string) {
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const mountedRef = useRef(true);

  const { guestId, guestName, setWsStatus, setCart, setGuests, setSessionId, setLastOrder, updateOrderStatus } =
    useCartStore();

  const send = useCallback((type: string, payload: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
    }
  }, []);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    setWsStatus("connecting");

    const url = `${WS_BASE}/ws/table/${tableId}?guest_id=${guestId}&venue_id=${venueId}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      attemptRef.current = 0;
      setWsStatus("connected");
      ws.send(
        JSON.stringify({
          type: "guest_join",
          payload: { guest_id: guestId, guest_name: guestName || "Гость", venue_id: venueId },
        })
      );
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      const { type, payload } = msg;

      if (type === "table_joined") {
        setSessionId(payload.session_id);
        setCart(payload.cart, payload.total);
        setGuests(payload.guests);
      }

      if (type === "cart_updated") {
        setCart(payload.cart, payload.total);
      }

      if (type === "order_confirmed") {
        setLastOrder({
          order_id: payload.order_id,
          status: payload.status,
          total_amount: payload.total_amount,
        });
        setCart([], 0);
      }

      if (type === "order_status_changed") {
        updateOrderStatus(payload.order_id, payload.status);
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setWsStatus("disconnected");
      const delay = RECONNECT_DELAYS[Math.min(attemptRef.current, RECONNECT_DELAYS.length - 1)];
      attemptRef.current++;
      setTimeout(connect, delay);
    };

    ws.onerror = () => {
      ws.close();
    };
  }, [tableId, venueId, guestId, guestName, setWsStatus, setCart, setGuests, setSessionId, setLastOrder, updateOrderStatus]);

  useEffect(() => {
    mountedRef.current = true;
    connect();
    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
  }, [connect]);

  return { send, wsRef };
}
