import { ScrollView, TouchableOpacity, Text, StyleSheet, View } from "react-native";

const DEFAULT_SUGGESTIONS = [
  "How much protein am I missing today?",
  "What should I eat next?",
  "Is my diet balanced?",
  "Suggest a high-protein snack",
  "What's my calorie budget left?",
  "Can I eat this before a workout?",
  "Why am I not hitting my goals?",
  "Give me a weekly summary",
];

interface Props {
  onSelect: (question: string) => void;
  suggestions?: string[];
}

export default function SuggestedQuestions({ onSelect, suggestions = DEFAULT_SUGGESTIONS }: Props) {
  return (
    <View style={styles.wrapper}>
      <ScrollView
        horizontal
        showsHorizontalScrollIndicator={false}
        contentContainerStyle={styles.scroll}
        keyboardShouldPersistTaps="handled"
      >
        {suggestions.map((q, i) => (
          <TouchableOpacity key={i} style={styles.chip} onPress={() => onSelect(q)} activeOpacity={0.7}>
            <Text style={styles.chipText}>{q}</Text>
          </TouchableOpacity>
        ))}
      </ScrollView>
    </View>
  );
}

const styles = StyleSheet.create({
  wrapper: {
    borderTopWidth: 1,
    borderTopColor: "#F0F0F0",
    paddingVertical: 10,
    backgroundColor: "#FAFAFA",
  },
  scroll: {
    paddingHorizontal: 16,
    gap: 8,
  },
  chip: {
    backgroundColor: "#E8F5E9",
    borderRadius: 20,
    paddingHorizontal: 14,
    paddingVertical: 8,
    borderWidth: 1,
    borderColor: "#C8E6C9",
  },
  chipText: {
    fontSize: 13,
    color: "#2E7D32",
    fontWeight: "500",
  },
});
