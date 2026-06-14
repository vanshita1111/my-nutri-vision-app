/**
 * Meal Detail Screen — shows every food item in a saved meal with
 * full macro breakdown. Accessible from History tab.
 */

import { useCallback, useState } from "react";
import {
  View,
  Text,
  ScrollView,
  StyleSheet,
  TouchableOpacity,
  Alert,
  ActivityIndicator,
} from "react-native";
import { useLocalSearchParams, router } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, MealDetail, FoodItemDetail } from "@/services/api";
import BloodSugarMeter from "@/components/BloodSugarMeter";
import ManualFoodModal from "@/components/ManualFoodModal";

const TRASH = "🗑";

// ── Helpers ───────────────────────────────────────────────────────────────────

const MACRO_COLORS = {
  protein: "#4CAF50",
  carbs:   "#FF9800",
  fat:     "#F44336",
  fiber:   "#9C27B0",
};

const CONF_COLORS: Record<string, string> = {
  high:   "#4CAF50",
  medium: "#FF9800",
  low:    "#F44336",
};

function fmt(n: number | undefined, decimals = 1) {
  return (n ?? 0).toFixed(decimals);
}

// ── Sub-components ────────────────────────────────────────────────────────────

function MacroPill({
  label,
  value,
  unit,
  color,
}: {
  label: string;
  value: number;
  unit: string;
  color: string;
}) {
  return (
    <View style={styles.macroPill}>
      <View style={[styles.macroDot, { backgroundColor: color }]} />
      <Text style={styles.macroLabel}>{label}</Text>
      <Text style={styles.macroValue}>
        {fmt(value)}
        <Text style={styles.macroUnit}>{unit}</Text>
      </Text>
    </View>
  );
}

function FoodRow({
  item,
  mealId,
  onDeleted,
  onEdit,
}: {
  item: FoodItemDetail;
  mealId: string;
  onDeleted: (updated: MealDetail) => void;
  onEdit: () => void;
}) {
  const deleteItemMutation = useMutation({
    mutationFn: () => api.deleteFoodItem(mealId, item.id),
    onSuccess: (updated) => onDeleted(updated),
    onError: (err: Error) => Alert.alert("Error", err.message),
  });

  const confirmDeleteItem = () => {
    Alert.alert(
      "Remove item?",
      `Remove "${item.label}" from this meal?`,
      [
        { text: "Cancel", style: "cancel" },
        { text: "Remove", style: "destructive", onPress: () => deleteItemMutation.mutate() },
      ]
    );
  };

  return (
    <View style={[styles.foodRow, item.is_hidden_ingredient && styles.hiddenRow]}>
      <View style={styles.foodRowLeft}>
        <Text style={styles.foodLabel}>
          {item.is_hidden_ingredient ? "🫣 " : ""}
          {item.label}
        </Text>
        <Text style={styles.foodGrams}>{fmt(item.grams, 0)} g</Text>
      </View>
      <View style={styles.foodRowRight}>
        <Text style={styles.foodCal}>{fmt(item.nutrition?.calories, 0)} kcal</Text>
        <View
          style={[
            styles.confBadge,
            { backgroundColor: CONF_COLORS[item.gram_confidence] + "22" },
          ]}
        >
          <Text style={[styles.confText, { color: CONF_COLORS[item.gram_confidence] }]}>
            {item.gram_confidence}
          </Text>
        </View>
        <View style={styles.itemActions}>
          <TouchableOpacity onPress={onEdit} hitSlop={8} style={styles.itemEditBtn}>
            <Text style={styles.itemEditIcon}>✏️</Text>
          </TouchableOpacity>
          <TouchableOpacity onPress={confirmDeleteItem} hitSlop={8} style={styles.itemDeleteBtn}>
            {deleteItemMutation.isLoading
              ? <ActivityIndicator size="small" color="#e53935" />
              : <Text style={styles.itemDeleteIcon}>{TRASH}</Text>
            }
          </TouchableOpacity>
        </View>
      </View>
    </View>
  );
}

// ── Main screen ───────────────────────────────────────────────────────────────

