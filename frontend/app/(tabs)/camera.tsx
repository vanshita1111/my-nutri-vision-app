/**
 * Camera screen — capture a meal photo and submit for analysis.
 * Uses expo-camera (works in Expo Go) instead of react-native-vision-camera.
 */

import { useRef, useCallback, useState } from "react";
import {
  View,
  TouchableOpacity,
  StyleSheet,
  Alert,
  ActivityIndicator,
  Text,
} from "react-native";
import { CameraView, CameraType, useCameraPermissions } from "expo-camera";
import { router } from "expo-router";
import { useAnalysis } from "@/hooks/useAnalysis";

const SHUTTER_SIZE = 72;

export default function CameraScreen() {
  const [permission, requestPermission] = useCameraPermissions();
  const cameraRef = useRef<CameraView>(null);
  const { submit, isAnalysing, error } = useAnalysis();

  const captureAndAnalyze = useCallback(async () => {
    if (!cameraRef.current || isAnalysing) return;
    try {
      const photo = await cameraRef.current.takePictureAsync({
        quality: 0.8,
        base64: false,
      });
      if (!photo?.uri) throw new Error("No photo captured");
      const id = await submit(photo.uri);
      router.push(`/analysis/${id}`);
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "Capture failed";
      Alert.alert("Error", msg);
    }
  }, [isAnalysing, submit]);

  // Permission not yet determined
  if (!permission) {
    return <View style={styles.center} />;
  }

  // Permission denied
  if (!permission.granted) {
    return (
      <View style={styles.center}>
        <Text style={styles.permText}>Camera access is needed to analyse meals.</Text>
        <TouchableOpacity style={styles.permBtn} onPress={requestPermission}>
          <Text style={styles.permBtnText}>Allow camera access</Text>
        </TouchableOpacity>
      </View>
    );
  }

  return (
    <View style={styles.container}>
      <CameraView
        ref={cameraRef}
        style={StyleSheet.absoluteFill}
        facing="back"
      />

      {/* Plate guide overlay */}
      <View style={styles.overlay} pointerEvents="none">
        <View style={styles.plateGuide} />
        <Text style={styles.hint}>
          {isAnalysing ? "Analysing…" : "Place your meal in frame"}
        </Text>
        {error ? <Text style={styles.errorHint}>{error}</Text> : null}
      </View>

      {/* Shutter */}
      <View style={styles.controls}>
        <TouchableOpacity
          style={[styles.shutterOuter, isAnalysing && styles.shutterDisabled]}
          onPress={captureAndAnalyze}
          disabled={isAnalysing}
          activeOpacity={0.7}
        >
          {isAnalysing
            ? <ActivityIndicator color="#fff" size="large" />
            : <View style={styles.shutterInner} />
          }
        </TouchableOpacity>
      </View>
    </View>
  );
}

const styles = StyleSheet.create({
  container:  { flex: 1, backgroundColor: "#000" },
  center:     { flex: 1, justifyContent: "center", alignItems: "center", backgroundColor: "#000", padding: 24 },
  overlay:    { ...StyleSheet.absoluteFillObject, justifyContent: "center", alignItems: "center" },
  plateGuide: {
    width: 280, height: 280, borderRadius: 140,
    borderWidth: 2, borderColor: "rgba(255,255,255,0.5)", borderStyle: "dashed",
  },
  hint:       { color: "rgba(255,255,255,0.85)", fontSize: 13, fontWeight: "500", marginTop: 12 },
  errorHint:  { color: "#FF5252", fontSize: 12, marginTop: 6 },
  controls:   { position: "absolute", bottom: 48, left: 0, right: 0, alignItems: "center" },
  shutterOuter: {
    width: SHUTTER_SIZE, height: SHUTTER_SIZE, borderRadius: SHUTTER_SIZE / 2,
    backgroundColor: "rgba(255,255,255,0.25)",
    justifyContent: "center", alignItems: "center",
    borderWidth: 3, borderColor: "#fff",
  },
  shutterDisabled: { opacity: 0.45 },
  shutterInner: {
    width: SHUTTER_SIZE - 16, height: SHUTTER_SIZE - 16,
    borderRadius: (SHUTTER_SIZE - 16) / 2, backgroundColor: "#fff",
  },
  permText:    { color: "#fff", textAlign: "center", marginBottom: 20, fontSize: 15 },
  permBtn:     { backgroundColor: "#4CAF50", paddingHorizontal: 24, paddingVertical: 12, borderRadius: 8 },
  permBtnText: { color: "#fff", fontWeight: "700" },
});
