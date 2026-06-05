/**
 * BloodSugarMeter — visual blood sugar impact card for a meal.
 * Shows an animated segmented bar (Low / Moderate / High), score,
 * macro buffer breakdown, personalised recommendations, and disclaimer.
 */

import { useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  StyleSheet,
  Animated,
  LayoutChangeEvent,
} from "react-native";
import type { BloodSugarBreakdown } from "@/services/api";

const LEVEL_CONFIG = {
  low:      { color: "#4CAF50", label: "Low Impact",      emoji: "🟢", bg: "#E8F5E9" },
  moderate: { color: "#FF9800", label: "Moderate Impact", emoji: "🟡", bg: "#FFF3E0" },
  high:     { color: "#F44336", label: "High Impact",     emoji: "🔴", bg: "#FFEBEE" },
} as const;

const NEEDLE_W = 18;

interface Props {
  data: BloodSugarBreakdown;
}

export default function BloodSugarMeter({ data }: Props) {
  const cfg = LEVEL_CONFIG[data.level] ?? LEVEL_CONFIG.moderate;

  // Clamp score to 0–100
  const score = Math.max(0, Math.min(100, data.score));

  // Measure actual bar width on layout so the needle never overflows
  const [barWidth, setBarWidth] = useState(0);
  const needleAnim = useRef(new Animated.Value(0)).current;

  function onBarLayout(e: LayoutChangeEvent) {
    setBarWidth(e.nativeEvent.layout.width);
  }

  useEffect(() => {
    if (barWidth === 0) return;
    Animated.timing(needleAnim, {
      toValue: score,
      duration: 900,
      useNativeDriver: false,
    }).start();
  }, [score, barWidth, needleAnim]);

  const needleLeft = needleAnim.interpolate({
    inputRange:  [0, 100],
    outputRange: [0, Math.max(0, barWidth - NEEDLE_W)],
    extrapolate: "clamp",
  });

  return (
    <View style={[styles.card, { borderLeftColor: cfg.color }]}>
      {/* Header */}
      <View style={styles.header}>
        <View style={[styles.badge, { backgroundColor: cfg.bg }]}>
          <Text style={styles.badgeEmoji}>{cfg.emoji}</Text>
          <Text style={[styles.badgeText, { color: cfg.color }]}>{cfg.label}</Text>
        </View>
        <Text style={[styles.score, { color: cfg.color }]}>{score}</Text>
      </View>

      <Text style={styles.sectionLabel}>Blood Sugar Impact Score</Text>

      {/* Segmented bar */}
      <View style={styles.barContainer}>
        <View style={styles.barTrack} onLayout={onBarLayout}>
          <View style={[styles.barSegment, { backgroundColor: "#4CAF50", flex: 34 }]} />
          <View style={[styles.barSegment, { backgroundColor: "#FF9800", flex: 33 }]} />
          <View style={[styles.barSegment, { backgroundColor: "#F44336", flex: 33 }]} />
        </View>
        {barWidth > 0 && (
          <Animated.View style={[styles.needle, { left: needleLeft }]} />
        )}
        <View style={styles.barLabels}>
          <Text style={[styles.barLabelText, { color: "#4CAF50" }]}>Low</Text>
          <Text style={[styles.barLabelText, { color: "#FF9800" }]}>Moderate</Text>
          <Text style={[styles.barLabelText, { color: "#F44336" }]}>High</Text>
        </View>
      </View>

      {/* Explanation */}
      {!!data.explanation && (
        <Text style={styles.explanation}>{data.explanation}</Text>
      )}

      {/* Breakdown rows */}
      <View style={styles.breakdown}>
        <BreakdownRow label="Glycemic Load"   value={`${data.glycemic_load.toFixed(1)} (adjusted)`} />
        {/* carb_density is stored as a percentage value (0–100 range) */}
        <BreakdownRow label="Carb Density"    value={`${data.carb_density.toFixed(1)}%`} />
        <BreakdownRow
          label="Fibre Buffer"
          value={`−${(data.fiber_impact * 100).toFixed(0)}%`}
          positive
        />
        <BreakdownRow
          label="Protein Buffer"
          value={`−${(data.protein_buffer * 100).toFixed(0)}%`}
          positive
        />
        <BreakdownRow
          label="Fat Buffer"
          value={`−${(data.fat_buffer * 100).toFixed(0)}%`}
          positive
        />
      </View>

      {/* Recommendations */}
      {data.recommendations.length > 0 && (
        <View style={styles.recsBlock}>
          <Text style={styles.recsTitle}>Personalised Tips</Text>
          {data.recommendations.map((rec, i) => (
            <View key={i} style={styles.recRow}>
              <Text style={styles.recBullet}>•</Text>
              <Text style={styles.recText}>{rec}</Text>
            </View>
          ))}
        </View>
      )}

      {/* Disclaimer */}
      <Text style={styles.disclaimer}>{data.disclaimer}</Text>
    </View>
  );
}

