export interface PriceUpdate {
  ticker: string;
  price: number;
  previous_price: number;
  change: number;
  change_percent: number;
  direction: "up" | "down" | "unchanged";
  timestamp: number;
}

export interface PriceMap {
  [ticker: string]: PriceUpdate;
}

export interface Position {
  ticker: string;
  quantity: number;
  avg_cost: number;
  current_price: number;
  unrealized_pnl: number;
  pnl_percent: number;
  market_value: number;
}

export interface Portfolio {
  cash: number;
  total_value: number;
  total_unrealized_pnl: number;
  positions: Position[];
}

export interface PortfolioSnapshot {
  total_value: number;
  recorded_at: string;
}

export interface WatchlistEntry {
  ticker: string;
  price?: number;
  change_percent?: number;
}

export interface ChatMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  actions?: ChatActions;
  created_at?: string;
}

export interface ChatActions {
  trades?: TradeResult[];
  watchlist_changes?: WatchlistChangeResult[];
}

export interface TradeResult {
  status: string;
  ticker: string;
  side: string;
  quantity: number;
  price?: number;
  total?: number;
  error?: string;
}

export interface WatchlistChangeResult {
  status: string;
  ticker: string;
  action: string;
  error?: string;
}

export type ConnectionStatus = "connected" | "connecting" | "disconnected";
