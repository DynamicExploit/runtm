'use client';

import { useEffect, useState } from 'react';
import { useItemsStore } from '@/lib/store';
import { ItemCard } from '@/components/ui/ItemCard';
import { AddItemForm } from '@/components/ui/AddItemForm';

/**
 * Interactive demo section for the home page.
 * Demonstrates the Items CRUD functionality with Zustand state management.
 */
export function HomeDemo() {
  const { items, isLoading, error, fetchItems, clearError } = useItemsStore();
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    fetchItems();
  }, [fetchItems]);

  if (!mounted) {
    return (
      <section id="demo" className="py-20 md:py-32">
        <div className="mx-auto max-w-6xl px-6">
          <div className="mx-auto max-w-2xl text-center">
            <h2 className="text-3xl font-bold tracking-tight md:text-4xl">Interactive Demo</h2>
            <p className="mt-4 text-lg text-[var(--muted)]">Loading...</p>
          </div>
        </div>
      </section>
    );
  }

  const completedCount = items.filter((i) => i.completed).length;
  const pendingCount = items.filter((i) => !i.completed).length;

  return (
    <section id="demo" className="py-20 md:py-32">
      <div className="mx-auto max-w-6xl px-6">
        {/* Section header */}
        <div className="mx-auto max-w-2xl text-center">
          <h2 className="text-3xl font-bold tracking-tight md:text-4xl">Interactive Demo</h2>
          <p className="mt-4 text-lg text-[var(--muted)]">
            Try the live API! Create, update, and delete items. State managed with Zustand, data
            persisted via FastAPI.
          </p>
        </div>

        {/* Demo content */}
        <div className="mx-auto mt-12 max-w-2xl">
          {/* Add item form */}
          <AddItemForm />

          {/* Error display */}
          {error && (
            <div className="mt-4 flex items-center justify-between rounded-lg border border-[var(--error)]/50 bg-[var(--error)]/10 p-4">
              <p className="text-sm text-[var(--error)]">{error}</p>
              <button
                onClick={clearError}
                className="text-sm text-[var(--error)] underline hover:no-underline"
              >
                Dismiss
              </button>
            </div>
          )}

          {/* Loading state */}
          {isLoading && items.length === 0 && (
            <div className="mt-8 flex items-center justify-center">
              <div className="h-8 w-8 animate-spin-slow rounded-full border-2 border-[var(--accent)] border-t-transparent" />
            </div>
          )}

          {/* Items list */}
          <div className="mt-8 space-y-4">
            {items.length === 0 && !isLoading ? (
              <div className="rounded-xl border border-dashed border-[var(--border)] p-8 text-center">
                <p className="text-[var(--muted)]">No items yet. Create one above!</p>
              </div>
            ) : (
              items.map((item) => <ItemCard key={item.id} item={item} />)
            )}
          </div>

          {/* Stats */}
          {items.length > 0 && (
            <div className="mt-8 flex items-center justify-center gap-8 text-sm text-[var(--muted)]">
              <span>{items.length} total items</span>
              <span>{completedCount} completed</span>
              <span>{pendingCount} pending</span>
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

