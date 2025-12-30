'use client';

import { useState } from 'react';
import { useItemsStore } from '@/lib/store';

export function AddItemForm() {
  const { createItem, isLoading } = useItemsStore();
  const [title, setTitle] = useState('');
  const [description, setDescription] = useState('');
  const [isExpanded, setIsExpanded] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!title.trim()) return;

    await createItem({
      title: title.trim(),
      description: description.trim() || undefined,
    });

    setTitle('');
    setDescription('');
    setIsExpanded(false);
  };

  return (
    <form
      onSubmit={handleSubmit}
      className="rounded-xl border border-[var(--border)] bg-[var(--card)] p-4"
    >
      <div className="flex gap-3">
        <input
          type="text"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onFocus={() => setIsExpanded(true)}
          placeholder="Add a new item..."
          className="flex-1 rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 text-sm placeholder:text-[var(--muted)] focus:border-[var(--accent)] focus:outline-none"
        />
        <button
          type="submit"
          disabled={!title.trim() || isLoading}
          className="rounded-lg bg-[var(--accent)] px-4 py-2.5 text-sm font-medium text-white transition-all hover:bg-[var(--accent-dim)] disabled:cursor-not-allowed disabled:opacity-50"
        >
          {isLoading ? (
            <span className="flex items-center gap-2">
              <svg className="h-4 w-4 animate-spin" viewBox="0 0 24 24">
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                  fill="none"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
              Adding...
            </span>
          ) : (
            'Add'
          )}
        </button>
      </div>

      {/* Expandable description field */}
      {isExpanded && (
        <div className="mt-3 animate-slide-up">
          <textarea
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            placeholder="Description (optional)"
            className="w-full resize-none rounded-lg border border-[var(--border)] bg-[var(--background)] px-4 py-2.5 text-sm placeholder:text-[var(--muted)] focus:border-[var(--accent)] focus:outline-none"
            rows={2}
          />
          <div className="mt-2 flex justify-end">
            <button
              type="button"
              onClick={() => {
                setIsExpanded(false);
                setDescription('');
              }}
              className="text-xs text-[var(--muted)] hover:text-[var(--foreground)]"
            >
              Collapse
            </button>
          </div>
        </div>
      )}
    </form>
  );
}

