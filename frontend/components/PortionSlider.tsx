/**
 * PortionSlider — V1 portion size selector (Small / Medium / Large / XL).
 * Used on the confirm screen before looking up nutrition.
 */

import { View, Text, TouchableOpacity, StyleSheet } from "react-native";

type PortionSize = "small" | "medium" | "large" | "xl";

const SIZES: { key: PortionSize; label: string; multiplier: number }[] = [
  { key: "small",  label: "S",  multiplier: 0.6  },
  { key: "medium", label: "M",  multiplier: 1.0  },
  { key: "large",  label: "L",  multiplier: 1.4  },
  { key: "xl",     label: "XL", multiplier: 1.8  },
];

interface Props {
  value: PortionSize;
  onChange: (size: PortionSize) => void;
  baseGrams: number;
}

export default function PortionSlider({ value, onChange, baseGrams }: Props) {
  const current = SIZES.find((s) => s.key === value) ?? SIZES[1];
  const displayGrams = Math.round(baseGrams * current.multiplier);

  return (
    <View style={styles.container}>
      <View style={styles.btnRow}>
        {SIZES.map((size) => (
          <TouchableOpacity
            key={size.key}
            style={[styles.btn, value === size.key && styles.btnActive]}
            onPress={() => onChange(size.key)}
            activeOpacity={0.7}
          >
            <Text style={[styles.btnText, value === size.key && styles.btnTextActive]}>
              {size.label}
            </Text>
          </TouchableOpacity>
        ))}
      </View>
      <Text style={styles.gramsLabel}>≈ {displayGrams}g</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  container: { alignItems: "center" },
  btnRow: { flexDirection: "row", gap: 8, marginBottom: 6 },
  btn: {
    width: 44, height: 44, borderRadius: 22,
    backgroundColor: "#f5f5f5",
    justifyContent: "center", alignItems: "center",
    borderWidth: 1.5, borderColor: "transparent",
  },
  btnActive: {
    backgroundColor: "#E8F5E9",
    borderColor: "#4CAF50",
  },
  btnText: { fontWeight: "700", color: "#666", fontSize: 13 },
  btnTextActive: { color: "#4CAF50" },
  gramsLabel: { fontSize: 12, color: "#888", marginTop: 2 },
});
