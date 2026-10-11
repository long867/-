/** Typed same-origin client. Authentication tokens stay in memory. */
export async function api<T>(
  path: string,
  init: RequestInit = {},
  token?: string,
): Promise<T> {
  return request<T>(`/api/v1${path}`, init, token);
}

export async function publicApi<T>(
  path: string,
  init: RequestInit = {},
  token?: string,
): Promise<T> {
  return request<T>(`/api${path}`, init, token);
}

async function request<T>(
  url: string,
  init: RequestInit,
  token?: string,
): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...init.headers,
    },
  });
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "服务暂时不可用" }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : "输入格式不正确，请检查填写内容",
    );
  }
  return response.status === 204
    ? (undefined as T)
    : (response.json() as Promise<T>);
}
