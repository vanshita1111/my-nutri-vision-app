/**
 * Insights screen — 7-day trends, cycle phase, weekly coaching,
 * and workout plan (today's session + full-week toggle).
 */

import { useState, useCallback } from "react";
import {
  View, Text, ScrollView, StyleSheet,
  ActivityIndicator, RefreshControl, TouchableOpacity,
} from "react-native";
import { useQuery } from "@tanstack/react-query";
import {
  api, DailyNutrition, CyclePhase, WeeklySummary,
  UserProfile, Recommendations, WorkoutDay,
} from "@/services/api";
import { InsightsScreenSkeleton } from "@/components/SkeletonLoader";

// ── Helpers ───────────────────────────────────────────────────────────────────

const DAY_NAMES = ["Sunday","Monday","Tuesday","Wednesday","Thursday","Friday","Saturday"];

function todayWorkout(plan: WorkoutDay[]): WorkoutDay | null {
  if (!plan?.length) return null;
  const todayName = DAY_NAMES[new Date().getDay()];
  return plan.find((d) => d.day === todayName) ?? plan[0];
}

const WORKOUT_COLORS: Record<string, string> = {
  "Strength":        "#3F51B5",
  "HIIT":            "#F44336",
  "Cardio":          "#00BCD4",
  "Cardio + Core":   "#009688",
  "Active Recovery": "#8BC34A",
  "Rest":            "#9E9E9E",
};

// Cycle phase — text symbols instead of moon emojis
const PHASE_SYMBOL: Record<string, string> = {
  menstrual:  "●",
  follicular: "◐",
  ovulatory:  "○",
  luteal:     "◑",
};

const PHASE_COLORS: Record<string, object> = {
  menstrual:  { backgroundColor: "#FFEBEE" },
  follicular: { backgroundColor: "#E8F5E9" },
  ovulatory:  { backgroundColor: "#E3F2FD" },
  luteal:     { backgroundColor: "#FFF3E0" },
};

// ── Sub-components ─────────────────────────────────────────────────────────────

