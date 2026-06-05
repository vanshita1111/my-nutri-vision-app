/**
 * Zustand auth store — persists JWT token to expo-secure-store.
 * Falls back to in-memory when SecureStore is unavailable (web/tests).
 */

import { create } from "zustand";
import { setAuthToken } from "@/services/api";

interface AuthState {
  token: string | null;
  hydrated: boolean;
  setToken: (token: string | null) => void;
  logout: () => void;
}

// Try to load SecureStore (not available in Expo Go web)
async function loadToken(): Promise<string | null> {
  try {
    const { getItemAsync } = await import("expo-secure-store");
    return await getItemAsync("auth_token");
  } catch {
    return null;
  }
}

async function saveToken(token: string | null): Promise<void> {
  try {
    const { setItemAsync, deleteItemAsync } = await import("expo-secure-store");
    if (token) {
      await setItemAsync("auth_token", token);
    } else {
      await deleteItemAsync("auth_token");
    }
  } catch {
    // Ignore — in-memory only
  }
}

export const useAuthStore = create<AuthState>((set) => {
  // Hydrate on first access — sync api token before marking hydrated
  loadToken().then((token) => {
    setAuthToken(token);
    set({ token, hydrated: true });
  });

  return {
    token: null,
    hydrated: false,

    setToken: (token) => {
      // Sync api client immediately so queries fired after navigation have auth
      setAuthToken(token);
      set({ token });
      saveToken(token);
    },

    logout: () => {
      setAuthToken(null);
      set({ token: null });
      saveToken(null);
    },
  };
});
