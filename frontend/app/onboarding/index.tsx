/**
 * Auth / Onboarding screens.
 *
 * Flow:
 *   welcome  →  (provider choice)
 *   email    →  login | register | forgot-password | reset-password
 *   social   →  Google or Apple OAuth → backend exchange
 *   guest    →  instant anonymous session
 *   setup    →  gender selection (first sign-in only, any provider)
 */

import { useState, useRef, useEffect } from "react";
import {
  View, Text, TextInput, TouchableOpacity, StyleSheet,
  KeyboardAvoidingView, Platform, ActivityIndicator,
  ScrollView, Animated, Dimensions,
} from "react-native";
import { useMutation } from "@tanstack/react-query";
import * as WebBrowser from "expo-web-browser";
import * as Google from "expo-auth-session/providers/google";
import * as AppleAuthentication from "expo-apple-authentication";
import Svg, { Path, Circle, G } from "react-native-svg";
import { api, setAuthToken } from "@/services/api";
import { useAuthStore } from "@/store/authStore";
import { Colors, Typography, Spacing, Radii, Shadows } from "@/constants/theme";

WebBrowser.maybeCompleteAuthSession();

const { height: SCREEN_H } = Dimensions.get("window");

// ── OAuth config ────────────────────────────────────────────────────────────
// Set these in your .env.local:
//   EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID=xxxx.apps.googleusercontent.com
//   EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID=xxxx.apps.googleusercontent.com

type Mode = "welcome" | "email-choice" | "login" | "register" | "forgot" | "reset" | "setup" | "setup-conditions";
type Gender = "male" | "female" | "other";

const GENDER_OPTIONS: { key: Gender; label: string; emoji: string }[] = [
  { key: "male",   label: "Male",   emoji: "♂" },
  { key: "female", label: "Female", emoji: "♀" },
  { key: "other",  label: "Prefer not to say", emoji: "⚧" },
];

const HEALTH_CONDITIONS = [
  { key: "diabetes",           label: "Diabetes",            emoji: "🩸" },
  { key: "pcod",               label: "PCOD / PCOS",         emoji: "🔄" },
  { key: "hypertension",       label: "High BP",             emoji: "❤️" },
  { key: "hypothyroidism",     label: "Hypothyroidism",      emoji: "🦋" },
  { key: "high_cholesterol",   label: "High Cholesterol",    emoji: "🫀" },
  { key: "anemia",             label: "Anaemia",             emoji: "💊" },
  { key: "fatty_liver",        label: "Fatty Liver",         emoji: "🫁" },
  { key: "ibs",                label: "IBS",                 emoji: "🌿" },
  { key: "lactose_intolerance",label: "Lactose Intolerant",  emoji: "🥛" },
  { key: "gluten_sensitivity", label: "Gluten Sensitivity",  emoji: "🌾" },
];

// ── Icons ────────────────────────────────────────────────────────────────────

function GoogleIcon() {
  return (
    <Svg width={20} height={20} viewBox="0 0 48 48">
      <Path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
      <Path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
      <Path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
      <Path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
    </Svg>
  );
}

function AppleIcon({ color = "#fff" }: { color?: string }) {
  return (
    <Svg width={20} height={20} viewBox="0 0 814 1000">
      <Path fill={color} d="M788.1 340.9c-5.8 4.5-108.2 62.2-108.2 190.5 0 148.4 130.3 200.9 134.2 202.2-.6 3.2-20.7 71.9-68.7 141.9-42.8 61.6-87.5 123.1-155.5 123.1s-85.5-39.5-164-39.5c-76 0-103.7 40.8-165.9 40.8s-105-57.8-155.5-127.4C46 447.5 0 324.7 0 212.3c0-170.7 111.3-261.1 220.5-261.1 82.5 0 150.7 54.2 198.6 54.2 45.3 0 123.7-57 217.5-57 38 0 142.5 3.2 214.8 108.9zm-281-108.9c-7.7 36.9-24.5 80.4-59.3 120.3-36.9 39.5-75.2 63.4-108.2 63.4-2.6-3.2-7.7-12.9-7.7-25.8 0-36.9 22-87 57.4-126.3 35.4-38 100.6-66.3 147.5-70.4.6 12.9 1.3 25.8.6 38.8z"/>
    </Svg>
  );
}

// ── Main component ───────────────────────────────────────────────────────────

