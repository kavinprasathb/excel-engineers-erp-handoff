import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { api } from "../../api/client";
import type { Role } from "../../api/types";

export interface StaffUser {
  id: number;
  email: string;
  full_name: string;
  role: Role;
  is_active: boolean;
  last_login_at: string | null;
}

export const ROLE_LABEL: Record<Role, string> = { admin: "Owner", staff: "Staff" };

const KEY = ["staff"] as const;

export function useStaff() {
  return useQuery({
    meta: { silent: true },
    queryKey: KEY,
    queryFn: ({ signal }) => api.get<StaffUser[]>("/users", undefined, signal),
  });
}

function useDone() {
  const client = useQueryClient();
  return () => client.invalidateQueries({ queryKey: KEY });
}

export function useCreateStaff() {
  const done = useDone();
  return useMutation({
    meta: { silent: true },
    mutationFn: (body: { email: string; full_name: string; role: Role; password: string }) =>
      api.post<StaffUser>("/users", body),
    onSuccess: done,
  });
}

export function useUpdateStaff() {
  const done = useDone();
  return useMutation({
    meta: { silent: true },
    mutationFn: ({ id, ...body }: { id: number; full_name?: string; role?: Role; is_active?: boolean }) =>
      api.patch<StaffUser>(`/users/${id}`, body),
    onSuccess: done,
  });
}

export function useResetStaffPassword() {
  return useMutation({
    meta: { silent: true },
    mutationFn: ({ id, password }: { id: number; password: string }) =>
      api.post<undefined>(`/users/${id}/password`, { password }),
  });
}
