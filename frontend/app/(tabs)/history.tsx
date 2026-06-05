/**
 * Meal history screen — shows past logged meals with daily totals.
 */

import {
  View, Text, FlatList, StyleSheet, TouchableOpacity,
  ActivityIndicator, RefreshControl, Alert,
} from "react-native";
import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { api, MealSummary } from "@/services/api";
import { HistoryScreenSkeleton } from "@/components/SkeletonLoader";

export default function HistoryScreen() {
  const qc = useQueryClient();
  const { data: meals, isLoading, error, refetch } = useQuery<MealSummary[]>({
    queryKey: ["meals", 30],
    queryFn: () => api.getMeals(30),
  });

  const [refreshing, setRefreshing] = useState(false);
  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await refetch();
    setRefreshing(false);
  }, [refetch]);

  const deleteMealMutation = useMutation({
    mutationFn: (mealId: string) => api.deleteMeal(mealId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["meals"] });
      qc.invalidateQueries({ queryKey: ["daily-nutrition"] });
      qc.invalidateQueries({ queryKey: ["weekly-summary"] });
    },
    onError: (err: Error) => Alert.alert("Error", err.message),
  });

  function confirmDeleteMeal(meal: MealSummary) {
    const label = meal.meal_type ?? "Meal";
    const date  = new Date(meal.eaten_at).toLocaleDateString([], { month: "short", day: "numeric" });
    Alert.alert(
      "Delete meal?",
      `Remove "${label}" from ${date}? This can't be undone.`,
      [
        { text: "Cancel", style: "cancel" },
        { text: "Delete", style: "destructive", onPress: () => deleteMealMutation.mutate(meal.id) },
      ]
    );
  }

  if (isLoading && !meals) {
    return (
      <FlatList
        style={styles.list}
        data={[]}
        renderItem={() => null}
        ListHeaderComponent={<HistoryScreenSkeleton />}
        refreshControl={<RefreshControl refreshing={false} onRefresh={onRefresh} tintColor="#4CAF50" />}
      />
    );
  }

  if (error || !meals) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Could not load meal history.</Text>
      </View>
    );
  }

  if (meals.length === 0) {
    return (
      <View style={styles.center}>
        <Text style={styles.emptyText}>No meals logged yet.</Text>
        <Text style={styles.subText}>Tap the camera tab to analyse your first meal!</Text>
      </View>
    );
  }

  return (
    <FlatList
      style={styles.list}
      data={meals}
      keyExtractor={(m) => m.id}
      renderItem={({ item }) => (
        <MealCard
          meal={item}
          onDelete={() => confirmDeleteMeal(item)}
          deleting={deleteMealMutation.isLoading && (deleteMealMutation.variables as string) === item.id}
        />
      )}
      contentContainerStyle={{ padding: 16, paddingBottom: 40 }}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#4CAF50" />}
    />
  );
}

function MealCard({
  meal,
  onDelete,
  deleting,
}: {
  meal: MealSummary;
  onDelete: () => void;
  deleting: boolean;
}) {
  const time = new Date(meal.eaten_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
  const date = new Date(meal.eaten_at).toLocaleDateString([], { weekday: "short", month: "short", day: "numeric" });

  return (
    <TouchableOpacity
      style={styles.card}
      onPress={() => router.push(`/meals/${meal.id}`)}
      activeOpacity={0.8}
    >
      <View style={styles.cardLeft}>
        <Text style={styles.mealType}>{meal.meal_type ?? "Meal"}</Text>
        <Text style={styles.mealTime}>{date} · {time}</Text>
        <Text style={styles.itemCount}>{meal.item_count} item{meal.item_count !== 1 ? "s" : ""}</Text>
      </View>
      <View style={styles.cardRight}>
        <Text style={styles.calories}>
          {meal.total_calories ? Math.round(meal.total_calories) : "–"}
        </Text>
        <Text style={styles.kcalLabel}>kcal</Text>
        <TouchableOpacity
          onPress={onDelete}
          hitSlop={8}
          style={styles.deleteBtn}
          disabled={deleting}
        >
          {deleting
            ? <ActivityIndicator size="small" color="#e53935" />
            : <Text style={styles.deleteIcon}>🗑</Text>
          }
        </TouchableOpacity>
      </View>
    </TouchableOpacity>
  );
}

const styles = StyleSheet.create({
  list: { flex: 1, backgroundColor: "#f5f5f5" },
  center: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24 },
  errorText: { color: "#e53935", fontSize: 16 },
  emptyText: { fontSize: 18, fontWeight: "600", color: "#333" },
  subText: { color: "#888", marginTop: 8, textAlign: "center" },
  card: {
    flexDirection: "row", backgroundColor: "#fff", borderRadius: 14,
    padding: 16, marginBottom: 10,
    shadowColor: "#000", shadowOpacity: 0.06, shadowRadius: 6, elevation: 2,
    justifyContent: "space-between", alignItems: "center",
  },
  cardLeft: { flex: 1 },
  mealType: { fontSize: 15, fontWeight: "700", textTransform: "capitalize" },
  mealTime: { color: "#888", fontSize: 12, marginTop: 2 },
  itemCount: { color: "#aaa", fontSize: 11, marginTop: 4 },
  cardRight: { alignItems: "flex-end" },
  calories: { fontSize: 28, fontWeight: "800", color: "#4CAF50" },
  kcalLabel: { fontSize: 11, color: "#aaa" },
  deleteBtn: { marginTop: 6, padding: 2 },
  deleteIcon: { fontSize: 15, opacity: 0.45 },
});
