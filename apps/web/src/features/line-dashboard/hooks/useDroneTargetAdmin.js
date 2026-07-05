// 파일 경로: src/features/line-dashboard/hooks/useDroneTargetAdmin.js
// superuser target 관리 화면의 서버 상태와 mutation을 관리합니다.
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createDroneTargetAdminRow,
  deleteDroneTargetAdminRow,
  fetchDroneTargetAdminRows,
  lineDashboardQueryKeys,
  updateDroneTargetAdminRow,
} from "../api"

export function useDroneTargetAdmin({ enabled = true } = {}) {
  const queryClient = useQueryClient()
  const queryKey = lineDashboardQueryKeys.droneTargetAdmin()
  const invalidateTargets = () => queryClient.invalidateQueries({ queryKey })

  const targetsQuery = useQuery({
    queryKey,
    queryFn: fetchDroneTargetAdminRows,
    enabled,
  })

  const createMutation = useMutation({
    mutationFn: createDroneTargetAdminRow,
    onSuccess: invalidateTargets,
  })

  const updateMutation = useMutation({
    mutationFn: updateDroneTargetAdminRow,
    onSuccess: invalidateTargets,
  })

  const deleteMutation = useMutation({
    mutationFn: deleteDroneTargetAdminRow,
    onSuccess: invalidateTargets,
  })

  return {
    targetsQuery,
    createMutation,
    updateMutation,
    deleteMutation,
  }
}
