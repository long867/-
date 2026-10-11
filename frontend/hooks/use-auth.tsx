"use client";
import { createContext, useContext, useState, type ReactNode } from "react";
import type { Token, User } from "@/types";
import { useQueryClient } from "@tanstack/react-query";
interface Auth {
  token?: string;
  user?: User;
  login: (value: Token) => void;
  logout: () => void;
}
const Context = createContext<Auth | null>(null);
export function AuthProvider({ children }: { children: ReactNode }) {
  const [value, setValue] = useState<Token>();
  const client = useQueryClient();
  return (
    <Context.Provider
      value={{
        token: value?.access_token,
        user: value?.user,
        login: (result) => {
          client.clear();
          setValue(result);
        },
        logout: () => {
          client.clear();
          setValue(undefined);
        },
      }}
    >
      {children}
    </Context.Provider>
  );
}
export function useAuth() {
  const value = useContext(Context);
  if (!value) throw new Error("AuthProvider missing");
  return value;
}
