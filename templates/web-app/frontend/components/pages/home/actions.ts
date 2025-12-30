'use server';

/**
 * Server Actions for the Home page.
 * 
 * Each page folder should have its own actions.ts file for:
 * - Data fetching from the backend API
 * - Form submissions
 * - Server-side mutations
 * 
 * These run on the server and can be called from client components.
 */

import type { Item, ItemCreate, ItemUpdate, ItemList, SuccessResponse } from '@/types';

// Get the backend URL from environment or use default
const BACKEND_URL = process.env.BACKEND_URL || 'http://localhost:8080';

async function fetchFromBackend<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${BACKEND_URL}${endpoint}`;
  const response = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      ...options.headers,
    },
    // Disable caching for dynamic data
    cache: 'no-store',
  });

  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: 'Unknown error' }));
    throw new Error(error.detail || error.error || 'Request failed');
  }

  return response.json();
}

/**
 * Fetch all items for the demo section.
 */
export async function getItems(): Promise<ItemList> {
  return fetchFromBackend<ItemList>('/api/v1/items');
}

/**
 * Create a new item.
 */
export async function createItem(data: ItemCreate): Promise<Item> {
  return fetchFromBackend<Item>('/api/v1/items', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Update an existing item.
 */
export async function updateItem(id: string, data: ItemUpdate): Promise<Item> {
  return fetchFromBackend<Item>(`/api/v1/items/${id}`, {
    method: 'PATCH',
    body: JSON.stringify(data),
  });
}

/**
 * Delete an item.
 */
export async function deleteItem(id: string): Promise<SuccessResponse> {
  return fetchFromBackend<SuccessResponse>(`/api/v1/items/${id}`, {
    method: 'DELETE',
  });
}

/**
 * Toggle item completion status.
 */
export async function toggleItemComplete(id: string, currentStatus: boolean): Promise<Item> {
  return updateItem(id, { completed: !currentStatus });
}

