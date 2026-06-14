/**
 * ManualFoodModal — search the nutrition DB, pick a food, enter grams, add to meal.
 */

import { useState, useCallback, useEffect } from "react";
import {
  Modal,
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  ActivityIndicator,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
} from "react-native";
import { useMutation } from "@tanstack/react-query";
import { api, FoodSearchResult, MealDetail } from "@/services/api";

interface Props {
  visible: boolean;
  mealId: string;
  onClose: () => void;
  onAdded: (updated: MealDetail) => void;
  /** When set, modal is in "correct" mode — patches this item instead of adding new */
  replaceItemId?: string;
  /** Pre-fill the search box with this label when correcting */
  initialQuery?: string;
}

export default function ManualFoodModal({ visible, mealId, onClose, onAdded, replaceItemId, initialQuery }: Props) {
  const isEditMode = !!replaceItemId;
  const [query, setQuery]         = useState("");
  const [results, setResults]     = useState<FoodSearchResult[]>([]);
  const [searching, setSearching] = useState(false);
  const [selected, setSelected]   = useState<FoodSearchResult | null>(null);
  const [grams, setGrams]         = useState("");
  const [searchErr, setSearchErr] = useState("");

  // Pre-fill search when opening in edit mode
  useEffect(() => {
    if (visible && isEditMode && initialQuery) {
      search(initialQuery);
    }
  }, [visible, isEditMode, initialQuery, search]);

  // Reset all state when modal closes so next open is always fresh
  useEffect(() => {
    if (!visible) {
      setQuery(""); setResults([]); setSelected(null);
      setGrams(""); setSearchErr("");
    }
  }, [visible]);

  // Debounced search
  const search = useCallback(async (text: string) => {
    setQuery(text);
    setSelected(null);
    setSearchErr("");
    if (text.trim().length < 2) { setResults([]); return; }
    setSearching(true);
    try {
      const data = await api.searchFoodsTyped(text.trim());
      setResults(data);
      if (data.length === 0) setSearchErr("No results — try a different name.");
    } catch {
      setSearchErr("Search failed. Check your connection.");
    } finally {
      setSearching(false);
    }
  }, []);

  const addMutation = useMutation({
    mutationFn: () => {
      const g = parseFloat(grams);
      const factor = g / 100;
      const p = selected!.per_100g;
      const payload = {
        label: selected!.name,
        grams: g,
        calories:  Math.round(p.calories  * factor * 10) / 10,
        protein_g: Math.round(p.protein_g * factor * 10) / 10,
        fat_g:     Math.round(p.fat_g     * factor * 10) / 10,
        carbs_g:   Math.round(p.carbs_g   * factor * 10) / 10,
        fiber_g:   Math.round((p.fiber_g || 0) * factor * 10) / 10,
        nutrition_source: selected!.source,
      };
      return isEditMode
        ? api.patchFoodItem(mealId, replaceItemId!, payload)
        : api.addFoodItem(mealId, payload);
    },
    onSuccess: (updated) => {
      onAdded(updated);
      handleClose();
    },
  });

  function handleClose() {
    setQuery(""); setResults([]); setSelected(null);
    setGrams(""); setSearchErr("");
    onClose();
  }

  const gramsNum = parseFloat(grams);
  const canAdd   = selected !== null && !isNaN(gramsNum) && gramsNum > 0 && gramsNum <= 5000;

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={handleClose}>
      <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === "ios" ? "padding" : undefined}>

        {/* Header */}
        <View style={styles.header}>
          <Text style={styles.title}>{isEditMode ? "Correct food item" : "Add food manually"}</Text>
          <TouchableOpacity onPress={handleClose} hitSlop={12}>
            <Text style={styles.closeBtn}>✕</Text>
          </TouchableOpacity>
        </View>

        {/* Search */}
        <View style={styles.searchRow}>
          <TextInput
            style={styles.searchInput}
            placeholder="Search food — e.g. dal, chicken, rice"
            placeholderTextColor="#aaa"
            value={query}
            onChangeText={search}
            autoFocus
            returnKeyType="search"
          />
          {searching && <ActivityIndicator style={styles.spinner} color="#4CAF50" />}
        </View>

        {!!searchErr && <Text style={styles.searchErr}>{searchErr}</Text>}

        {/* Results list */}
        {!selected && (
          <FlatList
            data={results}
            keyExtractor={(r) => r.food_id}
            style={styles.list}
            keyboardShouldPersistTaps="handled"
            renderItem={({ item }) => (
              <TouchableOpacity style={styles.resultRow} onPress={() => { setSelected(item); setGrams("100"); }}>
                <View style={styles.resultLeft}>
                  <Text style={styles.resultName}>{item.name}</Text>
                  <Text style={styles.resultMeta}>
                    {item.category ? `${item.category} · ` : ""}{item.source.toUpperCase()}
                  </Text>
                </View>
                <Text style={styles.resultCal}>{Math.round(item.per_100g.calories)} kcal/100g</Text>
              </TouchableOpacity>
            )}
          />
        )}

        {/* Selected food — gram entry */}
        {selected && (
          <View style={styles.selectedBlock}>
            <View style={styles.selectedHeader}>
              <Text style={styles.selectedName}>{selected.name}</Text>
              <TouchableOpacity onPress={() => { setSelected(null); setGrams(""); }} hitSlop={10}>
                <Text style={styles.changeBtn}>Change</Text>
              </TouchableOpacity>
            </View>

            <Text style={styles.gramLabel}>How many grams?</Text>
            <TextInput
              style={styles.gramInput}
              keyboardType="decimal-pad"
              value={grams}
              onChangeText={setGrams}
              placeholder="e.g. 150"
              placeholderTextColor="#aaa"
              selectTextOnFocus
            />

            {/* Nutrition preview */}
            {canAdd && (() => {
              const f = parseFloat(grams) / 100;
              const p = selected.per_100g;
              return (
                <View style={styles.preview}>
                  <PreviewPill label="Calories" value={`${Math.round(p.calories * f)} kcal`} color="#FF9800" />
                  <PreviewPill label="Protein"  value={`${(p.protein_g * f).toFixed(1)}g`}    color="#4CAF50" />
                  <PreviewPill label="Carbs"    value={`${(p.carbs_g   * f).toFixed(1)}g`}    color="#FF9800" />
                  <PreviewPill label="Fat"      value={`${(p.fat_g     * f).toFixed(1)}g`}    color="#F44336" />
                </View>
              );
            })()}

            {addMutation.isError && (
              <Text style={styles.addErr}>Failed to add — please try again.</Text>
            )}

            <TouchableOpacity
              style={[styles.addBtn, !canAdd && styles.addBtnDisabled]}
              disabled={!canAdd || addMutation.isLoading}
              onPress={() => addMutation.mutate()}
            >
              {addMutation.isLoading
                ? <ActivityIndicator color="#fff" />
                : <Text style={styles.addBtnText}>{isEditMode ? "Save changes" : "Add to meal"}</Text>
              }
            </TouchableOpacity>
          </View>
        )}
      </KeyboardAvoidingView>
    </Modal>
  );
}