function BreakdownRow({
  label,
  value,
  positive = false,
}: {
  label: string;
  value: string;
  positive?: boolean;
}) {
  return (
    <View style={styles.breakdownRow}>
      <Text style={styles.breakdownLabel}>{label}</Text>
      <Text style={[styles.breakdownValue, positive && styles.breakdownPositive]}>
        {value}
      </Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 18,
    marginVertical: 12,
    borderLeftWidth: 4,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07,
    shadowRadius: 8,
    elevation: 3,
  },

  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    marginBottom: 2,
  },
  badge: {
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 20,
    gap: 5,
  },
  badgeEmoji: { fontSize: 14 },
  badgeText:  { fontSize: 13, fontWeight: "700" },
  score: {
    fontSize: 42,
    fontWeight: "800",
    lineHeight: 46,
  },

  sectionLabel: {
    fontSize: 11,
    color: "#999",
    textTransform: "uppercase",
    letterSpacing: 0.5,
    marginBottom: 14,
  },

  barContainer: {
    width: "100%",
    marginBottom: 4,
  },
  barTrack: {
    flexDirection: "row",
    height: 10,
    borderRadius: 5,
    overflow: "hidden",
    width: "100%",
  },
  barSegment: { height: 10 },
  needle: {
    position: "absolute",
    top: -4,
    width: NEEDLE_W,
    height: 18,
    borderRadius: 3,
    backgroundColor: "#1A1A1A",
    opacity: 0.85,
  },
  barLabels: {
    flexDirection: "row",
    justifyContent: "space-between",
    marginTop: 6,
  },
  barLabelText: { fontSize: 11, fontWeight: "600" },

  explanation: {
    fontSize: 13,
    color: "#555",
    lineHeight: 19,
    marginTop: 12,
    marginBottom: 4,
  },

  breakdown: {
    marginTop: 14,
    borderTopWidth: 1,
    borderTopColor: "#F0F0F0",
    paddingTop: 12,
    gap: 8,
  },
  breakdownRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
  },
  breakdownLabel:    { fontSize: 13, color: "#555" },
  breakdownValue:    { fontSize: 13, fontWeight: "700", color: "#1A1A1A" },
  breakdownPositive: { color: "#4CAF50" },

  recsBlock: {
    marginTop: 14,
    backgroundColor: "#F9FBF9",
    borderRadius: 10,
    padding: 12,
    gap: 6,
  },
  recsTitle: { fontSize: 12, fontWeight: "700", color: "#2E7D32", marginBottom: 4 },
  recRow:    { flexDirection: "row", gap: 6 },
  recBullet: { fontSize: 13, color: "#4CAF50", lineHeight: 19 },
  recText:   { flex: 1, fontSize: 13, color: "#333", lineHeight: 19 },

  disclaimer: {
    fontSize: 11,
    color: "#AAA",
    marginTop: 12,
    lineHeight: 16,
    fontStyle: "italic",
  },
});
