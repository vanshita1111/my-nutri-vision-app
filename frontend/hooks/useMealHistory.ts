/**
 * useMealHistory — paginated meal log with infinite scroll support.
 *
 * Usage:
 *   const { meals, isLoading, fetchMore, hasMore } = useMealHistory();
 */

import { useState, useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { api, MealSummary } from "@/services/api";

const PAGE_SIZE = 20;

export function useMealHistory() {
  const qc = useQueryClient();
  const [offset, setOffset] = useState(0);
  const [allMeals, setAllMeals] = useState<MealSummary[]>([]);
  const [hasMore, setHasMore] = useState(true);

  const { isLoading, isFetching, error, refetch } = useQuery({
    queryKey: ["meals", offset],
    queryFn: async () => {
      const page = await api.getMeals(PAGE_SIZE, offset);
      if (page.length < PAGE_SIZE) setHasMore(false);
      if (offset === 0) {
        setAllMeals(page);
      } else {
        setAllMeals((prev) => [...prev, ...page]);
      }
      return page;
    },
    staleTime: 1000 * 30,
  });

  const fetchMore = useCallback(() => {
    if (!isFetching && hasMore) {
      setOffset((prev) => prev + PAGE_SIZE);
    }
  }, [isFetching, hasMore]);

  const refresh = useCallback(async () => {
    setOffset(0);
    setAllMeals([]);
    setHasMore(true);
    await qc.invalidateQueries({ queryKey: ["meals"] });
  }, [qc]);

  return {
    meals: allMeals,
    isLoading,
    isFetching,
    error: error as Error | null,
    fetchMore,
    hasMore,
    refresh,
  };
}
