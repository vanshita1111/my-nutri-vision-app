/**
 * VoiceButton — microphone for speech-to-text input.
 *
 * Uses expo-speech-recognition for STT (on-device, no API cost).
 * Gracefully degrades if the package is unavailable (web / unsupported devices).
 */

import { useEffect, useRef, useState } from "react";
import { TouchableOpacity, StyleSheet, Animated, Alert } from "react-native";
import { requireOptionalNativeModule } from "expo-modules-core";
import Svg, { Path, Circle } from "react-native-svg";

interface Props {
  onTranscript: (text: string) => void;
  disabled?: boolean;
}

export default function VoiceButton({ onTranscript, disabled = false }: Props) {
  const [listening, setListening]   = useState(false);
  const [available, setAvailable]   = useState(false);
  const pulse = useRef(new Animated.Value(1)).current;

  useEffect(() => {
    // requireOptionalNativeModule returns null (no throw) when the module
    // isn't linked — safe in Expo Go where expo-speech-recognition is absent
    setAvailable(!!requireOptionalNativeModule("ExpoSpeechRecognition"));
  }, []);

  // Pulse animation while recording
  useEffect(() => {
    if (listening) {
      Animated.loop(
        Animated.sequence([
          Animated.timing(pulse, { toValue: 1.25, duration: 600, useNativeDriver: true }),
          Animated.timing(pulse, { toValue: 1,    duration: 600, useNativeDriver: true }),
        ])
      ).start();
    } else {
      pulse.stopAnimation();
      Animated.timing(pulse, { toValue: 1, duration: 150, useNativeDriver: true }).start();
    }
  }, [listening]);

  const handlePress = async () => {
    if (!available) {
      Alert.alert("Voice input unavailable", "Voice input requires a full app build. You can type your question instead.");
      return;
    }

    try {
      const {
        ExpoSpeechRecognitionModule,
      } = require("expo-speech-recognition");

      if (listening) {
        ExpoSpeechRecognitionModule.stop();
        setListening(false);
        return;
      }

      const status = await ExpoSpeechRecognitionModule.requestPermissionsAsync();
      if (!status.granted) {
        Alert.alert("Permission required", "Please allow microphone access to use voice input.");
        return;
      }

      setListening(true);
      ExpoSpeechRecognitionModule.start({
        lang: "en-IN",
        interimResults: false,
        maxAlternatives: 1,
      });

      // One-shot result handler
      const unsubResult = ExpoSpeechRecognitionModule.addResultListener((event: { results: { transcript: string }[] }) => {
        const transcript = event.results?.[0]?.transcript ?? "";
        if (transcript) onTranscript(transcript);
        setListening(false);
        unsubResult?.remove?.();
        unsubEnd?.remove?.();
      });

      const unsubEnd = ExpoSpeechRecognitionModule.addEndListener(() => {
        setListening(false);
        unsubResult?.remove?.();
        unsubEnd?.remove?.();
      });

    } catch (err) {
      setListening(false);
      console.warn("[VoiceButton] Speech recognition error:", err);
    }
  };

  const color = listening ? "#e53935" : disabled ? "#ccc" : "#4CAF50";

  return (
    <Animated.View style={{ transform: [{ scale: pulse }] }}>
      <TouchableOpacity
        style={[styles.btn, listening && styles.btnActive, disabled && styles.btnDisabled]}
        onPress={handlePress}
        disabled={disabled}
        hitSlop={8}
      >
        {listening ? (
          <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
            <Circle cx={12} cy={12} r={5} fill="#e53935" />
            <Circle cx={12} cy={12} r={10} stroke="#e53935" strokeWidth={2} strokeOpacity={0.3} />
          </Svg>
        ) : (
          <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
            <Path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z" stroke={color} strokeWidth={2} strokeLinecap="round" />
            <Path d="M19 10v2a7 7 0 0 1-14 0v-2" stroke={color} strokeWidth={2} strokeLinecap="round" />
            <Path d="M12 19v4M8 23h8" stroke={color} strokeWidth={2} strokeLinecap="round" />
          </Svg>
        )}
      </TouchableOpacity>
    </Animated.View>
  );
}

const styles = StyleSheet.create({
  btn: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: "#F1F8E9",
    alignItems: "center",
    justifyContent: "center",
    borderWidth: 1.5,
    borderColor: "#C8E6C9",
  },
  btnActive: {
    backgroundColor: "#FFEBEE",
    borderColor: "#FFCDD2",
  },
  btnDisabled: {
    opacity: 0.4,
  },
});