function DailyBar({ day, max }: { day: DailyNutrition; max: number }) {
  const pct   = max > 0 ? day.total_calories / max : 0;
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

function MacroRow({ day }: { day: DailyNutrition }) {
  return (
    <View style={styles.macroMiniRow}>
      <MacroChip color="#4CAF50" label="P" value={day.total_protein_g} />
      <MacroChip color="#FF9800" label="C" value={day.total_carbs_g} />
      <MacroChip color="#F44336" label="F" value={day.total_fat_g} />
    </View>
  );
}

function MacroChip({ color, label, value }: { color: string; label: string; value: number }) {
  return (
    <View style={[styles.macroChip, { borderColor: color + "55" }]}>
      <Text style={[styles.macroChipLabel, { color }]}>{label}</Text>
      <Text style={styles.macroChipVal}>{Math.round(value)}g</Text>
    </View>
  );
}

function WorkoutDayCard({ day, defaultExpanded = false }: { day: WorkoutDay; defaultExpanded?: boolean }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const isRest = day.workout_type === "Rest";
  const color  = WORKOUT_COLORS[day.workout_type] ?? "#757575";

  return (
    <TouchableOpacity
      style={[styles.workoutDayCard, isRest && styles.workoutDayRest]}
      onPress={() => !isRest && setExpanded((v) => !v)}
      activeOpacity={isRest ? 1 : 0.75}
    >
      <View style={styles.workoutDayHeader}>
        <View style={[styles.workoutTypeBadge, { backgroundColor: color + "22" }]}>
          <Text style={[styles.workoutTypeText, { color }]}>{day.workout_type}</Text>
        </View>
        <View style={styles.workoutDayMeta}>
          <Text style={styles.workoutDayName}>{day.day}</Text>
          <Text style={styles.workoutDayFocus}>{day.focus}</Text>
        </View>
        {day.duration_mins > 0 && (
          <Text style={styles.workoutDuration}>{day.duration_mins} min</Text>
        )}
        {!isRest && (
          <Text style={styles.workoutChevron}>{expanded ? "▲" : "▼"}</Text>
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
                <Text style={styles.exerciseSets}>
                  {ex.sets > 0 ? `${ex.sets} × ` : ""}{ex.reps}
                </Text>
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

// ── Main screen ───────────────────────────────────────────────────────────────

export default function InsightsScreen() {
  const [showFullWeek, setShowFullWeek]   = useState(false);
  const [refreshing,   setRefreshing]     = useState(false);

  const { data: daily,   isLoading: loadingDaily,   refetch: refetchDaily   } = useQuery<DailyNutrition[]>({
    queryKey: ["daily-nutrition", 7],
    queryFn:  () => api.getDailyNutrition(7),
  });

  const { data: profile, refetch: refetchProfile } = useQuery<UserProfile>({
    queryKey: ["profile"],
    queryFn:  api.getProfile,
  });

  const showCycleCard = profile?.gender !== "male";

  const { data: cyclePhase, refetch: refetchCycle } = useQuery<CyclePhase>({
    queryKey: ["cycle-phase"],
    queryFn:  () => api.getCyclePhase(),
    enabled:  showCycleCard,
  });

  const { data: coaching, isLoading: loadingCoaching, refetch: refetchCoaching } = useQuery<WeeklySummary>({
    queryKey: ["weekly-summary"],
    queryFn:  () => api.getWeeklySummary(),
    staleTime: 1000 * 60 * 30,
  });

  const { data: rec, refetch: refetchRec } = useQuery<Recommendations>({
    queryKey: ["recommendations"],
    queryFn:  api.getRecommendations,
    staleTime: 1000 * 60 * 60,
    enabled:  !!(profile?.goal && profile?.weight_kg),
  });

  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([
      refetchDaily(),
      refetchProfile(),
      refetchCoaching(),
      refetchRec(),
      ...(showCycleCard ? [refetchCycle()] : []),
    ]);
    setRefreshing(false);
  }, [refetchDaily, refetchProfile, refetchCoaching, refetchCycle, refetchRec, showCycleCard]);

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

  const avgCalories = daily?.length
    ? Math.round(daily.reduce((s, d) => s + d.total_calories, 0) / daily.length)
    : 0;

  const todaySession = rec?.workout_plan ? todayWorkout(rec.workout_plan) : null;

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#4CAF50" />}
    >

      {/* ── 7-day average ─────────────────────────────────────── */}
      <View style={styles.avgCard}>
        <Text style={styles.avgLabel}>7-day average</Text>
        <Text style={styles.avgCal}>{avgCalories} kcal/day</Text>
        {coaching && coaching.streak_days > 0 && (
          <Text style={styles.streak}>
            ★ {coaching.streak_days}-day logging streak
          </Text>
        )}
      </View>

      {/* ── Daily calorie bars ────────────────────────────────── */}
      {daily && daily.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Daily calories</Text>
          {daily.map((d) => (
            <DailyBar key={d.date} day={d} max={Math.max(...daily.map((x) => x.total_calories), 1)} />
          ))}
        </View>
      )}

      {/* ── Macro breakdown (last day) ────────────────────────── */}
      {daily && daily.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Today's macros</Text>
          <MacroRow day={daily[daily.length - 1]} />
        </View>
      )}

      {/* ── Weekly coaching ───────────────────────────────────── */}
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

      {/* ── Workout plan ─────────────────────────────────────── */}
      {rec && rec.workout_plan.length > 0 && (
        <View style={styles.section}>
          <View style={styles.sectionRow}>
            <Text style={styles.sectionTitle}>Workout</Text>
            {rec.daily_steps > 0 && (
              <Text style={styles.stepsBadge}>
                {rec.daily_steps.toLocaleString()} steps/day
              </Text>
            )}
          </View>

          {/* Daily targets strip */}
          <View style={styles.targetsRow}>
            <View style={styles.targetChip}>
              <Text style={styles.targetVal}>{rec.water_glasses}</Text>
              <Text style={styles.targetLbl}>glasses water</Text>
            </View>
            <View style={styles.targetDivider} />
            <View style={styles.targetChip}>
              <Text style={styles.targetVal}>
                {rec.workout_plan.filter((d) => d.workout_type !== "Rest").length}
              </Text>
              <Text style={styles.targetLbl}>workout days/wk</Text>
            </View>
            <View style={styles.targetDivider} />
            <View style={styles.targetChip}>
              <Text style={styles.targetVal}>{rec.water_ml}</Text>
              <Text style={styles.targetLbl}>ml/day</Text>
            </View>
          </View>

          {/* Goal + timeline */}
          {rec.goal_timeline_estimate ? (
            <View style={styles.timelineCard}>
              <Text style={styles.timelineLabel}>Timeline estimate</Text>
              <Text style={styles.timelineText}>{rec.goal_timeline_estimate}</Text>
            </View>
          ) : null}

          {/* Today's session */}
          {todaySession && (
            <>
              <Text style={styles.subsectionLabel}>Today — {DAY_NAMES[new Date().getDay()]}</Text>
              <WorkoutDayCard day={todaySession} defaultExpanded />
            </>
          )}

          {/* Full week toggle */}
          <TouchableOpacity
            style={styles.toggleWeekBtn}
            onPress={() => setShowFullWeek((v) => !v)}
          >
            <Text style={styles.toggleWeekText}>
              {showFullWeek ? "▲  Hide full week" : "▼  Show full week"}
            </Text>
          </TouchableOpacity>

          {showFullWeek &&
            rec.workout_plan
              .filter((d) => d.day !== DAY_NAMES[new Date().getDay()])
              .map((day, i) => <WorkoutDayCard key={i} day={day} />)
          }
        </View>
      )}

      {/* Profile not set — prompt */}
      {!rec && profile && (!profile.goal || !profile.weight_kg) && (
        <View style={styles.setupPrompt}>
          <Text style={styles.setupSymbol}>◎</Text>
          <Text style={styles.setupTitle}>Set your goal to unlock workout plan</Text>
          <Text style={styles.setupSub}>
            Add your weight, height, and goal in Profile to get a personalised plan.
          </Text>
        </View>
      )}

      {/* ── Cycle phase card ──────────────────────────────────── */}
      {showCycleCard && cyclePhase && cyclePhase.phase !== "unknown" && (
        <View style={[styles.cycleCard, PHASE_COLORS[cyclePhase.phase]]}>
          <Text style={styles.cyclePhaseText}>
            <Text style={styles.cycleSymbol}>{PHASE_SYMBOL[cyclePhase.phase] ?? "●"}  </Text>
            {cyclePhase.phase.charAt(0).toUpperCase() + cyclePhase.phase.slice(1)} phase
          </Text>
          <Text style={styles.cycleDay}>Day {cyclePhase.day_in_cycle} of your cycle</Text>
          <Text style={styles.cycleNotes}>{cyclePhase.phase_notes}</Text>
          <Text style={styles.cycleSubtitle}>Today's focus foods:</Text>
          {cyclePhase.food_recommendations.slice(0, 4).map((rec, i) => (
            <Text key={i} style={styles.cycleRec}>+ {rec}</Text>
          ))}
        </View>
      )}

    </ScrollView>
  );
}

