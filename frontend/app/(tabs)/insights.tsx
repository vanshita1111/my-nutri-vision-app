/**
 * Insights screen — 7-day macro trends, cycle phase card, weekly coaching summary.
 */

import { View, Text, ScrollView, StyleSheet, ActivityIndicator, RefreshControl } from "react-native";
import { useState, useCallback } from "react";
import { useQuery } from "@tanstack/react-query";
import { api, DailyNutrition, CyclePhase, WeeklySummary, UserProfile } from "@/services/api";
import { InsightsScreenSkeleton } from "@/components/SkeletonLoader";

export default function InsightsScreen() {
  const { data: daily, isLoading: loadingDaily, refetch: refetchDaily } = useQuery<DailyNutrition[]>({
    queryKey: ["daily-nutrition", 7],
    queryFn: () => api.getDailyNutrition(7),
  });

  const { data: profile, refetch: refetchProfile } = useQuery<UserProfile>({
    queryKey: ["profile"],
    queryFn: api.getProfile,
  });

  const showCycleCard = profile?.gender !== "male";

  const { data: cyclePhase, refetch: refetchCycle } = useQuery<CyclePhase>({
    queryKey: ["cycle-phase"],
    queryFn: () => api.getCyclePhase(),
    enabled: showCycleCard,
  });

  const { data: coaching, isLoading: loadingCoaching, refetch: refetchCoaching } = useQuery<WeeklySummary>({
    queryKey: ["weekly-summary"],
    queryFn: () => api.getWeeklySummary(),
    staleTime: 1000 * 60 * 30,
  });

  const [refreshing, setRefreshing] = useState(false);
  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([refetchDaily(), refetchProfile(), refetchCoaching(), ...(showCycleCard ? [refetchCycle()] : [])]);
    setRefreshing(false);
  }, [refetchDaily, refetchProfile, refetchCoaching, refetchCycle, showCycleCard]);

  if (loadingDaily && !daily) {
    return (
      <ScrollView
        style={styles.scroll}
        refreshControl={<RefreshControl refreshing={false} onRefresh={onRefresh} tintColor="#4CAF50" />}
      >
        <InsightsScreenSkeleton />
      </ScrollView>
    );
  }

  const avgCalories = daily && daily.length > 0
    ? Math.round(daily.reduce((s, d) => s + d.total_calories, 0) / daily.length)
    : 0;

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#4CAF50" />}
    >
      {/* 7-day average */}
      <View style={styles.avgCard}>
        <Text style={styles.avgLabel}>7-day average</Text>
        <Text style={styles.avgCal}>{avgCalories} kcal/day</Text>
        {coaching && coaching.streak_days > 0 && (
          <Text style={styles.streak}>🔥 {coaching.streak_days}-day logging streak</Text>
        )}
      </View>

      {/* Daily bars */}
      {daily && daily.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Daily calories</Text>
          {daily.map((d) => (
            <DailyBar key={d.date} day={d} max={Math.max(...daily.map(x => x.total_calories))} />
          ))}
        </View>
      )}

      {/* Weekly coaching summary */}
      <View style={styles.section}>
        <Text style={styles.sectionTitle}>Weekly coaching</Text>
        {loadingCoaching ? (
          <View style={styles.coachingCard}>
            <ActivityIndicator size="small" color="#4CAF50" />
          </View>
        ) : coaching ? (
          <View style={styles.coachingCard}>
            <Text style={styles.coachingSummary}>{coaching.summary}</Text>
            {coaching.tips.length > 0 && (
              <View style={styles.tipsContainer}>
                <Text style={styles.tipsTitle}>Actionable tips</Text>
                {coaching.tips.map((tip, i) => (
                  <View key={i} style={styles.tipRow}>
                    <Text style={styles.tipBullet}>{i + 1}</Text>
                    <Text style={styles.tipText}>{tip}</Text>
                  </View>
                ))}
              </View>
            )}
          </View>
        ) : null}
      </View>

      {/* Cycle phase card — female/other only */}
      {showCycleCard && cyclePhase && cyclePhase.phase !== "unknown" && (
        <View style={[styles.cycleCard, phaseColors[cyclePhase.phase]]}>
          <Text style={styles.cyclePhase}>
            {phaseEmoji[cyclePhase.phase]} {cyclePhase.phase.charAt(0).toUpperCase() + cyclePhase.phase.slice(1)} phase
          </Text>
          <Text style={styles.cycleDay}>Day {cyclePhase.day_in_cycle} of your cycle</Text>
          <Text style={styles.cycleNotes}>{cyclePhase.phase_notes}</Text>
          <Text style={styles.cycleSubtitle}>Today's focus foods:</Text>
          {cyclePhase.food_recommendations.slice(0, 4).map((rec, i) => (
            <Text key={i} style={styles.cycleRec}>• {rec}</Text>
          ))}
        </View>
      )}
    </ScrollView>
  );
}

