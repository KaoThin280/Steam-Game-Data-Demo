# Steam Game Data Demo – Database Schema Documentation

## Overview

This document describes the database schema used in the **Steam Game Data Demo** project. The database is designed to store Steam game metadata, user reviews, and to support an application-level user authentication and authorization (RBAC) system.

The schema is implemented in **PostgreSQL** (specifically tailored for Supabase) and utilizes native features such as `BIGINT GENERATED ALWAYS AS IDENTITY` for primary keys and `TIMESTAMPTZ` for timezone-aware timestamps.

---

## Table of Contents

1. [Steam Database Schema](#1-steam-database-schema)
   - [Entity Relationship Overview](#entity-relationship-overview)
   - [Games Table](#games-table)
   - [Users & Reviews Tables](#users--reviews-tables)
2. [User Authentication & Authorization Schema](#2-user-authentication--authorization-schema)
   - [Auth Tables](#auth-tables)
   - [Roles & Permissions Definition](#roles--permissions-definition)
   - [Quick Reference](#quick-reference)

---

## 1. Steam Database Schema <a id="1-steam-database-schema"></a>

### Entity Relationship Overview <a id="entity-relationship-overview"></a>

The schema utilizes a flattened structure for game metadata to optimize bulk inserts and reduce complex joins. 

Main relationships:
- `games` **1—N** `reviews`
- `users` **1—N** `reviews`

### Games Table <a id="games-table"></a>

#### 1.1 `games` — Core Game Information

The main table that stores one row per Steam game. Array-like data (publishers, developers, genres) is stored as flattened comma-separated text strings.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `steam_appid` | `INTEGER` | `PRIMARY KEY` | Unique Steam application ID |
| `name` | `TEXT` | `NOT NULL` | Game name |
| `is_free` | `BOOLEAN` | `DEFAULT FALSE` | Whether the game is free to play |
| `supported_languages` | `TEXT` | – | Comma-separated list of supported languages |
| `required_age` | `INTEGER` | `DEFAULT 0` | Minimum required age |
| `release_date` | `DATE` | – | Game release date |
| `publishers` | `TEXT` | – | Comma-separated list of publishers |
| `developers` | `TEXT` | – | Comma-separated list of developers |
| `categories` | `TEXT` | – | Comma-separated list of categories |
| `genres` | `TEXT` | – | Comma-separated list of genres |
| `price_text` | `TEXT` | – | Formatted price string |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP` | Record creation time |

Indexes: 
- `idx_games_name ON games(name)`
- `idx_games_is_free ON games(is_free)`

### Users & Reviews Tables <a id="users--reviews-tables"></a>

#### 1.2 `users` — Steam Users

Stores Steam user profiles based on review extraction.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `steamid` | `BIGINT` | `PRIMARY KEY` | 17-digit Steam ID |
| `personaname` | `TEXT` | – | Steam display name |
| `num_games_owned` | `INTEGER` | `DEFAULT 0` | Number of games owned |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP` | Record creation time |

#### 1.3 `reviews` — User Reviews

Stores individual user reviews linked to specific games and users.

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `recommendationid` | `BIGINT` | `PRIMARY KEY` | Steam recommendation ID |
| `steam_appid` | `INTEGER` | `NOT NULL`, `FK → games(steam_appid) ON DELETE CASCADE` | Reviewed game |
| `steamid` | `BIGINT` | `NOT NULL`, `FK → users(steamid) ON DELETE CASCADE` | Reviewer |
| `language` | `TEXT` | – | Language of the review |
| `review_text` | `TEXT` | – | Review body |
| `timestamp_created` | `TIMESTAMPTZ` | – | Timestamp of review creation |
| `timestamp_updated` | `TIMESTAMPTZ` | – | Timestamp of last update |
| `refunded` | `BOOLEAN` | `DEFAULT FALSE` | Whether the purchase was refunded |
| `received_for_free` | `BOOLEAN` | `DEFAULT FALSE` | Whether the game was received for free |
| `written_during_early_access` | `BOOLEAN` | `DEFAULT FALSE` | Written during early access |
| `primarily_steam_deck` | `BOOLEAN` | `DEFAULT FALSE` | Primarily played on Steam Deck |
| `playtime_at_review` | `INTEGER` | `DEFAULT 0` | Playtime at the moment of the review |
| `playtime_last_two_weeks` | `INTEGER` | `DEFAULT 0` | Playtime in the last 2 weeks |
| `playtime_forever` | `INTEGER` | `DEFAULT 0` | Total playtime in minutes |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP` | DB record creation time |

Indexes: 
- `idx_reviews_appid ON reviews(steam_appid)`
- `idx_reviews_steamid ON reviews(steamid)`
- `idx_reviews_language ON reviews(language)`
- `idx_reviews_created ON reviews(timestamp_created)`

---

## 2. User Authentication & Authorization Schema <a id="2-user-authentication--authorization-schema"></a>

This schema implements **RBAC (Role-Based Access Control)** on top of the system. It uses a dedicated `app_users` table that is entirely separate from the Steam `users` table. Application users authenticate with a username/email and password, and are assigned one or more **roles**, each possessing specific **permissions**.

### Auth Tables <a id="auth-tables"></a>

#### 2.1 `roles` — System Roles

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `BIGINT` | `IDENTITY PRIMARY KEY` | Surrogate key |
| `role_name` | `TEXT` | `UNIQUE NOT NULL` | Role identifier |
| `description` | `TEXT` | – | Human-readable description |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP` | Record creation time |

#### 2.2 `permissions` — System Permissions

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `BIGINT` | `IDENTITY PRIMARY KEY` | Surrogate key |
| `permission_name` | `TEXT` | `UNIQUE NOT NULL` | Permission identifier |
| `description` | `TEXT` | – | Human-readable description |
| `resource` | `TEXT` | – | Target resource (e.g., `games`, `users`) |
| `action` | `TEXT` | – | Allowed action (e.g., `read`, `write`) |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP` | Record creation time |

#### 2.3 `role_permissions` — Role ↔ Permission Assignment

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `role_id` | `BIGINT` | `PK`, `FK → roles(id) ON DELETE CASCADE` | Role reference |
| `permission_id` | `BIGINT` | `PK`, `FK → permissions(id) ON DELETE CASCADE`| Permission reference |

#### 2.4 `app_users` — Application Accounts

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `id` | `BIGINT` | `IDENTITY PRIMARY KEY` | Surrogate key |
| `username` | `TEXT` | `UNIQUE NOT NULL` | Login name |
| `email` | `TEXT` | `UNIQUE NOT NULL` | Email address |
| `password_hash` | `TEXT` | `NOT NULL` | bcrypt-hashed password |
| `full_name` | `TEXT` | – | Display name |
| `is_active` | `BOOLEAN` | `DEFAULT TRUE` | Account enabled flag |
| `created_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP` | Account creation time |
| `last_login` | `TIMESTAMPTZ` | – | Last successful login |

#### 2.5 `user_roles` — User ↔ Role Assignment

| Column | Type | Constraints | Description |
|--------|------|-------------|-------------|
| `user_id` | `BIGINT` | `PK`, `FK → app_users(id) ON DELETE CASCADE` | User reference |
| `role_id` | `BIGINT` | `PK`, `FK → roles(id) ON DELETE CASCADE` | Role reference |
| `assigned_at` | `TIMESTAMPTZ` | `DEFAULT CURRENT_TIMESTAMP` | Assignment time |

### Roles & Permissions Definition <a id="roles--permissions-definition"></a>

The database is initialized with 4 default roles:

- **admin** – System administrator with full access.
- **analyst** – Read-only data analyst.
- **scientist** – Data scientist; read/write access.
- **viewer** – Guest visitor with basic read-only access.

Default Permissions Matrix:
- **Games**: `games_read`, `games_write`, `games_delete`
- **Reviews**: `reviews_read`, `reviews_write`, `reviews_delete`
- **Users**: `users_read`, `users_write`, `users_delete`, `users_manage_roles`
- **System**: `system_admin`

### Quick Reference <a id="quick-reference"></a>

| # | Table | Purpose |
|---|-------|---------|
| 1 | `games` | Flattened game metadata records |
| 2 | `users` | Steam user profiles |
| 3 | `reviews` | User reviews and playtime statistics |
| 4 | `roles` | RBAC roles definition |
| 5 | `permissions` | RBAC permissions definition |
| 6 | `role_permissions` | Junction table for Role ↔ Permission |
| 7 | `app_users` | Internal application accounts |
| 8 | `user_roles` | Junction table for App User ↔ Role |

---
*End of schema documentation.*