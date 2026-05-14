import { useQuery } from "@tanstack/react-query";
import { timelineApiClient } from "../api/client";

export const useDroneLogs = (eqpId) =>
  useQuery({
    queryKey: ["timeline", "logs", "drone", eqpId],
    queryFn: () =>
      timelineApiClient("/logs/drone", {
        params: { eqpId },
      }),
    enabled: !!eqpId,
    staleTime: 1000 * 60 * 5,
  });
