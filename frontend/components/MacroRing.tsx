/**
 * MacroRing — animated SVG donut chart showing macro breakdown.
 *
 * Usage:
 *   <MacroRing calories={520} protein={32} fat={18} carbs={60} size={180} />
 */

import { useEffect, useRef } from "react";
import { View, Text, StyleSheet, Animated } from "react-native";
import Svg, { Circle, G } from "react-native-svg";

const AnimatedCircle = Animated.createAnimatedComponent(Circle);

interface Props {
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
  size?: number;
}

// Caloric density (kcal per gram)
const PROTEIN_KCAL = 4;
const CARB_KCAL    = 4;
const FAT_KCAL     = 9;

const COLORS = {
  protein: "#4CAF50",
  carbs:   "#FF9800",
  fat:     "#F44336",
  empty:   "#F0F0F0",
};

export default function MacroRing({ calories, protein, fat, carbs, size = 160 }: Props) {
  const radius     = (size - 20) / 2;
  const circumference = 2 * Math.PI * radius;
  const cx = size / 2;
  const cy = size / 2;

  // Calculate proportions by caloric contribution
  const total = protein * PROTEIN_KCAL + carbs * CARB_KCAL + fat * FAT_KCAL || 1;
  const proteinPct = (protein * PROTEIN_KCAL) / total;
  const carbsPct   = (carbs * CARB_KCAL)     / total;
  const fatPct     = (fat * FAT_KCAL)         / total;

  // Convert to dash lengths
  const proteinDash = proteinPct * circumference;
  const carbsDash   = carbsPct   * circumference;
  const fatDash     = fatPct     * circumference;

  // Animation
  const anim = useRef(new Animated.Value(0)).current;
  useEffect(() => {
    anim.setValue(0);
    Animated.timing(anim, {
      toValue: 1,
      duration: 800,
      useNativeDriver: false,
    }).start();
  }, [calories]);

  // Rotation offsets: protein starts at top (-90°), then carbs, then fat
  const proteinOffset = 0;
  const carbsOffset   = proteinPct;
  const fatOffset     = proteinPct + carbsPct;

  function ring(dashLen: number, offsetPct: number, color: string) {
    const strokeDash = anim.interpolate({
      inputRange:  [0, 1],
      outputRange: [0, dashLen],
    });
    const gap = circumference - dashLen;
    return (
      <AnimatedCircle
        cx={cx}
        cy={cy}
        r={radius}
        fill="none"
        stroke={color}
        strokeWidth={16}
        strokeDasharray={[strokeDash as unknown as number, circumference]}
        strokeDashoffset={-circumference * offsetPct}
        strokeLinecap="round"
        rotation={-90}
        origin={`${cx}, ${cy}`}
      />
    );
  }

  return (
    <View style={[styles.container, { width: size, height: size }]}>
      <Svg width={size} height={size}>
        <G>
          {/* Background track */}
          <Circle
            cx={cx} cy={cy} r={radius}
            fill="none"
            stroke={COLORS.empty}
            strokeWidth={16}
          />
          {ring(fatDash,     fatOffset,     COLORS.fat)}
          {ring(carbsDash,   carbsOffset,   COLORS.carbs)}
          {ring(proteinDash, proteinOffset, COLORS.protein)}
        </G>
      </Svg>

      {/* Centre label */}
      <View style={styles.centre}>
        <Text style={styles.calCount}>{Math.round(calories)}</Text>
        <Text style={styles.calLabel}>kcal</Text>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { position: "relative", justifyContent: "center", alignItems: "center" },
  centre: { position: "absolute", alignItems: "center" },
  calCount: { fontSize: 28, fontWeight: "800", color: "#212121" },
  calLabel: { fontSize: 12, color: "#888", marginTop: -2 },
});
