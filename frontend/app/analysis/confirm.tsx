/**
 * Portion Confirmation Screen (V1)
 *
 * After analysis completes, lets the user adjust portion sizes before saving.
 * Accessed from analysis/[jobId].tsx via router.push("/analysis/confirm").
 *
 * Receives analysis result through Zustand (confirmStore) so no URL params
 * need to be serialised.
 */

import { useState, useCallback } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from "react-native";
import { router } from "expo-router";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { create } from "zustand";
import { api, AnalysisResult, FoodItemResult } from "@/services/api";

// ── Confirmation store (cleared after save) ───────────────────────────────────

interface ConfirmStore {
  jobId: string | null;
  result: AnalysisResult | null;
  setConfirmData: (jobId: string, result: AnalysisResult) => void;
  clear: () => void;
}

export const useConfirmStore = create<ConfirmStore>((set) => ({
  jobId:  null,
  result: null,
  setConfirmData: (jobId, result) => set({ jobId, result }),
  clear: () => set({ jobId: null, result: null }),
}));

// ── Portion multipliers ───────────────────────────────────────────────────────

const PORTIONS = [
  { label: "½",  multiplier: 0.5  },
  { label: "¾",  multiplier: 0.75 },
  { label: "1×", multiplier: 1.0  },
  { label: "1½", multiplier: 1.5  },
  { label: "2×", multiplier: 2.0  },
];

// ── Sub-component ─────────────────────────────────────────────────────────────

