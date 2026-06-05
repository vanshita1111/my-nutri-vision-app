/**
 * Skeleton loading components.
 * Use SkeletonBox for generic placeholders; compose into
 * screen-specific layouts (HomeSkeleton, PlanSkeleton, etc.).
 */

import { useEffect, useRef } from "react";
import { Animated, View, StyleSheet, ViewStyle } from "react-native";

interface SkeletonBoxProps {
  width?: number | `${number}%`;
  height: number;
  radius?: number;
  style?: ViewStyle;
}

export function SkeletonBox({ width = "100%", height, radius = 8, style }: SkeletonBoxProps) {
  const opacity = useRef(new Animated.Value(0.35)).current;

  useEffect(() => {
    Animated.loop(
      Animated.sequence([
        Animated.timing(opacity, { toValue: 0.8,  duration: 750, useNativeDriver: true }),
        Animated.timing(opacity, { toValue: 0.35, duration: 750, useNativeDriver: true }),
      ])
    ).start();
  }, []);

  return (
    <Animated.View
      style={[
        { width, height, borderRadius: radius, backgroundColor: "#E0E0E0", opacity },
        style,
      ]}
    />
  );
}

// ── Composed skeletons for specific screens ────────────────────────────────────

export function HomeScreenSkeleton() {
  return (
    <View style={sk.scroll}>
      {/* Greeting */}
      <SkeletonBox height={28} width="55%" style={{ marginBottom: 6 }} />
      <SkeletonBox height={16} width="35%" style={{ marginBottom: 24 }} />

      {/* Calorie card */}
      <View style={[sk.card, { padding: 18, marginBottom: 16 }]}>
        <SkeletonBox height={13} width="30%" style={{ marginBottom: 14 }} />
        <View style={sk.row}>
          <SkeletonBox height={52} width="28%" radius={4} />
          <SkeletonBox height={52} width="28%" radius={4} />
          <SkeletonBox height={52} width="28%" radius={4} />
        </View>
        <SkeletonBox height={10} style={{ marginTop: 16, marginBottom: 6 }} radius={5} />
        <View style={[sk.row, { marginTop: 18 }]}>
          <SkeletonBox height={40} width="30%" radius={4} />
          <SkeletonBox height={40} width="30%" radius={4} />
          <SkeletonBox height={40} width="30%" radius={4} />
        </View>
      </View>

      {/* Scan button */}
      <SkeletonBox height={56} radius={16} style={{ marginBottom: 24 }} />

      {/* Meals header */}
      <View style={[sk.row, { marginBottom: 10, justifyContent: "space-between" }]}>
        <SkeletonBox height={18} width="35%" />
        <SkeletonBox height={14} width="15%" />
      </View>

      {/* Meal rows */}
      {[1, 2, 3].map((i) => (
        <View key={i} style={[sk.card, { flexDirection: "row", justifyContent: "space-between", marginBottom: 8, padding: 16 }]}>
          <View style={{ gap: 6 }}>
            <SkeletonBox height={16} width={120} />
            <SkeletonBox height={12} width={80} />
          </View>
          <SkeletonBox height={26} width={60} radius={4} />
        </View>
      ))}
    </View>
  );
}

export function PlanScreenSkeleton() {
  return (
    <View style={sk.scroll}>
      {/* Goal banner */}
      <SkeletonBox height={88} radius={18} style={{ marginBottom: 12 }} />
      <SkeletonBox height={64} radius={14} style={{ marginBottom: 14 }} />

      {/* Stats row */}
      <View style={[sk.row, { gap: 10, marginBottom: 18 }]}>
        {[1, 2, 3].map((i) => (
          <View key={i} style={[sk.card, { flex: 1, padding: 14, alignItems: "center", gap: 6 }]}>
            <SkeletonBox height={28} width={28} radius={14} />
            <SkeletonBox height={22} width="60%" />
            <SkeletonBox height={12} width="80%" />
          </View>
        ))}
      </View>

      {/* Section tabs */}
      <SkeletonBox height={46} radius={12} style={{ marginBottom: 16 }} />

      {/* Day cards */}
      {[1, 2, 3, 4].map((i) => (
        <View key={i} style={[sk.card, { padding: 14, marginBottom: 10 }]}>
          <View style={sk.row}>
            <SkeletonBox height={22} width={80} radius={8} />
            <View style={{ flex: 1, marginLeft: 10, gap: 4 }}>
              <SkeletonBox height={16} width="60%" />
              <SkeletonBox height={12} width="40%" />
            </View>
            <SkeletonBox height={16} width={32} />
          </View>
        </View>
      ))}
    </View>
  );
}

export function InsightsScreenSkeleton() {
  return (
    <View style={sk.scroll}>
      <SkeletonBox height={100} radius={16} style={{ marginBottom: 20 }} />
      <SkeletonBox height={18} width="40%" style={{ marginBottom: 12 }} />
      {[1, 2, 3, 4, 5].map((i) => (
        <View key={i} style={[sk.row, { marginBottom: 8 }]}>
          <SkeletonBox height={12} width={32} />
          <SkeletonBox height={12} style={{ flex: 1, marginHorizontal: 8 }} radius={6} />
          <SkeletonBox height={12} width={38} />
        </View>
      ))}
      <SkeletonBox height={18} width="45%" style={{ marginTop: 24, marginBottom: 12 }} />
      <SkeletonBox height={140} radius={16} />
    </View>
  );
}

export function HistoryScreenSkeleton() {
  return (
    <View style={sk.scroll}>
      {[1, 2, 3, 4, 5, 6].map((i) => (
        <View
          key={i}
          style={[sk.card, { flexDirection: "row", justifyContent: "space-between", padding: 16, marginBottom: 10 }]}
        >
          <View style={{ gap: 6 }}>
            <SkeletonBox height={16} width={120} />
            <SkeletonBox height={12} width={150} />
            <SkeletonBox height={11} width={80} />
          </View>
          <View style={{ alignItems: "flex-end", gap: 4 }}>
            <SkeletonBox height={28} width={60} radius={4} />
            <SkeletonBox height={11} width={30} />
          </View>
        </View>
      ))}
    </View>
  );
}

const sk = StyleSheet.create({
  scroll: { padding: 16 },
  card: {
    backgroundColor: "#F5F5F5",
    borderRadius: 14,
  },
  row: { flexDirection: "row", alignItems: "center" },
});
