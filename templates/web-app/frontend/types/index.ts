/**
 * Shared TypeScript types that mirror the backend Pydantic models.
 * Keep these in sync with backend/app/models/
 */

// Common types
export interface HealthResponse {
  status: string;
}

export interface ErrorResponse {
  error: string;
  detail?: string | null;
}

export interface SuccessResponse {
  success: boolean;
  message?: string | null;
}

// Item types - mirrors backend/app/models/items.py
export interface Item {
  id: string;
  title: string;
  description?: string | null;
  completed: boolean;
  created_at: string; // ISO datetime string
  updated_at: string; // ISO datetime string
}

export interface ItemCreate {
  title: string;
  description?: string | null;
  completed?: boolean;
}

export interface ItemUpdate {
  title?: string;
  description?: string | null;
  completed?: boolean;
}

export interface ItemList {
  items: Item[];
  total: number;
}

