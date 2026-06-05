/**
 * Plan screen — personalised workout plan, steps/water targets,
 * supplement stack, and lifestyle tips based on the user's profile.
 */

import { useState, useCallback } from "react";
import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  ActivityIndicator, RefreshControl,
} from "react-native";
import { useQuery } from "@tanstack/react-query";
import { router } from "expo-router";
import { api, Recommendations, WorkoutDay, Supplement, UserProfile } from "@/services/api";
import { PlanScreenSkeleton } from "@/components/SkeletonLoader";

const PRIORITY_COLOR: Record<string, string> = {
  essential:   "#4CAF50",
  recommended: "#FF9800",
  optional:    "#9E9E9E",
};

const WORKOUT_TYPE_COLOR: Record<string, string> = {
  "Strength":         "#3F51B5",
  "HIIT":             "#F44336",
  "Cardio":           "#00BCD4",
  "Cardio + Core":    "#009688",
  "Active Recovery":  "#8BC34A",
  "Rest":             "#9E9E9E",
};

const GOAL_LABELS: Record<string, string> = {
  lose:     "Weight Loss",
  maintain: "Maintenance",
  gain:     "Muscle Building",
};

// ── Sub-components ─────────────────────────────────────────────────────────────

function StatCard({ emoji, value, label, sub }: { emoji: string; value: string; label: string; sub?: string }) {
  return (
    <View style={styles.statCard}>
      <Text style={styles.statEmoji}>{emoji}</Text>
      <Text style={styles.statValue}>{value}</Text>
      <Text style={styles.statLabel}>{label}</Text>
      {sub ? <Text style={styles.statSub}>{sub}</Text> : null}
    </View>
  );
}

function DayCard({ day }: { day: WorkoutDay }) {
  const [expanded, setExpanded] = useState(false);
  const isRest = day.workout_type === "Rest";
  const color  = WORKOUT_TYPE_COLOR[day.workout_type] ?? "#757575";

  return (
    <TouchableOpacity
      style={[styles.dayCard, isRest && styles.dayCardRest]}
      onPress={() => !isRest && setExpanded((v) => !v)}
      activeOpacity={isRest ? 1 : 0.75}
    >
      <View style={styles.dayHeader}>
        <View style={[styles.dayTypeBadge, { backgroundColor: color + "22" }]}>
          <Text style={[styles.dayTypeText, { color }]}>{day.workout_type}</Text>
        </View>
        <View style={styles.dayHeaderRight}>
          <Text style={styles.dayName}>{day.day}</Text>
          <Text style={styles.dayFocus}>{day.focus}</Text>
        </View>
        {day.duration_mins > 0 && (
          <Text style={styles.dayDuration}>{day.duration_mins}m</Text>
        )}
        {!isRest && (
          <Text style={styles.dayChevron}>{expanded ? "▲" : "▼"}</Text>
        )}
      </View>

      {day.cardio_note ? (
        <Text style={styles.cardioNote}>{day.cardio_note}</Text>
      ) : null}

      {expanded && day.exercises.length > 0 && (
        <View style={styles.exerciseList}>
          {day.exercises.map((ex, i) => (
            <View key={i} style={styles.exerciseRow}>
              <View style={styles.exerciseLeft}>
                <Text style={styles.exerciseName}>{ex.name}</Text>
                {ex.note ? <Text style={styles.exerciseNote}>{ex.note}</Text> : null}
              </View>
              <View style={styles.exerciseRight}>
                <Text style={styles.exerciseSets}>{ex.sets > 0 ? `${ex.sets} × ` : ""}{ex.reps}</Text>
                {ex.rest_sec > 0 && (
                  <Text style={styles.exerciseRest}>{ex.rest_sec}s rest</Text>
                )}
              </View>
            </View>
          ))}
        </View>
      )}
    </TouchableOpacity>
  );
}