// ── Styles ─────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  scroll:   { flex: 1, backgroundColor: "#f5f5f5" },
  content:  { padding: 16, paddingBottom: 48 },

  avgCard: {
    backgroundColor: "#fff", borderRadius: 16, padding: 20, alignItems: "center",
    marginBottom: 20, shadowColor: "#000", shadowOpacity: 0.06, shadowRadius: 6, elevation: 2,
  },
  avgLabel: { color: "#888", fontSize: 13 },
  avgCal:   { fontSize: 32, fontWeight: "800", color: "#212121", marginTop: 4 },
  streak:   { marginTop: 8, color: "#FF6F00", fontWeight: "600", fontSize: 13 },

  section:      { marginBottom: 24 },
  sectionRow:   { flexDirection: "row", alignItems: "center", justifyContent: "space-between", marginBottom: 12 },
  sectionTitle: { fontSize: 16, fontWeight: "700", color: "#212121", marginBottom: 12 },
  stepsBadge:   { fontSize: 12, color: "#4CAF50", fontWeight: "600" },
  subsectionLabel: { fontSize: 13, fontWeight: "700", color: "#888", marginBottom: 8, textTransform: "uppercase" },

  barRow:   { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  barLabel: { width: 38, fontSize: 12, color: "#888" },
  barBg:    { flex: 1, height: 12, backgroundColor: "#e0e0e0", borderRadius: 6, overflow: "hidden" },
  barFill:  { height: 12, backgroundColor: "#4CAF50", borderRadius: 6 },
  barVal:   { width: 44, textAlign: "right", fontSize: 12, color: "#666" },

  macroMiniRow: { flexDirection: "row", gap: 8 },
  macroChip: {
    flexDirection: "row", alignItems: "center", gap: 4,
    borderWidth: 1, borderRadius: 8,
    paddingHorizontal: 10, paddingVertical: 6,
    backgroundColor: "#fff",
  },
  macroChipLabel: { fontSize: 11, fontWeight: "700" },
  macroChipVal:   { fontSize: 13, fontWeight: "700", color: "#212121" },

  coachingCard: {
    backgroundColor: "#fff", borderRadius: 16, padding: 20,
    shadowColor: "#000", shadowOpacity: 0.06, shadowRadius: 6, elevation: 2,
    minHeight: 60, justifyContent: "center",
  },
  coachingSummary: { fontSize: 14, color: "#333", lineHeight: 22 },
  tipsContainer:   { marginTop: 16 },
  tipsTitle:       { fontWeight: "700", color: "#212121", marginBottom: 10, fontSize: 14 },
  tipRow:   { flexDirection: "row", marginBottom: 10, alignItems: "flex-start" },
  tipBullet: {
    width: 22, height: 22, borderRadius: 11, backgroundColor: "#4CAF50",
    color: "#fff", fontWeight: "700", fontSize: 12,
    textAlign: "center", lineHeight: 22, marginRight: 10, marginTop: 1,
  },
  tipText: { flex: 1, fontSize: 13, color: "#444", lineHeight: 20 },

  // Workout
  targetsRow:    { flexDirection: "row", backgroundColor: "#fff", borderRadius: 14, padding: 14, marginBottom: 12, alignItems: "center", shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 4, elevation: 1 },
  targetChip:    { flex: 1, alignItems: "center" },
  targetVal:     { fontSize: 20, fontWeight: "800", color: "#212121" },
  targetLbl:     { fontSize: 10, color: "#888", marginTop: 2, textAlign: "center" },
  targetDivider: { width: 1, height: 32, backgroundColor: "#f0f0f0" },

  timelineCard: {
    backgroundColor: "#fff", borderRadius: 12, padding: 12, marginBottom: 12,
    borderLeftWidth: 4, borderLeftColor: "#4CAF50",
  },
  timelineLabel: { fontSize: 10, color: "#888", fontWeight: "700", textTransform: "uppercase", marginBottom: 3 },
  timelineText:  { fontSize: 13, color: "#333", lineHeight: 20 },

  workoutDayCard: {
    backgroundColor: "#fff", borderRadius: 14, padding: 14, marginBottom: 10,
    shadowColor: "#000", shadowOpacity: 0.05, shadowRadius: 4, elevation: 1,
  },
  workoutDayRest:   { opacity: 0.55 },
  workoutDayHeader: { flexDirection: "row", alignItems: "center", gap: 10 },
  workoutTypeBadge: { borderRadius: 8, paddingHorizontal: 8, paddingVertical: 3 },
  workoutTypeText:  { fontSize: 11, fontWeight: "700" },
  workoutDayMeta:   { flex: 1 },
  workoutDayName:   { fontSize: 15, fontWeight: "700", color: "#212121" },
  workoutDayFocus:  { fontSize: 12, color: "#888", marginTop: 1 },
  workoutDuration:  { fontSize: 13, fontWeight: "700", color: "#4CAF50" },
  workoutChevron:   { fontSize: 11, color: "#bbb", marginLeft: 4 },
  cardioNote:       { fontSize: 12, color: "#888", marginTop: 8, fontStyle: "italic" },

  exerciseList: { marginTop: 14, borderTopWidth: 1, borderTopColor: "#f0f0f0", paddingTop: 10, gap: 8 },
  exerciseRow:  { flexDirection: "row", justifyContent: "space-between", alignItems: "flex-start", paddingVertical: 6, borderBottomWidth: 1, borderBottomColor: "#fafafa" },
  exerciseLeft:  { flex: 1, paddingRight: 8 },
  exerciseName:  { fontSize: 13, fontWeight: "600", color: "#212121" },
  exerciseNote:  { fontSize: 11, color: "#aaa", marginTop: 2 },
  exerciseRight: { alignItems: "flex-end" },
  exerciseSets:  { fontSize: 13, fontWeight: "700", color: "#4CAF50" },
  exerciseRest:  { fontSize: 11, color: "#aaa", marginTop: 2 },

  toggleWeekBtn: {
    alignItems: "center", paddingVertical: 10, marginBottom: 8,
    borderWidth: 1, borderColor: "#e0e0e0", borderRadius: 10,
    backgroundColor: "#fff",
  },
  toggleWeekText: { fontSize: 13, color: "#888", fontWeight: "600" },

  setupPrompt:  { backgroundColor: "#fff", borderRadius: 16, padding: 24, alignItems: "center", marginBottom: 24 },
  setupSymbol:  { fontSize: 28, color: "#4CAF50", marginBottom: 10 },
  setupTitle:   { fontSize: 15, fontWeight: "700", color: "#212121", textAlign: "center", marginBottom: 6 },
  setupSub:     { fontSize: 13, color: "#888", textAlign: "center", lineHeight: 20 },

  // Cycle
  cycleCard:     { borderRadius: 16, padding: 20, shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 4, elevation: 1 },
  cyclePhaseText:{ fontSize: 18, fontWeight: "700", color: "#333" },
  cycleSymbol:   { fontSize: 16 },
  cycleDay:      { color: "#666", marginTop: 4, fontSize: 13 },
  cycleNotes:    { marginTop: 12, color: "#444", lineHeight: 20, fontSize: 14 },
  cycleSubtitle: { marginTop: 14, fontWeight: "600", color: "#333" },
  cycleRec:      { color: "#555", marginTop: 4, fontSize: 13 },
});