export default function MealDetailScreen() {
  const { id } = useLocalSearchParams<{ id: string }>();
  const qc = useQueryClient();
  const insets = useSafeAreaInsets();
  const [showManualEntry, setShowManualEntry] = useState(false);
  const [editingItem, setEditingItem] = useState<FoodItemDetail | null>(null);

  const { data: meal, isLoading, isError } = useQuery<MealDetail>({
    queryKey: ["meal", id],
    queryFn: () => api.getMeal(id),
    enabled: !!id,
    staleTime: 5 * 60 * 1000,
  });

  function handleItemDeleted(updated: MealDetail) {
    qc.setQueryData(["meal", id], updated);
    qc.invalidateQueries({ queryKey: ["meals"] });
    qc.invalidateQueries({ queryKey: ["daily-nutrition"] });
    qc.invalidateQueries({ queryKey: ["weekly-summary"] });
  }

  function handleFoodAdded(updated: MealDetail) {
    qc.setQueryData(["meal", id], updated);
    qc.invalidateQueries({ queryKey: ["meals"] });
    qc.invalidateQueries({ queryKey: ["daily-nutrition"] });
    qc.invalidateQueries({ queryKey: ["weekly-summary"] });
    setShowManualEntry(false);
  }

  function handleFoodEdited(updated: MealDetail) {
    qc.setQueryData(["meal", id], updated);
    qc.invalidateQueries({ queryKey: ["meals"] });
    qc.invalidateQueries({ queryKey: ["daily-nutrition"] });
    qc.invalidateQueries({ queryKey: ["weekly-summary"] });
    setEditingItem(null);
  }

  const deleteMutation = useMutation({
    mutationFn: () => api.deleteMeal(id),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["meals"] });
      qc.invalidateQueries({ queryKey: ["daily-nutrition"] });
      qc.invalidateQueries({ queryKey: ["weekly-summary"] });
      router.back();
    },
    onError: (err: Error) => Alert.alert("Error", err.message),
  });

  const confirmDelete = useCallback(() => {
    Alert.alert(
      "Delete meal?",
      "This will permanently remove this meal from your history.",
      [
        { text: "Cancel", style: "cancel" },
        {
          text: "Delete",
          style: "destructive",
          onPress: () => deleteMutation.mutate(),
        },
      ]
    );
  }, [deleteMutation]);

  if (isLoading) {
    return (
      <View style={styles.center}>
        <ActivityIndicator size="large" color="#4CAF50" />
      </View>
    );
  }

  if (isError || !meal) {
    return (
      <View style={styles.center}>
        <Text style={styles.errorText}>Could not load meal.</Text>
        <TouchableOpacity onPress={() => router.back()} style={styles.backBtn}>
          <Text style={styles.backBtnText}>Go back</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const date = new Date(meal.eaten_at ?? new Date()).toLocaleDateString("en-IN", {
    weekday: "long",
    day: "numeric",
    month: "short",
    year: "numeric",
  });

  const visibleItems  = meal.food_items.filter((i) => !i.is_hidden_ingredient);
  const hiddenItems   = meal.food_items.filter((i) => i.is_hidden_ingredient);

  return (
    <>
    <ScrollView style={styles.scroll} contentContainerStyle={[styles.content, { paddingTop: insets.top + 8 }]}>
      {/* Header */}
      <View style={styles.header}>
        <TouchableOpacity onPress={() => router.back()} hitSlop={8}>
          <Text style={styles.backArrow}>←</Text>
        </TouchableOpacity>
        <View style={styles.headerText}>
          <Text style={styles.title}>Meal Detail</Text>
          <Text style={styles.subtitle}>{date}</Text>
        </View>
        <TouchableOpacity onPress={confirmDelete} hitSlop={8} disabled={deleteMutation.isLoading}>
          {deleteMutation.isLoading
            ? <ActivityIndicator size="small" color="#e53935" />
            : <Text style={styles.deleteBtn}>🗑</Text>
          }
        </TouchableOpacity>
      </View>

      {/* Total calories card */}
      <View style={styles.calorieCard}>
        <Text style={styles.calorieValue}>{fmt(meal.total_calories, 0)}</Text>
        <Text style={styles.calorieUnit}>kcal total</Text>
      </View>

      {/* Macro pills */}
      <View style={styles.macroRow}>
        <MacroPill label="Protein" value={meal.total_protein_g ?? 0} unit="g" color={MACRO_COLORS.protein} />
        <MacroPill label="Carbs"   value={meal.total_carbs_g   ?? 0} unit="g" color={MACRO_COLORS.carbs}   />
        <MacroPill label="Fat"     value={meal.total_fat_g     ?? 0} unit="g" color={MACRO_COLORS.fat}     />
        <MacroPill label="Fiber"   value={meal.total_fiber_g   ?? 0} unit="g" color={MACRO_COLORS.fiber}   />
      </View>

      {/* Food items */}
      {visibleItems.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Food Items</Text>
          {visibleItems.map((item) => (
            <FoodRow key={item.id} item={item} mealId={id} onDeleted={handleItemDeleted} onEdit={() => setEditingItem(item)} />
          ))}
        </View>
      )}

      {/* Hidden ingredients */}
      {hiddenItems.length > 0 && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Hidden Ingredients Detected</Text>
          <Text style={styles.sectionNote}>
            These weren't visible but are typically added during cooking.
          </Text>
          {hiddenItems.map((item) => (
            <FoodRow key={item.id} item={item} mealId={id} onDeleted={handleItemDeleted} onEdit={() => setEditingItem(item)} />
          ))}
        </View>
      )}

      {/* Add food manually */}
      <TouchableOpacity style={styles.addFoodBtn} onPress={() => setShowManualEntry(true)}>
        <Text style={styles.addFoodBtnText}>+ Add food manually</Text>
      </TouchableOpacity>

      {/* Blood Sugar Impact */}
      {meal.blood_sugar_impact && (
        <View style={styles.section}>
          <Text style={styles.sectionTitle}>Blood Sugar Impact</Text>
          <BloodSugarMeter data={meal.blood_sugar_impact} />
        </View>
      )}

      {/* LLM notes */}
      {!!meal.llm_notes?.trim() && (
        <View style={styles.notesCard}>
          <Text style={styles.notesTitle}>AI Notes</Text>
          <Text style={styles.notesBody}>{meal.llm_notes.trim()}</Text>
        </View>
      )}
    </ScrollView>

    <ManualFoodModal
      visible={showManualEntry}
      mealId={id}
      onClose={() => setShowManualEntry(false)}
      onAdded={handleFoodAdded}
    />
    <ManualFoodModal
      visible={editingItem !== null}
      mealId={id}
      replaceItemId={editingItem?.id}
      initialQuery={editingItem?.label}
      onClose={() => setEditingItem(null)}
      onAdded={handleFoodEdited}
    />
    </>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  scroll:      { flex: 1, backgroundColor: "#FAFAFA" },
  content:     { padding: 20, paddingBottom: 48 },
  center:      { flex: 1, justifyContent: "center", alignItems: "center", padding: 32 },
  errorText:   { fontSize: 16, color: "#666", marginBottom: 16, textAlign: "center" },

  header:      { flexDirection: "row", alignItems: "center", marginBottom: 24 },
  backArrow:   { fontSize: 24, color: "#333", marginRight: 12 },
  headerText:  { flex: 1 },
  title:       { fontSize: 20, fontWeight: "700", color: "#1A1A1A" },
  subtitle:    { fontSize: 13, color: "#888", marginTop: 2 },
  deleteBtn:   { fontSize: 20 },
  backBtn:     { marginTop: 8, padding: 12, backgroundColor: "#4CAF50", borderRadius: 8 },
  backBtnText: { color: "#fff", fontWeight: "600" },

  calorieCard: {
    backgroundColor: "#fff",
    borderRadius: 16,
    padding: 24,
    alignItems: "center",
    marginBottom: 16,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.06,
    shadowRadius: 6,
    elevation: 2,
  },
  calorieValue: { fontSize: 48, fontWeight: "800", color: "#1A1A1A" },
  calorieUnit:  { fontSize: 15, color: "#888", marginTop: 4 },

  macroRow: {
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
    marginBottom: 24,
  },
  macroPill: {
    flexDirection: "row",
    alignItems: "center",
    backgroundColor: "#fff",
    borderRadius: 20,
    paddingHorizontal: 12,
    paddingVertical: 6,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius: 3,
    elevation: 1,
    gap: 6,
  },
  macroDot:    { width: 8, height: 8, borderRadius: 4 },
  macroLabel:  { fontSize: 12, color: "#666" },
  macroValue:  { fontSize: 13, fontWeight: "700", color: "#1A1A1A" },
  macroUnit:   { fontSize: 11, fontWeight: "400", color: "#999" },

  section:      { marginBottom: 24 },
  sectionTitle: { fontSize: 15, fontWeight: "700", color: "#1A1A1A", marginBottom: 4 },
  sectionNote:  { fontSize: 12, color: "#888", marginBottom: 10 },

  foodRow: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    backgroundColor: "#fff",
    borderRadius: 10,
    padding: 14,
    marginBottom: 8,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 1 },
    shadowOpacity: 0.04,
    shadowRadius: 3,
    elevation: 1,
  },
  hiddenRow:    { borderLeftWidth: 3, borderLeftColor: "#FF9800" },
  foodRowLeft:  { flex: 1 },
  foodLabel:    { fontSize: 14, fontWeight: "600", color: "#1A1A1A" },
  foodGrams:    { fontSize: 12, color: "#888", marginTop: 2 },
  foodRowRight:    { alignItems: "flex-end", gap: 4 },
  foodCal:         { fontSize: 14, fontWeight: "700", color: "#1A1A1A" },
  confBadge:       { borderRadius: 4, paddingHorizontal: 6, paddingVertical: 2 },
  confText:        { fontSize: 10, fontWeight: "600" },
  itemActions:     { flexDirection: "row", gap: 6, alignItems: "center" },
  itemEditBtn:     { padding: 2 },
  itemEditIcon:    { fontSize: 13 },
  itemDeleteBtn:   { padding: 2 },
  itemDeleteIcon:  { fontSize: 13, opacity: 0.5 },

  addFoodBtn: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1.5,
    borderColor: "#4CAF50",
    borderStyle: "dashed",
    borderRadius: 12,
    padding: 14,
    marginBottom: 24,
  },
  addFoodBtnText: { fontSize: 15, fontWeight: "600", color: "#4CAF50" },

  notesCard: {
    backgroundColor: "#E8F5E9",
    borderRadius: 12,
    padding: 16,
    marginTop: 8,
  },
  notesTitle: { fontSize: 13, fontWeight: "700", color: "#2E7D32", marginBottom: 6 },
  notesBody:  { fontSize: 13, color: "#2E7D32", lineHeight: 20 },
});
