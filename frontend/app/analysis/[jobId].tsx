/**
 * Analysis result screen.
 * Polls the API until the job is complete, then displays the nutrition breakdown.
 */

import { useEffect, useCallback } from "react";
import {
  View,
  ScrollView,
  Text,
  StyleSheet,
  ActivityIndicator,
  TouchableOpacity,
} from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import { useQuery } from "@tanstack/react-query";
import { api, AnalysisJob, FoodItemResult, MacroNutrients } from "@/services/api";
import { useConfirmStore } from "@/app/analysis/confirm";
import BloodSugarMeter from "@/components/BloodSugarMeter";

const POLL_INTERVAL_MS = 2000;

export default function AnalysisResultScreen() {
  const { jobId } = useLocalSearchParams<{ jobId: string }>();
  const { setConfirmData } = useConfirmStore();

  const { data: job, error } = useQuery<AnalysisJob>({
    queryKey: ["analysis", jobId],
    queryFn: () => api.getAnalysisResult(jobId),
    // react-query v4: refetchInterval receives (data, query), not (query)
    refetchInterval: (data) => {
      const status = (data as AnalysisJob | undefined)?.status;
      return status === "complete" || status === "failed" ? false : POLL_INTERVAL_MS;
    },
    enabled: !!jobId,
  });

  if (!error && (!job || job.status === "queued" || job.status === "processing")) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#4CAF50" />
        <Text style={styles.loadingText}>Analysing your meal…</Text>
        <Text style={styles.subText}>This takes 5–15 seconds</Text>
      </View>
    );
  }

  if (!job || job.status === "failed" || error) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>⚠️ Analysis failed</Text>
        <Text style={styles.subText}>{job?.error ?? (error as Error)?.message ?? "Unknown error"}</Text>
        <TouchableOpacity style={styles.retryBtn} onPress={() => router.back()}>
          <Text style={styles.retryText}>Try again</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const result = job.result!;

  return (
    <ScrollView style={styles.scroll} contentContainerStyle={styles.content}>
      {/* Total macro summary */}
      <MacroCard total={result.total} confidence={result.llm_confidence} />

      {/* Per-item breakdown */}
      <Text style={styles.sectionTitle}>Food items detected</Text>
      {result.items
        .filter((it) => !it.is_hidden_ingredient)
        .map((item, i) => (
          <FoodItemRow key={i} item={item} />
        ))}

      {/* Hidden ingredients */}
      {result.items.filter((it) => it.is_hidden_ingredient).length > 0 && (
        <>
          <Text style={[styles.sectionTitle, { marginTop: 24 }]}>
            🫙 Hidden ingredients (estimated)
          </Text>
          {result.items
            .filter((it) => it.is_hidden_ingredient)
            .map((item, i) => (
              <FoodItemRow key={`h${i}`} item={item} muted />
            ))}
        </>
      )}

      {/* Blood Sugar Impact */}
      {result.blood_sugar_impact && (
        <>
          <Text style={[styles.sectionTitle, { marginTop: 24 }]}>Blood Sugar Impact</Text>
          <BloodSugarMeter data={result.blood_sugar_impact} />
        </>
      )}

      {/* LLM notes */}
      {!!result.llm_notes?.trim() && (
        <View style={styles.notesCard}>
          <Text style={styles.notesTitle}>🤖 Dietitian AI notes</Text>
          <Text style={styles.notesText}>{result.llm_notes.trim()}</Text>
        </View>
      )}

      {/* Save / Log button — goes to confirm screen for portion adjustment */}
      <TouchableOpacity
        style={styles.saveBtn}
        onPress={() => {
          setConfirmData(jobId, result);
          router.push("/analysis/confirm");
        }}
      >
        <Text style={styles.saveBtnText}>Confirm portions &amp; save</Text>
      </TouchableOpacity>
    </ScrollView>
  );
}

// ── Sub-components ──────────────────────────────────────────────────────────

