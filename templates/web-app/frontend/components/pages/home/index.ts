/**
 * Home page components, actions, and logic.
 * 
 * This folder contains everything specific to the home page:
 * - Components (HomeHero, HomeFeatures, HomeDemo)
 * - Server Actions (actions.ts) for data fetching
 * - Any page-specific hooks or utilities
 */

// Components
export { HomeHero } from './HomeHero';
export { HomeFeatures } from './HomeFeatures';
export { HomeDemo } from './HomeDemo';

// Server Actions
export {
  getItems,
  createItem,
  updateItem,
  deleteItem,
  toggleItemComplete,
} from './actions';
