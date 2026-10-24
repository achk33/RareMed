"use client";

import { useCallback, useEffect, useState } from "react";

import { ApiError, getStatus } from "@/lib/api";
import type { PlatformStatus } from "@/lib/types";

export function usePlatformStatus() {
  const [status, setStatus] = useState<PlatformStatus | null>(null);
  const [errorCode, setErrorCode] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [requestId, setRequestId] = useState(0);

  const reload = useCallback(() => {
    setLoading(true);
    setRequestId((current) => current + 1);
  }, []);

  useEffect(() => {
    let cancelled = false;
    getStatus()
      .then((next) => {
        if (cancelled) return;
        setStatus(next);
        setErrorCode(null);
        setLoading(false);
      })
      .catch((error: unknown) => {
        if (cancelled) return;
        setStatus(null);
        setErrorCode(error instanceof ApiError ? error.code : "request_failed");
        setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [requestId]);

  return { status, errorCode, loading, reload };
}
