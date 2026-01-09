import { useEffect, useState } from "react"

import { Badge } from "@/components/ui/badge"
import { Button } from "@/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card"
import { Input } from "@/components/ui/input"
import { Label } from "@/components/ui/label"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Separator } from "@/components/ui/separator"
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/common"

const ROLE_LABELS = {
  viewer: "뷰어",
  member: "멤버",
  manager: "관리자",
}

const ROLE_VARIANTS = {
  viewer: "secondary",
  member: "outline",
  manager: "default",
}

const ROLE_OPTIONS = [
  { value: "viewer", label: "뷰어 (보기 전용)" },
  { value: "member", label: "멤버 (승인 가능)" },
  { value: "manager", label: "관리자 (승인 + 권한 관리)" },
]

function getRoleLabel(role) {
  return ROLE_LABELS[role] || ROLE_LABELS.viewer
}

function getRoleVariant(role) {
  return ROLE_VARIANTS[role] || ROLE_VARIANTS.viewer
}

function MembersTable({ groups, onRevoke }) {
  if (!groups?.length) {
    return <p className="text-sm text-muted-foreground">관리 가능한 그룹이 없습니다.</p>
  }

  return (
    <div className="flex flex-col gap-4">
      {groups.map((group) => (
        <div key={group.userSdwtProd} className="grid gap-2">
          <div className="flex items-center gap-2">
            <h4 className="text-sm font-semibold text-foreground">{group.userSdwtProd}</h4>
            <Badge variant="secondary">관리</Badge>
          </div>
          <div className="rounded-lg border">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>사용자</TableHead>
                  <TableHead>권한</TableHead>
                  <TableHead className="text-right">작업</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {group.members?.length ? (
                  group.members.map((member) => (
                    <TableRow key={`${group.userSdwtProd}-${member.userId}`}>
                      <TableCell>
                        <div className="flex flex-col">
                          <span className="font-medium">{member.username}</span>
                          {member.name ? (
                            <span className="text-muted-foreground text-xs">{member.name}</span>
                          ) : null}
                        </div>
                      </TableCell>
                      <TableCell>
                        <Badge variant={getRoleVariant(member.role)}>
                          {getRoleLabel(member.role)}
                        </Badge>
                      </TableCell>
                      <TableCell className="text-right">
                        <Button
                          size="sm"
                          variant="outline"
                          onClick={() => onRevoke(group.userSdwtProd, member.userId)}
                        >
                          권한 회수
                        </Button>
                      </TableCell>
                    </TableRow>
                  ))
                ) : (
                  <TableRow>
                    <TableCell colSpan={3} className="text-center text-sm text-muted-foreground">
                      멤버가 없습니다.
                    </TableCell>
                  </TableRow>
                )}
              </TableBody>
            </Table>
          </div>
        </div>
      ))}
    </div>
  )
}

export function ManageGrantsCard({
  manageableGroups,
  onGrant,
  onRevoke,
  isSubmitting,
  error,
}) {
  const groupOptions = manageableGroups?.groups || []
  const [selectedGroup, setSelectedGroup] = useState("")
  const [knoxId, setKnoxId] = useState("")
  const [role, setRole] = useState("member")
  const hasGroups = groupOptions.length > 0

  useEffect(() => {
    if (groupOptions.length && !selectedGroup) {
      setSelectedGroup(groupOptions[0].userSdwtProd)
    }
  }, [groupOptions, selectedGroup])

  const handleGrant = (e) => {
    e.preventDefault()
    if (!selectedGroup || !knoxId) return
    onGrant(
      {
        userSdwtProd: selectedGroup,
        knox_id: knoxId,
        role,
      },
      () => {
        setKnoxId("")
        setRole("member")
      },
    )
  }

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle>그룹 권한 위임</CardTitle>
        <CardDescription>
          관리 권한이 있는 user_sdwt_prod 그룹의 멤버를 추가하거나 제거합니다.
        </CardDescription>
      </CardHeader>
      <CardContent className="flex flex-col gap-4">
        <form className="grid gap-3 rounded-lg border p-3" onSubmit={handleGrant}>
          <div className="grid gap-2">
            <Label htmlFor="grantGroup">그룹</Label>
            <Input
              id="grantGroup"
              list="grantGroupList"
              value={selectedGroup}
              onChange={(e) => setSelectedGroup(e.target.value)}
              placeholder="user_sdwt_prod 선택"
              required
              disabled={!hasGroups}
            />
            <datalist id="grantGroupList">
              {groupOptions.map((group) => (
                <option key={group.userSdwtProd} value={group.userSdwtProd} />
              ))}
            </datalist>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="grantUser">사용자 ID (knox_id)</Label>
            <Input
              id="grantUser"
              placeholder="예: KNOX-12345"
              value={knoxId}
              onChange={(e) => setKnoxId(e.target.value)}
              required
              disabled={!hasGroups}
            />
            <p className="text-sm text-muted-foreground">knox_id 기준으로 권한을 부여합니다.</p>
          </div>
          <div className="grid gap-2">
            <Label htmlFor="grantRole">권한 역할</Label>
            <Select
              value={role}
              onValueChange={setRole}
              disabled={!hasGroups}
            >
              <SelectTrigger id="grantRole" className="h-9">
                <SelectValue placeholder="권한 역할 선택" />
              </SelectTrigger>
              <SelectContent>
                {ROLE_OPTIONS.map((option) => (
                  <SelectItem key={option.value} value={option.value}>
                    {option.label}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">
              viewer는 보기만, member는 승인 가능, manager는 승인과 권한 관리를 포함합니다.
            </p>
          </div>

          {!hasGroups ? (
            <p className="text-sm text-muted-foreground">관리 가능한 user_sdwt_prod 그룹이 없습니다.</p>
          ) : null}

          {error ? <p className="text-destructive text-sm">{error}</p> : null}

          <div className="flex justify-end">
            <Button type="submit" disabled={isSubmitting || !selectedGroup || !knoxId || !hasGroups}>
              {isSubmitting ? "저장 중..." : "권한 부여/업데이트"}
            </Button>
          </div>
        </form>

        <Separator />

        <MembersTable groups={groupOptions} onRevoke={onRevoke} />
      </CardContent>
    </Card>
  )
}