export default function OnboardingScreen() {
  const [mode, setMode] = useState<Mode>("welcome");
  const { setToken } = useAuthStore();

  // Shared auth state
  const [pendingToken, setPendingToken]         = useState<string | null>(null);
  const [gender, setGender]                     = useState<Gender | null>(null);
  const [savingGender, setSavingGender]         = useState(false);
  const [selectedConditions, setSelectedConditions] = useState<string[]>([]);
  const [savingConditions, setSavingConditions] = useState(false);

  // Email form state
  const [email, setEmail]         = useState("");
  const [password, setPassword]   = useState("");
  const [name, setName]           = useState("");
  const [resetCode, setResetCode] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [errorMsg, setErrorMsg]   = useState<string | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  // Welcome animation
  const heroOpacity = useRef(new Animated.Value(0)).current;
  const heroY       = useRef(new Animated.Value(24)).current;
  const cardsOpacity = useRef(new Animated.Value(0)).current;
  const cardsY       = useRef(new Animated.Value(20)).current;

  useEffect(() => {
    if (mode !== "welcome") return;
    heroOpacity.setValue(0); heroY.setValue(24);
    cardsOpacity.setValue(0); cardsY.setValue(20);
    Animated.sequence([
      Animated.parallel([
        Animated.timing(heroOpacity, { toValue: 1, duration: 500, useNativeDriver: true }),
        Animated.timing(heroY,       { toValue: 0, duration: 500, useNativeDriver: true }),
      ]),
      Animated.parallel([
        Animated.timing(cardsOpacity, { toValue: 1, duration: 400, useNativeDriver: true }),
        Animated.timing(cardsY,       { toValue: 0, duration: 400, useNativeDriver: true }),
      ]),
    ]).start();
  }, [mode]);

  // ── Google OAuth ───────────────────────────────────────────────────────────
  // Fallback strings prevent useAuthRequest from throwing when env vars aren't set.
  // googleConfigured gates whether the button is rendered.
  const googleConfigured = Platform.OS === "ios"
    ? !!process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID
    : !!process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID;

  const [googleRequest, googleResponse, googlePrompt] = Google.useAuthRequest({
    webClientId: process.env.EXPO_PUBLIC_GOOGLE_WEB_CLIENT_ID ?? "not-configured",
    iosClientId: process.env.EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID ?? "not-configured",
  });

  useEffect(() => {
    if (googleResponse?.type === "success") {
      const { authentication } = googleResponse;
      if (authentication?.accessToken) {
        handleSocialToken("google", { access_token: authentication.accessToken });
      }
    }
    if (googleResponse?.type === "error") {
      setErrorMsg("Google sign-in failed. Please try again.");
    }
  }, [googleResponse]);

  // ── Shared: after any auth, check if gender is set ────────────────────────
  async function handleAuthSuccess(token: string) {
    setErrorMsg(null);
    setAuthToken(token);
    try {
      const profile = await api.getProfile();
      if (!profile.gender && !profile.is_guest) {
        setPendingToken(token);
        setMode("setup");
      } else {
        setToken(token);
      }
    } catch {
      setToken(token);
    }
  }

  // ── Social auth ────────────────────────────────────────────────────────────
  const socialMutation = useMutation({
    mutationFn: ({ provider, tokens }: { provider: "google" | "apple"; tokens: any }) =>
      api.socialAuth(provider, tokens),
    onSuccess: (data) => handleAuthSuccess(data.access_token),
    onError:   (e: Error) => setErrorMsg(e.message),
  });

  async function handleSocialToken(provider: "google" | "apple", tokens: any) {
    setErrorMsg(null);
    socialMutation.mutate({ provider, tokens });
  }

  async function handleAppleSignIn() {
    setErrorMsg(null);
    try {
      const credential = await AppleAuthentication.signInAsync({
        requestedScopes: [
          AppleAuthentication.AppleAuthenticationScope.FULL_NAME,
          AppleAuthentication.AppleAuthenticationScope.EMAIL,
        ],
      });
      const fullName = [
        credential.fullName?.givenName,
        credential.fullName?.familyName,
      ].filter(Boolean).join(" ") || undefined;

      handleSocialToken("apple", {
        identity_token: credential.identityToken,
        full_name: fullName,
      });
    } catch (e: any) {
      if (e?.code !== "ERR_CANCELED") {
        setErrorMsg("Apple sign-in failed. Please try again.");
      }
    }
  }

  // ── Email auth ─────────────────────────────────────────────────────────────
  const loginMutation = useMutation({
    mutationFn: () => api.login(email, password),
    onSuccess:  (d) => handleAuthSuccess(d.access_token),
    onError:    (e: Error) => setErrorMsg(e.message),
  });

  const registerMutation = useMutation({
    mutationFn: () => api.register(email, password, name || undefined),
    onSuccess:  (d) => handleAuthSuccess(d.access_token),
    onError:    (e: Error) => setErrorMsg(e.message),
  });

  const forgotMutation = useMutation({
    mutationFn: () => api.forgotPassword(email),
    onSuccess:  () => {
      setSuccessMsg("If that email is registered, you'll receive a reset code shortly. Check the API console in development.");
      setMode("reset");
    },
    onError: (e: Error) => setErrorMsg(e.message),
  });

  const resetMutation = useMutation({
    mutationFn: () => api.resetPassword(resetCode, newPassword),
    onSuccess:  () => {
      setSuccessMsg("Password updated! Sign in with your new password.");
      setMode("login");
      setPassword("");
    },
    onError: (e: Error) => setErrorMsg(e.message),
  });

  const guestMutation = useMutation({
    mutationFn: () => api.guestLogin(),
    onSuccess:  (d) => {
      setAuthToken(d.access_token);
      setToken(d.access_token);
    },
    onError: (e: Error) => setErrorMsg(e.message),
  });

  // ── Gender setup ────────────────────────────────────────────────────────────
  async function handleGenderContinue() {
    if (!gender || !pendingToken) return;
    setSavingGender(true);
    try { await api.updateProfile({ gender }); } catch { /* non-fatal */ }
    setSavingGender(false);
    setMode("setup-conditions");
  }

  function toggleCondition(key: string) {
    setSelectedConditions((prev) =>
      prev.includes(key) ? prev.filter((k) => k !== key) : [...prev, key]
    );
  }

  async function handleConditionsContinue() {
    if (!pendingToken) return;
    setSavingConditions(true);
    try {
      await api.updateProfile({ health_conditions: selectedConditions });
    } catch { /* non-fatal */ }
    setSavingConditions(false);
    setToken(pendingToken);
  }

  const busy = loginMutation.isLoading || registerMutation.isLoading ||
               socialMutation.isLoading || guestMutation.isLoading ||
               forgotMutation.isLoading || resetMutation.isLoading;

  function clearMessages() { setErrorMsg(null); setSuccessMsg(null); }

  // ────────────────────────────────────────────────────────────────────────────
  // ── WELCOME SCREEN ──────────────────────────────────────────────────────────
  // ────────────────────────────────────────────────────────────────────────────

  if (mode === "welcome") {
    return (
      <View style={s.welcomeRoot}>
        {/* Hero */}
        <Animated.View style={[s.hero, { opacity: heroOpacity, transform: [{ translateY: heroY }] }]}>
          <View style={s.logoWrap}>
            <Text style={s.logoEmoji}>🥗</Text>
          </View>
          <Text style={s.appName}>NutriVision</Text>
          <Text style={s.tagline}>
            AI-powered nutrition tracking{"\n"}built for your body & your goals
          </Text>
        </Animated.View>

        {/* Auth cards */}
        <Animated.View style={[s.authSheet, { opacity: cardsOpacity, transform: [{ translateY: cardsY }] }]}>
          {/* Google — only shown when EXPO_PUBLIC_GOOGLE_IOS_CLIENT_ID / WEB_CLIENT_ID is set */}
          {googleConfigured && (
            <TouchableOpacity
              style={s.socialBtn}
              onPress={() => { clearMessages(); googlePrompt(); }}
              disabled={!googleRequest || busy}
              activeOpacity={0.75}
            >
              <GoogleIcon />
              <Text style={s.socialBtnText}>Continue with Google</Text>
            </TouchableOpacity>
          )}

          {/* Apple — iOS only */}
          {Platform.OS === "ios" && (
            <TouchableOpacity
              style={s.appleBtnWrap}
              onPress={() => { clearMessages(); handleAppleSignIn(); }}
              disabled={busy}
              activeOpacity={0.8}
            >
              <AppleIcon />
              <Text style={s.appleBtnText}>Continue with Apple</Text>
            </TouchableOpacity>
          )}

          {/* Divider — only when at least one social button is shown */}
          {(googleConfigured || Platform.OS === "ios") && (
            <View style={s.dividerRow}>
              <View style={s.dividerLine} />
              <Text style={s.dividerText}>or</Text>
              <View style={s.dividerLine} />
            </View>
          )}

          {/* Email */}
          <TouchableOpacity
            style={s.emailBtn}
            onPress={() => { clearMessages(); setMode("email-choice"); }}
            disabled={busy}
            activeOpacity={0.8}
          >
            <Text style={s.emailBtnText}>Continue with Email</Text>
          </TouchableOpacity>

          {/* Guest */}
          <TouchableOpacity
            style={s.guestBtn}
            onPress={() => { clearMessages(); guestMutation.mutate(); }}
            disabled={busy}
          >
            {guestMutation.isLoading
              ? <ActivityIndicator size="small" color={Colors.inkTertiary} />
              : <Text style={s.guestBtnText}>Explore without an account →</Text>
            }
          </TouchableOpacity>

          {errorMsg ? <Text style={s.errorText}>{errorMsg}</Text> : null}

          {/* Terms */}
          <Text style={s.termsText}>
            By continuing you agree to our Terms of Service and Privacy Policy.
          </Text>
        </Animated.View>
      </View>
    );
  }

  // ────────────────────────────────────────────────────────────────────────────
  // ── EMAIL CHOICE: Login or Register ────────────────────────────────────────
  // ────────────────────────────────────────────────────────────────────────────

  if (mode === "email-choice") {
    return (
      <View style={s.formRoot}>
        <BackButton onPress={() => { clearMessages(); setMode("welcome"); }} />
        <Text style={s.formTitle}>Your email</Text>
        <Text style={s.formSubtitle}>Enter your email to sign in or create an account.</Text>
        <FormField label="Email" value={email} onChangeText={setEmail}
          placeholder="you@example.com" keyboardType="email-address" autoCapitalize="none" autoFocus />
        {errorMsg ? <ErrorBox msg={errorMsg} /> : null}
        <PrimaryButton
          label="Continue"
          loading={busy}
          onPress={async () => {
            clearMessages();
            if (!email.trim()) { setErrorMsg("Enter your email to continue."); return; }
            // Check if email exists → route to login, else register
            setMode("login");
          }}
        />
        <TouchableOpacity onPress={() => { clearMessages(); setMode("register"); }} style={s.switchRow}>
          <Text style={s.switchText}>New here? Create an account instead</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // ────────────────────────────────────────────────────────────────────────────
  // ── LOGIN ────────────────────────────────────────────────────────────────────
  // ────────────────────────────────────────────────────────────────────────────

  if (mode === "login") {
    return (
      <KeyboardAvoidingView style={s.flexRoot} behavior={Platform.OS === "ios" ? "padding" : "height"}>
        <ScrollView contentContainerStyle={s.scrollForm} keyboardShouldPersistTaps="handled">
          <BackButton onPress={() => { clearMessages(); setMode("email-choice"); }} />
          <Text style={s.formTitle}>Welcome back</Text>
          <Text style={s.formSubtitle}>Sign in to continue your journey.</Text>

          <FormField label="Email" value={email} onChangeText={setEmail}
            placeholder="you@example.com" keyboardType="email-address" autoCapitalize="none" />
          <FormField label="Password" value={password} onChangeText={setPassword}
            placeholder="Your password" secureTextEntry />

          <TouchableOpacity onPress={() => { clearMessages(); setMode("forgot"); }} style={s.forgotRow}>
            <Text style={s.forgotText}>Forgot password?</Text>
          </TouchableOpacity>

          {successMsg ? <SuccessBox msg={successMsg} /> : null}
          {errorMsg   ? <ErrorBox   msg={errorMsg}   /> : null}

          <PrimaryButton label="Sign in" loading={loginMutation.isLoading}
            onPress={() => { clearMessages(); if (!password) { setErrorMsg("Enter your password."); return; } loginMutation.mutate(); }} />

          <TouchableOpacity onPress={() => { clearMessages(); setMode("register"); }} style={s.switchRow}>
            <Text style={s.switchText}>Don't have an account? Register</Text>
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    );
  }

  // ────────────────────────────────────────────────────────────────────────────
  // ── REGISTER ────────────────────────────────────────────────────────────────
  // ────────────────────────────────────────────────────────────────────────────

  if (mode === "register") {
    return (
      <KeyboardAvoidingView style={s.flexRoot} behavior={Platform.OS === "ios" ? "padding" : "height"}>
        <ScrollView contentContainerStyle={s.scrollForm} keyboardShouldPersistTaps="handled">
          <BackButton onPress={() => { clearMessages(); setMode("email-choice"); }} />
          <Text style={s.formTitle}>Create account</Text>
          <Text style={s.formSubtitle}>Start tracking your nutrition in 30 seconds.</Text>

          <FormField label="Name (optional)" value={name} onChangeText={setName} placeholder="Priya Sharma" />
          <FormField label="Email" value={email} onChangeText={setEmail}
            placeholder="you@example.com" keyboardType="email-address" autoCapitalize="none" />
          <FormField label="Password" value={password} onChangeText={setPassword}
            placeholder="Min. 8 characters" secureTextEntry />

          {errorMsg ? <ErrorBox msg={errorMsg} /> : null}

          <PrimaryButton label="Create account" loading={registerMutation.isLoading}
            onPress={() => {
              clearMessages();
              if (password.length < 8) { setErrorMsg("Password must be at least 8 characters."); return; }
              registerMutation.mutate();
            }} />

          <TouchableOpacity onPress={() => { clearMessages(); setMode("login"); }} style={s.switchRow}>
            <Text style={s.switchText}>Already have an account? Sign in</Text>
          </TouchableOpacity>
        </ScrollView>
      </KeyboardAvoidingView>
    );
  }

  // ────────────────────────────────────────────────────────────────────────────
  // ── FORGOT PASSWORD ─────────────────────────────────────────────────────────
  // ────────────────────────────────────────────────────────────────────────────

  if (mode === "forgot") {
    return (
      <View style={s.formRoot}>
        <BackButton onPress={() => { clearMessages(); setMode("login"); }} />
        <Text style={s.formTitle}>Reset password</Text>
        <Text style={s.formSubtitle}>
          Enter your email and we'll send a reset code.
        </Text>
        <FormField label="Email" value={email} onChangeText={setEmail}
          placeholder="you@example.com" keyboardType="email-address" autoCapitalize="none" />

        {errorMsg   ? <ErrorBox   msg={errorMsg}   /> : null}
        {successMsg ? <SuccessBox msg={successMsg} /> : null}

        <PrimaryButton label="Send reset code" loading={forgotMutation.isLoading}
          onPress={() => { clearMessages(); forgotMutation.mutate(); }} />

        <TouchableOpacity onPress={() => { clearMessages(); setMode("reset"); }} style={s.switchRow}>
          <Text style={s.switchText}>Already have a code? Enter it here</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // ────────────────────────────────────────────────────────────────────────────
  // ── RESET PASSWORD ──────────────────────────────────────────────────────────
  // ────────────────────────────────────────────────────────────────────────────

  if (mode === "reset") {
    return (
      <KeyboardAvoidingView style={s.flexRoot} behavior={Platform.OS === "ios" ? "padding" : "height"}>
        <ScrollView contentContainerStyle={s.scrollForm} keyboardShouldPersistTaps="handled">
          <BackButton onPress={() => { clearMessages(); setMode("forgot"); }} />
          <Text style={s.formTitle}>New password</Text>
          <Text style={s.formSubtitle}>
            Enter the reset code from your email and choose a new password.
          </Text>
          {successMsg ? <SuccessBox msg={successMsg} /> : null}
          <FormField label="Reset code" value={resetCode} onChangeText={setResetCode}
            placeholder="e.g. aB3xYz12" autoCapitalize="none" />
          <FormField label="New password" value={newPassword} onChangeText={setNewPassword}
            placeholder="Min. 8 characters" secureTextEntry />

          {errorMsg ? <ErrorBox msg={errorMsg} /> : null}

          <PrimaryButton label="Update password" loading={resetMutation.isLoading}
            onPress={() => {
              clearMessages();
              if (!resetCode.trim()) { setErrorMsg("Enter your reset code."); return; }
              if (newPassword.length < 8) { setErrorMsg("Password must be at least 8 characters."); return; }
              resetMutation.mutate();
            }} />
        </ScrollView>
      </KeyboardAvoidingView>
    );
  }

  // ────────────────────────────────────────────────────────────────────────────
  // ── GENDER SETUP ────────────────────────────────────────────────────────────
  // ────────────────────────────────────────────────────────────────────────────

  if (mode === "setup") {
    return (
      <View style={s.setupRoot}>
        <Text style={s.setupEmoji}>👋</Text>
        <Text style={s.setupTitle}>One quick thing</Text>
        <Text style={s.setupSubtitle}>
          We personalise your nutrition targets and wellness features based on your biological sex.
        </Text>

        <View style={s.genderRow}>
          {GENDER_OPTIONS.map((opt) => (
            <TouchableOpacity
              key={opt.key}
              style={[s.genderCard, gender === opt.key && s.genderCardActive]}
              onPress={() => setGender(opt.key)}
              activeOpacity={0.8}
            >
              <Text style={s.genderEmoji}>{opt.emoji}</Text>
              <Text style={[s.genderLabel, gender === opt.key && s.genderLabelActive]}>
                {opt.label}
              </Text>
            </TouchableOpacity>
          ))}
        </View>

        <PrimaryButton
          label="Continue"
          loading={savingGender}
          disabled={!gender}
          onPress={handleGenderContinue}
        />
        <TouchableOpacity onPress={() => setMode("setup-conditions")} style={s.skipBtn}>
          <Text style={s.skipText}>Skip for now</Text>
        </TouchableOpacity>
      </View>
    );
  }

  // ────────────────────────────────────────────────────────────────────────────
  // ── HEALTH CONDITIONS SETUP ─────────────────────────────────────────────────
  // ────────────────────────────────────────────────────────────────────────────

  if (mode === "setup-conditions") {
    return (
      <ScrollView
        style={s.conditionsRoot}
        contentContainerStyle={s.conditionsContent}
        showsVerticalScrollIndicator={false}
      >
        <Text style={s.setupEmoji}>🏥</Text>
        <Text style={s.setupTitle}>Any health conditions?</Text>
        <Text style={s.setupSubtitle}>
          We'll personalise your nutrition targets and supplement suggestions.
          You can update this anytime in your Profile.
        </Text>

        <View style={s.conditionGrid}>
          {HEALTH_CONDITIONS.map((opt) => {
            const active = selectedConditions.includes(opt.key);
            return (
              <TouchableOpacity
                key={opt.key}
                style={[s.conditionChip, active && s.conditionChipActive]}
                onPress={() => toggleCondition(opt.key)}
                activeOpacity={0.75}
              >
                <Text style={s.conditionEmoji}>{opt.emoji}</Text>
                <Text style={[s.conditionLabel, active && s.conditionLabelActive]}>
                  {opt.label}
                </Text>
              </TouchableOpacity>
            );
          })}
        </View>

        <PrimaryButton
          label={
            selectedConditions.length > 0
              ? `Continue (${selectedConditions.length} selected)`
              : "None, continue"
          }
          loading={savingConditions}
          onPress={handleConditionsContinue}
        />
        <TouchableOpacity onPress={() => pendingToken && setToken(pendingToken)} style={s.skipBtn}>
          <Text style={s.skipText}>Skip for now</Text>
        </TouchableOpacity>
      </ScrollView>
    );
  }

  return null;
}

// ── Reusable sub-components ──────────────────────────────────────────────────

function BackButton({ onPress }: { onPress: () => void }) {
  return (
    <TouchableOpacity onPress={onPress} style={s.backBtn} hitSlop={12}>
      <Text style={s.backBtnText}>← Back</Text>
    </TouchableOpacity>
  );
}

function FormField({ label, ...props }: { label: string } & React.ComponentProps<typeof TextInput>) {
  return (
    <View style={s.fieldWrap}>
      <Text style={s.fieldLabel}>{label}</Text>
      <TextInput style={s.fieldInput} placeholderTextColor={Colors.inkDisabled} {...props} />
    </View>
  );
}

function PrimaryButton({ label, loading, disabled, onPress }: {
  label: string; loading?: boolean; disabled?: boolean; onPress: () => void;
}) {
  return (
    <TouchableOpacity
      style={[s.primaryBtn, (disabled || loading) && s.primaryBtnDisabled]}
      onPress={onPress}
      disabled={disabled || loading}
      activeOpacity={0.85}
    >
      {loading ? <ActivityIndicator color="#fff" /> : <Text style={s.primaryBtnText}>{label}</Text>}
    </TouchableOpacity>
  );
}

function ErrorBox({ msg }: { msg: string }) {
  return (
    <View style={s.errorBox}>
      <Text style={s.errorBoxText}>{msg}</Text>
    </View>
  );
}

function SuccessBox({ msg }: { msg: string }) {
  return (
    <View style={s.successBox}>
      <Text style={s.successBoxText}>{msg}</Text>
    </View>
  );
}

// ── Styles ───────────────────────────────────────────────────────────────────

const s = StyleSheet.create({
  // ── Welcome ──────────────────────────────────────────────────────────────
  welcomeRoot: {
    flex: 1, backgroundColor: Colors.surface,
    justifyContent: "space-between",
  },
  hero: {
    flex: 1, alignItems: "center", justifyContent: "center",
    paddingHorizontal: Spacing.xxxl,
    paddingTop: SCREEN_H * 0.06,
  },
  logoWrap: {
    width: 96, height: 96, borderRadius: 28,
    backgroundColor: Colors.primaryFaint,
    alignItems: "center", justifyContent: "center",
    marginBottom: Spacing.xl,
    ...Shadows.md,
  },
  logoEmoji:  { fontSize: 52 },
  appName:    { ...Typography.displayLarge, marginBottom: Spacing.sm, textAlign: "center" },
  tagline: {
    ...Typography.bodyLg,
    textAlign: "center", color: Colors.inkTertiary, lineHeight: 26,
  },

  authSheet: {
    backgroundColor: Colors.surface,
    borderTopLeftRadius: Radii.xxl,
    borderTopRightRadius: Radii.xxl,
    paddingHorizontal: Spacing.xl,
    paddingTop: Spacing.xxl,
    paddingBottom: Spacing.xxxl,
    ...Shadows.lg,
  },

  socialBtn: {
    flexDirection: "row", alignItems: "center", justifyContent: "center",
    gap: Spacing.md, backgroundColor: Colors.surface,
    borderWidth: 1.5, borderColor: Colors.border,
    borderRadius: Radii.lg, paddingVertical: 14,
    marginBottom: Spacing.sm,
    ...Shadows.sm,
  },
  socialBtnText: { ...Typography.headingSm, color: Colors.ink },

  appleBtnWrap: {
    flexDirection: "row", alignItems: "center", justifyContent: "center",
    gap: Spacing.md, backgroundColor: "#000",
    borderRadius: Radii.lg, paddingVertical: 14,
    marginBottom: Spacing.sm,
  },
  appleBtnText: { ...Typography.headingSm, color: "#fff" },

  dividerRow:  { flexDirection: "row", alignItems: "center", marginVertical: Spacing.lg },
  dividerLine: { flex: 1, height: 1, backgroundColor: Colors.divider },
  dividerText: { ...Typography.caption, paddingHorizontal: Spacing.md, color: Colors.inkTertiary },

  emailBtn: {
    borderWidth: 1.5, borderColor: Colors.primary,
    borderRadius: Radii.lg, paddingVertical: 14,
    alignItems: "center", marginBottom: Spacing.sm,
  },
  emailBtnText: { ...Typography.headingSm, color: Colors.primary },

  guestBtn:     { alignItems: "center", paddingVertical: Spacing.lg },
  guestBtnText: { ...Typography.bodySm, color: Colors.inkTertiary },

  termsText: {
    ...Typography.caption, textAlign: "center",
    color: Colors.inkDisabled, marginTop: Spacing.lg, lineHeight: 16,
  },

  // ── Forms ─────────────────────────────────────────────────────────────────
  flexRoot:   { flex: 1, backgroundColor: Colors.surface },
  formRoot: {
    flex: 1, backgroundColor: Colors.surface,
    padding: Spacing.xl, paddingTop: 60,
  },
  scrollForm: {
    padding: Spacing.xl, paddingTop: 60,
    backgroundColor: Colors.surface, flexGrow: 1,
  },
  backBtn:     { marginBottom: Spacing.xxl },
  backBtnText: { ...Typography.label, color: Colors.primary },

  formTitle:    { ...Typography.displayMedium, marginBottom: Spacing.sm },
  formSubtitle: { ...Typography.bodyMd, marginBottom: Spacing.xxl },

  fieldWrap:  { marginBottom: Spacing.lg },
  fieldLabel: { ...Typography.label, marginBottom: Spacing.xs },
  fieldInput: {
    borderWidth: 1.5, borderColor: Colors.border,
    borderRadius: Radii.md, padding: 14,
    fontSize: 15, color: Colors.ink,
    backgroundColor: Colors.backgroundAlt,
  },

  forgotRow: { alignItems: "flex-end", marginTop: -Spacing.sm, marginBottom: Spacing.lg },
  forgotText: { ...Typography.label, color: Colors.primary },

  primaryBtn: {
    backgroundColor: Colors.primary, borderRadius: Radii.lg,
    paddingVertical: 16, alignItems: "center", marginTop: Spacing.sm,
    ...Shadows.green,
  },
  primaryBtnDisabled: { opacity: 0.55, ...Shadows.sm },
  primaryBtnText:     { fontSize: 16, fontWeight: "700", color: "#fff" },

  switchRow: { alignItems: "center", marginTop: Spacing.xxl },
  switchText: { ...Typography.label, color: Colors.primary },

  errorBox: {
    backgroundColor: "#FFF3F3", borderWidth: 1, borderColor: "#FFCDD2",
    borderRadius: Radii.sm, padding: Spacing.md, marginBottom: Spacing.sm,
  },
  errorBoxText: { color: "#C62828", fontSize: 13, fontWeight: "500", textAlign: "center" },

  successBox: {
    backgroundColor: Colors.primaryFaint, borderWidth: 1, borderColor: Colors.primaryLight,
    borderRadius: Radii.sm, padding: Spacing.md, marginBottom: Spacing.sm,
  },
  successBoxText: { color: Colors.primaryDeep, fontSize: 13, fontWeight: "500", textAlign: "center", lineHeight: 18 },

  // ── Gender setup ──────────────────────────────────────────────────────────
  setupRoot: {
    flex: 1, backgroundColor: Colors.surface,
    alignItems: "center", justifyContent: "center",
    padding: Spacing.xxxl,
  },
  setupEmoji:    { fontSize: 56, marginBottom: Spacing.lg },
  setupTitle:    { ...Typography.displayMedium, textAlign: "center", marginBottom: Spacing.sm },
  setupSubtitle: {
    ...Typography.bodyMd, textAlign: "center",
    marginBottom: Spacing.xxxl, lineHeight: 22,
  },
  genderRow: { flexDirection: "row", gap: Spacing.md, marginBottom: Spacing.xxxl, width: "100%" },
  genderCard: {
    flex: 1, alignItems: "center", paddingVertical: Spacing.xl,
    borderRadius: Radii.lg, borderWidth: 1.5, borderColor: Colors.border,
    backgroundColor: Colors.backgroundAlt,
  },
  genderCardActive:  { borderColor: Colors.primary, backgroundColor: Colors.primaryFaint },
  genderEmoji:       { fontSize: 28, marginBottom: Spacing.sm },
  genderLabel:       { ...Typography.label, color: Colors.inkSecondary, textAlign: "center" },
  genderLabelActive: { color: Colors.primaryDark },

  skipBtn:  { marginTop: Spacing.lg, padding: Spacing.md },
  skipText: { ...Typography.label, color: Colors.inkDisabled },

  // ── Health conditions setup ───────────────────────────────────────────────
  conditionsRoot:    { flex: 1, backgroundColor: Colors.surface },
  conditionsContent: {
    alignItems: "center", padding: Spacing.xxxl, paddingBottom: 48,
  },
  conditionGrid: {
    flexDirection: "row", flexWrap: "wrap", gap: Spacing.sm,
    justifyContent: "center", marginBottom: Spacing.xxxl, width: "100%",
  },
  conditionChip: {
    flexDirection: "row", alignItems: "center", gap: Spacing.xs,
    paddingHorizontal: Spacing.md, paddingVertical: Spacing.sm + 2,
    borderRadius: Radii.pill, borderWidth: 1.5, borderColor: Colors.border,
    backgroundColor: Colors.backgroundAlt,
  },
  conditionChipActive: { borderColor: Colors.primary, backgroundColor: Colors.primaryFaint },
  conditionEmoji:      { fontSize: 14 },
  conditionLabel:      { ...Typography.label, color: Colors.inkSecondary },
  conditionLabelActive:{ color: Colors.primaryDark },
});
