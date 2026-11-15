import type { CSSProperties } from "react";
import { SANS, useTokens } from "../theme";

/** Tag de filtro ativo: `sunken`, cantos 4 px. Ex.: "Hub Color Shopping ×". */
export const FilterChip = ({
  label,
  value,
  style,
}: {
  readonly label: string;
  readonly value: string;
  readonly style?: CSSProperties;
}) => {
  const t = useTokens();
  return (
    <span
      style={{
        display: "inline-flex",
        alignItems: "center",
        gap: 12,
        height: 56,
        padding: "0 18px",
        borderRadius: 4,
        background: t.sunken,
        border: `1px solid ${t.rule}`,
        fontFamily: SANS,
        fontSize: 30,
        color: t.ink,
        whiteSpace: "nowrap",
        ...style,
      }}
    >
      <span style={{ color: t.muted }}>{label}</span>
      <span style={{ fontWeight: 600 }}>{value}</span>
      <span style={{ color: t.muted, fontSize: 32, marginLeft: 2 }}>×</span>
    </span>
  );
};