function PreviewPill({ label, value, color }: { label: string; value: string; color: string }) {
  return (
    <View style={styles.pill}>
      <Text style={[styles.pillValue, { color }]}>{value}</Text>
      <Text style={styles.pillLabel}>{label}</Text>
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#FAFAFA" },

  header: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    padding: 20, paddingTop: 24, borderBottomWidth: 1, borderBottomColor: "#F0F0F0",
    backgroundColor: "#fff",
  },
  title:    { fontSize: 18, fontWeight: "700", color: "#1A1A1A" },
  closeBtn: { fontSize: 18, color: "#888" },

  searchRow: {
    flexDirection: "row", alignItems: "center",
    margin: 16, backgroundColor: "#fff",
    borderRadius: 12, borderWidth: 1, borderColor: "#E0E0E0",
    paddingHorizontal: 14,
  },
  searchInput: {
    flex: 1, height: 46, fontSize: 15, color: "#1A1A1A",
  },
  spinner: { marginLeft: 8 },
  searchErr: { fontSize: 13, color: "#888", textAlign: "center", marginTop: -8, marginBottom: 8 },

  list: { flex: 1 },
  resultRow: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center",
    backgroundColor: "#fff", marginHorizontal: 16, marginBottom: 8,
    borderRadius: 12, padding: 14,
    shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 4, elevation: 1,
  },
  resultLeft:  { flex: 1, marginRight: 8 },
  resultName:  { fontSize: 14, fontWeight: "600", color: "#1A1A1A" },
  resultMeta:  { fontSize: 11, color: "#999", marginTop: 2 },
  resultCal:   { fontSize: 13, fontWeight: "700", color: "#FF9800" },

  selectedBlock: {
    flex: 1, padding: 20,
  },
  selectedHeader: {
    flexDirection: "row", justifyContent: "space-between", alignItems: "center", marginBottom: 20,
  },
  selectedName: { fontSize: 16, fontWeight: "700", color: "#1A1A1A", flex: 1 },
  changeBtn:    { fontSize: 14, color: "#4CAF50", fontWeight: "600" },

  gramLabel: { fontSize: 13, color: "#666", marginBottom: 8 },
  gramInput: {
    backgroundColor: "#fff", borderRadius: 12, borderWidth: 1, borderColor: "#E0E0E0",
    paddingHorizontal: 16, height: 52, fontSize: 22, fontWeight: "700", color: "#1A1A1A",
  },

  preview: {
    flexDirection: "row", justifyContent: "space-around",
    backgroundColor: "#fff", borderRadius: 12, padding: 14, marginTop: 16,
    shadowColor: "#000", shadowOpacity: 0.04, shadowRadius: 4, elevation: 1,
  },
  pill:      { alignItems: "center" },
  pillValue: { fontSize: 14, fontWeight: "700" },
  pillLabel: { fontSize: 11, color: "#888", marginTop: 2 },

  addErr: { color: "#e53935", fontSize: 13, textAlign: "center", marginTop: 12 },

  addBtn: {
    marginTop: 24, backgroundColor: "#4CAF50",
    borderRadius: 14, padding: 18, alignItems: "center",
  },
  addBtnDisabled: { backgroundColor: "#ccc" },
  addBtnText: { color: "#fff", fontSize: 17, fontWeight: "700" },
});
