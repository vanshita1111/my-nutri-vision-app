import React from "react";
import { View, Text, StyleSheet, TextStyle } from "react-native";

interface Props {
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

// ── Inline bold renderer ──────────────────────────────────────────────────────
// Splits "Hello **world** today" into mixed Text nodes.
function InlineText({ text, style }: { text: string; style: TextStyle }) {
  const parts = text.split(/(\*\*[^*\n]+\*\*)/g);
  if (parts.length === 1) return <Text style={style}>{text}</Text>;
  return (
    <Text style={style}>
      {parts.map((part, i) => {
        if (part.startsWith("**") && part.endsWith("**") && part.length > 4) {
          return (
            <Text key={i} style={[style, styles.bold]}>
              {part.slice(2, -2)}
            </Text>
          );
        }
        return part ? part : null;
      })}
    </Text>
  );
}

// ── Assistant message renderer ────────────────────────────────────────────────
function AssistantContent({ content, streaming }: { content: string; streaming?: boolean }) {
  const lines = content.split("\n");
  const nodes: React.ReactNode[] = [];

  lines.forEach((raw, i) => {
    const line = raw.trim();

    // Empty line → breathing space
    if (line === "") {
      nodes.push(<View key={i} style={styles.gap} />);
      return;
    }

    // Heading ## or ###
    if (line.startsWith("### ")) {
      nodes.push(
        <Text key={i} style={styles.h3}>{line.slice(4)}</Text>
      );
      return;
    }
    if (line.startsWith("## ")) {
      nodes.push(
        <Text key={i} style={styles.h2}>{line.slice(3)}</Text>
      );
      return;
    }

    // Numbered list  "1. " / "2. "
    const numMatch = line.match(/^(\d+)\.\s(.+)/);
    if (numMatch) {
      nodes.push(
        <View key={i} style={styles.listRow}>
          <Text style={styles.listNum}>{numMatch[1]}.</Text>
          <InlineText text={numMatch[2]} style={styles.bodyText} />
        </View>
      );
      return;
    }

    // Bullet  "- " / "• " / "* "
    const bulletMatch = line.match(/^[-•*]\s(.+)/);
    if (bulletMatch) {
      nodes.push(
        <View key={i} style={styles.listRow}>
          <Text style={styles.bullet}>•</Text>
          <InlineText text={bulletMatch[1]} style={styles.bodyText} />
        </View>
      );
      return;
    }

    // Regular paragraph line
    nodes.push(
      <InlineText key={i} text={line} style={styles.bodyText} />
    );
  });

  return (
    <View>
      {nodes}
      {streaming && <Text style={styles.cursor}>▋</Text>}
    </View>
  );
}

// ── Component ─────────────────────────────────────────────────────────────────
export default function ChatBubble({ role, content, streaming = false }: Props) {
  const isUser = role === "user";

  return (
    <View style={[styles.row, isUser ? styles.rowUser : styles.rowAssistant]}>
      {!isUser && (
        <View style={styles.avatar}>
          <Text style={styles.avatarEmoji}>🥗</Text>
        </View>
      )}
      <View style={[styles.bubble, isUser ? styles.bubbleUser : styles.bubbleAssistant]}>
        {isUser ? (
          <Text style={styles.userText}>
            {content}
            {streaming && <Text style={styles.cursor}>▋</Text>}
          </Text>
        ) : (
          <AssistantContent content={content} streaming={streaming} />
        )}
      </View>
    </View>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────
const styles = StyleSheet.create({
  row: { flexDirection: "row", marginBottom: 12, paddingHorizontal: 16 },
  rowUser:      { justifyContent: "flex-end" },
  rowAssistant: { justifyContent: "flex-start", alignItems: "flex-end" },

  avatar: {
    width: 32, height: 32, borderRadius: 16,
    backgroundColor: "#E8F5E9",
    alignItems: "center", justifyContent: "center",
    marginRight: 8, marginBottom: 2,
  },
  avatarEmoji: { fontSize: 16 },

  bubble: { maxWidth: "78%", borderRadius: 18, paddingHorizontal: 14, paddingVertical: 10 },
  bubbleUser: {
    backgroundColor: "#4CAF50",
    borderBottomRightRadius: 4,
  },
  bubbleAssistant: {
    backgroundColor: "#ffffff",
    borderBottomLeftRadius: 4,
    shadowColor: "#000", shadowOpacity: 0.06,
    shadowRadius: 6, shadowOffset: { width: 0, height: 1 },
    elevation: 2,
  },

  userText: { fontSize: 15, lineHeight: 22, color: "#ffffff" },

  bodyText: { fontSize: 15, lineHeight: 22, color: "#1A1A1A", flexShrink: 1 } as TextStyle,
  bold:     { fontWeight: "700" } as TextStyle,

  h2: { fontSize: 16, fontWeight: "700", color: "#1A1A1A", marginTop: 8, marginBottom: 2 },
  h3: { fontSize: 15, fontWeight: "700", color: "#2E7D32", marginTop: 6, marginBottom: 2 },

  gap: { height: 5 },

  listRow: { flexDirection: "row", marginBottom: 4, paddingRight: 4 },
  bullet:  { width: 16, fontSize: 15, lineHeight: 22, color: "#4CAF50", fontWeight: "700" },
  listNum: { width: 22, fontSize: 15, lineHeight: 22, color: "#4CAF50", fontWeight: "700" },

  cursor: { color: "#4CAF50", fontWeight: "700" },
});
