/**
 * FoodItemChip — compact chip showing a detected food item with confidence badge.
 * Tapping opens an inline edit for label + grams correction.
 */

import { useState } from "react";
import { View, Text, TextInput, TouchableOpacity, StyleSheet, Animated } from "react-native";

interface FoodItem {
  label: string;
  grams: number;
  gram_confidence: "high" | "medium" | "low";
  nutrition: { calories: number };
  is_hidden_ingredient?: boolean;
}

interface Props {
  item: FoodItem;
  onCorrect?: (label: string, grams: number) => void;
}

const CONFIDENCE_COLORS = {
  high:   { bg: "#E8F5E9", text: "#2E7D32" },
  medium: { bg: "#FFF3E0", text: "#E65100" },
  low:    { bg: "#FFEBEE", text: "#C62828" },
};

export default function FoodItemChip({ item, onCorrect }: Props) {
  const [editing, setEditing] = useState(false);
  const [label,   setLabel]   = useState(item.label);
  const [grams,   setGrams]   = useState(String(item.grams));

  const conf    = CONFIDENCE_COLORS[item.gram_confidence];
  const isHidden = item.is_hidden_ingredient;

  function save() {
    const g = parseFloat(grams);
    if (!isNaN(g) && g > 0 && onCorrect) {
      onCorrect(label, g);
    }
    setEditing(false);
  }

  return (
    <View style={[styles.chip, isHidden && styles.chipHidden]}>
      {editing ? (
        <View style={styles.editRow}>
          <TextInput
            style={styles.editLabel}
            value={label}
            onChangeText={setLabel}
            autoFocus
            returnKeyType="next"
          />
          <TextInput
            style={styles.editGrams}
            value={grams}
            onChangeText={setGrams}
            keyboardType="decimal-pad"
            returnKeyType="done"
            onSubmitEditing={save}
          />
          <Text style={styles.editUnit}>g</Text>
          <TouchableOpacity style={styles.saveBtn} onPress={save}>
            <Text style={styles.saveBtnText}>✓</Text>
          </TouchableOpacity>
        </View>
      ) : (
        <TouchableOpacity style={styles.displayRow} onPress={() => onCorrect && setEditing(true)}>
          <View style={styles.left}>
            {isHidden && <Text style={styles.hiddenBadge}>hidden</Text>}
            <Text style={styles.label}>{item.label}</Text>
            <Text style={styles.grams}>{item.grams}g</Text>
          </View>
          <View style={styles.right}>
            <Text style={styles.calories}>{Math.round(item.nutrition.calories)} kcal</Text>
            <View style={[styles.confBadge, { backgroundColor: conf.bg }]}>
              <Text style={[styles.confText, { color: conf.text }]}>
                {item.gram_confidence}
              </Text>
            </View>
          </View>
        </TouchableOpacity>
      )}
    </View>
  );
}

const styles = StyleSheet.create({
  chip: {
    backgroundColor: "#fff",
    borderRadius: 14,
    padding: 14,
    marginBottom: 8,
    shadowColor: "#000",
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  chipHidden: { opacity: 0.65, borderStyle: "dashed", borderWidth: 1, borderColor: "#ddd" },

  displayRow:  { flexDirection: "row", justifyContent: "space-between", alignItems: "center" },
  left:  { flex: 1 },
  right: { alignItems: "flex-end", gap: 4 },

  hiddenBadge: {
    fontSize: 9, fontWeight: "700", color: "#888",
    backgroundColor: "#f5f5f5", paddingHorizontal: 6, paddingVertical: 2,
    borderRadius: 4, alignSelf: "flex-start", marginBottom: 2, textTransform: "uppercase",
  },
  label:    { fontSize: 15, fontWeight: "600", textTransform: "capitalize", color: "#212121" },
  grams:    { fontSize: 12, color: "#888", marginTop: 2 },
  calories: { fontSize: 16, fontWeight: "700", color: "#4CAF50" },

  confBadge: { paddingHorizontal: 8, paddingVertical: 3, borderRadius: 8 },
  confText:  { fontSize: 11, fontWeight: "600" },

  // Edit row
  editRow: { flexDirection: "row", alignItems: "center", gap: 8 },
  editLabel: {
    flex: 1, borderBottomWidth: 1.5, borderColor: "#4CAF50",
    fontSize: 14, paddingVertical: 4, color: "#212121",
  },
  editGrams: {
    width: 60, borderBottomWidth: 1.5, borderColor: "#4CAF50",
    fontSize: 14, paddingVertical: 4, textAlign: "right", color: "#212121",
  },
  editUnit:  { fontSize: 13, color: "#888" },
  saveBtn:   { backgroundColor: "#4CAF50", borderRadius: 8, paddingHorizontal: 10, paddingVertical: 6 },
  saveBtnText: { color: "#fff", fontWeight: "700", fontSize: 14 },
});
