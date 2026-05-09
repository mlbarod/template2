import { useState } from "react";
import { timelineApi } from "../api/timelineApi";

export function useDirectEquipmentQuery({
  setLine,
  setSdwt,
  setPrcGroup,
  setEqp,
}) {
  const [isDirectQuery, setIsDirectQuery] = useState(false);
  const [inputEqpId, setInputEqpId] = useState("");
  const [isLoading, setIsLoading] = useState(false);

  const handleToggleChange = (checked) => {
    setIsDirectQuery(checked);

    if (checked) {
      setLine("");
      setSdwt("");
      setPrcGroup("");
      setEqp("");
    }
    setInputEqpId("");
  };

  const handleDirectQuery = async () => {
    if (!inputEqpId.trim()) return;

    setIsLoading(true);
    try {
      const eqpInfo = await timelineApi.fetchEquipmentInfoByEqpId(inputEqpId);

      if (eqpInfo) {
        setLine(eqpInfo.lineId);
        setSdwt(eqpInfo.sdwtId);
        setPrcGroup(eqpInfo.prcGroup);
        setEqp(inputEqpId);
      } else {
        alert("유효하지 않은 EQP ID입니다.");
      }
    } catch (error) {
      console.error("EQP 정보 조회 실패:", error);
      alert("EQP 정보 조회에 실패했습니다.");
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (event) => {
    if (event.key === "Enter") {
      handleDirectQuery();
    }
  };

  const handleInputChange = (event) => {
    setInputEqpId(event.target.value.toUpperCase());
  };

  return {
    isDirectQuery,
    inputEqpId,
    isLoading,
    handleToggleChange,
    handleDirectQuery,
    handleInputChange,
    handleKeyPress,
  };
}