function DailyBar({ day, max }: { day: DailyNutrition; max: number }) {
  const pct = max > 0 ? day.total_calories / max : 0;
  const label = new Date(day.date + "T12:00:00").toLocaleDateString([], { weekday: "short" });
  return (
    <View style={styles.barRow}>
      <Text style={styles.barLabel}>{label}</Text>
      <View style={styles.barBg}>
        <View style={[styles.barFill, { width: `${Math.round(pct * 100)}%` }]} />
      </View>
      <Text style={styles.barVal}>{Math.round(day.total_calories)}</Text>
    </View>
  );
}

const phaseColors: Record<string, object> = {
  menstrual:  { backgroundColor: "#FFEBEE" },
  follicular: { backgroundColor: "#E8F5E9" },
  ovulatory:  { backgroundColor: "#E3F2FD" },
  luteal:     { backgroundColor: "#FFF3E0" },
};

const phaseEmoji: Record<string, string> = {
  menstrual: "🌑", follicular: "🌒", ovulatory: "🌕", luteal: "🌖",
};

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: "#f5f5f5" },
  content: { padding: 16, paddingBottom: 40 },
  center: { flex: 1, justifyContent: "center", alignItems: "center" },

  avgCard: {
    backgroundColor: "#fff", borderRadius: 16, padding: 20, alignItems: "center",
    marginBottom: 20, shadowColor: "#000", shadowOpacity: 0.06, shadowRadius: 6, elevation: 2,
  },
  avgLabel: { color: "#888", fontSize: 13 },
  avgCal: { fontSize: 32, fontWeight: "800", color: "#212121", marginTop: 4 },
  streak: { marginTop: 8, color: "#FF6F00", fontWeight: "600", fontSize: 13 },

  section: { marginBottom: 24 },
  sectionTitle: { fontSize: 16, fontWeight: "700", marginBottom: 12, color: "#212121" },

  barRow: { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  barLabel: { width: 38, fontSize: 12, color: "#888" },
  barBg: { flex: 1, height: 12, backgroundColor: "#e0e0e0", borderRadius: 6, overflow: "hidden" },
  barFill: { height: 12, backgroundColor: "#4CAF50", borderRadius: 6 },
  barVal: { width: 44, textAlign: "right", fontSize: 12, color: "#666" },

  coachingCard: {
    backgroundColor: "#fff", borderRadius: 16, padding: 20,
    shadowColor: "#000", shadowOpacity: 0.06, shadowRadius: 6, elevation: 2,
    minHeight: 60, justifyContent: "center",
  },
  coachingSummary: { fontSize: 14, color: "#333", lineHeight: 22 },
  tipsContainer: { marginTop: 16 },
  tipsTitle: { fontWeight: "700", color: "#212121", marginBottom: 10, fontSize: 14 },
  tipRow: { flexDirection: "row", marginBottom: 10, alignItems: "flex-start" },
  tipBullet: {
    width: 22, height: 22, borderRadius: 11, backgroundColor: "#4CAF50",
    color: "#fff", fontWeight: "700", fontSize: 12, textAlign: "center",
    lineHeight: 22, marginRight: 10, marginTop: 1,
  },
  tipText: { flex: 1, fontSize: 13, color: "#444", lineHeight: 20 },

  cycleCard: {
    borderRadius: 16, padding: 20,
    shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 4, elevation: 1,
  },
  cyclePhase: { fontSize: 18, fontWeight: "700", color: "#333" },
  cycleDay: { color: "#666", marginTop: 4, fontSize: 13 },
  cycleNotes: { marginTop: 12, color: "#444", lineHeight: 20, fontSize: 14 },
  cycleSubtitle: { marginTop: 14, fontWeight: "600", color: "#333" },
  cycleRec: { color: "#555", marginTop: 4, fontSize: 13 },
});
