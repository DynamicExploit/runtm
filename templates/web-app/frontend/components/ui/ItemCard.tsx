'use client';

import { useState } from 'react';
import type { Item } from '@/types';
import { useItemsStore } from '@/lib/store';

interface ItemCardProps {
  item: Item;
}

export function ItemCard({ item }: ItemCardProps) {
  const { updateItem, deleteItem, toggleComplete } = useItemsStore();
  const [isEditing, setIsEditing] = useState(false);
  const [editTitle, setEditTitle] = useState(item.title);
  const [editDescription, setEditDescription] = useState(item.description || '');
  const [isDeleting, setIsDeleting] = useState(false);

  const handleSave = async () => {
    await updateItem(item.id, {
      title: editTitle,
      description: editDescription || null,
    });
    setIsEditing(false);
  };

  const handleDelete = async () => {
    setIsDeleting(true);
    await deleteItem(item.id);
  };

  const handleCancel = () => {
    setEditTitle(item.title);
    setEditDescription(item.description || '');
    setIsEditing(false);
  };

  return (
    <div
      className={`group rounded-xl border border-[var(--border)] bg-[var(--card)] p-4 transition-all hover:border-[var(--accent)]/30 ${
        isDeleting ? 'animate-fade-out opacity-50' : ''
      }`}
    >
      {isEditing ? (
        <div className="space-y-3">
          <input
            type="text"
            value={editTitle}
            onChange={(e) => setEditTitle(e.target.value)}
            className="w-full rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:border-[var(--accent)] focus:outline-none"
            placeholder="Title"
          />
          <textarea
            value={editDescription}
            onChange={(e) => setEditDescription(e.target.value)}
            className="w-full resize-none rounded-lg border border-[var(--border)] bg-[var(--background)] px-3 py-2 text-sm focus:border-[var(--accent)] focus:outline-none"
            placeholder="Description (optional)"
            rows={2}
          />
          <div className="flex gap-2">
            <button
              onClick={handleSave}
              className="rounded-lg bg-[var(--accent)] px-3 py-1.5 text-xs font-medium text-white transition-colors hover:bg-[var(--accent-dim)]"
            >
              Save
            </button>
            <button
              onClick={handleCancel}
              className="rounded-lg border border-[var(--border)] px-3 py-1.5 text-xs font-medium transition-colors hover:bg-white/5"
            >
              Cancel
            </button>
          </div>
        </div>
      ) : (
        <div className="flex items-start gap-3">
          {/* Checkbox */}
          <input
            type="checkbox"
            checked={item.completed}
            onChange={() => toggleComplete(item.id)}
            className="mt-1 flex-shrink-0"
          />

          {/* Content */}
          <div className="flex-1 min-w-0">
            <h3
              className={`font-medium ${
                item.completed ? 'text-[var(--muted)] line-through' : ''
              }`}
            >
              {item.title}
            </h3>
            {item.description && (
              <p className="mt-1 text-sm text-[var(--muted)]">{item.description}</p>
            )}
            <p className="mt-2 text-xs text-[var(--muted)]">
              Created {new Date(item.created_at).toLocaleDateString()}
            </p>
          </div>

          {/* Actions */}
          <div className="flex gap-2 opacity-0 transition-opacity group-hover:opacity-100">
            <button
              onClick={() => setIsEditing(true)}
              className="rounded-lg p-1.5 text-[var(--muted)] transition-colors hover:bg-white/5 hover:text-[var(--foreground)]"
              title="Edit"
            >
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"
                />
              </svg>
            </button>
            <button
              onClick={handleDelete}
              className="rounded-lg p-1.5 text-[var(--muted)] transition-colors hover:bg-[var(--error)]/10 hover:text-[var(--error)]"
              title="Delete"
            >
              <svg
                className="h-4 w-4"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={1.5}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"
                />
              </svg>
            </button>
          </div>
        </div>
      )}
    </div>
  );
}

