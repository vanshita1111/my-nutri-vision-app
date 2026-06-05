import { Redirect } from "expo-router";
import { useAuthStore } from "@/store/authStore";

export default function Index() {
  const { token, hydrated } = useAuthStore();

  if (!hydrated) return null;

  return <Redirect href={token ? "/(tabs)/home" : "/onboarding"} />;
}
