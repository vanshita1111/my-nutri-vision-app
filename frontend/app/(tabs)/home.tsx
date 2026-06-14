/**
 * Home screen — personalized greeting, today's calorie + macro progress,
 * quick scan CTA, and today's meal list.
 */

import {
  View, Text, ScrollView, StyleSheet, TouchableOpacity,
  ActivityIndicator, Animated, Easing, RefreshControl,
} from "react-native";
import { useRef, useEffect, useState, useCallback } from "react";
import { router } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { api, UserProfile, DailyNutrition, MealSummary } from "@/services/api";
import { HomeScreenSkeleton } from "@/components/SkeletonLoader";

interface DailyGoals {
  daily_calorie_goal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  cycle_calorie_adjustment: number;
}

function greeting() {
  const h = new Date().getHours();
  if (h < 12) return "Good morning";
  if (h < 17) return "Good afternoon";
  return "Good evening";
}

function todayLabel() {
  return new Date().toLocaleDateString([], { weekday: "long", day: "numeric", month: "long" });
}

// ── Animated progress bar fill ─────────────────────────────────────────────

function AnimatedBar({
  value,
  goal,
  color,
  delay = 0,
}: {
  value: number;
  goal: number;
  color: string;
  delay?: number;
}) {
  const anim = useRef(new Animated.Value(0)).current;
  const target = Math.min(value / Math.max(goal, 1), 1);

  useEffect(() => {
    Animated.timing(anim, {
      toValue: target,
      duration: 700,
      delay,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    }).start();
  }, [target]);

  const animWidth = anim.interpolate({ inputRange: [0, 1], outputRange: ["0%", "100%"] });

  return (
    <View style={barStyles.bg}>
      <Animated.View style={[barStyles.fill, { width: animWidth, backgroundColor: color }]} />
    </View>
  );
}

const barStyles = StyleSheet.create({
  bg:   { height: 6, backgroundColor: "#f0f0f0", borderRadius: 3, overflow: "hidden", marginBottom: 4 },
  fill: { height: 6, borderRadius: 3 },
});

// ── Animated calorie progress bar ─────────────────────────────────────────

function AnimatedCalBar({ pct }: { pct: number }) {
  const anim = useRef(new Animated.Value(0)).current;

  useEffect(() => {
    Animated.timing(anim, {
      toValue: Math.min(pct, 1),
      duration: 900,
      delay: 150,
      easing: Easing.out(Easing.cubic),
      useNativeDriver: false,
    }).start();
  }, [pct]);

  const animWidth = anim.interpolate({ inputRange: [0, 1], outputRange: ["0%", "100%"] });

  return (
    <View style={styles.progressBg}>
      <Animated.View style={[styles.progressFill, { width: animWidth }]} />
    </View>
  );
}

// ── Staggered meal card ────────────────────────────────────────────────────

function AnimatedMealRow({ meal, index }: { meal: MealSummary; index: number }) {
  const opacity    = useRef(new Animated.Value(0)).current;
  const translateY = useRef(new Animated.Value(14)).current;

  useEffect(() => {
    Animated.parallel([
      Animated.timing(opacity, {
        toValue: 1,
        duration: 300,
        delay: index * 70,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
      Animated.timing(translateY, {
        toValue: 0,
        duration: 300,
        delay: index * 70,
        easing: Easing.out(Easing.quad),
        useNativeDriver: true,
      }),
    ]).start();
  }, []);

  const time = new Date(meal.eaten_at).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });

  return (
    <Animated.View style={{ opacity, transform: [{ translateY }] }}>
      <TouchableOpacity
        style={styles.mealCard}
        onPress={() => router.push(`/meals/${meal.id}`)}
        activeOpacity={0.8}
      >
        <View style={styles.mealLeft}>
          <Text style={styles.mealName}>{meal.meal_type ?? "Meal"}</Text>
          <Text style={styles.mealMeta}>{time} · {meal.item_count} item{meal.item_count !== 1 ? "s" : ""}</Text>
        </View>
        <Text style={styles.mealCal}>
          {meal.total_calories ? Math.round(meal.total_calories) : "–"}
          {" "}<Text style={styles.mealKcal}>kcal</Text>
        </Text>
      </TouchableOpacity>
    </Animated.View>
  );
}

