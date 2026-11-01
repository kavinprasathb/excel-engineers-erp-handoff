import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import { queryKeys } from "../../api/queryKeys";
import type { ChangePasswordBody, LoginBody, User } from "../../api/types";
import { navigateTo } from "../../lib/navigation";

/**
 * Auth state is a query, not a context holding a token.
 *
 * The session is an httpOnly cookie — JavaScript cannot read it, so there is
 * nothing for a provider to hold. `GET /auth/me` succeeding *is* the login
 * state, and React Query already owns caching and invalidation of it.
 */
export function useMe() {
  return useQuery({
    queryKey: queryKeys.me,
    queryFn: () => api.get<User>("/auth/me"),
    // A 401 here is the normal logged-out answer, not something to shout about.
    meta: { silent: true },
    retry: false,
    staleTime: 5 * 60_000,
  });
}

export function useLogin() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: (body: LoginBody) => api.post<{ user: User }>("/auth/login", body),
    // The form renders the failure inline; a toast would duplicate it.
    meta: { silent: true },
    onSuccess: (data) => {
      client.setQueryData(queryKeys.me, data.user);
    },
  });
}

export function useLogout() {
  const client = useQueryClient();
  return useMutation({
    mutationFn: () => api.post<void>("/auth/logout"),
    onSettled: () => {
      // Even a failed logout should drop local data: the user asked to leave.
      client.clear();
      navigateTo("/login", { replace: true });
    },
  });
}

export function useChangePassword() {
  return useMutation({
    mutationFn: (body: ChangePasswordBody) => api.post<void>("/auth/change-password", body),
    meta: { silent: true },
  });
}

/** The owner can delete, see purchase cost, analytics, settings, staff and the activity log. */
export function useIsOwner(): boolean {
  const { data } = useMe();
  return data?.role === "admin";
}
