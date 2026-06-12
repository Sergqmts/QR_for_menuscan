"use client";

import { useEffect, useRef, useState, useCallback } from "react";

const WS_BASE = (process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000")
  .replace(/^http/, "ws");

export interface KitchenOrderItem {
  dish_name: string;
  quantity: number;
  comment: string;
  guest_name: string;
}

export interface KitchenOrder {
  order_id: string;
  table: { number: number; label: string };
  status: "accepted" | "cooking" | "ready" | "served";
  total_amount: number;
  created_at: string;
  items: KitchenOrderItem[];
}

const RECONNECT_DELAYS = [1000, 2000, 4000, 8000, 16000, 30000];

export function useKitchenWebSocket(venueId: string, token: string, code = "") {
  const [orders, setOrders] = useState<KitchenOrder[]>([]);
  const [status, setStatus] = useState<"disconnected" | "connecting" | "connected">("disconnected");
  const wsRef = useRef<WebSocket | null>(null);
  const attemptRef = useRef(0);
  const mountedRef = useRef(true);

  const send = useCallback((type: string, payload: Record<string, unknown>) => {
    if (wsRef.current?.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type, payload }));
    }
  }, []);

  const updateOrderStatus = useCallback((orderId: string, newStatus: KitchenOrder["status"]) => {
    send("update_order_status", { order_id: orderId, status: newStatus });
  }, [send]);

  const connect = useCallback(() => {
    if (!mountedRef.current) return;
    setStatus("connecting");

    const qs = code ? `code=${code}` : `token=${token}`;
    const url = `${WS_BASE}/ws/kitchen/${venueId}?${qs}`;
    const ws = new WebSocket(url);
    wsRef.current = ws;

    ws.onopen = () => {
      attemptRef.current = 0;
      setStatus("connected");
    };

    ws.onmessage = (event) => {
      const msg = JSON.parse(event.data);
      const { type, payload } = msg;

      if (type === "kitchen_connected") {
        setOrders(payload.active_orders ?? []);
      }

      if (type === "new_order") {
        setOrders((prev) => [payload, ...prev]);
      }

      if (type === "order_status_updated") {
        setOrders((prev) =>
          prev
            .map((o) =>
              o.order_id === payload.order_id ? { ...o, status: payload.status } : o
            )
            .filter((o) => o.status !== "served")
        );
      }
    };

    ws.onclose = () => {
      if (!mountedRef.current) return;
      setStatus("disconnected");
      const delay = RECONNECT_DELAYS[Math.min(attemptRef.current, RECONNECT_DELAYS.length - 1)];
      attemptRef.current++;
      setTimeout(connect, delay);
    };

    ws.onerror = () => ws.close();
  }, [venueId, token, send]);

  useEffect(() => {
    mountedRef.current = true;
    if (token) connect();
    return () => {
      mountedRef.current = false;
      wsRef.current?.close();
    };
  }, [connect, token]);

  return { orders, status, updateOrderStatus };
}
