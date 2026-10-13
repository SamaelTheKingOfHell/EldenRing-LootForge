# LootForge: Item Distribution & Shop Variety Overhaul Plan

## Executive Summary

Currently in LootForge, procedural Diablo-style loot generation and vanilla base distribution frequently cause **shop monoculture**: a single merchant (such as Merchant Kalé) is flooded with 8 to 12 pieces from the *exact same armor set* across multiple rolled variants. This occurs because:
1. Multiple variants of the same mod set roll the same destination vendor (`(v_idx // 5) % len(merchant_pool)`).
2. All 4 pieces of an armor set (Head, Body, Arms, Legs) are injected as an all-or-nothing package into that single merchant.
3. Only 3 merchants exist in `data/loot_routes.json`, leaving almost zero shelf space across the world and instantly hitting row limits.

This document outlines the architectural plan to eliminate duplicate set variants at vendors, expand the merchant network to 22+ authentic in-game vendors, introduce regional progression tiering, enforce category variety, and make item discovery across the Lands Between feel rich, balanced, and rewarding.

---

## 1. Problem Diagnosis: Why Shops Become Monocultures

### The Root Deficiencies
1. **No Anti-Cluster Guard**:
   - There is no restriction preventing multiple variants of the *same* base item from landing in the *same* shop.
2. **The 3-Merchant Bottleneck**:
   - `loot_routes.json` only tracks `kale_church_of_elleh` (25 slots), `twin_maiden_husks` (100 slots), and `nomadic_merchant_liurnia` (13 slots).
   - With only 38 non-Roundtable shop rows in the entire game, overflow happens immediately.
3. **Rigid 4-Piece Set Dumping**:
   - Injecting an entire 4-piece set at once consumes nearly 20% of a merchant's total lifetime capacity in one go.
4. **Zero Item Class Balancing**:
   - No quota ensures that a shop offers a healthy mix of weapons, armor, and utility passives.
5. **Agnostic to Game Progression**:
   - A level 1 starter merchant in Limgrave can sell a Mythic end-game relic, while a merchant in Mountaintops sells mundane gear.

---

## 2. Core Architectural Pillars of the New System

* **Pillar 1: Anti-Cluster Guard (1 Variant / Set / Vendor)**
* **Pillar 2: Expanded 22+ Merchant Network**
* **Pillar 3: Regional Progression Tiering (T1-T4)**
* **Pillar 4: Category Diversity Balancing**
* **Pillar 5: Flexible Set Dispersal Modes**

---

## 3. Pillar 1: Anti-Cluster Guard (Strict 1-Variant-Per-Vendor Quota)

### Rule Specification
- **Hard Constraint**: A single merchant can stock at most **ONE variant** of any base item or set.
- If a mod set has 5 generated variants:
  - Variant 1 -> Merchant A (or Boss A)
  - Variant 2 -> Merchant B (different vendor)
  - Variant 3 -> World Chest C
  - Variant 4 -> Elite Enemy D
  - Variant 5 -> Remembrance Boss E
- **Collision Resolution**: If a variant rolls a merchant that already stocks *any* variant of that base set, the distributor immediately rotates it to the next eligible merchant in the pool.

---

## 4. Pillar 2: Expanded Regional Merchant Network (from 3 to 22+ Vendors)

Expanding from 3 to 22+ authentic FromSoftware merchants across all regions provides over **450 safe, native shop rows** in `ShopLineupParam`.

