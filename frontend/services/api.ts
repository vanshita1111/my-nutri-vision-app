/**
 * Typed API client for the Nutrition Vision backend.
 * All endpoints mirror the FastAPI routes.
 */

function getBaseUrl(): string {
  // On web, use same origin so the proxy routes /api/* to the backend — no CORS needed.
  if (typeof window !== "undefined" && typeof document !== "undefined") {
    return `${window.location.origin}/api/v1`;
  }
  // On native (Expo Go), fall back to the baked-in env var.
  return process.env.EXPO_PUBLIC_API_URL ?? "http://localhost:8000/api/v1";
}

const BASE_URL = getBaseUrl();

// ── Types ──────────────────────────────────────────────────────────────────

export interface MacroNutrients {
  calories: number;
  protein_g: number;
  fat_g: number;
  carbs_g: number;
  fiber_g: number;
}

export interface FoodItemResult {
  label: string;
  grams: number;
  gram_confidence: "high" | "medium" | "low";
  nutrition: MacroNutrients;
  nutrition_source?: string;
  is_hidden_ingredient?: boolean;
}

export interface BloodSugarBreakdown {
  score: number;
  level: "low" | "moderate" | "high";
  glycemic_load: number;
  raw_glycemic_load: number;
  carb_density: number;
  fiber_impact: number;
  protein_buffer: number;
  fat_buffer: number;
  explanation: string;
  recommendations: string[];
  disclaimer: string;
  per_item_gi: Record<string, number>;
}

export interface AnalysisResult {
  items: FoodItemResult[];
  hidden_ingredients: FoodItemResult[];
  total: MacroNutrients;
  llm_notes?: string;
  llm_confidence?: "high" | "medium" | "low";
  analysis_version: string;
  analyzed_at?: string;
  blood_sugar_impact?: BloodSugarBreakdown;
}

export interface AnalysisJob {
  job_id: string;
  status: "queued" | "processing" | "complete" | "failed";
  result?: AnalysisResult;
  error?: string;
}

export interface FoodItemDetail {
  id: string;
  label: string;
  grams: number;
  gram_confidence: "high" | "medium" | "low";
  is_hidden_ingredient: boolean;
  nutrition_source?: string;
  nutrition: MacroNutrients;
}

export interface MealDetail {
  id: string;
  meal_type?: string;
  total_calories?: number;
  total_protein_g?: number;
  total_fat_g?: number;
  total_carbs_g?: number;
  total_fiber_g?: number;
  llm_notes?: string;
  analysis_version?: string;
  eaten_at: string;
  food_items: FoodItemDetail[];
  blood_sugar_impact?: BloodSugarBreakdown;
}

export interface MealSummary {
  id: string;
  meal_type?: string;
  total_calories?: number;
  total_protein_g?: number;
  total_fat_g?: number;
  total_carbs_g?: number;
  eaten_at: string;
  item_count: number;
}

export interface DailyNutrition {
  date: string;
  total_calories: number;
  total_protein_g: number;
  total_fat_g: number;
  total_carbs_g: number;
  total_fiber_g: number;
  meal_count: number;
}

export interface UserProfile {
  id: string;
  email: string;
  full_name?: string;
  is_premium: boolean;
  is_guest: boolean;
  auth_provider?: string;
  date_of_birth?: string;
  weight_kg?: number;
  height_cm?: number;
  target_weight_kg?: number;
  activity_level?: string;
  goal?: string;
  gender?: "male" | "female" | "other";
  health_conditions?: string[];
  last_period_date?: string;
  cycle_length_days: number;
}

export interface CyclePhase {
  phase: "menstrual" | "follicular" | "ovulatory" | "luteal" | "unknown";
  day_in_cycle: number;
  calorie_adjustment_pct: number;
  protein_target_g: number;
  iron_target_mg: number;
  magnesium_target_mg: number;
  phase_notes: string;
  food_recommendations: string[];
}

export interface WeeklySummary {
  summary: string;
  tips: string[];
  avg_calories: number;
  streak_days: number;
  cycle_phase?: string;
}

export interface Exercise {
  name: string;
  sets: number;
  reps: string;
  rest_sec: number;
  note?: string;
}

export interface WorkoutDay {
  day: string;
  workout_type: string;
  focus: string;
  exercises: Exercise[];
  duration_mins: number;
  cardio_note?: string;
}

export interface Supplement {
  name: string;
  reason: string;
  timing: string;
  priority: "essential" | "recommended" | "optional";
  dose: string;
}

export interface Recommendations {
  daily_steps: number;
  water_glasses: number;
  water_ml: number;
  workout_plan: WorkoutDay[];
  supplements: Supplement[];
  lifestyle_tips: string[];
  weekly_workout_summary: string;
  goal_timeline_estimate: string;
}

// ── Auth store (simple in-memory; replace with SecureStore in prod) ─────────

let _authToken: string | null = null;

export function setAuthToken(token: string | null) {
  _authToken = token;
}

// ── Fetch helper ────────────────────────────────────────────────────────────

async function request<T>(path: string, options: RequestInit = {}): Promise<T> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(options.headers as Record<string, string>),
  };
  if (_authToken) {
    headers["Authorization"] = `Bearer ${_authToken}`;
  }

  const resp = await fetch(`${BASE_URL}${path}`, { ...options, headers });

  if (!resp.ok) {
    const body = await resp.json().catch(() => ({}));
    throw new Error(body.detail ?? `HTTP ${resp.status}`);
  }
  return resp.json() as Promise<T>;
}

