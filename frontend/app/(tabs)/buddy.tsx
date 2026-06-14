/**
 * AI Nutrition Buddy — conversational nutrition assistant.
 * Flagship feature: real-time streaming chat with full user context.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import {
  View,
  Text,
  TextInput,
  TouchableOpacity,
  FlatList,
  StyleSheet,
  KeyboardAvoidingView,
  Platform,
  ActivityIndicator,
  Modal,
  Alert,
  Animated,
  Keyboard,
} from "react-native";
import { useFocusEffect } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import * as Speech from "expo-speech";
import { api, BuddyConversation, BuddyMessage } from "@/services/api";
import ChatBubble from "@/components/buddy/ChatBubble";
import TypingIndicator from "@/components/buddy/TypingIndicator";
import SuggestedQuestions from "@/components/buddy/SuggestedQuestions";
import VoiceButton from "@/components/buddy/VoiceButton";

// ── Types ─────────────────────────────────────────────────────────────────────

interface UIMessage {
  id: string;
  role: "user" | "assistant";
  content: string;
  streaming?: boolean;
}

// ── Welcome message ───────────────────────────────────────────────────────────

const WELCOME: UIMessage = {
  id: "welcome",
  role: "assistant",
  content:
    "Hi! I'm NutriBuddy 🥗\n\nI can see your meal history, daily targets, and nutrition goals. Ask me anything — from 'what should I eat next?' to 'am I hitting my protein goals this week?'",
};

// ── Helpers ───────────────────────────────────────────────────────────────────

let _speakingMsgId: string | null = null;

function speakMessage(id: string, text: string) {
  if (_speakingMsgId === id) {
    Speech.stop();
    _speakingMsgId = null;
    return;
  }
  Speech.stop();
  _speakingMsgId = id;
  Speech.speak(text.slice(0, 1000), {
    language: "en-IN",
    rate: 0.9,
    onDone: () => { _speakingMsgId = null; },
    onError: () => { _speakingMsgId = null; },
  });
}

// ── History Modal ─────────────────────────────────────────────────────────────

function HistoryModal({
  visible,
  onClose,
  onSelect,
  onDeleteAll,
}: {
  visible: boolean;
  onClose: () => void;
  onSelect: (conv: BuddyConversation) => void;
  onDeleteAll: () => void;
}) {
  const { data: convs = [], isLoading } = useQuery<BuddyConversation[]>({
    queryKey: ["buddy-conversations"],
    queryFn: () => api.getBuddyConversations(),
    enabled: visible,
  });

  return (
    <Modal visible={visible} animationType="slide" presentationStyle="pageSheet" onRequestClose={onClose}>
      <View style={histStyles.root}>
        <View style={histStyles.header}>
          <Text style={histStyles.title}>Chat History</Text>
          <TouchableOpacity onPress={onClose} hitSlop={12}>
            <Text style={histStyles.close}>✕</Text>
          </TouchableOpacity>
        </View>

        {isLoading ? (
          <ActivityIndicator style={{ marginTop: 40 }} color="#4CAF50" />
        ) : convs.length === 0 ? (
          <Text style={histStyles.empty}>No conversations yet.</Text>
        ) : (
          <FlatList
            data={convs}
            keyExtractor={(c) => c.id}
            contentContainerStyle={{ padding: 16 }}
            renderItem={({ item }) => (
              <TouchableOpacity style={histStyles.row} onPress={() => { onSelect(item); onClose(); }}>
                <Text style={histStyles.rowTitle} numberOfLines={1}>{item.title ?? "Untitled"}</Text>
                <Text style={histStyles.rowMeta}>{item.message_count} messages · {new Date(item.updated_at).toLocaleDateString("en-IN", { day: "numeric", month: "short" })}</Text>
              </TouchableOpacity>
            )}
          />
        )}

        {convs.length > 0 && (
          <TouchableOpacity
            style={histStyles.deleteAll}
            onPress={() => {
              Alert.alert("Clear all history?", "This permanently deletes all conversations.", [
                { text: "Cancel", style: "cancel" },
                { text: "Delete all", style: "destructive", onPress: onDeleteAll },
              ]);
            }}
          >
            <Text style={histStyles.deleteAllText}>Delete all conversations</Text>
          </TouchableOpacity>
        )}
      </View>
    </Modal>
  );
}

// ── Main Screen ───────────────────────────────────────────────────────────────

export default function BuddyScreen() {
  const qc = useQueryClient();
  const insets = useSafeAreaInsets();

  const [messages,        setMessages]        = useState<UIMessage[]>([WELCOME]);
  const [input,           setInput]           = useState("");
  const [conversationId,  setConversationId]  = useState<string | null>(null);
  const [streaming,       setStreaming]       = useState(false);
  const [showSuggestions, setShowSuggestions] = useState(true);
  const [showHistory,     setShowHistory]     = useState(false);
  const [ttsEnabled,      setTtsEnabled]      = useState(false);

  const listRef    = useRef<FlatList>(null);
  const cancelRef  = useRef<(() => void) | null>(null);
  const inputRef   = useRef<TextInput>(null);
  const headerAnim = useRef(new Animated.Value(0)).current;

  // Animate header gradient on focus
  useFocusEffect(
    useCallback(() => {
      Animated.timing(headerAnim, { toValue: 1, duration: 500, useNativeDriver: false }).start();
      return () => {};
    }, [])
  );

  const scrollToBottom = useCallback((animated = true) => {
    setTimeout(() => listRef.current?.scrollToEnd({ animated }), 80);
  }, []);

  // Scroll to bottom whenever messages change (new message added or streaming chunk)
  useEffect(() => {
    scrollToBottom();
  }, [messages.length]);

  const sendMessage = useCallback((text: string) => {
    const trimmed = text.trim();
    if (!trimmed || streaming) return;

    Keyboard.dismiss();
    setInput("");
    setShowSuggestions(false);

    const userMsg: UIMessage = { id: `u-${Date.now()}`, role: "user", content: trimmed };
    const assistantId = `a-${Date.now()}`;
    const assistantMsg: UIMessage = { id: assistantId, role: "assistant", content: "", streaming: true };

    setMessages((prev) => [...prev, userMsg, assistantMsg]);
    setStreaming(true);
    scrollToBottom();

    let fullText = "";
    let resolvedConvId = conversationId;

    cancelRef.current = api.streamBuddyChat(
      trimmed,
      conversationId,

      // onConversationId
      (id) => {
        resolvedConvId = id;
        setConversationId(id);
        qc.invalidateQueries({ queryKey: ["buddy-conversations"] });
      },

      // onDelta — no animation during streaming to avoid stutter
      (delta) => {
        fullText += delta;
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: fullText, streaming: true } : m
          )
        );
        scrollToBottom(false);
      },

      // onDone
      () => {
        setStreaming(false);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId ? { ...m, content: fullText, streaming: false } : m
          )
        );
        if (ttsEnabled && fullText) {
          speakMessage(assistantId, fullText);
        }
      },

      // onError
      (err) => {
        setStreaming(false);
        setMessages((prev) =>
          prev.map((m) =>
            m.id === assistantId
              ? { ...m, content: `Sorry, something went wrong: ${err}`, streaming: false }
              : m
          )
        );
      }
    );
  }, [streaming, conversationId, ttsEnabled, scrollToBottom, qc]);

  const loadConversation = useCallback(async (conv: BuddyConversation) => {
    try {
      const detail = await api.getBuddyConversation(conv.id);
      const loaded: UIMessage[] = detail.messages.map((m) => ({
        id: m.id,
        role: m.role as "user" | "assistant",
        content: m.content,
      }));
      setMessages(loaded.length > 0 ? loaded : [WELCOME]);
      setConversationId(conv.id);
      setShowSuggestions(false);
      scrollToBottom();
    } catch {
      Alert.alert("Error", "Could not load conversation.");
    }
  }, [scrollToBottom]);

  const startNewConversation = useCallback(() => {
    if (cancelRef.current) { cancelRef.current(); cancelRef.current = null; }
    Speech.stop();
    setMessages([WELCOME]);
    setConversationId(null);
    setStreaming(false);
    setShowSuggestions(true);
    setInput("");
  }, []);

  const deleteAllHistory = useCallback(async () => {
    try {
      await api.deleteAllBuddyConversations();
      qc.invalidateQueries({ queryKey: ["buddy-conversations"] });
      startNewConversation();
    } catch {
      Alert.alert("Error", "Could not delete history.");
    }
  }, [qc, startNewConversation]);

  // Clean up on unmount
  useEffect(() => {
    return () => {
      if (cancelRef.current) cancelRef.current();
      Speech.stop();
    };
  }, []);

  const canSend = input.trim().length > 0 && !streaming;

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : undefined}
      keyboardVerticalOffset={0}
    >
      {/* Header */}
      <View style={[styles.header, { paddingTop: insets.top + 8 }]}>
        <View style={styles.headerLeft}>
          <View style={styles.headerIcon}>
            <Text style={styles.headerEmoji}>🥗</Text>
          </View>
          <View>
            <Text style={styles.headerTitle}>NutriBuddy</Text>
            <Text style={styles.headerSub}>Your AI nutrition coach</Text>
          </View>
        </View>
        <View style={styles.headerRight}>
          <TouchableOpacity
            style={[styles.headerBtn, ttsEnabled && styles.headerBtnActive]}
            onPress={() => { setTtsEnabled((v) => !v); Speech.stop(); }}
            hitSlop={8}
          >
            <Text style={styles.headerBtnText}>{ttsEnabled ? "🔊" : "🔇"}</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.headerBtn} onPress={() => setShowHistory(true)} hitSlop={8}>
            <Text style={styles.headerBtnText}>📋</Text>
          </TouchableOpacity>
          <TouchableOpacity style={styles.headerBtn} onPress={startNewConversation} hitSlop={8}>
            <Text style={styles.headerBtnText}>✏️</Text>
          </TouchableOpacity>
        </View>
      </View>

      {/* Messages */}
      <FlatList
        ref={listRef}
        data={messages}
        keyExtractor={(m) => m.id}
        style={styles.list}
        contentContainerStyle={styles.listContent}
        keyboardShouldPersistTaps="handled"
        renderItem={({ item }) => {
          // Don't render the placeholder empty assistant bubble — TypingIndicator
          // shows in its place via ListFooterComponent below
          if (item.role === "assistant" && item.streaming && item.content === "") return null;
          return (
            <TouchableOpacity
              activeOpacity={item.role === "assistant" ? 0.7 : 1}
              onLongPress={item.role === "assistant" ? () => speakMessage(item.id, item.content) : undefined}
            >
              <ChatBubble role={item.role} content={item.content} streaming={item.streaming} />
            </TouchableOpacity>
          );
        }}
        ListFooterComponent={
          streaming && messages[messages.length - 1]?.role === "assistant" && messages[messages.length - 1]?.content === ""
            ? <TypingIndicator />
            : null
        }
      />

      {/* Suggestions (shown on empty / new conversation) */}
      {showSuggestions && !streaming && (
        <SuggestedQuestions
          onSelect={(q) => { setInput(q); inputRef.current?.focus(); }}
        />
      )}

      {/* Input bar */}
      <View style={[styles.inputBar, { paddingBottom: Math.max(insets.bottom, 10) }]}>
        <VoiceButton
          onTranscript={(t) => { setInput(t); }}
          disabled={streaming}
        />
        <TextInput
          ref={inputRef}
          style={styles.textInput}
          value={input}
          onChangeText={setInput}
          placeholder="Ask NutriBuddy anything…"
          placeholderTextColor="#aaa"
          multiline
          maxLength={2000}
          returnKeyType="send"
          onSubmitEditing={() => sendMessage(input)}
          blurOnSubmit={false}
          editable={!streaming}
        />
        {streaming ? (
          <TouchableOpacity
            style={[styles.sendBtn, styles.stopBtn]}
            onPress={() => { cancelRef.current?.(); setStreaming(false); }}
          >
            <Text style={styles.stopText}>■</Text>
          </TouchableOpacity>
        ) : (
          <TouchableOpacity
            style={[styles.sendBtn, !canSend && styles.sendBtnDisabled]}
            onPress={() => sendMessage(input)}
            disabled={!canSend}
          >
            <Text style={styles.sendText}>↑</Text>
          </TouchableOpacity>
        )}
      </View>

      {/* History Modal */}
      <HistoryModal
        visible={showHistory}
        onClose={() => setShowHistory(false)}
        onSelect={loadConversation}
        onDeleteAll={deleteAllHistory}
      />
    </KeyboardAvoidingView>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#F7FBF7" },

  header: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 16,
    paddingBottom: 12,
    backgroundColor: "#ffffff",
    borderBottomWidth: 1,
    borderBottomColor: "#E8F5E9",
  },
  headerLeft:  { flexDirection: "row", alignItems: "center", gap: 10 },
  headerRight: { flexDirection: "row", alignItems: "center", gap: 6 },
  headerIcon: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#E8F5E9",
    alignItems: "center",
    justifyContent: "center",
  },
  headerEmoji:   { fontSize: 20 },
  headerTitle:   { fontSize: 16, fontWeight: "700", color: "#1A1A1A" },
  headerSub:     { fontSize: 11, color: "#888", marginTop: 1 },
  headerBtn: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "#F5F5F5",
    alignItems: "center",
    justifyContent: "center",
  },
  headerBtnActive: { backgroundColor: "#E8F5E9" },
  headerBtnText:   { fontSize: 16 },

  list:        { flex: 1 },
  listContent: { paddingTop: 16, paddingBottom: 8 },

  inputBar: {
    flexDirection: "row",
    alignItems: "flex-end",
    paddingHorizontal: 12,
    paddingTop: 10,
    backgroundColor: "#ffffff",
    borderTopWidth: 1,
    borderTopColor: "#F0F0F0",
    gap: 8,
  },
  textInput: {
    flex: 1,
    minHeight: 44,
    maxHeight: 120,
    backgroundColor: "#F5F5F5",
    borderRadius: 22,
    paddingHorizontal: 16,
    paddingVertical: 11,
    fontSize: 15,
    color: "#1A1A1A",
    borderWidth: 1,
    borderColor: "#E0E0E0",
  },
  sendBtn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "#4CAF50",
    alignItems: "center",
    justifyContent: "center",
  },
  sendBtnDisabled: { backgroundColor: "#C8E6C9" },
  sendText: { fontSize: 20, color: "#fff", fontWeight: "700", marginTop: -2 },
  stopBtn:  { backgroundColor: "#e53935" },
  stopText: { fontSize: 14, color: "#fff", fontWeight: "700" },
});

const histStyles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#FAFAFA" },
  header: {
    flexDirection: "row",
    justifyContent: "space-between",
    alignItems: "center",
    padding: 20,
    paddingTop: 24,
    borderBottomWidth: 1,
    borderBottomColor: "#F0F0F0",
    backgroundColor: "#fff",
  },
  title:   { fontSize: 18, fontWeight: "700", color: "#1A1A1A" },
  close:   { fontSize: 18, color: "#888" },
  empty:   { textAlign: "center", color: "#888", marginTop: 48, fontSize: 15 },
  row: {
    backgroundColor: "#fff",
    borderRadius: 12,
    padding: 16,
    marginBottom: 10,
    shadowColor: "#000",
    shadowOpacity: 0.04,
    shadowRadius: 4,
    elevation: 1,
  },
  rowTitle:   { fontSize: 14, fontWeight: "600", color: "#1A1A1A", marginBottom: 4 },
  rowMeta:    { fontSize: 12, color: "#999" },
  deleteAll:  { margin: 20, padding: 14, alignItems: "center" },
  deleteAllText: { color: "#e53935", fontSize: 14, fontWeight: "600" },
});
