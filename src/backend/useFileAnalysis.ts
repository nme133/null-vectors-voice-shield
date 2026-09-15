import { useCallback, useEffect, useRef, useState } from 'react';
import {
  BACKEND_UPLOAD_URL,
  UploadResult,
  UploadStageEvent,
  UploadStatus,
  UploadStreamEvent,
} from './uploadTypes';

export interface UseFileAnalysisOptions {
  onStage?: (event: UploadStageEvent) => void;
  onResult?: (result: UploadResult) => void;
  onError?: (message: string) => void;
}

export interface UseFileAnalysisReturn {
  status: UploadStatus;
  selectedFile: File | null;
  stages: UploadStageEvent[];
  result: UploadResult | null;
  error: string | null;
  analyze: (file: File, language: string) => Promise<void>;
  reset: () => void;
}

/**
 * Sends a real audio file to the backend upload-analysis endpoint and streams
 * the backend's newline-delimited JSON back.  Progress is reported from real
 * stage events emitted by the actual pipeline — no fabricated percentages.
 */
export function useFileAnalysis({
  onStage,
  onResult,
  onError,
}: UseFileAnalysisOptions = {}): UseFileAnalysisReturn {
  const [status, setStatus] = useState<UploadStatus>('idle');
  const [selectedFile, setSelectedFile] = useState<File | null>(null);
  const [stages, setStages] = useState<UploadStageEvent[]>([]);
  const [result, setResult] = useState<UploadResult | null>(null);
  const [error, setError] = useState<string | null>(null);

  const handlersRef = useRef({ onStage, onResult, onError });
  handlersRef.current = { onStage, onResult, onError };

  const analyze = useCallback(async (file: File, language: string) => {
    setSelectedFile(file);
    setStages([]);
    setResult(null);
    setError(null);
    setStatus('uploading');

    const form = new FormData();
    form.append('file', file);
    form.append('language', language);

    try {
      const response = await fetch(BACKEND_UPLOAD_URL, {
        method: 'POST',
        body: form,
      });

      if (!response.ok) {
        let message = `Upload failed (HTTP ${response.status})`;
        try {
          const body = await response.json();
          if (body && typeof body.detail === 'string') {
            message = body.detail;
          } else if (body && Array.isArray(body.detail) && body.detail[0]?.msg) {
            message = body.detail[0].msg;
          }
        } catch {
          // keep the default message
        }
        throw new Error(message);
      }

      if (!response.body) {
        throw new Error('Backend returned no response body');
      }

      setStatus('processing');
      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = '';

      while (true) {
        const { done, value } = await reader.read();
        if (done) break;

        buffer += decoder.decode(value, { stream: true });
        let newlineIndex = buffer.indexOf('\n');
        while (newlineIndex >= 0) {
          const line = buffer.slice(0, newlineIndex).trim();
          buffer = buffer.slice(newlineIndex + 1);
          newlineIndex = buffer.indexOf('\n');

          if (!line) continue;

          let event: UploadStreamEvent;
          try {
            event = JSON.parse(line) as UploadStreamEvent;
          } catch {
            continue;
          }

          if (event.type === 'stage') {
            setStages((prev) => (prev.some((e) => e.stage === event.stage) ? prev : [...prev, event]));
            handlersRef.current.onStage?.(event);
          } else if (event.type === 'result') {
            setResult(event);
            handlersRef.current.onResult?.(event);
          } else if (event.type === 'error') {
            throw Object.assign(new Error(event.message || 'Analysis failed'), { code: event.code });
          }
        }
      }

      setStatus('done');
    } catch (err) {
      const message = err instanceof Error ? err.message : 'Upload failed';
      setError(message);
      setStatus('error');
      handlersRef.current.onError?.(message);
    }
  }, []);

  const reset = useCallback(() => {
    setSelectedFile(null);
    setStages([]);
    setResult(null);
    setError(null);
    setStatus('idle');
  }, []);

  useEffect(() => {
    return () => {
      setSelectedFile(null);
      setStatus('idle');
    };
  }, []);

  return { status, selectedFile, stages, result, error, analyze, reset };
}