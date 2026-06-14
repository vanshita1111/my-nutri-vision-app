/**
 * Camera screen — multi-photo meal capture.
 *
 * Users can take 1–4 photos before submitting for analysis:
 *   Photo 1 → the food / portion
 *   Photo 2 → nutrition label / packaging  (optional, improves accuracy)
 *   Photos 3–4 → additional angles
 *
 * Claude Vision receives ALL photos in one message and cross-references them,
 * e.g. reading exact macros from a label and scaling to the visible portion.
 */

import { useRef, useCallback, useState } from "react";
import {
  View,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
  Text,
  Image,
  ScrollView,
} from "react-native";
import { CameraView, CameraType, useCameraPermissions } from "expo-camera";
import { router } from "expo-router";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { useAnalysis } from "@/hooks/useAnalysis";

const SHUTTER_SIZE = 72;
const MAX_PHOTOS   = 4;

// Hint shown below the viewfinder, changes with each captured photo
const CAPTURE_HINTS = [
  "Place your food in frame",
  "Show the nutrition label or packaging for exact macros",
  "Add another angle or close-up",
  "One more angle — then analyse when ready",
];

export default function CameraScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const { submit, isAnalysing, error } = useAnalysis();
  const insets = useSafeAreaInsets();

  const [facing,         setFacing]         = useState<CameraType>("back");
  const [capturedPhotos, setCapturedPhotos] = useState<string[]>([]);
  const [capturing,      setCapturing]      = useState(false);   // per-shot lock

  // ── Capture one photo ──────────────────────────────────────────────────────
  const capturePhoto = useCallback(async () => {
    if (!cameraRef.current || isAnalysing || capturing || capturedPhotos.length >= MAX_PHOTOS) return;
    setCapturing(true);
    try {
      const photo = await cameraRef.current.takePictureAsync({ quality: 0.85, base64: false });
      if (!photo?.uri) throw new Error("No photo captured");
      setCapturedPhotos((prev) => [...prev, photo.uri]);
    } catch (err: unknown) {
      Alert.alert("Capture failed", err instanceof Error ? err.message : "Unknown error");
    } finally {
      setCapturing(false);
    }
  }, [isAnalysing, capturing, capturedPhotos.length]);

  // ── Remove a thumbnail ─────────────────────────────────────────────────────
  const removePhoto = useCallback((index: number) => {
    setCapturedPhotos((prev) => prev.filter((_, i) => i !== index));
  }, []);

  // ── Submit all photos for analysis ────────────────────────────────────────
  const analyzePhotos = useCallback(async () => {
    if (capturedPhotos.length === 0 || isAnalysing) return;
    try {
      const jobId = await submit(capturedPhotos);
      router.push(`/analysis/${jobId}`);
    } catch (err: unknown) {
      Alert.alert("Analysis failed", err instanceof Error ? err.message : "Unknown error");
    }
  }, [capturedPhotos, isAnalysing, submit]);

  // ── Hint text ──────────────────────────────────────────────────────────────
  const hintText = isAnalysing
    ? "Uploading…"
    : capturedPhotos.length === 0
      ? CAPTURE_HINTS[0]
      : capturedPhotos.length < MAX_PHOTOS
        ? CAPTURE_HINTS[capturedPhotos.length]
        : "Max 4 photos — tap Analyse when ready";

  // ── Permission states ──────────────────────────────────────────────────────
  if (!permission) return <View style={styles.container} />;

  if (!permission.granted) {
    return (
      <View style={styles.permContainer}>
        <Text style={styles.permEmoji}>📷</Text>
        <Text style={styles.permTitle}>Camera access needed</Text>
        <Text style={styles.permSub}>Allow access to scan and analyse your meals.</Text>
        <TouchableOpacity style={styles.permBtn} onPress={requestPermission}>
          <Text style={styles.permBtnText}>Allow camera</Text>
        </TouchableOpacity>
      </View>
    );
  }

  const shutterBusy     = isAnalysing || capturing;
  const shutterMaxed    = capturedPhotos.length >= MAX_PHOTOS;
  const shutterDisabled = shutterBusy || shutterMaxed;

  return (
    <View style={styles.container}>
      {/* Live camera preview */}
      <CameraView ref={cameraRef} style={StyleSheet.absoluteFill} facing={facing} />

      {/* ── Top overlay: counter + guide frame + hint ───────────────────── */}
      <View style={[styles.topOverlay, { paddingTop: insets.top + 12 }]} pointerEvents="none">
        {capturedPhotos.length > 0 && (
          <View style={styles.counterBadge}>
            <Text style={styles.counterText}>{capturedPhotos.length}/{MAX_PHOTOS} photos</Text>
          </View>
        )}
        {capturedPhotos.length === 0 && <View style={styles.plateGuide} />}
        <Text style={styles.hint}>{hintText}</Text>
        {!!error && <Text style={styles.errorHint}>{error}</Text>}
      </View>

      {/* ── Bottom panel ────────────────────────────────────────────────── */}
      <View style={[styles.bottomPanel, { paddingBottom: Math.max(insets.bottom + 16, 32) }]}>

        {/* Thumbnail strip */}
        {capturedPhotos.length > 0 && (
          <ScrollView
            horizontal
            showsHorizontalScrollIndicator={false}
            style={styles.thumbScroll}
            contentContainerStyle={styles.thumbContent}
          >
            {capturedPhotos.map((uri, index) => (
              <View key={`thumb-${index}`} style={styles.thumbWrapper}>
                <Image source={{ uri }} style={styles.thumb} resizeMode="cover" />
                <View style={styles.thumbLabel}>
                  <Text style={styles.thumbLabelText}>
                    {index === 0 ? "Food" : index === 1 ? "Label" : `Angle ${index + 1}`}
                  </Text>
                </View>
                <TouchableOpacity
                  style={styles.thumbRemove}
                  onPress={() => removePhoto(index)}
                  hitSlop={8}
                >
                  <Text style={styles.thumbRemoveText}>✕</Text>
                </TouchableOpacity>
              </View>
            ))}

            {capturedPhotos.length < MAX_PHOTOS && (
              <TouchableOpacity
                style={styles.addMoreSlot}
                onPress={capturePhoto}
                disabled={shutterBusy}
                activeOpacity={0.7}
              >
                <Text style={styles.addMorePlus}>+</Text>
                <Text style={styles.addMoreLabel}>Add photo</Text>
              </TouchableOpacity>
            )}
          </ScrollView>
        )}

        {/* Analyse button */}
        {capturedPhotos.length > 0 && (
          <TouchableOpacity
            style={[styles.analyzeBtn, isAnalysing && styles.analyzeBtnBusy]}
            onPress={analyzePhotos}
            disabled={isAnalysing}
            activeOpacity={0.85}
          >
            {isAnalysing ? (
              <ActivityIndicator color="#fff" />
            ) : (
              <Text style={styles.analyzeBtnText}>
                Analyse {capturedPhotos.length} photo{capturedPhotos.length > 1 ? "s" : ""}  →
              </Text>
            )}
          </TouchableOpacity>
        )}

        {/* Shutter row */}
        <View style={styles.shutterRow}>
          {/* Flip */}
          <TouchableOpacity
            style={styles.sideBtn}
            onPress={() => setFacing((f) => (f === "back" ? "front" : "back"))}
            disabled={shutterBusy}
            hitSlop={8}
          >
            <Text style={styles.sideBtnIcon}>⟳</Text>
          </TouchableOpacity>

          {/* Shutter */}
          <TouchableOpacity
            style={[styles.shutterOuter, shutterDisabled && styles.shutterOuterDisabled]}
            onPress={capturePhoto}
            disabled={shutterDisabled}
            activeOpacity={0.75}
          >
            {shutterBusy ? (
              <ActivityIndicator color="#fff" size="large" />
            ) : (
              <View
                style={[
                  styles.shutterInner,
                  capturedPhotos.length > 0 && styles.shutterInnerMulti,
                ]}
              />
            )}
          </TouchableOpacity>

          {/* Clear all */}
          {capturedPhotos.length > 0 ? (
            <TouchableOpacity
              style={styles.sideBtn}
              onPress={() =>
                Alert.alert("Clear photos?", "Remove all captured photos?", [
                  { text: "Keep", style: "cancel" },
                  { text: "Clear", style: "destructive", onPress: () => setCapturedPhotos([]) },
                ])
              }
              hitSlop={8}
            >
              <Text style={styles.sideBtnIcon}>✕</Text>
            </TouchableOpacity>
          ) : (
            <View style={styles.sideBtn} />
          )}
        </View>
      </View>
    </View>
  );
}

