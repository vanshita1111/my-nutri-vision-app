"""
Seed script: populates the `foods` Postgres table AND rewrites
embedded_nutrition.json with 300+ Indian foods (IFCT 2017 + USDA values).

Run inside Docker:
  docker compose exec api python /app/../scripts/seed_indian_foods.py
"""

import asyncio
import json
import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Food data: (name, category, cal, protein_g, fat_g, carbs_g, fiber_g,
#             iron_mg, calcium_mg, zinc_mg)   — all per 100 g
# ---------------------------------------------------------------------------

FOODS = [

    # ── Rice & Rice Dishes ──────────────────────────────────────────────────
    ("rice",                   "Rice",    130, 2.7,  0.3,  28.0, 0.4,  0.2,  10,  0.6),
    ("steamed rice",           "Rice",    130, 2.7,  0.3,  28.0, 0.4,  0.2,  10,  0.6),
    ("basmati rice",           "Rice",    130, 2.7,  0.4,  28.0, 0.2,  0.2,   5,  0.5),
    ("brown rice",             "Rice",    112, 2.3,  0.8,  24.0, 1.8,  0.5,  10,  1.0),
    ("jeera rice",             "Rice",    145, 2.5,  3.5,  27.0, 0.4,  0.3,  10,  0.6),
    ("veg fried rice",         "Rice",    160, 3.5,  5.0,  26.0, 1.2,  0.5,  15,  0.7),
    ("egg fried rice",         "Rice",    185, 6.0,  6.0,  27.0, 0.8,  0.9,  20,  0.9),
    ("chicken fried rice",     "Rice",    195, 9.0,  6.5,  26.0, 0.8,  0.8,  15,  1.0),
    ("biryani",                "Rice",    165, 6.0,  5.5,  25.0, 1.2,  0.8,  18,  1.0),
    ("veg biryani",            "Rice",    160, 4.0,  5.0,  27.0, 1.5,  0.6,  20,  0.8),
    ("chicken biryani",        "Rice",    175, 10.0, 6.0,  23.0, 1.2,  0.9,  15,  1.2),
    ("mutton biryani",         "Rice",    195, 12.0, 8.0,  22.0, 1.0,  1.2,  18,  2.5),
    ("hyderabadi biryani",     "Rice",    185, 11.0, 7.5,  22.0, 1.2,  1.0,  16,  2.0),
    ("pulao",                  "Rice",    150, 3.0,  4.0,  27.0, 1.0,  0.4,  12,  0.7),
    ("veg pulao",              "Rice",    150, 3.0,  4.0,  27.0, 1.0,  0.4,  12,  0.7),
    ("curd rice",              "Rice",    110, 3.5,  2.5,  18.0, 0.3,  0.2,  80,  0.4),
    ("lemon rice",             "Rice",    145, 2.5,  4.5,  25.0, 0.8,  0.3,  10,  0.5),
    ("tamarind rice",          "Rice",    150, 2.5,  5.0,  25.0, 1.0,  0.4,  10,  0.5),
    ("pongal",                 "Rice",    140, 3.5,  4.0,  23.0, 1.0,  0.5,  12,  0.8),
    ("ven pongal",             "Rice",    140, 3.5,  4.0,  23.0, 1.0,  0.5,  12,  0.8),
    ("khichdi",                "Rice",    120, 4.5,  2.0,  22.0, 2.0,  1.0,  20,  0.8),
    ("moong dal khichdi",      "Rice",    118, 5.0,  2.0,  21.0, 2.5,  1.2,  22,  0.9),

    # ── Dals & Legumes ──────────────────────────────────────────────────────
    ("dal",                    "Dal",     116, 7.0,  0.4,  20.0, 4.0,  2.0,  25,  0.9),
    ("toor dal",               "Dal",     116, 7.0,  0.4,  20.0, 4.0,  2.0,  25,  0.9),
    ("arhar dal",              "Dal",     116, 7.0,  0.4,  20.0, 4.0,  2.0,  25,  0.9),
    ("masoor dal",             "Dal",     116, 9.0,  0.4,  20.0, 8.0,  3.3,  19,  1.2),
    ("red lentil dal",         "Dal",     116, 9.0,  0.4,  20.0, 8.0,  3.3,  19,  1.2),
    ("chana dal",              "Dal",     164, 8.9,  2.5,  27.0, 3.9,  1.5,  45,  1.5),
    ("moong dal",              "Dal",     105, 7.6,  0.4,  18.0, 4.0,  1.4,  27,  0.9),
    ("urad dal",               "Dal",     118, 8.0,  0.6,  20.0, 3.0,  1.8,  30,  1.5),
    ("dal makhani",            "Dal",     160, 7.0,  8.0,  16.0, 4.0,  2.5,  40,  1.0),
    ("dal tadka",              "Dal",     120, 7.0,  4.0,  17.0, 4.0,  2.0,  30,  0.9),
    ("dal fry",                "Dal",     125, 7.0,  5.0,  16.0, 4.0,  2.0,  28,  0.9),
    ("dal baati",              "Dal",     310, 9.0, 14.0,  40.0, 4.0,  2.0,  28,  1.2),
    ("rajma",                  "Dal",     127, 7.5,  0.5,  23.0, 6.0,  2.5,  34,  1.1),
    ("rajma chawal",           "Dal",     135, 6.0,  1.5,  27.0, 3.5,  1.5,  22,  0.9),
    ("chole",                  "Dal",     140, 7.0,  4.0,  22.0, 6.0,  2.8,  50,  1.4),
    ("chana masala",           "Dal",     140, 7.0,  4.0,  22.0, 6.0,  2.8,  50,  1.4),
    ("pindi chana",            "Dal",     150, 7.5,  5.0,  22.0, 6.0,  3.0,  48,  1.4),
    ("kadhi",                  "Dal",      85, 3.0,  4.5,   9.0, 0.5,  0.5, 120,  0.4),
    ("kadhi pakora",           "Dal",     130, 4.0,  7.0,  14.0, 1.0,  0.7, 100,  0.5),
    ("sambar",                 "Dal",      45, 2.0,  1.5,   7.0, 2.0,  1.0,  30,  0.4),
    ("rasam",                  "Dal",      20, 0.8,  0.5,   4.0, 0.5,  0.5,  10,  0.2),

    # ── Roti & Breads ───────────────────────────────────────────────────────
    ("roti",                   "Bread",   297, 9.0,  3.7,  57.0, 2.0,  2.5,  14,  1.3),
    ("chapati",                "Bread",   297, 9.0,  3.7,  57.0, 2.0,  2.5,  14,  1.3),
    ("whole wheat roti",       "Bread",   265, 8.5,  2.5,  54.0, 3.5,  3.0,  16,  1.6),
    ("phulka",                 "Bread",   270, 9.0,  2.8,  55.0, 2.5,  2.5,  14,  1.3),
    ("paratha",                "Bread",   326, 8.0, 11.0,  48.0, 2.0,  2.2,  12,  1.1),
    ("aloo paratha",           "Bread",   280, 6.0, 10.0,  44.0, 3.0,  2.0,  14,  1.0),
    ("paneer paratha",         "Bread",   310,10.0, 12.0,  42.0, 2.5,  1.5,  80,  1.0),
    ("gobi paratha",           "Bread",   275, 7.0, 10.0,  43.0, 3.0,  2.0,  16,  1.0),
    ("dal paratha",            "Bread",   285, 9.0, 10.0,  44.0, 3.5,  2.2,  20,  1.2),
    ("methi paratha",          "Bread",   280, 8.0, 10.0,  43.0, 3.5,  3.5,  90,  1.2),
    ("naan",                   "Bread",   310, 9.5,  5.5,  56.0, 2.0,  1.5,  12,  0.8),
    ("garlic naan",            "Bread",   330, 9.0,  8.0,  55.0, 2.0,  1.5,  12,  0.8),
    ("butter naan",            "Bread",   340, 9.0,  9.5,  55.0, 2.0,  1.5,  12,  0.8),
    ("puri",                   "Bread",   380, 7.0, 20.0,  46.0, 2.0,  2.0,  12,  1.0),
    ("bhatura",                "Bread",   350, 8.0, 16.0,  46.0, 1.0,  1.5,  10,  0.8),
    ("kulcha",                 "Bread",   285, 9.0,  4.5,  54.0, 2.0,  1.5,  12,  0.8),
    ("amritsari kulcha",       "Bread",   310, 9.0,  8.0,  52.0, 3.0,  1.8,  20,  1.0),
    ("missi roti",             "Bread",   285,11.0,  4.0,  50.0, 5.0,  3.0,  40,  1.5),
    ("bajra roti",             "Bread",   270, 8.0,  4.0,  52.0, 3.0,  2.8,  14,  1.5),
    ("jowar roti",             "Bread",   265, 8.5,  3.0,  53.0, 3.5,  2.5,  14,  1.2),
    ("ragi roti",              "Bread",   260, 7.5,  2.5,  53.0, 4.0,  3.5, 344,  1.5),
    ("thepla",                 "Bread",   305, 8.0, 10.0,  46.0, 3.0,  3.0,  80,  1.2),
    ("besan cheela",           "Bread",   245,12.0,  8.0,  34.0, 6.0,  3.0,  45,  1.5),
    ("bread",                  "Bread",   265, 8.0,  3.3,  49.0, 2.3,  2.5,  20,  0.7),
    ("white bread",            "Bread",   265, 8.0,  3.3,  49.0, 2.3,  2.5,  20,  0.7),
    ("brown bread",            "Bread",   240, 9.0,  2.5,  46.0, 4.0,  3.0,  25,  1.2),

    # ── Paneer Dishes ──────────────────────────────────────────────────────
    ("paneer",                 "Paneer",  265,18.0, 20.0,   3.0, 0.0,  0.5, 480,  1.0),
    ("palak paneer",           "Paneer",  145, 6.5, 10.0,   8.0, 3.0,  2.0, 180,  0.8),
    ("paneer butter masala",   "Paneer",  185, 8.0, 13.0,  10.0, 1.5,  0.8, 150,  0.7),
    ("shahi paneer",           "Paneer",  195, 8.0, 14.0,  10.0, 1.0,  0.7, 155,  0.7),
    ("matar paneer",           "Paneer",  150, 7.0,  9.0,  12.0, 2.0,  1.2, 120,  0.8),
    ("paneer tikka",           "Paneer",  230,16.0, 14.0,   9.0, 0.5,  0.5, 320,  0.9),
    ("paneer tikka masala",    "Paneer",  195,12.0, 13.0,   9.0, 1.5,  0.8, 200,  0.8),
    ("kadai paneer",           "Paneer",  170, 8.0, 12.0,   9.0, 2.0,  0.8, 160,  0.8),
    ("paneer bhurji",          "Paneer",  200,13.0, 13.0,   7.0, 0.5,  0.6, 280,  0.9),
    ("paneer do pyaza",        "Paneer",  175, 9.0, 12.0,  10.0, 1.5,  0.7, 180,  0.8),
    ("saag paneer",            "Paneer",  150, 7.0, 10.0,   9.0, 3.0,  2.0, 190,  0.9),

    # ── Chicken Dishes ─────────────────────────────────────────────────────
    ("chicken",                "Chicken", 165,31.0,  3.6,   0.0, 0.0,  1.0,  11,  1.8),
    ("grilled chicken",        "Chicken", 165,31.0,  3.6,   0.0, 0.0,  1.0,  11,  1.8),
    ("butter chicken",         "Chicken", 155,15.0,  9.0,   5.0, 0.5,  0.8,  25,  0.9),
    ("murgh makhani",          "Chicken", 155,15.0,  9.0,   5.0, 0.5,  0.8,  25,  0.9),
    ("chicken tikka masala",   "Chicken", 170,16.0, 10.0,   6.0, 0.5,  0.9,  22,  1.0),
    ("chicken curry",          "Chicken", 165,17.0,  9.0,   4.0, 0.5,  1.0,  18,  1.2),
    ("chicken korma",          "Chicken", 185,15.0, 12.0,   5.0, 0.5,  0.8,  30,  0.9),
    ("tandoori chicken",       "Chicken", 165,22.0,  7.0,   3.0, 0.3,  0.9,  14,  1.5),
    ("chicken tikka",          "Chicken", 180,23.0,  8.0,   4.0, 0.3,  0.9,  12,  1.5),
    ("chicken 65",             "Chicken", 215,20.0, 12.0,   8.0, 0.5,  1.0,  14,  1.5),
    ("chicken keema",          "Chicken", 175,19.0, 10.0,   2.0, 0.5,  1.5,  12,  2.0),
    ("chicken kadai",          "Chicken", 170,18.0,  9.5,   5.0, 1.0,  1.0,  16,  1.3),
    ("chicken do pyaza",       "Chicken", 165,17.0,  9.0,   6.0, 1.0,  1.0,  18,  1.3),
    ("chicken vindaloo",       "Chicken", 180,18.0, 11.0,   5.0, 0.8,  1.0,  14,  1.4),
    ("chicken rezala",         "Chicken", 190,16.0, 13.0,   4.0, 0.5,  0.9,  20,  1.0),
    ("chicken roll",           "Chicken", 240,13.0, 10.0,  26.0, 1.5,  1.5,  25,  1.2),

    # ── Mutton & Lamb ──────────────────────────────────────────────────────
    ("mutton",                 "Mutton",  294,26.0, 21.0,   0.0, 0.0,  2.5,  13,  5.0),
    ("mutton curry",           "Mutton",  210,17.0, 15.0,   2.0, 0.3,  2.0,  14,  4.0),
    ("mutton rogan josh",      "Mutton",  200,17.0, 13.0,   3.0, 0.5,  2.0,  14,  4.0),
    ("mutton korma",           "Mutton",  215,16.0, 15.0,   4.0, 0.5,  1.8,  20,  3.5),
    ("keema",                  "Mutton",  195,18.0, 13.0,   2.0, 0.5,  2.5,  12,  4.5),
    ("keema matar",            "Mutton",  185,16.0, 11.0,   6.0, 2.0,  2.2,  14,  4.0),
    ("seekh kebab",            "Mutton",  200,18.0, 12.0,   5.0, 0.5,  2.0,  12,  3.5),
    ("galouti kebab",          "Mutton",  280,18.0, 20.0,   9.0, 0.5,  2.0,  12,  3.5),
    ("nihari",                 "Mutton",  225,19.0, 16.0,   2.0, 0.3,  2.5,  16,  4.5),
    ("lamb chops",             "Mutton",  250,20.0, 18.0,   0.0, 0.0,  1.8,  14,  3.0),

    # ── Fish & Seafood ─────────────────────────────────────────────────────
    ("fish",                   "Fish",     97,17.0,  2.5,   0.0, 0.0,  0.5,  20,  0.8),
    ("fish curry",             "Fish",    130,18.0,  5.0,   3.0, 0.3,  0.8,  25,  0.9),
    ("fish fry",               "Fish",    175,20.0,  9.0,   4.0, 0.3,  0.8,  22,  0.8),
    ("fish masala",            "Fish",    145,19.0,  6.0,   4.0, 0.5,  1.0,  28,  0.9),
    ("rohu fish",              "Fish",     97,17.0,  2.5,   0.0, 0.0,  0.5,  20,  0.8),
    ("pomfret",                "Fish",     95,18.0,  2.0,   0.0, 0.0,  0.6,  22,  0.6),
    ("surmai / kingfish",      "Fish",    105,19.0,  2.8,   0.0, 0.0,  0.8,  20,  0.6),
    ("prawn curry",            "Fish",    120,18.0,  4.0,   4.0, 0.5,  0.8,  70,  1.0),
    ("prawn masala",           "Fish",    135,19.0,  5.0,   5.0, 0.8,  0.9,  70,  1.0),
    ("shrimp",                 "Fish",     99,24.0,  0.3,   0.2, 0.0,  0.5,  54,  1.1),
    ("crab curry",             "Fish",    110,16.0,  4.0,   4.0, 0.3,  0.6, 100,  3.5),

    # ── Eggs ──────────────────────────────────────────────────────────────
    ("egg",                    "Eggs",    155,13.0, 11.0,   1.0, 0.0,  1.8,  50,  1.1),
    ("boiled egg",             "Eggs",    155,13.0, 11.0,   1.0, 0.0,  1.8,  50,  1.1),
    ("scrambled egg",          "Eggs",    170,12.0, 13.0,   1.0, 0.0,  1.7,  55,  1.1),
    ("omelette",               "Eggs",    165,12.0, 12.0,   2.0, 0.0,  1.7,  55,  1.0),
    ("egg curry",              "Eggs",    145,12.0,  9.0,   5.0, 0.5,  1.9,  55,  1.0),
    ("anda bhurji",            "Eggs",    175,13.0, 12.0,   5.0, 0.5,  1.8,  55,  1.1),
    ("egg roll",               "Eggs",    230,11.0, 10.0,  26.0, 1.5,  1.8,  50,  1.0),

    # ── South Indian ──────────────────────────────────────────────────────
    ("idli",                   "South Indian",  58, 2.5,  0.4,  12.0, 0.5, 0.4, 10, 0.3),
    ("dosa",                   "South Indian", 168, 4.0,  7.0,  23.0, 1.0, 0.5, 12, 0.4),
    ("masala dosa",            "South Indian", 175, 4.5,  8.0,  25.0, 2.0, 0.7, 16, 0.5),
    ("plain dosa",             "South Indian", 155, 3.5,  6.5,  22.0, 0.8, 0.4, 12, 0.4),
    ("rava dosa",              "South Indian", 185, 3.5,  9.0,  24.0, 0.8, 0.5, 10, 0.4),
    ("set dosa",               "South Indian", 160, 4.0,  7.0,  23.0, 1.0, 0.4, 12, 0.4),
    ("uttapam",                "South Indian", 130, 4.0,  4.0,  22.0, 1.5, 0.5, 16, 0.5),
    ("vada",                   "South Indian", 250, 7.0, 14.0,  27.0, 2.0, 1.0, 20, 0.8),
    ("medu vada",              "South Indian", 250, 7.0, 14.0,  27.0, 2.0, 1.0, 20, 0.8),
    ("sambhar vada",           "South Indian", 180, 6.0,  9.0,  22.0, 2.5, 1.0, 30, 0.7),
    ("rava idli",              "South Indian",  95, 3.0,  3.0,  15.0, 0.5, 0.4, 12, 0.4),
    ("coconut chutney",        "South Indian", 180, 2.0, 16.0,   7.0, 4.0, 0.5, 10, 0.3),
    ("appam",                  "South Indian", 140, 3.0,  2.5,  28.0, 0.5, 0.5, 10, 0.4),
    ("puttu",                  "South Indian", 160, 3.0,  1.5,  34.0, 1.0, 0.5, 12, 0.5),
    ("pesarattu",              "South Indian", 140, 7.0,  3.5,  22.0, 4.0, 1.0, 20, 0.8),
    ("idiyappam",              "South Indian", 140, 2.5,  0.5,  31.0, 0.3, 0.4,  8, 0.3),
    ("chettinad chicken",      "South Indian", 180,19.0, 10.0,   5.0, 1.0, 1.0, 14, 1.4),
    ("fish moilee",            "South Indian", 125,17.0,  5.5,   3.0, 0.5, 0.8, 30, 0.8),

    # ── Breakfast & Snacks ─────────────────────────────────────────────────
    ("poha",                   "Breakfast", 130, 2.0,  3.0,  24.0, 0.4, 0.5, 10, 0.4),
    ("aloo poha",              "Breakfast", 140, 2.5,  4.0,  25.0, 1.0, 0.5, 12, 0.5),
    ("upma",                   "Breakfast", 155, 4.5,  5.0,  24.0, 1.5, 0.8, 14, 0.7),
    ("rava upma",              "Breakfast", 155, 4.5,  5.0,  24.0, 1.5, 0.8, 14, 0.7),
    ("sheera",                 "Breakfast", 210, 3.0,  8.0,  32.0, 0.5, 0.5, 10, 0.5),
    ("suji halwa",             "Breakfast", 210, 3.0,  8.0,  32.0, 0.5, 0.5, 10, 0.5),
    ("vermicelli upma",        "Breakfast", 165, 4.0,  5.0,  27.0, 1.0, 0.6, 12, 0.5),
    ("sabudana khichdi",       "Breakfast", 210, 2.0,  6.0,  37.0, 0.5, 0.3, 12, 0.3),
    ("besan cheela",           "Breakfast", 245,12.0,  8.0,  34.0, 6.0, 3.0, 45, 1.5),
    ("moong dal cheela",       "Breakfast", 195,12.0,  5.0,  28.0, 5.0, 2.5, 35, 1.3),
    ("oats",                   "Breakfast",  68, 2.4,  1.4,  12.0, 1.7, 0.7, 14, 0.5),
    ("oats porridge",          "Breakfast",  68, 2.4,  1.4,  12.0, 1.7, 0.7, 14, 0.5),
    ("cornflakes",             "Breakfast", 357, 7.0,  0.9,  84.0, 2.0, 8.0, 10, 0.5),
    ("muesli",                 "Breakfast", 360, 9.0,  6.0,  68.0, 6.0, 3.5, 28, 1.5),

    # ── Street Food & Chaat ─────────────────────────────────────────────────
    ("samosa",                 "Street Food", 262, 4.0, 17.0, 25.0, 2.0, 1.0, 15, 0.6),
    ("vada pav",               "Street Food", 280, 6.0, 12.0, 38.0, 3.0, 1.2, 20, 0.8),
    ("pav bhaji",              "Street Food", 180, 4.0,  8.0, 25.0, 3.0, 1.0, 30, 0.6),
    ("pani puri",              "Street Food", 225, 4.0,  8.0, 35.0, 2.5, 0.8, 15, 0.5),
    ("gol gappa",              "Street Food", 225, 4.0,  8.0, 35.0, 2.5, 0.8, 15, 0.5),
    ("bhel puri",              "Street Food", 125, 3.5,  4.0, 20.0, 2.0, 0.8, 12, 0.5),
    ("sev puri",               "Street Food", 145, 3.5,  5.5, 22.0, 2.0, 0.8, 12, 0.5),
    ("dahi puri",              "Street Food", 135, 4.0,  4.0, 22.0, 1.5, 0.7, 60, 0.5),
    ("papdi chaat",            "Street Food", 180, 5.0,  7.0, 28.0, 2.0, 0.9, 40, 0.7),
    ("aloo chaat",             "Street Food", 120, 3.0,  4.0, 20.0, 2.5, 0.8, 16, 0.6),
    ("kachori",                "Street Food", 380, 8.0, 20.0, 44.0, 4.0, 2.0, 18, 1.0),
    ("dahi bhalla",            "Street Food", 120, 5.0,  3.5, 19.0, 1.0, 0.8, 80, 0.7),
    ("raj kachori",            "Street Food", 285, 7.0, 14.0, 38.0, 4.0, 1.5, 45, 0.9),
    ("aloo tikki",             "Street Food", 170, 3.0,  7.0, 25.0, 2.5, 0.8, 14, 0.6),
    ("dhokla",                 "Snack",       160, 5.0,  5.0, 25.0, 1.0, 1.0, 20, 0.7),
    ("khaman dhokla",          "Snack",       160, 5.0,  5.0, 25.0, 1.0, 1.0, 20, 0.7),
    ("khandvi",                "Snack",       155, 6.0,  7.0, 19.0, 1.0, 0.8, 40, 0.6),
    ("chakli",                 "Snack",       475, 8.0, 28.0, 52.0, 2.0, 2.0, 20, 1.0),
    ("murukku",                "Snack",       490, 7.0, 28.0, 55.0, 2.0, 2.0, 18, 0.9),
    ("namkeen",                "Snack",       520, 9.0, 30.0, 58.0, 2.5, 2.0, 20, 1.0),
    ("bhujia",                 "Snack",       545,12.0, 34.0, 52.0, 4.0, 3.0, 38, 1.5),
    ("mixture",                "Snack",       480, 9.0, 26.0, 55.0, 3.0, 2.0, 22, 1.0),
    ("mathri",                 "Snack",       470, 8.0, 24.0, 58.0, 2.0, 1.5, 14, 0.8),

    # ── Sweets & Desserts ──────────────────────────────────────────────────
    ("gulab jamun",            "Sweet",   310, 5.0, 12.0, 47.0, 0.5, 0.5, 80, 0.4),
    ("jalebi",                 "Sweet",   390, 1.5, 10.0, 71.0, 0.0, 0.5,  8, 0.2),
    ("gajar halwa",            "Sweet",   180, 3.0,  7.0, 27.0, 2.5, 0.5, 50, 0.3),
    ("moong dal halwa",        "Sweet",   370, 7.0, 18.0, 48.0, 2.0, 1.5, 20, 0.8),
    ("besan ladoo",            "Sweet",   440, 8.0, 22.0, 56.0, 2.0, 2.5, 40, 1.2),
    ("motichoor ladoo",        "Sweet",   395, 5.0, 14.0, 64.0, 1.0, 1.5, 30, 0.8),
    ("barfi",                  "Sweet",   380, 7.0, 16.0, 55.0, 0.0, 0.5,140, 0.4),
    ("kaju katli",             "Sweet",   520,12.0, 26.0, 63.0, 2.0, 1.0, 10, 2.5),
    ("peda",                   "Sweet",   370, 7.0, 11.0, 60.0, 0.0, 0.3,130, 0.3),
    ("kheer",                  "Sweet",   155, 4.0,  5.0, 24.0, 0.2, 0.2, 90, 0.4),
    ("rice kheer",             "Sweet",   155, 4.0,  5.0, 24.0, 0.2, 0.2, 90, 0.4),
    ("seviyan kheer",          "Sweet",   160, 4.5,  5.0, 25.0, 0.3, 0.3, 85, 0.4),
    ("sheer khurma",           "Sweet",   165, 4.5,  6.0, 25.0, 0.5, 0.4, 90, 0.5),
    ("payasam",                "Sweet",   150, 4.0,  5.0, 23.0, 0.3, 0.3, 80, 0.4),
    ("rasmalai",               "Sweet",   185, 7.0,  8.0, 24.0, 0.0, 0.3,160, 0.3),
    ("rasgulla",               "Sweet",   186, 5.5,  5.0, 31.0, 0.0, 0.4,120, 0.3),
    ("sandesh",                "Sweet",   235, 9.0,  8.0, 34.0, 0.0, 0.2,180, 0.3),
    ("mishti doi",             "Sweet",   120, 4.0,  3.5, 20.0, 0.0, 0.2,110, 0.3),
    ("kulfi",                  "Sweet",   195, 4.5,  9.0, 27.0, 0.0, 0.2,130, 0.3),
    ("mango kulfi",            "Sweet",   205, 4.0, 8.5, 30.0, 0.5, 0.2,120, 0.3),
    ("halwa",                  "Sweet",   290, 3.5, 12.0, 43.0, 0.8, 0.5, 20, 0.4),
    ("imarti",                 "Sweet",   350, 3.0,  8.0, 65.0, 0.5, 0.8, 15, 0.4),
    ("balushahi",              "Sweet",   450, 5.0, 22.0, 60.0, 0.5, 0.5, 12, 0.4),
    ("phirni",                 "Sweet",   135, 4.0,  4.0, 21.0, 0.2, 0.2, 95, 0.3),
    ("shrikhand",              "Sweet",   200, 6.0,  5.5, 34.0, 0.0, 0.2,160, 0.3),
    ("basundi",                "Sweet",   175, 5.5,  6.0, 26.0, 0.0, 0.2,180, 0.3),

    # ── Beverages ─────────────────────────────────────────────────────────
    ("chai",                   "Beverage", 40, 1.5,  1.5,  5.0, 0.0, 0.1, 40, 0.1),
    ("milk tea",               "Beverage", 40, 1.5,  1.5,  5.0, 0.0, 0.1, 40, 0.1),
    ("masala chai",            "Beverage", 45, 1.5,  1.5,  6.0, 0.0, 0.1, 42, 0.1),
    ("coffee",                 "Beverage", 35, 0.5,  2.0,  4.0, 0.0, 0.0,  8, 0.1),
    ("filter coffee",          "Beverage", 45, 1.5,  2.5,  5.0, 0.0, 0.1, 40, 0.1),
    ("lassi",                  "Beverage", 80, 3.0,  3.0, 10.0, 0.0, 0.1,100, 0.3),
    ("sweet lassi",            "Beverage", 95, 3.0,  3.0, 14.0, 0.0, 0.1,100, 0.3),
    ("mango lassi",            "Beverage",100, 3.0,  2.5, 18.0, 0.5, 0.1, 90, 0.3),
    ("chaas",                  "Beverage", 35, 2.0,  1.0,  4.5, 0.0, 0.1, 60, 0.2),
    ("buttermilk",             "Beverage", 35, 2.0,  1.0,  4.5, 0.0, 0.1, 60, 0.2),
    ("coconut water",          "Beverage", 19, 0.7,  0.2,  4.0, 1.1, 0.1, 24, 0.1),
    ("sugarcane juice",        "Beverage", 73, 0.2,  0.2, 18.0, 0.0, 0.4, 10, 0.1),
    ("nimbu pani",             "Beverage", 25, 0.4,  0.1,  6.5, 0.1, 0.1,  4, 0.1),
    ("rooh afza",              "Beverage",100, 0.0,  0.0, 25.0, 0.0, 0.0,  2, 0.0),
    ("shikanjvi",              "Beverage", 28, 0.4,  0.1,  7.0, 0.1, 0.1,  4, 0.1),

    # ── Dairy ─────────────────────────────────────────────────────────────
    ("milk",                   "Dairy",    65, 3.3,  3.7,  4.8, 0.0, 0.1,120, 0.4),
    ("full fat milk",          "Dairy",    65, 3.3,  3.7,  4.8, 0.0, 0.1,120, 0.4),
    ("toned milk",             "Dairy",    49, 3.1,  1.5,  5.0, 0.0, 0.1,110, 0.4),
    ("skimmed milk",           "Dairy",    35, 3.4,  0.1,  5.0, 0.0, 0.1,110, 0.4),
    ("curd",                   "Dairy",    60, 3.1,  3.3,  4.7, 0.0, 0.1,120, 0.4),
    ("yogurt",                 "Dairy",    60, 3.1,  3.3,  4.7, 0.0, 0.1,120, 0.4),
    ("greek yogurt",           "Dairy",   100,10.0,  5.0,  3.6, 0.0, 0.1,110, 0.5),
    ("raita",                  "Dairy",     50, 2.5,  2.0,  5.5, 0.5, 0.1, 90, 0.3),
    ("boondi raita",           "Dairy",     75, 2.5,  3.0,  9.0, 0.5, 0.1, 80, 0.3),
    ("ghee",                   "Dairy",   900, 0.0, 99.0,   0.0, 0.0, 0.0,  0, 0.0),
    ("butter",                 "Dairy",   720, 0.9, 80.0,   0.7, 0.0, 0.0, 12, 0.0),
    ("malai",                  "Dairy",   340, 2.5, 35.0,   4.0, 0.0, 0.0, 20, 0.1),
    ("cream",                  "Dairy",   340, 2.5, 35.0,   4.0, 0.0, 0.0, 20, 0.1),
    ("cheese",                 "Dairy",   350,22.0, 28.0,   2.0, 0.0, 0.2,700, 2.5),
    ("paneer",                 "Dairy",   265,18.0, 20.0,   3.0, 0.0, 0.5,480, 1.0),
    ("khoya",                  "Dairy",   330,15.0, 18.0,  28.0, 0.0, 0.1,380, 0.8),
    ("mawa",                   "Dairy",   330,15.0, 18.0,  28.0, 0.0, 0.1,380, 0.8),

    # ── Vegetables ────────────────────────────────────────────────────────
    ("potato",                 "Vegetable", 77, 2.0,  0.1, 17.0, 2.2, 0.8, 12, 0.3),
    ("aloo",                   "Vegetable", 77, 2.0,  0.1, 17.0, 2.2, 0.8, 12, 0.3),
    ("sweet potato",           "Vegetable", 86, 1.6,  0.1, 20.0, 3.0, 0.6, 30, 0.3),
    ("spinach",                "Vegetable", 23, 2.9,  0.4,  3.6, 2.2, 2.7, 99, 0.5),
    ("palak",                  "Vegetable", 23, 2.9,  0.4,  3.6, 2.2, 2.7, 99, 0.5),
    ("tomato",                 "Vegetable", 18, 0.9,  0.2,  3.9, 1.2, 0.3, 10, 0.2),
    ("onion",                  "Vegetable", 40, 1.1,  0.1,  9.3, 1.7, 0.2, 23, 0.2),
    ("carrot",                 "Vegetable", 41, 0.9,  0.2, 10.0, 2.8, 0.3, 33, 0.2),
    ("cauliflower",            "Vegetable", 25, 2.0,  0.3,  5.0, 2.0, 0.4, 22, 0.3),
    ("gobi",                   "Vegetable", 25, 2.0,  0.3,  5.0, 2.0, 0.4, 22, 0.3),
    ("bhindi",                 "Vegetable", 33, 1.9,  0.2,  7.5, 3.2, 0.4, 82, 0.3),
    ("okra",                   "Vegetable", 33, 1.9,  0.2,  7.5, 3.2, 0.4, 82, 0.3),
    ("baingan",                "Vegetable", 25, 1.0,  0.2,  6.0, 3.0, 0.2, 14, 0.2),
    ("eggplant",               "Vegetable", 25, 1.0,  0.2,  6.0, 3.0, 0.2, 14, 0.2),
    ("capsicum",               "Vegetable", 31, 1.0,  0.3,  7.0, 2.1, 0.4, 10, 0.2),
    ("green peas",             "Vegetable", 81, 5.4,  0.4, 14.4, 5.7, 1.5, 25, 1.2),
    ("matar",                  "Vegetable", 81, 5.4,  0.4, 14.4, 5.7, 1.5, 25, 1.2),
    ("corn",                   "Vegetable", 86, 3.3,  1.4, 19.0, 2.7, 0.5,  2, 0.5),
    ("aloo gobi",              "Curry",     85, 2.5,  3.5, 13.0, 2.0, 0.7, 18, 0.4),
    ("aloo matar",             "Curry",     90, 3.0,  3.0, 14.0, 2.5, 0.8, 18, 0.5),
    ("baingan bharta",         "Curry",     75, 2.0,  4.0,  9.0, 3.0, 0.6, 16, 0.4),
    ("bhindi masala",          "Curry",     75, 2.0,  4.0,  9.0, 3.0, 0.5, 70, 0.4),
    ("mixed veg sabzi",        "Curry",     70, 2.0,  3.0, 10.0, 2.0, 0.6, 30, 0.4),
    ("lauki sabzi",            "Curry",     45, 1.0,  2.0,  7.0, 1.5, 0.3, 16, 0.3),
    ("tori sabzi",             "Curry",     42, 1.0,  2.0,  6.5, 1.2, 0.3, 14, 0.3),

    # ── Fruits ────────────────────────────────────────────────────────────
    ("mango",                  "Fruit",    60, 0.8,  0.4, 15.0, 1.6, 0.2, 11, 0.1),
    ("banana",                 "Fruit",    89, 1.1,  0.3, 23.0, 2.6, 0.3,  5, 0.2),
    ("apple",                  "Fruit",    52, 0.3,  0.2, 14.0, 2.4, 0.1,  6, 0.0),
    ("orange",                 "Fruit",    47, 0.9,  0.1, 12.0, 2.4, 0.1, 40, 0.1),
    ("papaya",                 "Fruit",    43, 0.5,  0.3, 11.0, 1.7, 0.2, 20, 0.1),
    ("guava",                  "Fruit",    68, 2.6,  1.0, 14.0, 5.4, 0.3, 18, 0.2),
    ("pomegranate",            "Fruit",    83, 1.7,  1.2, 19.0, 4.0, 0.3, 10, 0.4),
    ("grapes",                 "Fruit",    69, 0.7,  0.2, 18.0, 0.9, 0.4, 11, 0.1),
    ("watermelon",             "Fruit",    30, 0.6,  0.2,  8.0, 0.4, 0.2,  7, 0.1),
    ("chikoo",                 "Fruit",    83, 0.4,  1.1, 20.0, 5.3, 0.8, 21, 0.1),
    ("sapodilla",              "Fruit",    83, 0.4,  1.1, 20.0, 5.3, 0.8, 21, 0.1),
    ("lychee",                 "Fruit",    66, 0.8,  0.4, 17.0, 1.3, 0.3,  5, 0.1),
    ("pineapple",              "Fruit",    50, 0.5,  0.1, 13.0, 1.4, 0.3, 13, 0.1),
    ("strawberry",             "Fruit",    32, 0.7,  0.3,  7.7, 2.0, 0.4, 16, 0.1),
    ("kiwi",                   "Fruit",    61, 1.1,  0.5, 15.0, 3.0, 0.3, 34, 0.1),

    # ── Nuts & Seeds ──────────────────────────────────────────────────────
    ("almonds",                "Nuts",    579,21.0, 50.0, 22.0,12.5, 3.7,264, 3.1),
    ("cashews",                "Nuts",    553,18.0, 44.0, 30.0, 3.3, 5.8, 37, 5.6),
    ("peanuts",                "Nuts",    567,26.0, 49.0, 16.0, 8.5, 2.0, 92, 3.3),
    ("walnuts",                "Nuts",    654,15.0, 65.0, 14.0, 6.7, 2.9, 98, 3.1),
    ("pistachios",             "Nuts",    562,20.0, 45.0, 28.0,10.0, 3.9,105, 2.2),
    ("peanut chikki",          "Snack",   480,12.0, 25.0, 56.0, 4.0, 1.5, 55, 1.5),
    ("sesame seeds",           "Nuts",    573,17.0, 50.0, 23.0,11.8,14.6,975, 7.8),
    ("flax seeds",             "Nuts",    534,18.0, 42.0, 29.0,27.3, 5.7,255, 4.3),
    ("pumpkin seeds",          "Nuts",    559,30.0, 49.0, 11.0, 6.0, 8.8, 46,10.3),

    # ── Grains & Flours ───────────────────────────────────────────────────
    ("atta",                   "Grains",  340,12.0,  2.0, 73.0,12.0, 3.5, 14, 1.5),
    ("whole wheat flour",      "Grains",  340,12.0,  2.0, 73.0,12.0, 3.5, 14, 1.5),
    ("maida",                  "Grains",  348, 9.0,  0.9, 78.0, 2.0, 1.0, 14, 0.7),
    ("besan",                  "Grains",  364,22.0,  5.6, 58.0,10.0, 6.2, 45, 3.0),
    ("gram flour",             "Grains",  364,22.0,  5.6, 58.0,10.0, 6.2, 45, 3.0),
    ("sooji",                  "Grains",  360,12.0,  1.0, 73.0, 2.0, 1.5, 14, 1.0),
    ("semolina",               "Grains",  360,12.0,  1.0, 73.0, 2.0, 1.5, 14, 1.0),
    ("ragi",                   "Grains",  328, 7.3,  1.5, 72.0, 3.6, 3.9,344, 2.3),
    ("finger millet",          "Grains",  328, 7.3,  1.5, 72.0, 3.6, 3.9,344, 2.3),
    ("bajra",                  "Grains",  361,11.6,  5.0, 67.0, 1.2, 8.0, 42, 3.1),
    ("pearl millet",           "Grains",  361,11.6,  5.0, 67.0, 1.2, 8.0, 42, 3.1),
    ("jowar",                  "Grains",  329,10.4,  1.7, 72.0, 1.6, 1.6, 28, 1.7),
    ("sorghum",                "Grains",  329,10.4,  1.7, 72.0, 1.6, 1.6, 28, 1.7),
    ("quinoa",                 "Grains",  120, 4.4,  1.9, 22.0, 2.8, 1.4, 17, 0.6),

    # ── Packaged & Processed ──────────────────────────────────────────────
    ("maggi noodles",          "Packaged",280, 7.0, 11.0, 39.0, 1.0, 1.5, 14, 0.5),
    ("instant noodles",        "Packaged",280, 7.0, 11.0, 39.0, 1.0, 1.5, 14, 0.5),
    ("parle-g biscuit",        "Packaged",446, 7.0, 11.0, 76.0, 0.3, 1.8, 14, 0.4),
    ("marie biscuit",          "Packaged",425, 8.0, 12.0, 73.0, 2.0, 1.5, 14, 0.5),
    ("good day biscuit",       "Packaged",510, 7.0, 24.0, 66.0, 1.0, 1.2, 12, 0.5),
    ("bread pakora",           "Snack",   280, 7.0, 14.0, 34.0, 2.0, 1.5, 18, 0.7),
    ("pizza",                  "Packaged",270,11.0, 10.0, 35.0, 2.0, 1.5, 60, 0.8),
    ("burger",                 "Packaged",250,12.0, 10.0, 30.0, 2.0, 1.5, 40, 0.8),
    ("french fries",           "Packaged",312, 3.4, 15.0, 41.0, 3.8, 0.5, 14, 0.5),

    # ── Oil & Condiments ──────────────────────────────────────────────────
    ("oil",                    "Condiment",884, 0.0, 100.0, 0.0, 0.0, 0.0, 0, 0.0),
    ("coconut oil",            "Condiment",892, 0.0, 100.0, 0.0, 0.0, 0.0, 0, 0.0),
    ("mustard oil",            "Condiment",884, 0.0, 100.0, 0.0, 0.0, 0.0, 0, 0.0),
    ("pickle",                 "Condiment", 70, 0.5,  5.0,  8.0, 1.0, 1.5, 10, 0.2),
    ("chutney",                "Condiment", 65, 1.5,  2.0, 12.0, 2.0, 0.5, 15, 0.2),
    ("tomato sauce",           "Condiment", 90, 1.5,  0.3, 22.0, 0.8, 0.5,  8, 0.2),
    ("ketchup",                "Condiment", 90, 1.5,  0.3, 22.0, 0.8, 0.5,  8, 0.2),
]


# ---------------------------------------------------------------------------
# Build the embedded_nutrition.json
# ---------------------------------------------------------------------------

def build_embedded_nutrition() -> dict:
    data = {"_comment": "IFCT 2017 / USDA per-100g values. Do not edit by hand — regenerate with seed_indian_foods.py"}
    for row in FOODS:
        name, _cat, cal, prot, fat, carbs, fiber = row[0], row[1], row[2], row[3], row[4], row[5], row[6]
        data[name] = {
            "calories":  float(cal),
            "protein_g": float(prot),
            "fat_g":     float(fat),
            "carbs_g":   float(carbs),
            "fiber_g":   float(fiber),
        }
    return data


# ---------------------------------------------------------------------------
# Seed the Postgres foods table
# ---------------------------------------------------------------------------

async def seed_database():
    import os
    db_url = os.getenv(
        "DATABASE_URL",
        "postgresql+asyncpg://nutrition:nutrition@postgres:5432/nutrition_vision",
    )

    from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
    from sqlalchemy import text, pool as sa_pool

    engine = create_async_engine(db_url, poolclass=sa_pool.NullPool)
    Session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)

    inserted = 0
    skipped  = 0

    async with Session() as db:
        for row in FOODS:
            name, cat, cal, prot, fat, carbs, fiber, iron, calcium, zinc = row
            food_id = name.lower().replace(" ", "_").replace("/", "_")

            # Skip duplicates
            exists = await db.execute(text("SELECT 1 FROM foods WHERE food_id = :id"), {"id": food_id})
            if exists.scalar():
                skipped += 1
                continue

            await db.execute(text("""
                INSERT INTO foods
                  (food_id, name, category, source,
                   calories_per_100g, protein_g_per_100g, fat_g_per_100g,
                   carbs_g_per_100g, fiber_g_per_100g,
                   iron_mg_per_100g, calcium_mg_per_100g, zinc_mg_per_100g)
                VALUES
                  (:id, :name, :cat, 'ifct',
                   :cal, :prot, :fat, :carbs, :fiber,
                   :iron, :calcium, :zinc)
            """), {
                "id": food_id, "name": name, "cat": cat,
                "cal": float(cal), "prot": float(prot), "fat": float(fat),
                "carbs": float(carbs), "fiber": float(fiber),
                "iron": float(iron), "calcium": float(calcium), "zinc": float(zinc),
            })
            inserted += 1

        await db.commit()

    await engine.dispose()
    return inserted, skipped


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # 1. Write embedded_nutrition.json
    out_path = Path(__file__).parent.parent / "nutrition_engine" / "density_tables" / "embedded_nutrition.json"
    data = build_embedded_nutrition()
    out_path.write_text(json.dumps(data, indent=2, ensure_ascii=False))
    print(f"[✓] Wrote {len(data) - 1} foods to {out_path}")

    # 2. Seed Postgres
    inserted, skipped = asyncio.run(seed_database())
    print(f"[✓] Database: inserted={inserted}  skipped(already exists)={skipped}")
    print(f"[✓] Total foods available: {inserted + skipped}")