function PortionRow({
  item,
  multiplier,
  onChangeMultiplier,
}: {
  item: FoodItemResult;
  multiplier: number;
  onChangeMultiplier: (m: number) => void;
}) {
  const adjGrams    = item.grams * multiplier;
  const adjCalories = item.nutrition.calories * multiplier;

  return (
    <View style={styles.portionRow}>
      <View style={styles.portionInfo}>
        <Text style={styles.portionLabel}>{item.label}</Text>
        <Text style={styles.portionDetail}>
          {adjGrams.toFixed(0)} g · {adjCalories.toFixed(0)} kcal
        </Text>
      </View>
      <View style={styles.portionBtns}>
        {PORTIONS.map((p) => (
          <TouchableOpacity
            key={p.label}
            style={[
              styles.portionBtn,
              multiplier === p.multiplier && styles.portionBtnActive,
            ]}
            onPress={() => onChangeMultiplier(p.multiplier)}
          >
            <Text
              style={[
                styles.portionBtnText,
                multiplier === p.multiplier && styles.portionBtnTextActive,
              ]}
            >
              {p.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────

export default function ConfirmScreen() {
  const { jobId, result, clear } = useConfirmStore();
  const qc = useQueryClient();

  // Per-item multipliers keyed by index
  const [multipliers, setMultipliers] = useState<Record<number, number>>(() =>
    Object.fromEntries((result?.items ?? []).map((_, i) => [i, 1.0]))
  );

  const setMultiplier = useCallback((index: number, m: number) => {
    setMultipliers((prev) => ({ ...prev, [index]: m }));
  }, []);

  const saveMutation = useMutation({
    mutationFn: async () => {
      if (!jobId) throw new Error("No job ID");
      const meal = await api.saveMeal(jobId);
      // Match saved food items back to analysis result items by label so that
      // DB return-order differences don't apply the wrong multiplier.
      const adjustments = meal.food_items
        .map((fi) => {
          const resultIdx = result!.items.findIndex(
            (it) => it.label.toLowerCase() === fi.label.toLowerCase()
          );
          return { food_item_id: fi.id, multiplier: resultIdx >= 0 ? (multipliers[resultIdx] ?? 1) : 1 };
        })
        .filter((a) => a.multiplier !== 1.0);
      if (adjustments.length > 0) {
        return api.adjustPortions(meal.id, adjustments);
      }
      return meal;
    },
    onSuccess: (meal) => {
      // Invalidate all data that depends on the new meal being logged
      qc.invalidateQueries({ queryKey: ["meals"] });
      qc.invalidateQueries({ queryKey: ["daily-nutrition"] });
      qc.invalidateQueries({ queryKey: ["weekly-summary"] });
      clear();
      router.replace(`/meals/${meal.id}`);
    },
    onError: (err: Error) => Alert.alert("Save failed", err.message),
  });

  if (!result || !jobId) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>No analysis to confirm.</Text>
        <TouchableOpacity onPress={() => router.replace("/(tabs)/camera")} style={styles.retryBtn}>
          <Text style={styles.retryBtnText}>Take a new photo</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // Compute totals with adjustments
  const adjustedTotal = result.items.reduce(
    (acc, item, i) => {
      const m = multipliers[i] ?? 1;
      acc.calories  += item.nutrition.calories  * m;
      acc.protein_g += item.nutrition.protein_g * m;
      acc.fat_g     += item.nutrition.fat_g     * m;
      acc.carbs_g   += item.nutrition.carbs_g   * m;
      acc.fiber_g   += item.nutrition.fiber_g   * m;
      return acc;
    },
    { calories: 0, protein_g: 0, fat_g: 0, carbs_g: 0, fiber_g: 0 }
  );

  // Preserve original indices so multiplier keys always match result.items positions,
  // even when hidden items appear between visible ones in the array.
  const indexedItems   = result.items.map((item, originalIndex) => ({ item, originalIndex }));
  const visibleIndexed = indexedItems.filter(({ item }) => !item.is_hidden_ingredient);
  const hiddenIndexed  = indexedItems.filter(({ item }) =>  item.is_hidden_ingredient);

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={8}>
          <Text style={styles.backArrow}>←</Text>
        </TouchableOpacity>
        <Text style={styles.title}>Confirm Portions</Text>
      </View>

      <Text style={styles.subtitle}>
        Adjust serving sizes if they look off — we'll save the corrected values.
      </Text>

      {/* Adjusted totals */}
      <View style={styles.totalCard}>
        <Text style={styles.totalCal}>{adjustedTotal.calories.toFixed(0)}</Text>
        <Text style={styles.totalUnit}>kcal</Text>
        <View style={styles.macroRow}>
          {[
            { label: "P", value: adjustedTotal.protein_g, color: "#4CAF50" },
            { label: "C", value: adjustedTotal.carbs_g,   color: "#FF9800" },
            { label: "F", value: adjustedTotal.fat_g,     color: "#F44336" },
          ].map((m) => (
            <View key={m.label} style={styles.macroPill}>
              <View style={[styles.macroDot, { backgroundColor: m.color }]} />
              <Text style={styles.macroText}>
                {m.label} {m.value.toFixed(1)}g
              </Text>
            </View>
          ))}
        </View>
      </View>

      {/* Detected items — keyed by original index so multipliers stay correct */}
      <Text style={styles.sectionTitle}>Detected items</Text>
      {visibleIndexed.map(({ item, originalIndex }) => (
        <PortionRow
          key={originalIndex}
          item={item}
          multiplier={multipliers[originalIndex] ?? 1}
          onChangeMultiplier={(m) => setMultiplier(originalIndex, m)}
        />
      ))}

      {/* Hidden ingredients (display only — can't adjust) */}
      {hiddenIndexed.length > 0 && (
        <>
          <Text style={[styles.sectionTitle, { marginTop: 20 }]}>
            🫣 Hidden ingredients
          </Text>
          <Text style={styles.hiddenNote}>
            Detected by AI — typically added during cooking.
          </Text>
          {hiddenIndexed.map(({ item, originalIndex }) => (
            <View key={originalIndex} style={styles.hiddenChip}>
              <Text style={styles.hiddenLabel}>{item.label}</Text>
              <Text style={styles.hiddenGrams}>{item.grams.toFixed(0)} g estimated</Text>
            </View>
          ))}
        </>
      )}

      {/* Save button */}
      <TouchableOpacity
        style={[styles.saveBtn, saveMutation.isLoading && styles.saveBtnDisabled]}
        onPress={() => saveMutation.mutate()}
        disabled={saveMutation.isLoading}
        activeOpacity={0.8}
      >
        {saveMutation.isLoading ? (
          <ActivityIndicator color="#fff" />
        ) : (
          <Text style={styles.saveBtnText}>Save meal to history</Text>
        )}
      </TouchableOpacity>

      <TouchableOpacity
        onPress={() => { clear(); router.replace("/(tabs)/camera"); }}
        style={styles.discardBtn}
      >
        <Text style={styles.discardBtnText}>Discard</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  scroll:   { flex: 1, backgroundColor: "#FAFAFA" },
  content:  { padding: 20, paddingBottom: 48 },
  center:   { flex: 1, justifyContent: "center", alignItems: "center", padding: 32 },

  header:    { flexDirection: "row", alignItems: "center", marginBottom: 8 },
  backArrow: { fontSize: 24, color: "#333", marginRight: 12 },
  title:     { fontSize: 20, fontWeight: "700", color: "#1A1A1A" },
  subtitle:  { fontSize: 13, color: "#888", marginBottom: 20, lineHeight: 18 },

  errorText:    { fontSize: 16, color: "#666", marginBottom: 16, textAlign: "center" },
  retryBtn:     { padding: 14, backgroundColor: "#4CAF50", borderRadius: 10 },
  retryBtnText: { color: "#fff", fontWeight: "600" },

  totalCard: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 20,
    alignItems: "center",
    marginBottom: 24,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  totalCal:  { fontSize: 44, fontWeight: "800", color: "#1A1A1A" },
  totalUnit: { fontSize: 14, color: "#888", marginBottom: 12 },
  macroRow:  { flexDirection: "row", gap: 10 },
  macroPill: { flexDirection: "row", alignItems: "center", gap: 4 },
  macroDot:  { width: 8, height: 8, borderRadius: 4 },
  macroText: { fontSize: 12, color: "#555" },

  sectionTitle: { fontSize: 15, fontWeight: "700", color: "#1A1A1A", marginBottom: 10 },

  portionRow: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 14,
    marginBottom: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 3,
    elevation: 1,
  },
  portionInfo:   { marginBottom: 10 },
  portionLabel:  { fontSize: 14, fontWeight: "600", color: "#1A1A1A" },
  portionDetail: { fontSize: 12, color: "#888", marginTop: 2 },
  portionBtns:   { flexDirection: "row", gap: 6 },
  portionBtn: {
    flex: 1,
    paddingVertical: 6,
    borderRadius: 6,
    backgroundColor: "#F0F0F0",
    alignItems: "center",
  },
  portionBtnActive:     { backgroundColor: "#4CAF50" },
  portionBtnText:       { fontSize: 12, fontWeight: "600", color: "#555" },
  portionBtnTextActive: { color: "#fff" },

  hiddenNote:  { fontSize: 12, color: "#888", marginBottom: 8 },
  hiddenChip: {
    backgroundColor: "#FFF3E0",
    borderRadius: 8,
    padding: 10,
    marginBottom: 6,
    flexDirection: "row",
    justifyContent: "space-between",
  },
  hiddenLabel: { fontSize: 13, fontWeight: "600", color: "#E65100" },
  hiddenGrams: { fontSize: 12, color: "#E65100" },

  saveBtn: {
    backgroundColor: "#4CAF50",
    borderRadius: 12,
    padding: 16,
    alignItems: "center",
    marginTop: 28,
  },
  saveBtnDisabled: { opacity: 0.6 },
  saveBtnText:     { color: "#fff", fontSize: 16, fontWeight: "700" },

  discardBtn:     { alignItems: "center", marginTop: 14, padding: 10 },
  discardBtnText: { color: "#999", fontSize: 14 },
});