// ── Styles ────────────────────────────────────────────────────────────────────

const styles = StyleSheet.create({
  container: { flex: 1, backgroundColor: "#000" },

  permContainer: {
    flex: 1, justifyContent: "center", alignItems: "center",
    backgroundColor: "#111", padding: 32,
  },
  permEmoji:   { fontSize: 52, marginBottom: 16 },
  permTitle:   { fontSize: 20, fontWeight: "700", color: "#fff", marginBottom: 8 },
  permSub:     { fontSize: 14, color: "rgba(255,255,255,0.65)", textAlign: "center", marginBottom: 28 },
  permBtn:     { backgroundColor: "#4CAF50", paddingHorizontal: 28, paddingVertical: 14, borderRadius: 12 },
  permBtnText: { color: "#fff", fontWeight: "700", fontSize: 15 },

  topOverlay: {
    position: "absolute", top: 0, left: 0, right: 0,
    alignItems: "center", paddingHorizontal: 24,
  },
  counterBadge: {
    backgroundColor: "rgba(0,0,0,0.55)", borderRadius: 12,
    paddingHorizontal: 12, paddingVertical: 4, marginBottom: 12,
  },
  counterText: { color: "#fff", fontSize: 13, fontWeight: "700" },
  plateGuide: {
    width: 260, height: 260, borderRadius: 130, marginTop: 40, marginBottom: 12,
    borderWidth: 2, borderColor: "rgba(255,255,255,0.5)", borderStyle: "dashed",
  },
  hint:      { color: "rgba(255,255,255,0.9)", fontSize: 13, fontWeight: "500", textAlign: "center", marginTop: 8 },
  errorHint: { color: "#FF5252", fontSize: 12, marginTop: 6, textAlign: "center" },

  bottomPanel: {
    position: "absolute", bottom: 0, left: 0, right: 0, paddingTop: 12,
  },

  thumbScroll:  { maxHeight: 96, marginBottom: 12 },
  thumbContent: { paddingHorizontal: 16, gap: 8, alignItems: "center" },
  thumbWrapper: { width: 76, height: 76, borderRadius: 10 },
  thumb: {
    width: 76, height: 76, borderRadius: 10,
    borderWidth: 2, borderColor: "#fff",
  },
  thumbLabel: {
    position: "absolute", bottom: 0, left: 0, right: 0,
    backgroundColor: "rgba(0,0,0,0.55)",
    borderBottomLeftRadius: 9, borderBottomRightRadius: 9,
    paddingVertical: 2, alignItems: "center",
  },
  thumbLabelText: { color: "#fff", fontSize: 9, fontWeight: "700" },
  thumbRemove: {
    position: "absolute", top: -6, right: -6,
    width: 20, height: 20, borderRadius: 10,
    backgroundColor: "#e53935", alignItems: "center", justifyContent: "center",
  },
  thumbRemoveText: { color: "#fff", fontSize: 10, fontWeight: "700", lineHeight: 14 },

  addMoreSlot: {
    width: 76, height: 76, borderRadius: 10,
    borderWidth: 2, borderColor: "rgba(255,255,255,0.45)", borderStyle: "dashed",
    alignItems: "center", justifyContent: "center",
  },
  addMorePlus:  { color: "rgba(255,255,255,0.8)", fontSize: 26, fontWeight: "300" },
  addMoreLabel: { color: "rgba(255,255,255,0.7)", fontSize: 9, fontWeight: "600", marginTop: 2 },

  analyzeBtn: {
    marginHorizontal: 24, marginBottom: 14, paddingVertical: 15,
    backgroundColor: "#4CAF50", borderRadius: 14, alignItems: "center",
    shadowColor: "#000", shadowOpacity: 0.3, shadowRadius: 8, elevation: 5,
  },
  analyzeBtnBusy: { backgroundColor: "#388E3C", opacity: 0.8 },
  analyzeBtnText: { color: "#fff", fontSize: 16, fontWeight: "700", letterSpacing: 0.3 },

  shutterRow: {
    flexDirection: "row", alignItems: "center",
    justifyContent: "space-between", paddingHorizontal: 40,
  },
  sideBtn:     { width: 48, height: 48, alignItems: "center", justifyContent: "center" },
  sideBtnIcon: { fontSize: 28, color: "#fff" },

  shutterOuter: {
    width: SHUTTER_SIZE, height: SHUTTER_SIZE, borderRadius: SHUTTER_SIZE / 2,
    backgroundColor: "rgba(255,255,255,0.2)",
    justifyContent: "center", alignItems: "center",
    borderWidth: 3, borderColor: "#fff",
  },
  shutterOuterDisabled: { opacity: 0.4 },
  shutterInner: {
    width: SHUTTER_SIZE - 16, height: SHUTTER_SIZE - 16,
    borderRadius: (SHUTTER_SIZE - 16) / 2, backgroundColor: "#fff",
  },
  // Inner disc turns green after first photo — signals "add another angle"
  shutterInnerMulti: { backgroundColor: "#4CAF50" },
});
