/**
 * Design system — single source of truth for all visual tokens.
 * Import from here instead of hardcoding values in components.
 */

export const Colors = {
  // Brand
  primary:        "#4CAF50",
  primaryDark:    "#388E3C",
  primaryDeep:    "#1B5E20",
  primaryLight:   "#C8E6C9",
  primaryFaint:   "#E8F5E9",

  // Semantic
  success:        "#4CAF50",
  warning:        "#FF9800",
  error:          "#E53935",
  info:           "#2196F3",

  // Neutrals
  ink:            "#1A1A1A",
  inkSecondary:   "#555555",
  inkTertiary:    "#888888",
  inkDisabled:    "#BDBDBD",

  // Surfaces
  surface:        "#FFFFFF",
  surfaceRaised:  "#FFFFFF",
  background:     "#F5F5F5",
  backgroundAlt:  "#FAFAFA",
  border:         "#E8E8E8",
  borderStrong:   "#CCCCCC",
  divider:        "#F0F0F0",

  // Macro colours (consistent across charts)
  macroProtein:   "#4CAF50",
  macroCarbs:     "#FF9800",
  macroFat:       "#F44336",
  macroFiber:     "#9C27B0",

  // Overlay
  overlay:        "rgba(0,0,0,0.45)",
  overlayLight:   "rgba(0,0,0,0.08)",
} as const;

export const Typography = {
  displayLarge:  { fontSize: 36, fontWeight: "800" as const, letterSpacing: -0.5, color: Colors.ink },
  displayMedium: { fontSize: 28, fontWeight: "800" as const, letterSpacing: -0.3, color: Colors.ink },
  displaySmall:  { fontSize: 22, fontWeight: "700" as const, color: Colors.ink },
  headingLg:     { fontSize: 20, fontWeight: "700" as const, color: Colors.ink },
  headingMd:     { fontSize: 17, fontWeight: "700" as const, color: Colors.ink },
  headingSm:     { fontSize: 15, fontWeight: "700" as const, color: Colors.ink },
  bodyLg:        { fontSize: 16, fontWeight: "400" as const, color: Colors.inkSecondary, lineHeight: 24 },
  bodyMd:        { fontSize: 14, fontWeight: "400" as const, color: Colors.inkSecondary, lineHeight: 21 },
  bodySm:        { fontSize: 13, fontWeight: "400" as const, color: Colors.inkSecondary, lineHeight: 19 },
  caption:       { fontSize: 11, fontWeight: "500" as const, color: Colors.inkTertiary },
  label:         { fontSize: 13, fontWeight: "600" as const, color: Colors.inkSecondary },
  labelSm:       { fontSize: 11, fontWeight: "600" as const, color: Colors.inkTertiary, textTransform: "uppercase" as const, letterSpacing: 0.6 },
} as const;

export const Spacing = {
  xxs:  2,
  xs:   4,
  sm:   8,
  md:   12,
  lg:   16,
  xl:   20,
  xxl:  24,
  xxxl: 32,
  huge: 48,
} as const;

export const Radii = {
  xs:   4,
  sm:   8,
  md:   12,
  lg:   16,
  xl:   20,
  xxl:  24,
  pill: 100,
} as const;

export const Shadows = {
  sm: {
    shadowColor:   "#000",
    shadowOffset:  { width: 0, height: 1 },
    shadowOpacity: 0.05,
    shadowRadius:  3,
    elevation:     1,
  },
  md: {
    shadowColor:   "#000",
    shadowOffset:  { width: 0, height: 2 },
    shadowOpacity: 0.07,
    shadowRadius:  6,
    elevation:     2,
  },
  lg: {
    shadowColor:   "#000",
    shadowOffset:  { width: 0, height: 4 },
    shadowOpacity: 0.10,
    shadowRadius:  12,
    elevation:     4,
  },
  green: {
    shadowColor:   "#4CAF50",
    shadowOffset:  { width: 0, height: 4 },
    shadowOpacity: 0.30,
    shadowRadius:  8,
    elevation:     4,
  },
} as const;