| Region | Merchant Name | Location | Native Param Range | Thematic Focus |
| :--- | :--- | :--- | :--- | :--- |
| **Limgrave** | Merchant Kalé | Church of Elleh | `100500 - 100524` | Starter Adventurer, Shields, Tools |
| **Limgrave** | Nomadic Merchant Coastal | Coastal Cave Beach | `100525 - 100549` | Light weapons, arrows, leather |
| **Limgrave** | Nomadic Merchant East | Mistwood / Waypoint | `100550 - 100574` | Heavy woodsman gear, axes |
| **Weeping Pen.** | Nomadic Merchant Morne | Castle Morne Rampart | `100575 - 100599` | Defense armor, crossbows, shields |
| **Weeping Pen.** | Isolated Merchant Shack | West Coast Shack | `100600 - 100624` | Lanterns, unique bludgeons |
| **Liurnia** | Nomadic Merchant South | Liurnia Lake Shore | `100625 - 100649` | Astrologer robes, curved swords |
| **Liurnia** | Nomadic Merchant North | Bellum Church Highway | `100650 - 100674` | Composite bows, knight gear |
| **Liurnia** | Isolated Merchant Academy | Main Academy Gate | `100675 - 100699` | Sorcerer gear, staves, glintstone |
| **Liurnia** | Pidia, Carian Servant | Caria Manor Balcony | `100700 - 100724` | Rare exotic weapons, magic relics |
| **Liurnia** | Master Smith Iji | Road to the Manor | `100725 - 100749` | Colossal weapons, heavy armor |
| **Caelid** | Nomadic Merchant Highway | Caelid Highway South | `100750 - 100774` | Fire wards, status resistance gear |
| **Caelid** | Isolated Merchant Dragon | Dragonbarrow Shack | `100775 - 100799` | Dragon-themed relics, high-stat gear |
| **Caelid** | Nomadic Merchant North | Bestial Sanctum Road | `100800 - 100824` | Beast-slayer gear, holy items |
| **Altus Plateau** | Nomadic Merchant Forest | Forest-Spanning Bridge | `100825 - 100849` | Gilded armor, lightning gear |
| **Altus Plateau** | Hermit Merchant Shack | Leyndell Capital Outskirts | `100850 - 100874` | Perfumer gear, rare cloaks |
| **Mt. Gelmir** | Nomadic Merchant Gelmir | 9th Mt. Gelmir Campsite | `100875 - 100899` | Fire resistance, serpentine blades |
| **Underground** | Nomadic Merchant Siofra | Siofra River Ruin Floor | `100900 - 100924` | Ancient spirit relics, curved blades |
| **Underground** | Hermit Merchant Ainsel | Ainsel River Ruins | `100925 - 100949` | Astel/Cosmic relics, frost gear |
| **Mountaintops** | Isolated Merchant Giants | Freezing Lake / Shack | `100950 - 100974` | Heavy winter furs, colossal swords |
| **Roundtable** | Twin Maiden Husks | Central Sanctuary | `101800 - 101899` | Overflow depot & universal shop |
| **Roundtable** | Finger Reader Enia | Two Fingers Chamber | `101900 - 101949` | Boss Soul Remembrances |

---

## 5. Pillar 3: Regional Progression Tiering (T1 - T4)

To make exploration feel rewarding and preserve Souls progression, loot rarity tiers and item potency scale with regional difficulty:
- **Tier 1 (Limgrave & Peninsula)**: Level 1-30 appropriate. Common: 50%, Magic: 35%, Rare: 15%.
- **Tier 2 (Liurnia & Siofra)**: Level 30-70 appropriate. Magic: 35%, Rare: 45%, Legendary: 20%.
- **Tier 3 (Caelid, Altus, Leyndell)**: Level 70-100 appropriate. Rare: 30%, Legendary: 55%, Mythic: 15%.
- **Tier 4 (Mountaintops, Farum, Enia)**: Level 100+ end-game. Legendary: 60%, Mythic: 40%.

---

## 6. Pillar 4: Category Diversity Balancing (The Shop Mix Controller)

To prevent any shop from feeling like an exclusively helmet or greaves store, each vendor maintains a balanced **Item Type Quota**:

| Category | Target Percentage | Maximum Per Single Shop |
| :--- | :--- | :--- |
| **Weapons** | 35% - 40% | 4 weapons max |
| **Body Armor** | 20% - 25% | 2 chest pieces max |
| **Headwear** | 15% - 20% | 2 helms max |
| **Arms / Legs** | 15% - 20% | 2 gauntlets / 2 greaves max |
| **Total Injected Slots** | 100% | Cap at 8-12 custom items per merchant |

When a vendor reaches their cap for a specific slot, incoming items automatically cascade to the next eligible vendor.

---

## 7. Pillar 5: Set Dispersal vs. Set Cohesion Options

Two user-selectable distribution styles via GUI settings:

### Option A: "Dispersed World Scavenger" (Maximum Variety - Recommended)
- Rather than dropping all 4 pieces of an armor set in one merchant, pieces are **scattered thematically across a region**:
  - **Helm**: Found in a regional dungeon chest.
  - **Armor (Body)**: Sold by the regional Nomad Merchant.
  - **Gauntlets**: Dropped by the regional elite knight.
  - **Greaves**: Dropped by roaming soldiers.

### Option B: "Curated Set Vendor" (Cohesive Sets, Zero Duplicates)
- If the user prefers armor pieces to stay together:
  - An entire set is placed at **one single merchant**.
  - **Strict Anti-Monoculture**: That merchant is **locked** from receiving any other armor set.
  - Other armor sets must go to other merchants across Liurnia, Caelid, or Altus.
