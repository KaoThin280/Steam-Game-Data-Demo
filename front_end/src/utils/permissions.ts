/**
 * Role / permission helpers.
 * The back-end stores roles as RoleName strings on the user.
 */
import type { RoleName } from "@/lib/types";

export const ROLE_LABELS: Record<RoleName, string> = {
  admin: "Administrator",
  analyst: "Data Analyst",
  scientist: "Data Scientist",
  viewer: "Viewer",
};

/** Permission matrix mirrors back_end/app/models/user.py PermissionName. */
export type Permission =
  | "games_read"
  | "games_write"
  | "games_delete"
  | "reviews_read"
  | "reviews_write"
  | "reviews_delete"
  | "users_read"
  | "users_write"
  | "users_delete"
  | "users_manage_roles"
  | "system_admin"
  | "ai_chat"; // synthetic permission for the analyst/scientist chat

const ROLE_PERMS: Record<RoleName, Permission[]> = {
  admin: [
    "system_admin",
    "users_manage_roles",
    "games_read", "games_write", "games_delete",
    "reviews_read", "reviews_write", "reviews_delete",
    "users_read", "users_write", "users_delete",
    "ai_chat",
  ],
  scientist: [
    "games_read", "games_write",
    "reviews_read", "reviews_write",
    "users_read",
    "ai_chat",
  ],
  analyst: [
    "games_read",
    "reviews_read",
    "users_read",
    "ai_chat",
  ],
  viewer: [
    "games_read",
    "reviews_read",
  ],
};

export const rolesWith = (perm: Permission): RoleName[] =>
  (Object.keys(ROLE_PERMS) as RoleName[]).filter((r) =>
    ROLE_PERMS[r].includes(perm)
  );

export const userHasAnyRole = (
  userRoles: RoleName[] | undefined,
  ...needed: RoleName[]
): boolean => !!userRoles && needed.some((r) => userRoles.includes(r));

export const userHasPermission = (
  userRoles: RoleName[] | undefined,
  perm: Permission
): boolean => !!userRoles && userRoles.some((r) => ROLE_PERMS[r].includes(perm));

/** True for any role that can use the analyst-style chat interface. */
export const canUseAnalystChat = (roles: RoleName[] | undefined): boolean =>
  userHasAnyRole(roles, "admin", "analyst", "scientist");
