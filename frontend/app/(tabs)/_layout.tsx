/**
 * Tab bar layout — bottom navigation with 5 tabs + animated icons.
 */

import { useEffect, useRef } from "react";
import { Animated, Platform, StyleSheet } from "react-native";
import { Tabs } from "expo-router";
import Svg, { Path, Circle } from "react-native-svg";

const ACTIVE   = "#4CAF50";
const INACTIVE = "#9E9E9E";

// ── Animated wrapper: spring-bounces icon when tab becomes focused ─────────

function AnimatedIcon({
  focused,
  children,
}: {
  focused: boolean;
  children: React.ReactNode;
}) {
  const scale = useRef(new Animated.Value(focused ? 1 : 0.88)).current;

  useEffect(() => {
    Animated.spring(scale, {
      toValue: focused ? 1 : 0.88,
      friction: 6,
      tension: 120,
      useNativeDriver: true,
    }).start();
  }, [focused]);

  return (
    <Animated.View style={{ transform: [{ scale }] }}>
      {children}
    </Animated.View>
  );
}

// ── SVG icons ─────────────────────────────────────────────────────────────

function HomeIcon({ color }: { color: string }) {
  return (
    <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
      <Path d="M3 9.5L12 3l9 6.5V20a1 1 0 0 1-1 1H5a1 1 0 0 1-1-1V9.5z" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
      <Path d="M9 21V12h6v9" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

function CameraIcon({ color }: { color: string }) {
  return (
    <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
      <Path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
      <Circle cx={12} cy={13} r={4} stroke={color} strokeWidth={1.8} />
    </Svg>
  );
}

function HistoryIcon({ color }: { color: string }) {
  return (
    <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
      <Path d="M3 3h18v4H3zM3 10h18v4H3zM3 17h18v4H3z" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

function InsightsIcon({ color }: { color: string }) {
  return (
    <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
      <Path d="M18 20V10M12 20V4M6 20v-6" stroke={color} strokeWidth={2} strokeLinecap="round" strokeLinejoin="round" />
    </Svg>
  );
}

function PlanIcon({ color }: { color: string }) {
  return (
    <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
      <Path d="M6 4v16M18 4v16M6 12h12" stroke={color} strokeWidth={1.8} strokeLinecap="round" strokeLinejoin="round" />
      <Circle cx={6}  cy={4}  r={2} fill={color} />
      <Circle cx={18} cy={4}  r={2} fill={color} />
      <Circle cx={6}  cy={20} r={2} fill={color} />
      <Circle cx={18} cy={20} r={2} fill={color} />
    </Svg>
  );
}

function ProfileIcon({ color }: { color: string }) {
  return (
    <Svg width={24} height={24} viewBox="0 0 24 24" fill="none">
      <Path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" stroke={color} strokeWidth={1.8} strokeLinecap="round" />
      <Circle cx={12} cy={7} r={4} stroke={color} strokeWidth={1.8} />
    </Svg>
  );
}

export default function TabLayout() {
  return (
    <Tabs
      screenOptions={{
        tabBarActiveTintColor: ACTIVE,
        tabBarInactiveTintColor: INACTIVE,
        tabBarStyle: styles.tabBar,
        tabBarLabelStyle: styles.tabLabel,
        headerShown: true,
        headerStyle: styles.header,
        headerTitleStyle: styles.headerTitle,
      }}
    >
      <Tabs.Screen
        name="home"
        options={{
          title: "Home",
          tabBarIcon: ({ color, focused }) => (
            <AnimatedIcon focused={focused}><HomeIcon color={color} /></AnimatedIcon>
          ),
        }}
      />
      <Tabs.Screen
        name="camera"
        options={{
          title: "Scan",
          headerShown: false,
          tabBarIcon: ({ color, focused }) => (
            <AnimatedIcon focused={focused}><CameraIcon color={color} /></AnimatedIcon>
          ),
        }}
      />
      <Tabs.Screen
        name="history"
        options={{
          title: "History",
          tabBarIcon: ({ color, focused }) => (
            <AnimatedIcon focused={focused}><HistoryIcon color={color} /></AnimatedIcon>
          ),
        }}
      />
      <Tabs.Screen
        name="insights"
        options={{
          title: "Insights",
          tabBarIcon: ({ color, focused }) => (
            <AnimatedIcon focused={focused}><InsightsIcon color={color} /></AnimatedIcon>
          ),
        }}
      />
      <Tabs.Screen
        name="plan"
        options={{
          title: "Plan",
          tabBarIcon: ({ color, focused }) => (
            <AnimatedIcon focused={focused}><PlanIcon color={color} /></AnimatedIcon>
          ),
        }}
      />
      <Tabs.Screen
        name="profile"
        options={{
          title: "Profile",
          tabBarIcon: ({ color, focused }) => (
            <AnimatedIcon focused={focused}><ProfileIcon color={color} /></AnimatedIcon>
          ),
        }}
      />
    </Tabs>
  );
}

const styles = StyleSheet.create({
  tabBar: {
    backgroundColor: "#ffffff",
    borderTopWidth: 1,
    borderTopColor: "#f0f0f0",
    paddingTop: 6,
    paddingBottom: Platform.OS === "ios" ? 20 : 8,
    height: Platform.OS === "ios" ? 84 : 64,
    elevation: 8,
    shadowColor: "#000",
    shadowOpacity: 0.06,
    shadowRadius: 8,
  },
  tabLabel: {
    fontSize: 11,
    fontWeight: "600",
    marginTop: 2,
  },
  header: {
    backgroundColor: "#ffffff",
    elevation: 0,
    shadowOpacity: 0,
    borderBottomWidth: 1,
    borderBottomColor: "#f0f0f0",
  },
  headerTitle: {
    fontSize: 18,
    fontWeight: "700",
    color: "#212121",
  },
});
