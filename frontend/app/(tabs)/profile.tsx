/**
 * Profile screen — health goals, body stats, health conditions, cycle settings.
 * Loads current profile on mount and saves changes via PATCH /me.
 */

import { useState, useEffect } from "react";
import {
  View, Text, TextInput, ScrollView, StyleSheet,
  TouchableOpacity, Alert, ActivityIndicator,
} from "react-native";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { router } from "expo-router";
import { api, UserProfile } from "@/services/api";
import { useAuthStore } from "@/store/authStore";

interface DailyGoals {
  daily_calorie_goal: number;
  protein_g: number;
  carbs_g: number;
  fat_g: number;
  fiber_g: number;
  cycle_calorie_adjustment: number;
  condition_tips?: string[];
  setup_required?: boolean;
}

type ActivityLevel = "sedentary" | "light" | "moderate" | "active" | "very_active";
type Goal = "lose" | "maintain" | "gain";
type Gender = "male" | "female" | "other";

const ACTIVITY_OPTIONS: { key: ActivityLevel; label: string }[] = [
  { key: "sedentary",   label: "Sedentary" },
  { key: "light",       label: "Light" },
  { key: "moderate",    label: "Moderate" },
  { key: "active",      label: "Active" },
  { key: "very_active", label: "Very active" },
];

const GOAL_OPTIONS: { key: Goal; label: string }[] = [
  { key: "lose",     label: "Lose weight" },
  { key: "maintain", label: "Maintain" },
  { key: "gain",     label: "Gain muscle" },
];

const GENDER_OPTIONS: { key: Gender; label: string }[] = [
  { key: "male",   label: "Male" },
  { key: "female", label: "Female" },
  { key: "other",  label: "Other" },
];

interface HealthConditionOption {
  key: string;
  label: string;
  emoji: string;
}

const HEALTH_CONDITIONS: HealthConditionOption[] = [
  { key: "diabetes",          label: "Diabetes",           emoji: "🩸" },
  { key: "pcod",              label: "PCOD / PCOS",        emoji: "🔄" },
  { key: "hypertension",      label: "High BP",            emoji: "❤️" },
  { key: "hypothyroidism",    label: "Hypothyroidism",     emoji: "🦋" },
  { key: "high_cholesterol",  label: "High Cholesterol",   emoji: "🫀" },
  { key: "anemia",            label: "Anaemia",            emoji: "💊" },
  { key: "fatty_liver",       label: "Fatty Liver",        emoji: "🫁" },
  { key: "ibs",               label: "IBS",                emoji: "🌿" },
  { key: "lactose_intolerance", label: "Lactose Intolerant", emoji: "🥛" },
  { key: "gluten_sensitivity",  label: "Gluten Sensitivity",  emoji: "🌾" },
];

