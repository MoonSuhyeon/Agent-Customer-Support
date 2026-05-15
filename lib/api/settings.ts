import { apiClient } from "./client";

export interface UserProfile {
  name: string;
  email: string;
  phone: string;
}

export function getProfile(): Promise<UserProfile> {
  return apiClient.get<UserProfile>("/user/profile");
}

export function updateProfile(data: { email: string; phone: string }): Promise<UserProfile> {
  return apiClient.patch<UserProfile>("/user/profile", data);
}

export function changePassword(data: { current: string; next: string }): Promise<void> {
  return apiClient.patch<void>("/user/password", data);
}

export function changeTransferPassword(data: { current: string; next: string }): Promise<void> {
  return apiClient.patch<void>("/user/transfer-password", data);
}
