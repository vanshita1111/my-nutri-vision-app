const { getDefaultConfig } = require("expo/metro-config");

const config = getDefaultConfig(__dirname);

// Resolve .mjs and .cjs module formats
config.resolver.sourceExts = [...config.resolver.sourceExts, "mjs", "cjs"];

// Force Babel to transpile any package that may contain private class fields
// (#field syntax) which Hermes in Expo Go cannot parse when left untranspiled.
//
// Pattern breakdown:
//   expo(?:-[^/]+)?        → "expo" OR "expo-router", "expo-camera", etc.
//   @expo(?:/[^/]+)?       → "@expo/vector-icons", "@expo/metro-config", etc.
//   react-native(?:-[^/]+)?→ "react-native" OR "react-native-screens", etc.
//   @react-native(?:/[^/]+)?→ "@react-native/assets", etc.
//   @tanstack(?:/[^/]+)?   → "@tanstack/react-query"
//   @react-navigation(?:/[^/]+)? → "@react-navigation/native", etc.
config.transformer.transformIgnorePatterns = [
  "node_modules/(?!(?:" + [
    "expo(?:-[^/]+)?",
    "@expo(?:/[^/]+)?",
    "@unimodules(?:/[^/]+)?",
    "react-native(?:-[^/]+)?",
    "@react-native(?:/[^/]+)?",
    "react-navigation(?:-[^/]+)?",
    "@react-navigation(?:/[^/]+)?",
    "@tanstack(?:/[^/]+)?",
    "zustand",
  ].join("|") + ")/)",
];

config.transformer.getTransformOptions = async () => ({
  transform: {
    experimentalImportSupport: false,
    inlineRequires: true,
  },
});

module.exports = config;