export default function ProfileScreen() {
  const qc = useQueryClient();
  const { logout } = useAuthStore();
  const [loadTimedOut, setLoadTimedOut] = useState(false);
  useEffect(() => {
    const t = setTimeout(() => setLoadTimedOut(true), 8000);
    return () => clearTimeout(t);
  }, []);

  const { data: profile, isLoading: loadingProfile } = useQuery<UserProfile>({
    queryKey: ["profile"],
    queryFn: api.getProfile,
  });

  const { data: goals } = useQuery<DailyGoals>({
    queryKey: ["daily-goals"],
    queryFn: api.getDailyGoals as () => Promise<DailyGoals>,
  });

  // Local form state
  const [gender, setGender]                       = useState<Gender | null>(null);
  const [lastPeriodDate, setLastPeriodDate]        = useState("");
  const [cycleLength, setCycleLength]              = useState("28");
  const [weightKg, setWeightKg]                   = useState("");
  const [heightCm, setHeightCm]                   = useState("");
  const [targetWeightKg, setTargetWeightKg]        = useState("");
  const [activityLevel, setActivityLevel]          = useState<ActivityLevel>("moderate");
  const [goal, setGoal]                            = useState<Goal>("maintain");
  const [selectedConditions, setSelectedConditions] = useState<string[]>([]);

  useEffect(() => {
    if (!profile) return;
    if (profile.weight_kg)          setWeightKg(String(profile.weight_kg));
    if (profile.height_cm)          setHeightCm(String(profile.height_cm));
    if (profile.target_weight_kg)   setTargetWeightKg(String(profile.target_weight_kg));
    if (profile.last_period_date)   setLastPeriodDate(profile.last_period_date);
    if (profile.cycle_length_days)  setCycleLength(String(profile.cycle_length_days));
    if (profile.activity_level)     setActivityLevel(profile.activity_level as ActivityLevel);
    if (profile.goal)               setGoal(profile.goal as Goal);
    if (profile.gender)             setGender(profile.gender as Gender);
    if (profile.health_conditions)  setSelectedConditions(profile.health_conditions);
  }, [profile]);

  function toggleCondition(key: string) {
    setSelectedConditions((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  }

  const isFemale = gender === "female" || gender === "other" || gender === null;

  const updateMutation = useMutation({
    mutationFn: async () => {
      const wt  = weightKg       ? parseFloat(weightKg)       : undefined;
      const ht  = heightCm       ? parseFloat(heightCm)       : undefined;
      const twt = targetWeightKg ? parseFloat(targetWeightKg) : undefined;
      const cl  = cycleLength    ? parseInt(cycleLength, 10)  : undefined;

      if (wt  !== undefined && (isNaN(wt)  || wt  < 20 || wt  > 300)) throw new Error("Weight must be between 20 and 300 kg.");
      if (ht  !== undefined && (isNaN(ht)  || ht  < 100 || ht > 250)) throw new Error("Height must be between 100 and 250 cm.");
      if (twt !== undefined && (isNaN(twt) || twt < 20 || twt > 300)) throw new Error("Target weight must be between 20 and 300 kg.");
      if (cl  !== undefined && (isNaN(cl)  || cl  < 19 || cl  > 44))  throw new Error("Cycle length must be between 19 and 44 days.");
      if (lastPeriodDate && !/^\d{4}-\d{2}-\d{2}$/.test(lastPeriodDate)) throw new Error("Last period date must be in YYYY-MM-DD format.");

      return api.updateProfile({
        weight_kg:         wt,
        height_cm:         ht,
        target_weight_kg:  twt,
        activity_level:    activityLevel,
        goal,
        gender:            gender ?? undefined,
        health_conditions: selectedConditions,
        last_period_date:  lastPeriodDate || undefined,
        cycle_length_days: cl,
      });
    },
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["profile"] });
      qc.invalidateQueries({ queryKey: ["cycle-phase"] });
      qc.invalidateQueries({ queryKey: ["daily-goals"] });
      qc.invalidateQueries({ queryKey: ["recommendations"] }); // goal/weight/activity changed
      qc.invalidateQueries({ queryKey: ["weekly-summary"] });  // cycle phase or goal may affect coaching
      Alert.alert("Saved!", "Your profile has been updated.");
    },
    onError: (e: Error) => Alert.alert("Could not save", e.message),
  });

  if (loadingProfile && !loadTimedOut) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#4CAF50" />
      </View>
    );
  }

  const isGuest = profile?.is_guest === true;

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
      <Text style={styles.heading}>Health Profile</Text>

      {/* Guest upgrade banner */}
      {isGuest && (
        <TouchableOpacity
          style={styles.guestBanner}
          onPress={() => router.replace("/onboarding")}
          activeOpacity={0.85}
        >
          <View style={styles.guestBannerLeft}>
            <Text style={styles.guestBannerTitle}>You're on a guest account</Text>
            <Text style={styles.guestBannerSub}>
              Create a free account to save your data, track progress, and unlock all features.
            </Text>
          </View>
          <Text style={styles.guestBannerArrow}>→</Text>
        </TouchableOpacity>
      )}

      {/* Daily goals summary */}
      {goals && !goals.setup_required && (
        <View style={styles.goalsCard}>
          <Text style={styles.cardTitle}>Today's targets</Text>
          <View style={styles.goalsRow}>
            <GoalPill label="Calories" value={goals.daily_calorie_goal} unit="kcal" />
            <GoalPill label="Protein"  value={goals.protein_g}          unit="g" />
            <GoalPill label="Carbs"    value={goals.carbs_g}            unit="g" />
            <GoalPill label="Fat"      value={goals.fat_g}              unit="g" />
          </View>
          {goals.cycle_calorie_adjustment !== 0 && (
            <Text style={styles.cycleAdj}>
              {goals.cycle_calorie_adjustment > 0 ? "+" : ""}
              {goals.cycle_calorie_adjustment} kcal cycle adjustment applied
            </Text>
          )}
        </View>
      )}

      {/* Setup prompt */}
      {goals?.setup_required && (
        <View style={styles.setupPrompt}>
          <Text style={styles.setupPromptText}>
            Add your weight and height below to unlock personalised calorie targets.
          </Text>
        </View>
      )}

      {/* Condition tips */}
      {goals?.condition_tips && goals.condition_tips.length > 0 && (
        <View style={styles.tipsCard}>
          <Text style={styles.cardTitle}>Tips for your health conditions</Text>
          {goals.condition_tips.slice(0, 5).map((tip, i) => (
            <View key={i} style={styles.tipRow}>
              <Text style={styles.tipBullet}>{i + 1}</Text>
              <Text style={styles.tipText}>{tip}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Gender */}
      <Text style={styles.sectionTitle}>Biological sex</Text>
      <View style={styles.chipRow}>
        {GENDER_OPTIONS.map((opt) => (
          <TouchableOpacity
            key={opt.key}
            style={[styles.chip, gender === opt.key && styles.chipActive]}
            onPress={() => setGender(opt.key)}
          >
            <Text style={[styles.chipText, gender === opt.key && styles.chipTextActive]}>
              {opt.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Health conditions */}
      <Text style={styles.sectionTitle}>Health conditions</Text>
      <Text style={styles.sectionNote}>Select all that apply — we'll adjust your targets accordingly.</Text>
      <View style={styles.conditionGrid}>
        {HEALTH_CONDITIONS.map((opt) => {
          const active = selectedConditions.includes(opt.key);
          return (
            <TouchableOpacity
              key={opt.key}
              style={[styles.conditionChip, active && styles.conditionChipActive]}
              onPress={() => toggleCondition(opt.key)}
              activeOpacity={0.75}
            >
              <Text style={styles.conditionEmoji}>{opt.emoji}</Text>
              <Text style={[styles.conditionLabel, active && styles.conditionLabelActive]}>
                {opt.label}
              </Text>
            </TouchableOpacity>
          );
        })}
      </View>

      {/* Body stats */}
      <Text style={styles.sectionTitle}>Body measurements</Text>
      <LabeledInput label="Current weight (kg)" value={weightKg} onChangeText={setWeightKg} keyboardType="decimal-pad" placeholder="e.g. 62" />
      <LabeledInput label="Target weight (kg)"  value={targetWeightKg} onChangeText={setTargetWeightKg} keyboardType="decimal-pad" placeholder="e.g. 55" />
      <LabeledInput label="Height (cm)"          value={heightCm} onChangeText={setHeightCm} keyboardType="decimal-pad" placeholder="e.g. 165" />

      {/* Activity level */}
      <Text style={styles.sectionTitle}>Activity level</Text>
      <View style={styles.chipRow}>
        {ACTIVITY_OPTIONS.map((opt) => (
          <TouchableOpacity
            key={opt.key}
            style={[styles.chip, activityLevel === opt.key && styles.chipActive]}
            onPress={() => setActivityLevel(opt.key)}
          >
            <Text style={[styles.chipText, activityLevel === opt.key && styles.chipTextActive]}>
              {opt.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Goal */}
      <Text style={styles.sectionTitle}>Goal</Text>
      <View style={styles.chipRow}>
        {GOAL_OPTIONS.map((opt) => (
          <TouchableOpacity
            key={opt.key}
            style={[styles.chip, goal === opt.key && styles.chipActive]}
            onPress={() => setGoal(opt.key)}
          >
            <Text style={[styles.chipText, goal === opt.key && styles.chipTextActive]}>
              {opt.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>

      {/* Cycle settings — only for female / other / unset */}
      {isFemale && (
        <>
          <Text style={styles.sectionTitle}>Menstrual cycle</Text>
          <LabeledInput
            label="Last period start date (YYYY-MM-DD)"
            value={lastPeriodDate}
            onChangeText={setLastPeriodDate}
            placeholder="e.g. 2026-05-10"
          />
          <LabeledInput
            label="Average cycle length (days)"
            value={cycleLength}
            onChangeText={setCycleLength}
            keyboardType="number-pad"
            placeholder="e.g. 28"
          />
        </>
      )}

      <TouchableOpacity
        style={[styles.saveBtn, updateMutation.isLoading && styles.saveBtnDisabled]}
        onPress={() => updateMutation.mutate()}
        disabled={updateMutation.isLoading}
      >
        {updateMutation.isLoading
          ? <ActivityIndicator color="#fff" />
          : <Text style={styles.saveBtnText}>Save profile</Text>
        }
      </TouchableOpacity>

      <TouchableOpacity style={styles.logoutBtn} onPress={logout}>
        <Text style={styles.logoutBtnText}>Log out</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

function GoalPill({ label, value, unit }: { label: string; value: number; unit: string }) {
  return (
    <View style={styles.goalPill}>
      <Text style={styles.goalVal}>{Math.round(value)}</Text>
      <Text style={styles.goalUnit}>{unit}</Text>
      <Text style={styles.goalLabel}>{label}</Text>
    </View>
  );
}

function LabeledInput({ label, ...props }: { label: string } & React.ComponentProps<typeof TextInput>) {
  return (
    <View style={styles.inputGroup}>
      <Text style={styles.inputLabel}>{label}</Text>
      <TextInput style={styles.input} placeholderTextColor="#aaa" {...props} />
    </View>
  );
}

const styles = StyleSheet.create({
  scroll:   { flex: 1, backgroundColor: "#f5f5f5" },
  content:  { padding: 16, paddingBottom: 48 },
  center:   { flex: 1, justifyContent: "center", alignItems: "center" },
  heading:  { fontSize: 24, fontWeight: "800", marginBottom: 20 },

  guestBanner: {
    backgroundColor: "#1B5E20", borderRadius: 16, padding: 16, marginBottom: 16,
    flexDirection: "row", alignItems: "center",
  },
  guestBannerLeft: { flex: 1 },
  guestBannerTitle: { color: "#fff", fontWeight: "700", fontSize: 14, marginBottom: 4 },
  guestBannerSub: { color: "rgba(255,255,255,0.75)", fontSize: 12, lineHeight: 18 },
  guestBannerArrow: { color: "rgba(255,255,255,0.6)", fontSize: 20, marginLeft: 12 },

  goalsCard: {
    backgroundColor: "#fff", borderRadius: 16, padding: 18, marginBottom: 16,
    shadowColor: "#000", shadowOpacity: 0.06, shadowRadius: 6, elevation: 2,
  },
  cardTitle:  { fontWeight: "700", marginBottom: 12 },
  goalsRow:   { flexDirection: "row", justifyContent: "space-between" },
  goalPill:   { alignItems: "center" },
  goalVal:    { fontSize: 22, fontWeight: "800", color: "#4CAF50" },
  goalUnit:   { fontSize: 11, color: "#aaa" },
  goalLabel:  { fontSize: 11, color: "#888", marginTop: 2 },
  cycleAdj:   { marginTop: 12, color: "#888", fontSize: 12, textAlign: "center" },

  setupPrompt: {
    backgroundColor: "#FFF8E1", borderRadius: 12, padding: 14, marginBottom: 16,
    borderWidth: 1, borderColor: "#FFE082",
  },
  setupPromptText: { color: "#795548", fontSize: 13, lineHeight: 20 },

  tipsCard: {
    backgroundColor: "#E8F5E9", borderRadius: 16, padding: 16, marginBottom: 16,
  },
  tipRow:    { flexDirection: "row", alignItems: "flex-start", marginTop: 8 },
  tipBullet: {
    width: 20, height: 20, borderRadius: 10, backgroundColor: "#4CAF50",
    color: "#fff", fontWeight: "700", fontSize: 11, textAlign: "center",
    lineHeight: 20, marginRight: 8, marginTop: 1,
  },
  tipText: { flex: 1, fontSize: 13, color: "#2E7D32", lineHeight: 19 },

  sectionTitle: { fontWeight: "700", fontSize: 16, marginTop: 24, marginBottom: 6 },
  sectionNote:  { fontSize: 12, color: "#888", marginBottom: 10 },

  chipRow: { flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 4 },
  chip: {
    paddingHorizontal: 14, paddingVertical: 8, borderRadius: 20,
    backgroundColor: "#fff", borderWidth: 1.5, borderColor: "#e0e0e0",
  },
  chipActive:     { backgroundColor: "#E8F5E9", borderColor: "#4CAF50" },
  chipText:       { fontSize: 13, color: "#666", fontWeight: "600" },
  chipTextActive: { color: "#4CAF50" },

  conditionGrid: {
    flexDirection: "row", flexWrap: "wrap", gap: 8, marginBottom: 4,
  },
  conditionChip: {
    flexDirection: "row", alignItems: "center", gap: 6,
    paddingHorizontal: 12, paddingVertical: 8, borderRadius: 20,
    backgroundColor: "#fff", borderWidth: 1.5, borderColor: "#e0e0e0",
  },
  conditionChipActive: { backgroundColor: "#E8F5E9", borderColor: "#4CAF50" },
  conditionEmoji:      { fontSize: 14 },
  conditionLabel:      { fontSize: 12, color: "#666", fontWeight: "600" },
  conditionLabelActive:{ color: "#4CAF50" },

  inputGroup:  { marginBottom: 14 },
  inputLabel:  { color: "#555", fontSize: 13, marginBottom: 4 },
  input: {
    backgroundColor: "#fff", borderRadius: 10, padding: 14,
    fontSize: 15, borderWidth: 1, borderColor: "#e0e0e0",
  },

  saveBtn: {
    marginTop: 28, backgroundColor: "#4CAF50",
    borderRadius: 14, padding: 18, alignItems: "center",
  },
  saveBtnDisabled: { opacity: 0.6 },
  saveBtnText: { color: "#fff", fontSize: 17, fontWeight: "700" },

  logoutBtn: {
    marginTop: 12, borderRadius: 14, padding: 18, alignItems: "center",
    borderWidth: 1.5, borderColor: "#e53935",
  },
  logoutBtnText: { color: "#e53935", fontSize: 17, fontWeight: "700" },
});
