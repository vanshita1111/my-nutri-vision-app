/**
 * Root layout — sets up QueryClient, auth state, and font loading.
 * Uses expo-router's Stack navigator as the root container.
 */

import { useEffect } from "react";
import { Stack, useRouter, useSegments } from "expo-router";
import { StatusBar } from "expo-status-bar";
import { QueryClient, QueryClientProvider, useQueryClient } from "@tanstack/react-query";
import { GestureHandlerRootView } from "react-native-gesture-handler";
import { StyleSheet } from "react-native";
import * as SplashScreen from "expo-splash-screen";
import { useAuthStore } from "@/store/authStore";

// Keep splash screen visible until auth state is resolved (no-op on web)
SplashScreen.preventAutoHideAsync().catch(() => {});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime:  1000 * 60 * 5,   // 5 min
      gcTime:     1000 * 60 * 30,  // 30 min
      retry: 1,
    },
  },
});

function AuthGuard() {
  const { token, hydrated } = useAuthStore();
  const segments = useSegments();
  const router = useRouter();
  const qc = useQueryClient();

  useEffect(() => {
    if (!hydrated) return;

    const inAuthGroup = segments[0] === "(tabs)";
    const inOnboarding = segments[0] === "onboarding";

    if (!token && inAuthGroup) {
      // Clear cache so next login starts fresh
      qc.clear();
      router.replace("/onboarding");
    } else if (token && inOnboarding) {
      // Clear any pre-auth stale/error query states before entering the app
      qc.clear();
      router.replace("/(tabs)/home");
    }
  }, [token, hydrated, segments]);

  return null;
}

export default function RootLayout() {
  const { hydrated } = useAuthStore();

  useEffect(() => {
    if (hydrated) {
      SplashScreen.hideAsync().catch(() => {});
    }
  }, [hydrated]);

  if (!hydrated) return null;

  return (
    <GestureHandlerRootView style={styles.root}>
      <QueryClientProvider client={queryClient}>
        <StatusBar style="auto" />
        <Stack screenOptions={{ headerShown: false }}>
          <Stack.Screen name="index" />
          <Stack.Screen name="onboarding/index" />
          <Stack.Screen name="(tabs)" />
          <Stack.Screen name="analysis/[jobId]" options={{ presentation: "modal", headerShown: true, title: "Meal Analysis" }} />
          <Stack.Screen name="analysis/confirm"  options={{ presentation: "card",  headerShown: false }} />
          <Stack.Screen name="meals/[id]"        options={{ presentation: "card",  headerShown: false }} />
        </Stack>
        <AuthGuard />
      </QueryClientProvider>
    </GestureHandlerRootView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1 },
});