function SupplementRow({ s }: { s: Supplement }) {
  const color = PRIORITY_COLOR[s.priority] ?? "#9E9E9E";
  return (
    <View style={styles.suppRow}>
      <View style={styles.suppLeft}>
        <View style={styles.suppNameRow}>
          <Text style={styles.suppName}>{s.name}</Text>
          <View style={[styles.prioTag, { backgroundColor: color + "22" }]}>
            <Text style={[styles.prioText, { color }]}>{s.priority}</Text>
          </View>
        </View>
        <Text style={styles.suppReason}>{s.reason}</Text>
        <Text style={styles.suppMeta}>{s.timing}{s.dose ? `  ·  ${s.dose}` : ""}</Text>
      </View>
    </View>
  );
}

// ── Main screen ────────────────────────────────────────────────────────────────

export default function PlanScreen() {
  const { data: profile, isLoading: loadingProfile, refetch: refetchProfile } = useQuery<UserProfile>({
    queryKey: ["profile"],
    queryFn: api.getProfile,
  });

  const { data: rec, isLoading: loadingRec, isError, refetch: refetchRec } = useQuery<Recommendations>({
    queryKey: ["recommendations"],
    queryFn: api.getRecommendations,
    staleTime: 1000 * 60 * 60,
  });

  const [activeSection, setActiveSection] = useState<"workout" | "supplements" | "tips">("workout");
  const [refreshing, setRefreshing] = useState(false);

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([refetchProfile(), refetchRec()]);
    setRefreshing(false);
  }, [refetchProfile, refetchRec]);

  if (!profile && loadingProfile) {
    return (
      <ScrollView
        style={styles.scroll}
        refreshControl={<RefreshControl refreshing={false} onRefresh={onRefresh} tintColor="#4CAF50" />}
      >
        <PlanScreenSkeleton />
      </ScrollView>
    );
  }

  if (!profile?.goal || !profile?.weight_kg) {
    return (
      <View style={styles.emptyWrap}>
        <Text style={styles.emptyEmoji}>🎯</Text>
        <Text style={styles.emptyTitle}>Set your goal first</Text>
        <Text style={styles.emptySub}>
          Add your weight, height, and goal in Profile to get a personalised workout plan and supplement guide.
        </Text>
        <TouchableOpacity style={styles.emptyBtn} onPress={() => router.push("/(tabs)/profile")}>
          <Text style={styles.emptyBtnText}>Go to Profile</Text>
        </TouchableOpacity>
      </View>
    );
  }

  if (loadingRec && !rec) {
    return (
      <ScrollView
        style={styles.scroll}
        refreshControl={<RefreshControl refreshing={false} onRefresh={onRefresh} tintColor="#4CAF50" />}
      >
        <PlanScreenSkeleton />
      </ScrollView>
    );
  }

  if (isError || !rec) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Could not load your plan. Check your connection.</Text>
      </View>
    );
  }

  const goalLabel = GOAL_LABELS[profile.goal] ?? profile.goal;

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#4CAF50" />}
    >

      {/* Goal banner */}
      <View style={styles.goalBanner}>
        <View>
          <Text style={styles.goalBannerTitle}>Your Plan: {goalLabel}</Text>
          <Text style={styles.goalBannerSub}>{rec.weekly_workout_summary}</Text>
        </View>
      </View>

      {/* Timeline */}
      <View style={styles.timelineCard}>
        <Text style={styles.timelineLabel}>Timeline estimate</Text>
        <Text style={styles.timelineText}>{rec.goal_timeline_estimate}</Text>
      </View>

      {/* Stats row */}
      <View style={styles.statsRow}>
        <StatCard
          emoji="👟"
          value={rec.daily_steps.toLocaleString()}
          label="Steps / day"
        />
        <StatCard
          emoji="💧"
          value={`${rec.water_glasses}`}
          label="Glasses / day"
          sub={`${rec.water_ml} ml`}
        />
        <StatCard
          emoji="🏋️"
          value={`${rec.workout_plan.filter(d => d.workout_type !== "Rest").length}`}
          label="Workout days"
          sub="per week"
        />
      </View>

      {/* Section tabs */}
      <View style={styles.sectionTabs}>
        {(["workout", "supplements", "tips"] as const).map((s) => (
          <TouchableOpacity
            key={s}
            style={[styles.sectionTab, activeSection === s && styles.sectionTabActive]}
            onPress={() => setActiveSection(s)}
          >
            <Text style={[styles.sectionTabText, activeSection === s && styles.sectionTabTextActive]}>
              {s === "workout" ? "Workout" : s === "supplements" ? "Supplements" : "Tips"}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* ── Workout plan ─────────────────────────────────────── */}
      {activeSection === "workout" && (
        <View>
          <Text style={styles.sectionHint}>Tap a day to expand exercises</Text>
          {rec.workout_plan.map((day, i) => (
            <DayCard key={i} day={day} />
          ))}
        </View>
      )}

      {/* ── Supplements ──────────────────────────────────────── */}
      {activeSection === "supplements" && (
        <View>
          <Text style={styles.sectionHint}>
            These are general evidence-based suggestions — always consult your doctor before starting supplements.
          </Text>
          {["essential", "recommended", "optional"].map((prio) => {
            const group = rec.supplements.filter((s) => s.priority === prio);
            if (!group.length) return null;
            return (
              <View key={prio} style={styles.suppGroup}>
                <View style={[styles.suppGroupHeader, { borderLeftColor: PRIORITY_COLOR[prio] }]}>
                  <Text style={[styles.suppGroupTitle, { color: PRIORITY_COLOR[prio] }]}>
                    {prio.charAt(0).toUpperCase() + prio.slice(1)}
                  </Text>
                </View>
                {group.map((s, i) => <SupplementRow key={i} s={s} />)}
              </View>
            );
          })}
        </View>
      )}

      {/* ── Lifestyle tips ────────────────────────────────────── */}
      {activeSection === "tips" && (
        <View style={styles.tipsCard}>
          {rec.lifestyle_tips.map((tip, i) => (
            <View key={i} style={styles.tipRow}>
              <View style={styles.tipNum}>
                <Text style={styles.tipNumText}>{i + 1}</Text>
              </View>
              <Text style={styles.tipText}>{tip}</Text>
            </View>
          ))}
        </View>
      )}

    </ScrollView>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  scroll:  { flex: 1, backgroundColor: "#f5f5f5" },
  content: { padding: 16, paddingBottom: 48 },
  center:  { flex: 1, justifyContent: "center", alignItems: "center", padding: 24 },
  errorText: { color: "#888", textAlign: "center", fontSize: 14 },

  emptyWrap:    { flex: 1, alignItems: "center", justifyContent: "center", padding: 32 },
  emptyEmoji:   { fontSize: 56, marginBottom: 16 },
  emptyTitle:   { fontSize: 22, fontWeight: "800", color: "#212121", textAlign: "center" },
  emptySub:     { color: "#888", textAlign: "center", marginTop: 8, lineHeight: 22, fontSize: 14 },
  emptyBtn:     { marginTop: 24, backgroundColor: "#4CAF50", borderRadius: 14, paddingHorizontal: 28, paddingVertical: 14 },
  emptyBtnText: { color: "#fff", fontWeight: "700", fontSize: 15 },

  goalBanner: {
    backgroundColor: "#1B5E20", borderRadius: 18, padding: 18, marginBottom: 12,
  },
  goalBannerTitle: { color: "#fff", fontSize: 18, fontWeight: "800", marginBottom: 6 },
  goalBannerSub:   { color: "rgba(255,255,255,0.75)", fontSize: 13, lineHeight: 20 },

  timelineCard: {
    backgroundColor: "#fff", borderRadius: 14, padding: 14, marginBottom: 14,
    borderLeftWidth: 4, borderLeftColor: "#4CAF50",
  },
  timelineLabel: { fontSize: 11, color: "#888", fontWeight: "700", textTransform: "uppercase", marginBottom: 4 },
  timelineText:  { fontSize: 13, color: "#333", lineHeight: 20 },

  statsRow: { flexDirection: "row", gap: 10, marginBottom: 18 },
  statCard: {
    flex: 1, backgroundColor: "#fff", borderRadius: 14, padding: 14, alignItems: "center",
    shadowColor: "#000", shadowOpacity: 0.05, shadowRadius: 4, elevation: 1,
  },
  statEmoji: { fontSize: 24, marginBottom: 6 },
  statValue: { fontSize: 20, fontWeight: "800", color: "#212121" },
  statLabel: { fontSize: 10, color: "#888", marginTop: 2, textAlign: "center" },
  statSub:   { fontSize: 10, color: "#aaa", textAlign: "center" },

  sectionTabs: {
    flexDirection: "row", backgroundColor: "#fff", borderRadius: 12, padding: 4, marginBottom: 16,
    shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 4, elevation: 1,
  },
  sectionTab: {
    flex: 1, paddingVertical: 9, alignItems: "center", borderRadius: 9,
  },
  sectionTabActive:     { backgroundColor: "#4CAF50" },
  sectionTabText:       { fontSize: 13, fontWeight: "600", color: "#888" },
  sectionTabTextActive: { color: "#fff" },

  sectionHint: { fontSize: 12, color: "#aaa", marginBottom: 10, textAlign: "center" },

  // Workout day cards
  dayCard: {
    backgroundColor: "#fff", borderRadius: 14, padding: 14, marginBottom: 10,
    shadowColor: "#000", shadowOpacity: 0.05, shadowRadius: 4, elevation: 1,
  },
  dayCardRest: { opacity: 0.6 },
  dayHeader:      { flexDirection: "row", alignItems: "center", gap: 10 },
  dayTypeBadge:   { borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  dayTypeText:    { fontSize: 11, fontWeight: "700" },
  dayHeaderRight: { flex: 1 },
  dayName:        { fontSize: 15, fontWeight: "700", color: "#212121" },
  dayFocus:       { fontSize: 12, color: "#888", marginTop: 1 },
  dayDuration:    { fontSize: 13, fontWeight: "700", color: "#4CAF50" },
  dayChevron:     { fontSize: 11, color: "#bbb", marginLeft: 4 },
  cardioNote:     { fontSize: 12, color: "#888", marginTop: 8, fontStyle: "italic" },

  exerciseList: { marginTop: 14, borderTopWidth: 1, borderTopColor: "#f0f0f0", paddingTop: 10, gap: 8 },
  exerciseRow: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start",
    paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: "#fafafa",
  },
  exerciseLeft:  { flex: 1, paddingRight: 8 },
  exerciseName:  { fontSize: 13, fontWeight: "600", color: "#212121" },
  exerciseNote:  { fontSize: 11, color: "#aaa", marginTop: 2 },
  exerciseRight: { alignItems: "flex-end" },
  exerciseSets:  { fontSize: 13, fontWeight: "700", color: "#4CAF50" },
  exerciseRest:  { fontSize: 11, color: "#aaa", marginTop: 2 },

  // Supplements
  suppGroup: { marginBottom: 18 },
  suppGroupHeader: { borderLeftWidth: 3, paddingLeft: 10, marginBottom: 10 },
  suppGroupTitle:  { fontWeight: "700", fontSize: 13, textTransform: "uppercase" },
  suppRow: {
    backgroundColor: "#fff", borderRadius: 12, padding: 14, marginBottom: 8,
    shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 3, elevation: 1,
  },
  suppLeft:    { flex: 1 },
  suppNameRow: { flexDirection: "row", alignItems: "center", gap: 8, marginBottom: 4 },
  suppName:    { fontSize: 14, fontWeight: "700", color: "#212121", flex: 1 },
  prioTag:     { borderRadius: 6, paddingHorizontal: 6, paddingVertical: 2 },
  prioText:    { fontSize: 10, fontWeight: "700" },
  suppReason:  { fontSize: 12, color: "#555", lineHeight: 18, marginBottom: 4 },
  suppMeta:    { fontSize: 11, color: "#aaa" },

  // Tips
  tipsCard: {
    backgroundColor: "#fff", borderRadius: 16, padding: 18,
    shadowColor: "#000", shadowOpacity: 0.05, shadowRadius: 4, elevation: 1,
  },
  tipRow:     { flexDirection: "row", alignItems: "flex-start", marginBottom: 16 },
  tipNum:     {
    width: 24, height: 24, borderRadius: 12, backgroundColor: "#4CAF50",
    alignItems: "center", justifyContent: "center", marginRight: 12, marginTop: 1,
  },
  tipNumText: { color: "#fff", fontSize: 12, fontWeight: "700" },
  tipText:    { flex: 1, fontSize: 13, color: "#333", lineHeight: 20 },
});