// ── API methods ──────────────────────────────────────────────────────────────

export const api = {
  // Auth
  async register(email: string, password: string, fullName?: string) {
    return request<{ access_token: string; token_type: string }>("/auth/register", {
      method: "POST",
      body: JSON.stringify({ email, password, full_name: fullName }),
    });
  },

  async login(email: string, password: string) {
    return request<{ access_token: string; token_type: string }>("/auth/login", {
      method: "POST",
      body: JSON.stringify({ email, password }),
    });
  },

  async socialAuth(provider: "google" | "apple", tokens: { access_token?: string; identity_token?: string; full_name?: string }) {
    return request<{ access_token: string; token_type: string }>("/auth/social", {
      method: "POST",
      body: JSON.stringify({ provider, ...tokens }),
    });
  },

  async guestLogin() {
    return request<{ access_token: string; token_type: string }>("/auth/guest", {
      method: "POST",
    });
  },

  async forgotPassword(email: string) {
    return request<{ message: string }>("/auth/forgot-password", {
      method: "POST",
      body: JSON.stringify({ email }),
    });
  },

  async resetPassword(code: string, newPassword: string) {
    return request<{ message: string }>("/auth/reset-password", {
      method: "POST",
      body: JSON.stringify({ code, new_password: newPassword }),
    });
  },

  // Analysis
  async submitAnalysis(photoPath: string): Promise<AnalysisJob> {
    const formData = new FormData();
    formData.append("image", {
      uri: photoPath,
      type: "image/jpeg",
      name: "meal.jpg",
    } as unknown as Blob);

    const headers: Record<string, string> = {};
    if (_authToken) headers["Authorization"] = `Bearer ${_authToken}`;

    const resp = await fetch(`${BASE_URL}/analysis`, {
      method: "POST",
      headers,
      body: formData,
    });

    if (!resp.ok) {
      const body = await resp.json().catch(() => ({}));
      throw new Error(body.detail ?? `HTTP ${resp.status}`);
    }
    return resp.json();
  },

  async getAnalysisResult(jobId: string): Promise<AnalysisJob> {
    return request<AnalysisJob>(`/analysis/${jobId}`);
  },

  async correctFoodItem(jobId: string, foodItemId: string, correctedLabel?: string, correctedGrams?: number) {
    return request(`/analysis/${jobId}/correct`, {
      method: "POST",
      body: JSON.stringify({ food_item_id: foodItemId, corrected_label: correctedLabel, corrected_grams: correctedGrams }),
    });
  },

  // Meals
  async getMeals(limit = 20, offset = 0): Promise<MealSummary[]> {
    return request<MealSummary[]>(`/meals?limit=${limit}&offset=${offset}`);
  },

  async getMeal(mealId: string): Promise<MealDetail> {
    return request<MealDetail>(`/meals/${mealId}`);
  },

  /**
   * Called after analysis completes. Returns the meal that was auto-persisted
   * for this job, so we can navigate to meals/[id].
   */
  async saveMeal(jobId: string): Promise<MealDetail> {
    return request<MealDetail>(`/meals/from-job/${jobId}`, { method: "POST" });
  },

  async adjustPortions(
    mealId: string,
    adjustments: { food_item_id: string; multiplier: number }[]
  ): Promise<MealDetail> {
    return request<MealDetail>(`/meals/${mealId}/portions`, {
      method: "PATCH",
      body: JSON.stringify({ adjustments }),
    });
  },

  async deleteMeal(mealId: string) {
    return request(`/meals/${mealId}`, { method: "DELETE" });
  },

  // Nutrition
  async getDailyNutrition(days = 7): Promise<DailyNutrition[]> {
    return request<DailyNutrition[]>(`/nutrition/daily?days=${days}`);
  },

  async getCyclePhase(): Promise<CyclePhase> {
    return request<CyclePhase>("/nutrition/cycle-phase");
  },

  async getDailyGoals() {
    return request("/nutrition/daily-goals");
  },

  async searchFoods(query: string) {
    return request(`/nutrition/search?q=${encodeURIComponent(query)}`);
  },

  async getWeeklySummary() {
    return request<WeeklySummary>("/coaching/weekly-summary");
  },

  async getRecommendations() {
    return request<Recommendations>("/coaching/recommendations");
  },

  // Profile
  async getProfile() {
    return request<UserProfile>("/me");
  },

  async updateProfile(updates: {
    full_name?: string;
    weight_kg?: number;
    height_cm?: number;
    target_weight_kg?: number;
    activity_level?: "sedentary" | "light" | "moderate" | "active" | "very_active";
    goal?: "lose" | "maintain" | "gain";
    gender?: "male" | "female" | "other";
    health_conditions?: string[];
    date_of_birth?: string;        // YYYY-MM-DD
    last_period_date?: string;     // YYYY-MM-DD
    cycle_length_days?: number;
  }) {
    return request<UserProfile>("/me", {
      method: "PATCH",
      body: JSON.stringify(updates),
    });
  },

  async deleteFoodItem(mealId: string, itemId: string): Promise<MealDetail> {
    return request<MealDetail>(`/meals/${mealId}/items/${itemId}`, { method: "DELETE" });
  },
};