// ── Macro row item ─────────────────────────────────────────────────────────

function MacroBar({
  label, value, goal, color, unit, delay,
}: {
  label: string; value: number; goal: number; color: string; unit: string; delay: number;
}) {
  return (
    <View style={styles.macroItem}>
      <Text style={styles.macroLabel}>{label}</Text>
      <AnimatedBar value={value} goal={goal} color={color} delay={delay} />
      <Text style={styles.macroVal}>
        {Math.round(value)}<Text style={styles.macroGoal}>/{Math.round(goal)}{unit}</Text>
      </Text>
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────

export default function HomeScreen() {
  const { data: profile, isLoading: loadingProfile, refetch: refetchProfile } = useQuery<UserProfile>({
    queryKey: ["profile"],
    queryFn: api.getProfile,
  });

  const { data: goals, isLoading: loadingGoals, refetch: refetchGoals } = useQuery<DailyGoals>({
    queryKey: ["daily-goals"],
    queryFn: api.getDailyGoals as () => Promise<DailyGoals>,
  });

  const { data: daily, isLoading: loadingDaily, refetch: refetchDaily } = useQuery<DailyNutrition[]>({
    queryKey: ["daily-nutrition", 1],
    queryFn: () => api.getDailyNutrition(1),
  });

  const { data: meals, isLoading: loadingMeals, refetch: refetchMeals } = useQuery<MealSummary[]>({
    queryKey: ["meals", 20],
    queryFn: () => api.getMeals(20),
  });

  const [refreshing,    setRefreshing]    = useState(false);
  const [loadTimedOut, setLoadTimedOut]  = useState(false);

  // Safety net — stop showing skeleton after 8s regardless of query state
  useEffect(() => {
    const t = setTimeout(() => setLoadTimedOut(true), 8000);
    return () => clearTimeout(t);
  }, []);
  const onRefresh = useCallback(async () => {
    setRefreshing(true);
    await Promise.all([refetchProfile(), refetchGoals(), refetchDaily(), refetchMeals()]);
    setRefreshing(false);
  }, [refetchProfile, refetchGoals, refetchDaily, refetchMeals]);

  // Show skeleton only on first load — never indefinitely if network is down
  const anyLoading = loadingProfile || loadingGoals || loadingDaily || loadingMeals;
  const anyData    = !!(profile || goals || daily || meals);
  const showSkeleton = anyLoading && !anyData && !loadTimedOut;

  // Card entrance animation — declared unconditionally (Rules of Hooks)
  const cardOpacity = useRef(new Animated.Value(0)).current;
  const cardY       = useRef(new Animated.Value(20)).current;

  useEffect(() => {
    if (showSkeleton) return;
    cardOpacity.setValue(0);
    cardY.setValue(20);
    Animated.parallel([
      Animated.timing(cardOpacity, { toValue: 1, duration: 500, delay: 80, easing: Easing.out(Easing.quad), useNativeDriver: true }),
      Animated.timing(cardY, { toValue: 0, duration: 500, delay: 80, easing: Easing.out(Easing.quad), useNativeDriver: true }),
    ]).start();
  }, [showSkeleton]);

  const firstName = profile?.full_name?.split(" ")[0] ?? "there";
  const today     = daily?.[0];

  const consumed = {
    calories: today?.total_calories ?? 0,
    protein:  today?.total_protein_g ?? 0,
    carbs:    today?.total_carbs_g ?? 0,
    fat:      today?.total_fat_g ?? 0,
  };

  const calGoal   = goals?.daily_calorie_goal ?? 2000;
  const calPct    = consumed.calories / calGoal;
  const remaining = Math.max(0, Math.round(calGoal - consumed.calories));

  const todayStr   = new Date().toISOString().slice(0, 10);
  const todayMeals = (meals ?? []).filter((m) => m.eaten_at.slice(0, 10) === todayStr);

  if (showSkeleton) {
    return (
      <ScrollView
        style={styles.scroll}
        refreshControl={<RefreshControl refreshing={false} onRefresh={onRefresh} tintColor="#4CAF50" />}
      >
        <HomeScreenSkeleton />
      </ScrollView>
    );
  }

  return (
    <ScrollView
      style={styles.scroll}
      contentContainerStyle={styles.content}
      refreshControl={<RefreshControl refreshing={refreshing} onRefresh={onRefresh} tintColor="#4CAF50" />}
    >

      {/* ── Greeting ──────────────────────────────────────────────── */}
      <View style={styles.greetingRow}>
        <View>
          <Text style={styles.greetingText}>{greeting()}, {firstName}!</Text>
          <Text style={styles.dateText}>{todayLabel()}</Text>
        </View>
      </View>

      {/* ── Calorie card ──────────────────────────────────────────── */}
      <Animated.View style={[styles.card, { opacity: cardOpacity, transform: [{ translateY: cardY }] }]}>
        <Text style={styles.cardTitle}>Today's calories</Text>
        <View style={styles.calRow}>
          <View>
            <Text style={styles.calConsumed}>{Math.round(consumed.calories)}</Text>
            <Text style={styles.calLabel}>consumed</Text>
          </View>
          <View style={styles.calDivider} />
          <View style={{ alignItems: "center" }}>
            <Text style={styles.calGoalNum}>{calGoal}</Text>
            <Text style={styles.calLabel}>goal</Text>
          </View>
          <View style={styles.calDivider} />
          <View style={{ alignItems: "flex-end" }}>
            <Text style={[styles.calConsumed, { color: remaining === 0 ? "#4CAF50" : "#212121" }]}>
              {remaining}
            </Text>
            <Text style={styles.calLabel}>remaining</Text>
          </View>
        </View>

        <AnimatedCalBar pct={calPct} />
        <Text style={styles.progressPct}>{Math.round(Math.min(calPct, 1) * 100)}% of daily goal</Text>

        <View style={styles.macroRow}>
          <MacroBar label="Protein" value={consumed.protein} goal={goals?.protein_g ?? 50} color="#42A5F5" unit="g" delay={250} />
          <MacroBar label="Carbs"   value={consumed.carbs}   goal={goals?.carbs_g ?? 250}  color="#FFA726" unit="g" delay={350} />
          <MacroBar label="Fat"     value={consumed.fat}     goal={goals?.fat_g ?? 70}      color="#EF5350" unit="g" delay={450} />
        </View>
      </Animated.View>

      {/* ── Scan CTA ──────────────────────────────────────────────── */}
      <TouchableOpacity style={styles.scanBtn} onPress={() => router.push("/(tabs)/camera")} activeOpacity={0.85}>
        <Text style={styles.scanIcon}>📷</Text>
        <Text style={styles.scanText}>Scan a meal</Text>
        <Text style={styles.scanArrow}>→</Text>
      </TouchableOpacity>

      {/* ── Today's meals ─────────────────────────────────────────── */}
      <View style={styles.sectionHeader}>
        <Text style={styles.sectionTitle}>Today's meals</Text>
        {todayMeals.length > 0 && (
          <TouchableOpacity onPress={() => router.push("/(tabs)/history")}>
            <Text style={styles.seeAll}>See all</Text>
          </TouchableOpacity>
        )}
      </View>

      {loadingMeals ? (
        <ActivityIndicator color="#4CAF50" style={{ marginTop: 12 }} />
      ) : todayMeals.length === 0 ? (
        <View style={styles.emptyMeals}>
          <Text style={styles.emptyText}>No meals logged today yet.</Text>
          <Text style={styles.emptySubText}>Scan your first meal to get started!</Text>
        </View>
      ) : (
        todayMeals.slice(0, 4).map((meal, i) => (
          <AnimatedMealRow key={meal.id} meal={meal} index={i} />
        ))
      )}

    </ScrollView>
  );
}

const styles = StyleSheet.create({
  scroll:   { flex: 1, backgroundColor: "#f5f5f5" },
  content:  { padding: 16, paddingBottom: 48 },

  greetingRow: { marginBottom: 20, marginTop: 4 },
  greetingText: { fontSize: 24, fontWeight: "800", color: "#212121" },
  dateText:     { fontSize: 13, color: "#888", marginTop: 3 },

  card: {
    backgroundColor: "#fff", borderRadius: 18, padding: 18, marginBottom: 16,
    shadowColor: "#000", shadowOpacity: 0.07, shadowRadius: 8, elevation: 3,
  },
  cardTitle: { fontSize: 13, fontWeight: "600", color: "#888", marginBottom: 14, textTransform: "uppercase", letterSpacing: 0.5 },

  calRow: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 16 },
  calConsumed: { fontSize: 28, fontWeight: "800", color: "#212121" },
  calGoalNum:  { fontSize: 28, fontWeight: "800", color: "#9E9E9E" },
  calLabel:    { fontSize: 11, color: "#aaa", marginTop: 2, textAlign: "center" },
  calDivider:  { width: 1, height: 40, backgroundColor: "#f0f0f0" },

  progressBg:   { height: 10, backgroundColor: "#f0f0f0", borderRadius: 5, overflow: "hidden" },
  progressFill: { height: 10, backgroundColor: "#4CAF50", borderRadius: 5 },
  progressPct:  { fontSize: 12, color: "#aaa", marginTop: 6, textAlign: "right" },

  macroRow: { flexDirection: "row", marginTop: 18, gap: 12 },
  macroItem: { flex: 1 },
  macroLabel: { fontSize: 11, color: "#888", marginBottom: 5, fontWeight: "600" },
  macroVal:   { fontSize: 12, fontWeight: "700", color: "#333" },
  macroGoal:  { fontSize: 11, fontWeight: "400", color: "#aaa" },

  scanBtn: {
    backgroundColor: "#4CAF50", borderRadius: 16, padding: 18,
    flexDirection: "row", alignItems: "center", justifyContent: "space-between",
    marginBottom: 24,
    shadowColor: "#4CAF50", shadowOpacity: 0.35, shadowRadius: 8, shadowOffset: { width: 0, height: 4 },
    elevation: 4,
  },
  scanIcon: { fontSize: 22 },
  scanText: { flex: 1, color: "#fff", fontWeight: "700", fontSize: 17, marginLeft: 12 },
  scanArrow: { color: "rgba(255,255,255,0.8)", fontSize: 20, fontWeight: "300" },

  sectionHeader: { flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 10 },
  sectionTitle:  { fontSize: 16, fontWeight: "700", color: "#212121" },
  seeAll:        { fontSize: 13, color: "#4CAF50", fontWeight: "600" },

  emptyMeals:   { backgroundColor: "#fff", borderRadius: 14, padding: 24, alignItems: "center" },
  emptyText:    { fontSize: 15, fontWeight: "600", color: "#555" },
  emptySubText: { fontSize: 13, color: "#aaa", marginTop: 6, textAlign: "center" },

  mealCard: {
    backgroundColor: "#fff", borderRadius: 14, padding: 16, marginBottom: 8,
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    shadowColor: "#000", shadowOpacity: 0.05, shadowRadius: 4, elevation: 1,
  },
  mealLeft: { flex: 1 },
  mealName: { fontSize: 15, fontWeight: "700", color: "#212121", textTransform: "capitalize" },
  mealMeta: { fontSize: 12, color: "#aaa", marginTop: 3 },
  mealCal:  { fontSize: 20, fontWeight: "800", color: "#4CAF50" },
  mealKcal: { fontSize: 12, fontWeight: "400", color: "#aaa" },
});
