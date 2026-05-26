import { getBackendBaseUrl } from "@/lib/api";

const DEFAULT_TIMEOUT = 30000;
const MAX_RETRIES = 3;
const TIMELINE_API_PREFIX = "/api/v1/timeline";

const envCandidates = [
  () => import.meta?.env?.VITE_TIMELINE_API_BASE_URL,
  () => import.meta?.env?.VITE_API_BASE_URL,
  () => process?.env?.VITE_TIMELINE_API_BASE_URL,
  () => process?.env?.VITE_API_BASE_URL,
];

const trimTrailingSlash = (value) => value.replace(/\/+$/, "");

function resolveBaseUrl() {
  const raw = envCandidates
    .map((read) => {
      try {
        return read();
      } catch {
        return undefined;
      }
    })
    .find((value) => typeof value === "string" && value.trim());

  return trimTrailingSlash((raw || getBackendBaseUrl()).trim());
}

function buildQueryString(params) {
  if (!params) return "";

  const searchParams = new URLSearchParams();

  Object.entries(params).forEach(([key, value]) => {
    if (value === undefined || value === null) return;
    searchParams.append(key, String(value));
  });

  const query = searchParams.toString();
  return query ? `?${query}` : "";
}

function buildTimelineUrl(baseUrl, path, params) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${baseUrl}${TIMELINE_API_PREFIX}${normalizedPath}${buildQueryString(
    params
  )}`;
}

/**
 * Timeline 전용 API 클라이언트
 * - 프로젝트 기본 backend URL(getBackendBaseUrl) 또는 VITE_TIMELINE_API_BASE_URL을 사용
 * - 모든 엔드포인트는 /api/v1/timeline 프리픽스를 따름
 */
export const timelineApiClient = async (
  path,
  { params, timeout = DEFAULT_TIMEOUT, retries = MAX_RETRIES, ...opts } = {}
) => {
  const baseUrl = resolveBaseUrl();
  const fullUrl = buildTimelineUrl(baseUrl, path, params);

  const executeRequest = async (attempt = 1) => {
    const controller = new AbortController();
    const timeoutId = setTimeout(() => controller.abort(), timeout);

    try {
      const response = await fetch(fullUrl, {
        headers: {
          "Content-Type": "application/json",
          ...opts.headers,
        },
        credentials: "include",
        signal: controller.signal,
        ...opts,
      });

      if (!response.ok) {
        const errorText = await response.text();
        let errorMessage;

        switch (response.status) {
          case 400:
            errorMessage = "잘못된 요청입니다.";
            break;
          case 401: {
            errorMessage = "인증이 필요합니다.";
            const currentUrl = window.location.href;
            const ssoUrl = `${baseUrl}/sso?target=${encodeURIComponent(
              currentUrl
            )}`;
            window.location.href = ssoUrl;
            break;
          }
          case 403:
            errorMessage = "접근 권한이 없습니다.";
            break;
          case 404:
            errorMessage = "요청한 데이터를 찾을 수 없습니다.";
            break;
          case 500:
            errorMessage = "서버 오류가 발생했습니다.";
            break;
          case 503:
            errorMessage = "서비스를 일시적으로 사용할 수 없습니다.";
            break;
          default:
            errorMessage = errorText || `HTTP ${response.status} 오류`;
        }

        const error = new Error(errorMessage);
        error.status = response.status;
        error.url = fullUrl;
        throw error;
      }

      return response.json();
    } catch (error) {
      if (error.name === "AbortError") {
        throw new Error(`요청 시간이 초과되었습니다. (${timeout}ms)`);
      }

      if (attempt < retries && isRetryableError(error)) {
        await delay(Math.pow(2, attempt) * 1000);
        return executeRequest(attempt + 1);
      }

      throw error;
    } finally {
      clearTimeout(timeoutId);
    }
  };

  return executeRequest();
};

function isRetryableError(error) {
  return (
    !error.status ||
    error.status >= 500 ||
    error.status === 408 ||
    error.status === 429
  );
}

function delay(ms) {
  return new Promise((resolve) => setTimeout(resolve, ms));
}