function MacroCard({ total, confidence }: { total: MacroNutrients; confidence?: string }) {
  return (
    <View style={styles.macroCard}>
      <Text style={styles.calCount}>{Math.round(total.calories)}</Text>
      <Text style={styles.calLabel}>kcal</Text>
      <View style={styles.macroRow}>
        <MacroPill label="Protein" value={total.protein_g} unit="g" color="#4CAF50" />
        <MacroPill label="Carbs"   value={total.carbs_g}   unit="g" color="#FF9800" />
        <MacroPill label="Fat"     value={total.fat_g}     unit="g" color="#F44336" />
        <MacroPill label="Fibre"   value={total.fiber_g}   unit="g" color="#9C27B0" />
      </View>
      {confidence && (
        <Text style={styles.confidence}>Confidence: {confidence}</Text>
      )}
    </View>
  );
}

function MacroPill({ label, value, unit, color }: { label: string; value: number; unit: string; color: string }) {
  return (
    <View style={styles.pill}>
      <Text style={[styles.pillValue, { color }]}>{value.toFixed(1)}{unit}</Text>
      <Text style={styles.pillLabel}>{label}</Text>
    </View>
  );
}

function FoodItemRow({ item, muted }: { item: FoodItemResult; muted?: boolean }) {
  return (
    <View style={[styles.itemRow, muted && styles.itemRowMuted]}>
      <View style={styles.itemLeft}>
        <Text style={styles.itemLabel}>{item.label}</Text>
        <Text style={styles.itemGrams}>
          {item.grams}g · {item.gram_confidence} confidence
        </Text>
      </View>
      <Text style={styles.itemCal}>{Math.round(item.nutrition.calories)} kcal</Text>
    </View>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  scroll: { flex: 1, backgroundColor: "#f5f5f5" },
  content: { padding: 16, paddingBottom: 40 },
  center: { flex: 1, justifyContent: "center", alignItems: "center", padding: 24 },
  loadingText: { fontSize: 18, fontWeight: "600", marginTop: 16 },
  subText: { color: "#666", marginTop: 8, textAlign: "center" },
  errorText: { fontSize: 20, fontWeight: "700", color: "#e53935" },
  retryBtn: {
    marginTop: 20, backgroundColor: "#4CAF50",
    paddingHorizontal: 28, paddingVertical: 12, borderRadius: 24,
  },
  retryText: { color: "#fff", fontWeight: "700", fontSize: 15 },

  macroCard: {
    backgroundColor: "#fff", borderRadius: 16, padding: 20,
    alignItems: "center", marginBottom: 20,
    shadowColor: "#000", shadowOpacity: 0.08, shadowRadius: 8, elevation: 3,
  },
  calCount: { fontSize: 56, fontWeight: "800", color: "#212121" },
  calLabel: { fontSize: 16, color: "#666", marginTop: -6 },
  macroRow: { flexDirection: "row", marginTop: 16, gap: 12 },
  pill: { alignItems: "center", minWidth: 60 },
  pillValue: { fontSize: 16, fontWeight: "700" },
  pillLabel: { fontSize: 11, color: "#888", marginTop: 2 },
  confidence: { marginTop: 12, fontSize: 12, color: "#aaa" },

  sectionTitle: { fontSize: 16, fontWeight: "700", color: "#212121", marginBottom: 10 },

  itemRow: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    backgroundColor: "#fff", borderRadius: 12, padding: 14, marginBottom: 8,
    shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 4, elevation: 1,
  },
  itemRowMuted: { opacity: 0.6 },
  itemLeft: { flex: 1 },
  itemLabel: { fontSize: 15, fontWeight: "600", textTransform: "capitalize" },
  itemGrams: { fontSize: 12, color: "#888", marginTop: 2 },
  itemCal: { fontSize: 16, fontWeight: "700", color: "#4CAF50" },

  notesCard: {
    backgroundColor: "#E8F5E9", borderRadius: 12, padding: 16, marginTop: 16,
  },
  notesTitle: { fontWeight: "700", marginBottom: 6, color: "#2E7D32" },
  notesText: { color: "#388E3C", lineHeight: 20 },

  saveBtn: {
    marginTop: 28, backgroundColor: "#4CAF50",
    borderRadius: 14, padding: 18, alignItems: "center",
  },
  saveBtnText: { color: "#fff", fontSize: 17, fontWeight: "700" },
});
