/**
 * useAnalysis — submits a meal photo and polls until analysis is complete.
 *
 * Usage:
 *   const { submit, job, isAnalysing, result, error } = useAnalysis();
 *   await submit(photoPath);
 */

import { useState, useCallback } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api, AnalysisJob } from "@/services/api";

const POLL_INTERVAL_MS = 2000;

export function useAnalysis() {
  const qc = useQueryClient();
  const [jobId, setJobId] = useState<string | null>(null);

  // Submit photo → get job_id
  const submitMutation = useMutation({
    mutationFn: (photoPath: string) => api.submitAnalysis(photoPath),
    onSuccess: (job) => {
      setJobId(job.job_id);
    },
  });

  // Poll for result
  const pollQuery = useQuery<AnalysisJob>({
    queryKey: ["analysis", jobId],
    queryFn: () => api.getAnalysisResult(jobId!),
    enabled: !!jobId,
    // react-query v4: refetchInterval receives (data, query), not (query)
    refetchInterval: (data) => {
      const status = (data as AnalysisJob | undefined)?.status;
      if (!status || status === "complete" || status === "failed") return false;
      return POLL_INTERVAL_MS;
    },
    retry: false,
  });

  /**
   * Submit a photo for analysis.
   * Returns the job_id immediately so callers can navigate without waiting
   * for a React state re-render (avoids the race condition where jobId is
   * still null right after the mutateAsync resolves).
   */
  const submit = useCallback(
    async (photoPath: string): Promise<string> => {
      setJobId(null);
      const job = await submitMutation.mutateAsync(photoPath);
      return job.job_id;
    },
    [submitMutation]
  );

  const reset = useCallback(() => {
    setJobId(null);
    submitMutation.reset();
    if (jobId) {
      qc.removeQueries({ queryKey: ["analysis", jobId] });
    }
  }, [jobId, submitMutation, qc]);

  const job = pollQuery.data;
  const isAnalysing =
    submitMutation.isLoading ||
    (!!jobId && (!job || job.status === "queued" || job.status === "processing"));

  return {
    submit,
    reset,
    jobId,
    job,
    isAnalysing,
    result: job?.status === "complete" ? job.result : null,
    error: (submitMutation.error as Error | null)?.message ?? (job?.status === "failed" ? job.error : null),
  };
}
