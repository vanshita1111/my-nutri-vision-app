/**
 * NutritionCard — displays total macros for a meal or day.
 * Uses MacroRing + individual macro pills.
 */

import { View, Text, StyleSheet } from "react-native";
import MacroRing from "./MacroRing";

interface Props {
  calories: number;
  protein: number;
  fat: number;
  carbs: number;
  fiber?: number;
  title?: string;
  subtitle?: string;
}

export default function NutritionCard({
  calories, protein, fat, carbs, fiber = 0, title, subtitle
}: Props) {
  return (
    <View style={styles.card}>
      {(title || subtitle) && (
        <View style={styles.header}>
          {title    && <Text style={styles.title}>{title}</Text>}
          {subtitle && <Text style={styles.subtitle}>{subtitle}</Text>}
        </View>
      )}

      <View style={styles.body}>
        <MacroRing calories={calories} protein={protein} fat={fat} carbs={carbs} size={140} />

        <View style={styles.pills}>
          <MacroPill label="Protein" value={protein} unit="g" color="#4CAF50" />
          <MacroPill label="Carbs"   value={carbs}   unit="g" color="#FF9800" />
          <MacroPill label="Fat"     value={fat}     unit="g" color="#F44336" />
          {fiber > 0 && (
            <MacroPill label="Fibre" value={fiber} unit="g" color="#9C27B0" />
          )}
        </View>
      </View>
    </View>
  );
}

function MacroPill({ label, value, unit, color }: {
  label: string; value: number; unit: string; color: string;
}) {
  return (
    <View style={styles.pill}>
      <View style={[styles.pillDot, { backgroundColor: color }]} />
      <Text style={styles.pillValue}>{value.toFixed(1)}{unit}</Text>
      <Text style={styles.pillLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    backgroundColor: "#fff",
    borderRadius: 20,
    padding: 20,
    shadowColor: "#000",
    shadowOpacity: 0.07,
    shadowRadius: 10,
    elevation: 3,
  },
  header: { marginBottom: 16 },
  title:    { fontSize: 17, fontWeight: "700", color: "#212121" },
  subtitle: { fontSize: 13, color: "#888", marginTop: 2 },
  body: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 16,
  },
  pills: { flex: 1, gap: 12 },
  pill: { flexDirection: "row", alignItems: "center", gap: 8 },
  pillDot: { width: 10, height: 10, borderRadius: 5 },
  pillValue: { fontSize: 14, fontWeight: "700", color: "#212121", minWidth: 52 },
  pillLabel: { fontSize: 12, color: "#888" },
});
